import pymysql
import os
import logging
import json
import math
import sys
from dotenv import load_dotenv

load_dotenv()
VERSION = "PHASE_15_V1"

# ── 连接池初始化 ──────────────────────────────────────────────────────────────
_pool = None

def _init_pool():
    global _pool
    if _pool is not None: return
    try:
        from dbutils.pooled_db import PooledDB
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=10,
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", "12345678"),
            database=os.getenv("MYSQL_DATABASE", "medical"),
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            charset="utf8mb4",
        )
    except Exception as e:
        print(f"Pool Init Error: {e}")
        _pool = None

def get_connection():
    _init_pool()
    if _pool: return _pool.connection()
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "12345678"),
        database=os.getenv("MYSQL_DATABASE", "medical"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

def init_db():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Tables
            cursor.execute("CREATE TABLE IF NOT EXISTS interaction_logs (id INT AUTO_INCREMENT PRIMARY KEY, session_id VARCHAR(100), user_query TEXT, rewritten_query TEXT, intent VARCHAR(50), confidence FLOAT, reasoning TEXT, total_tokens INT DEFAULT 0, retrieved_docs TEXT, graph_paths TEXT, ai_response TEXT, generation_time_ms INT, is_factually_consistent BOOLEAN DEFAULT TRUE, fact_check_feedback TEXT, user_feedback VARCHAR(50), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
            cursor.execute("CREATE TABLE IF NOT EXISTS rewrite_rules (id INT AUTO_INCREMENT PRIMARY KEY, case_word VARCHAR(255) UNIQUE, standard_word VARCHAR(255)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
            cursor.execute("CREATE TABLE IF NOT EXISTS patient_profiles (session_id VARCHAR(100) PRIMARY KEY, profile_data JSON) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
            cursor.execute("CREATE TABLE IF NOT EXISTS bad_cases (id INT AUTO_INCREMENT PRIMARY KEY, query TEXT, ai_response TEXT, user_feedback TEXT, status VARCHAR(20) DEFAULT 'pending', interaction_log_id INT, retrieved_docs TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
            
            # New Tables for Intent & Strategy
            cursor.execute("CREATE TABLE IF NOT EXISTS intent_configs (intent_id VARCHAR(50) PRIMARY KEY, label_name VARCHAR(100), confidence_threshold FLOAT, resource_binding VARCHAR(255)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
            cursor.execute("CREATE TABLE IF NOT EXISTS strategy_snapshots (id INT AUTO_INCREMENT PRIMARY KEY, version_tag VARCHAR(100), description TEXT, config_data JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
            cursor.execute("CREATE TABLE IF NOT EXISTS categories (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255), level INT, parent_id INT) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
            cursor.execute("CREATE TABLE IF NOT EXISTS ingestion_logs (id INT AUTO_INCREMENT PRIMARY KEY, file_name VARCHAR(255), chunk_count INT, chunk_size INT, chunk_overlap INT, l1_name VARCHAR(100), l2_name VARCHAR(100), l3_name VARCHAR(100), vector_ids_prefix VARCHAR(100), op_user VARCHAR(100), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
            
            # Seed default intent configs if none exist
            cursor.execute("SELECT COUNT(*) as cnt FROM intent_configs")
            if cursor.fetchone()['cnt'] == 0:
                defaults = [
                    ('ADMIN', '行政/导诊', 0.8, '系统级向量库'),
                    ('PHARMA', '药理知识', 0.85, '通用药理图谱库'),
                    ('DIAG', '诊断科普', 0.85, '临床医学知识库'),
                    ('VIOLATION', '安全规则', 0.9, '安全风控网格')
                ]
                cursor.executemany("INSERT INTO intent_configs (intent_id, label_name, confidence_threshold, resource_binding) VALUES (%s,%s,%s,%s)", defaults)
    finally: conn.close()


# --- Functions ---
def get_recent_interactions(limit: int = 30) -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            l_val = int(limit) # Defend against dict
            cursor.execute("SELECT * FROM interaction_logs ORDER BY id DESC LIMIT %s", (l_val,))
            return cursor.fetchall() or []
    except Exception as e:
        print(f"DB Error: {e}")
        return []
    finally: conn.close()

def calculate_quality_score(log_input) -> dict:
    if hasattr(log_input, 'get'):
        row = log_input
    else:
        try:
            log_id = int(log_input)
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM interaction_logs WHERE id=%s", (log_id,))
                    row = cursor.fetchone()
            finally: conn.close()
        except: return {}

    if not row: return {}
    safety = 100
    if not row.get('is_factually_consistent', True): safety -= 50
    if row.get('user_feedback') == 'negative': safety -= 20
    ms = row.get('generation_time_ms') or 5000
    efficiency = 100 if ms < 3000 else (70 if ms < 8000 else 40)
    
    # Coverage score (Simulation or based on retrieved docs count)
    docs = json.loads(row.get('retrieved_docs', '[]'))
    coverage = min(100, len(docs) * 35) if docs else 0
    
    # Ensure float for round() to satisfy some linters/type checkers
    weighted = round(float(safety * 0.4 + efficiency * 0.3 + coverage * 0.3), 1)
    return {
        'safety_score': safety, 
        'efficiency_score': efficiency, 
        'coverage_score': coverage,
        'weighted_score': weighted, 
        'grade': '合格' if weighted >= 70 else ('风险' if weighted >= 40 else '危险')
    }

def get_dashboard_stats():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM interaction_logs WHERE DATE(created_at) = CURDATE()")
            total = cursor.fetchone()['cnt']
            cursor.execute("SELECT AVG(generation_time_ms) as avg_ms FROM interaction_logs WHERE DATE(created_at) = CURDATE()")
            avg = cursor.fetchone()['avg_ms'] or 0
            
            # P90/P99 Calculation (Simplified for performance)
            cursor.execute("SELECT generation_time_ms FROM interaction_logs WHERE DATE(created_at) = CURDATE() ORDER BY generation_time_ms")
            times = [r['generation_time_ms'] for r in cursor.fetchall()]
            p90 = times[int(len(times)*0.9)] if times else 0
            p99 = times[int(len(times)*0.99)] if times else 0

            cursor.execute("SELECT COUNT(*) as cnt FROM interaction_logs WHERE user_feedback='positive'")
            pos = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM interaction_logs WHERE user_feedback='negative'")
            neg = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM rewrite_rules")
            rules = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM bad_cases WHERE status='pending'")
            pending = cursor.fetchone()['cnt']
            return {
                'total_today': total, 
                'avg_time_ms': int(avg), 
                'p90_ms': p90, 
                'p99_ms': p99,
                'positive': pos, 
                'negative': neg, 
                'rule_count': rules, 
                'pending_cases': pending
            }
    except:
        return {'total_today': 0, 'avg_time_ms': 0, 'p90_ms': 0, 'p99_ms': 0, 'positive': 0, 'negative': 0, 'rule_count': 0, 'pending_cases': 0}
    finally: conn.close()

def get_feedback_trends(days=7):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Group by day and calculate subjective score
            sql = """
                SELECT DATE(created_at) as date, 
                COUNT(*) as total,
                SUM(CASE WHEN user_feedback='positive' THEN 1 ELSE 0 END) as pos 
                FROM interaction_logs 
                GROUP BY DATE(created_at) 
                ORDER BY date DESC LIMIT %s
            """
            cursor.execute(sql, (days,))
            rows = cursor.fetchall() or []
            for r in rows:
                r['subjective_score'] = round(r['pos'] / r['total'] * 100, 1) if r['total'] > 0 else 0
            return rows
    except: return []
    finally: conn.close()

# --- Intent / Strategy Functions ---
def get_intent_configs():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM intent_configs")
            return cursor.fetchall() or []
    finally: conn.close()

def update_intent_config(intent_id, binding, threshold):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE intent_configs SET resource_binding=%s, confidence_threshold=%s WHERE intent_id=%s", (binding, threshold, intent_id))
    finally: conn.close()

def save_strategy_snapshot(tag, desc):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM intent_configs")
            configs = cursor.fetchall()
            cursor.execute("INSERT INTO strategy_snapshots (version_tag, description, config_data) VALUES (%s, %s, %s)", (tag, desc, json.dumps(configs)))
            return True
    except: return False
    finally: conn.close()

def get_strategy_snapshots(limit=5):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM strategy_snapshots ORDER BY created_at DESC LIMIT %s", (int(limit),))
            return cursor.fetchall() or []
    finally: conn.close()

def rollback_strategy(snapshot_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT config_data FROM strategy_snapshots WHERE id=%s", (snapshot_id,))
            row = cursor.fetchone()
            if row:
                configs = json.loads(row['config_data'])
                for cfg in configs:
                    cursor.execute("UPDATE intent_configs SET resource_binding=%s, confidence_threshold=%s WHERE intent_id=%s", (cfg['resource_binding'], cfg['confidence_threshold'], cfg['intent_id']))
                return True
    except: return False
    finally: conn.close()

# --- Knowledge Hierarchy Functions ---
def get_categories_by_level(level):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM categories WHERE level=%s", (int(level),))
            return cursor.fetchall() or []
    finally: conn.close()

def get_children(parent_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM categories WHERE parent_id=%s", (int(parent_id),))
            return cursor.fetchall() or []
    finally: conn.close()

def add_category(name, level, parent_id=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "INSERT INTO categories (name, level, parent_id) VALUES (%s, %s, %s)"
            cursor.execute(sql, (name, level, parent_id))
            return cursor.lastrowid
    finally: conn.close()

def delete_category(category_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 递归删除逻辑 (简单处理：删除该节点)
            cursor.execute("DELETE FROM categories WHERE id=%s", (category_id,))
            # 同时删除子节点
            cursor.execute("DELETE FROM categories WHERE parent_id=%s", (category_id,))
    finally: conn.close()

def get_ingestion_logs(limit=20):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM ingestion_logs ORDER BY created_at DESC LIMIT %s", (int(limit),))
            return cursor.fetchall() or []
    finally: conn.close()

def add_ingestion_log(file_name, l1, l2, l3, l3_id, chunk_count, chunk_size, chunk_overlap, vector_ids_prefix, op_user="admin"):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "INSERT INTO ingestion_logs (file_name, l1_name, l2_name, l3_name, chunk_count, chunk_size, chunk_overlap, vector_ids_prefix, op_user) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(sql, (file_name, l1, l2, l3, chunk_count, chunk_size, chunk_overlap, vector_ids_prefix, op_user))
    finally: conn.close()

def delete_ingestion_log(log_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM ingestion_logs WHERE id=%s", (log_id,))
    finally: conn.close()

# --- Dictionary / Glossary Functions ---
def add_rewrite_rule(c_word, s_word):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO rewrite_rules (case_word, standard_word) VALUES (%s, %s) ON DUPLICATE KEY UPDATE standard_word=VALUES(standard_word)", (c_word, s_word))
    finally: conn.close()

def get_all_rules():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, case_word, standard_word FROM rewrite_rules")
            return cursor.fetchall() or []
    finally: conn.close()

def update_rule(rule_id, c_word, s_word):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE rewrite_rules SET case_word=%s, standard_word=%s WHERE id=%s", (c_word, s_word, rule_id))
    finally: conn.close()

def delete_rule(rule_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM rewrite_rules WHERE id = %s", (rule_id,))
    finally: conn.close()

# --- Bad Case Functions ---
def add_bad_case(query, response, feedback, log_id=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Capture docs if log_id provided
            docs = ""
            if log_id:
                cursor.execute("SELECT retrieved_docs FROM interaction_logs WHERE id=%s", (log_id,))
                r = cursor.fetchone()
                if r: docs = r['retrieved_docs']
            cursor.execute("INSERT INTO bad_cases (query, ai_response, user_feedback, interaction_log_id, retrieved_docs) VALUES (%s, %s, %s, %s, %s)", (query, response, feedback, log_id, docs))
    finally: conn.close()

def get_pending_bad_cases():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, query, ai_response, user_feedback, status, interaction_log_id, retrieved_docs FROM bad_cases WHERE status = 'pending'")
            return cursor.fetchall() or []
    finally: conn.close()

def update_bad_case_status(case_id, status):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE bad_cases SET status = %s WHERE id = %s", (status, case_id))
    finally: conn.close()

# --- Standard Agent Functions ---
def log_interaction(session_id, query, rewritten, intent, confidence, reasoning, docs, graphs, response, time_ms, is_consistent=True, feedback=""):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            d_json = json.dumps(docs, ensure_ascii=False) if docs else "[]"
            g_json = json.dumps(graphs, ensure_ascii=False) if graphs else "[]"
            sql = "INSERT INTO interaction_logs (session_id, user_query, rewritten_query, intent, confidence, reasoning, retrieved_docs, graph_paths, ai_response, generation_time_ms, is_factually_consistent, fact_check_feedback) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            cursor.execute(sql, (session_id, query, rewritten, intent, confidence, reasoning, d_json, g_json, response, int(time_ms), is_consistent, feedback))
            return cursor.lastrowid
    except Exception as e:
        print(f"Log Error: {e}")
        return -1
    finally: conn.close()

def update_interaction_feedback(log_id, feedback):
    """更新交互日志中的用户反馈 (positive/negative)"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE interaction_logs SET user_feedback=%s WHERE id=%s", (feedback, log_id))
    except Exception as e:
        print(f"Feedback Update Error: {e}")
    finally: conn.close()

def save_patient_profile(sid, data):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO patient_profiles (session_id, profile_data) VALUES (%s, %s) ON DUPLICATE KEY UPDATE profile_data=VALUES(profile_data)", (sid, data))
    finally: conn.close()

def get_patient_profile(sid):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT profile_data FROM patient_profiles WHERE session_id=%s", (sid,))
            r = cursor.fetchone()
            return json.loads(r['profile_data']) if r else {}
    finally: conn.close()

try:
    init_db()
except Exception as e:
    print(f"CRITICAL: Database initialization failed: {e}")
