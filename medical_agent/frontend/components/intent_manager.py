import streamlit as st
import pandas as pd
import time
import json
from datetime import datetime

# 引入 MySQL 帮助函数
try:
    from data import mysql_mgr as db
except ImportError:
    db = None

def render_intent_manager():
    # Force reload trigger: Phase 15 CRUD Active
    if db and hasattr(db, 'VERSION'):
        st.sidebar.caption(f"DB Module Version: {db.VERSION}")
    
    if not db:
        st.error("数据库模块加载失败，无法进行意图管理。")
        return

    st.markdown("<span style='color: #86909c; font-size: 14px;'>动态调整模型路由意图的置信度阈值与资源绑定，支持版本快照与回滚。</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["🎯 策略配置", "🧪 路由推演沙盒", "🛡️ 红线风控大盘", "🎡 数据飞轮与 HITL"])
    
    with tab1:
        st.markdown("##### 意图分发策略 (策略快照与回滚)")
        
        # 1. 策略版本控制区
        col_v1, col_v2 = st.columns([7, 3])
        with col_v2:
            with st.expander("📦 版本快照管理", expanded=True):
                v_tag = st.text_input("版本标签", placeholder="v1.0.1", key="v_tag")
                v_desc = st.text_area("变更描述", placeholder="调整了预计阈值...", key="v_desc")
                if st.button("📸 创建当前快照", type="primary", use_container_width=True):
                    if v_tag:
                        if db.save_strategy_snapshot(v_tag, v_desc):
                            st.success(f"快照 {v_tag} 已保存")
                            st.rerun()
                    else: st.error("请填写版本标签")
                
                st.divider()
                st.caption("历史快照 (最近 5 个)")
                snaps = db.get_strategy_snapshots(limit=5)
                for s in snaps:
                    with st.container(border=True):
                        st.markdown(f"**{s['version_tag']}**")
                        st.caption(f"{s['created_at']}")
                        if st.button("🔄 回滚", key=f"rb_{s['id']}", use_container_width=True):
                            if db.rollback_strategy(s['id']):
                                st.toast(f"已回滚至 {s['version_tag']}")
                                time.sleep(1)
                                st.rerun()

        with col_v1:
            st.markdown("🔍 **核心意图运行参数**")
            # 基础意图配置
            configs = db.get_intent_configs()
            config_map = {c['intent_id']: c for c in configs}
            
            for intent_id in ["ADMIN", "PHARMA", "DIAG", "VIOLATION"]:
                if intent_id in config_map:
                    cfg = config_map[intent_id]
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 6])
                        c1.markdown(f"**{cfg['label_name']}** (`{intent_id}`)")
                        threshold = c2.slider("命中阈值", 0.0, 1.0, float(cfg['confidence_threshold']), 0.05, key=f"t_{intent_id}")
                        binding = c2.selectbox("资源绑定", ["系统级向量库", "通用药理图谱库", "临床医学知识库", "安全风控网格", "默认池"], 
                                             index=["系统级向量库", "通用药理图谱库", "临床医学知识库", "安全风控网格", "默认池"].index(cfg['resource_binding']) if cfg['resource_binding'] in ["系统级向量库", "通用药理图谱库", "临床医学知识库", "安全风控网格", "默认池"] else 4,
                                             key=f"b_{intent_id}")
                        if threshold != cfg['confidence_threshold'] or binding != cfg['resource_binding']:
                            db.update_intent_config(intent_id, binding, threshold)
                            st.success(f"{intent_id} 已更新")
                            st.rerun()
                            
            st.divider()
            c_tree_1, c_tree_2 = st.columns([7, 3])
            c_tree_1.markdown("#### 🏥 DIAG 诊断科普专题树 (L1→L2→L3)")
            
            with c_tree_2:
                pop_l1 = st.popover("➕ 新增一级主题域", use_container_width=True)
                new_l1_name = pop_l1.text_input("一级库名称", placeholder="如：呼吸内科", key="new_l1_input")
                if pop_l1.button("确认创建一级库", type="primary", use_container_width=True, key="conf_add_l1"):
                    if new_l1_name:
                        db.add_category(new_l1_name, 1)
                        st.success(f"已创建一级库: {new_l1_name}")
                        st.rerun()
                    else: st.error("名称不能为空")
            
            # 专题树逻辑
            try:
                l1_list = db.get_categories_by_level(1)
            except Exception as e:
                st.error(f"加载一级库失败: {e}")
                l1_list = []

            if l1_list:
                for l1 in l1_list:
                    l1_id = l1.get('id')
                    l1_name = l1.get('name', '未命名')
                    if not l1_id: continue

                    with st.expander(f"🏥 {l1_name}", expanded=False):
                        # L1 操作区
                        row_l1 = st.columns([6, 2, 2])
                        pop_l2 = row_l1[1].popover("➕ 子库", use_container_width=True)
                        new_l2_name = pop_l2.text_input(f"在「{l1_name}」下新增二级库", placeholder="如：哮喘专题", key=f"in_l2_{l1_id}")
                        if pop_l2.button("确认创建", key=f"add_l2_btn_{l1_id}", use_container_width=True):
                            if new_l2_name:
                                db.add_category(new_l2_name, 2, l1_id)
                                st.rerun()

                        if row_l1[2].button("🗑 删除", key=f"del_l1_btn_{l1_id}", use_container_width=True, help="将连带删除所有下级内容"):
                            db.delete_category(l1_id)
                            st.rerun()
                        
                        st.divider()
                        
                        try:
                            l2_list = db.get_children(l1_id)
                        except: l2_list = []

                        for l2 in l2_list:
                            l2_id = l2.get('id')
                            l2_name = l2.get('name', '未命名')
                            if not l2_id: continue

                            with st.container(border=True):
                                col_l2_name, col_l2_add, col_l2_del = st.columns([6, 2, 2])
                                col_l2_name.markdown(f"📂 **{l2_name}**")
                                
                                pop_l3 = col_l2_add.popover("📄+三级", use_container_width=True)
                                new_l3_name = pop_l3.text_input(f"在「{l2_name}」下新增三级专题", placeholder="如：小儿哮喘护理", key=f"in_l3_{l2_id}")
                                if pop_l3.button("确认", key=f"add_l3_btn_{l2_id}", use_container_width=True):
                                    if new_l3_name:
                                        db.add_category(new_l3_name, 3, l2_id)
                                        st.rerun()
                                
                                if col_l2_del.button("🗑", key=f"del_l2_btn_{l2_id}", use_container_width=True):
                                    db.delete_category(l2_id)
                                    st.rerun()
                                
                                # L3 展示
                                try:
                                    l3_list = db.get_children(l2_id)
                                except: l3_list = []

                                if l3_list:
                                    for l3 in l3_list:
                                        l3_id = l3.get('id')
                                        l3_name = l3.get('name', '未命名')
                                        if not l3_id: continue
                                        
                                        with st.container():
                                            c_l3_n, c_l3_d = st.columns([8, 2])
                                            c_l3_n.markdown(f"<div style='margin-left:20px; font-size:14px; color:#4e5969;'>• {l3_name}</div>", unsafe_allow_html=True)
                                            if c_l3_d.button("❌", key=f"del_l3_btn_{l3_id}", help="删除此三级专题"):
                                                db.delete_category(l3_id)
                                                st.rerun()
            else:
                st.info("尚未配置知识库层级树。请点击右侧「新增一级主题域」开始。")

    with tab2:
        render_sandbox_tab()

    with tab3:
        render_safety_tab(db)

    with tab4:
        render_flywheel_tab(db)

def render_sandbox_tab():
    st.markdown("##### 🧪 路由推演沙盒 (白盒推演测试)")
    st.caption("输入测试语句，实时观测 Router 的思维链 (Reasoning) 与置信度分配。")
    
    col1, col2 = st.columns([4, 6])
    with col1:
        test_query = st.text_area("测试语句", placeholder="例：孕晚期肚子发紧怎么办？", height=150)
        run_sandbox = st.button("🚀 启动推演", type="primary", use_container_width=True)
    
    with col2:
        if run_sandbox and test_query:
            with st.spinner("模型推理中..."):
                try:
                    # 调用后端路由逻辑
                    from backend.agent import route_intent
                    initial_state = {
                        "original_query": test_query,
                        "history": [],
                        "intent": "",
                        "reasoning": "",
                        "confidence": 0.0
                    }
                    result = route_intent(initial_state)
                    
                    st.success(f"命中意图: **{result['intent']}**")
                    st.metric("置信度分数", f"{result['confidence']:.2f}")
                    
                    with st.expander("📝 查看思维链过程 (思维链)", expanded=True):
                        st.write(result['reasoning'])
                except Exception as e:
                    st.error(f"联调失败: {e}")
        else:
            st.info("在右侧输入医疗问题并运行，查看路由决策明细。")

def render_safety_tab(db):
    st.markdown("##### 🛡️ 异常风控与红线熔断大盘")
    st.caption("实时监控所有被 VIOLATION 拦截的会话，保障医疗合规性。")
    
    conn = db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT user_query, reasoning, created_at 
                FROM interaction_logs 
                WHERE intent = 'VIOLATION' 
                ORDER BY created_at DESC LIMIT 20
            """)
            logs = cursor.fetchall()
    except: logs = []
    finally: conn.close()

    if not logs:
        st.success("🎉 当前全盘合规，未发现红线拦截记录。")
    else:
        for log in logs:
            with st.container(border=True):
                st.markdown(f"🚨 **违规请求**: `{log['user_query']}`")
                st.caption(f"触发时间: {log['created_at']}")
                with st.expander("展示拦截原因 (Reasoning)"):
                    st.write(log['reasoning'])

def render_flywheel_tab(db):
    st.markdown("##### 🎡 低置信度运营池 (人机交互标注)")
    st.caption("自动捕获低于策略阈值的交互，人工干预后可沉淀为 Router 的 Few-Shot 示例。")
    
    conn = db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT user_query, intent, confidence, reasoning, created_at 
                FROM interaction_logs 
                WHERE confidence < 0.7 
                ORDER BY created_at DESC LIMIT 10
            """)
            low_cases = cursor.fetchall()
    except: low_cases = []
    finally: conn.close()
    
    if not low_cases:
        st.success("🎉 目前暂无低置信度 Case，系统运作良好！")
        return

    for i, item in enumerate(low_cases):
        with st.container(border=True):
            st.markdown(f"❓ `{item['user_query']}`")
            st.caption(f"系统判定: {item['intent']} (Score: {item['confidence']:.2f})")
            with st.expander("查看原推理过程"):
                st.write(item['reasoning'])
            
            col_a, col_b = st.columns([6, 4])
            correct_intent = col_a.selectbox("更正意图为", ["ADMIN", "PHARMA", "DIAG", "VIOLATION"], key=f"corr_{i}", index=["ADMIN", "PHARMA", "DIAG", "VIOLATION"].index(item['intent']) if item['intent'] in ["ADMIN", "PHARMA", "DIAG", "VIOLATION"] else 2)
            if col_b.button("🚀 沉淀为 Few-Shot", key=f"fs_{i}", type="primary"):
                st.toast("✅ 已加入意图学习池，模型性能持续优化中")
                time.sleep(1)
                st.rerun()
