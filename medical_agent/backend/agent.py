import os
import time
import logging
import threading
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END
from langchain_ollama import OllamaLLM, OllamaEmbeddings
import chromadb
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config.settings import LLM_MODEL, EMBEDDING_MODEL, CHROMA_DB_PATH, CHROMA_COLLECTION_NAME, LOG_DIR, CACHE_TTL_SECONDS
from prompts.system_prompts import ROUTER_PROMPT, L3_CATEGORY_PROMPT, GENERATION_PROMPT, PROFILE_EXTRACTOR_PROMPT, CONTEXT_ANALYZER_PROMPT, FACT_CHECK_PROMPT
from data.vector_store.chroma_processor import VectorProcessor
from data.mapping_layer.mapper import VectorGraphMapper
from backend.exceptions import LLMServiceError, RetrievalError
from backend.metrics import metrics

# Configure Logger
logging.basicConfig(filename=os.path.join(LOG_DIR, "agent.log"), level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# NOTE: langchain-ollama 0.2.0 内部使用流式返回并聚合的方式调用 Ollama，
# 而本地 Ollama v0.19.0 对此路径返回 502。
# 通过调用 ChatOllamaGen异或 httpx 由我们自己封装调用避开这个问题。
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

llm = OllamaLLM(model=LLM_MODEL, base_url=OLLAMA_BASE_URL)
embedder = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)

def _call_ollama_direct(prompt: str, timeout: int = LLM_TIMEOUT) -> str:
    """
    HACK: 直接使用 httpx 调用 Ollama REST API，绕开 langchain-ollama 的流式模式问题。
    Ollama v0.19.0 对非流式 POST /api/generate 完全正常，对流式连接返回 502。
    NOTE: 强制 HTTP/1.1（http2=False），因 Ollama v0.19.0 不支持 HTTP/2 协议。
    """
    import httpx
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {"model": LLM_MODEL, "prompt": prompt, "stream": False}
    # NOTE: 强制 HTTP/1.1，curl -s 默认 HTTP/1.1 所以成功，而 httpx 会尝试 HTTP/2 导致 502
    transport = httpx.HTTPTransport(http2=False)
    with httpx.Client(timeout=timeout, transport=transport) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")

# ── TTL 缓存工具 ─────────────────────────────────────────────────────────────
class TTLCache:
    """简单的线程安全 TTL 缓存"""
    def __init__(self, ttl_seconds: int = 300):
        self._cache = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def get(self, key: str):
        with self._lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if time.time() - ts < self._ttl:
                    return value
                del self._cache[key]
        return None

    def set(self, key: str, value):
        with self._lock:
            self._cache[key] = (value, time.time())

    def invalidate(self):
        with self._lock:
            self._cache.clear()

_rules_cache = TTLCache(ttl_seconds=CACHE_TTL_SECONDS)
_l3_cache = TTLCache(ttl_seconds=CACHE_TTL_SECONDS)

# Define Agent State
class AgentState(TypedDict):
    session_id: str
    original_query: str
    resolved_query: str  # 指代消除后的查询
    rewritten_query: str # 术语规范化后的查询
    history: List[Dict[str, str]]
    intent: str  # 主要意图
    decomposed_queries: List[Dict[str, str]] # [{'query': '...', 'intent': '...'}]
    patient_profile: dict  # {age, gender, medical_history, symptoms}
    l3_category: str
    expert_advice: List[str]  # 汇总各专家的意见
    retrieved_docs: List[str]
    doc_sources: List[str]
    graph_context: List[str]
    final_answer: str
    error_or_warning: str
    reasoning: str
    confidence: float
    log_id: int
    applied_rules: List[str]
    low_relevance: bool  # 🚩 检索相关性过低标识
    is_factually_consistent: bool # 🛡️ 事实一致性标识
    fact_check_feedback: str # 审计反馈

# ── 带重试的 LLM 调用 ─────────────────────────────────────────────────────────
def _safe_llm_invoke(prompt: str) -> str:
    """
    带自动重试的 LLM 调用：最多3次，指数退避。
    优先使用直接 httpx 调用 Ollama REST API，避免 langchain-ollama 流式层的 502 问题。
    """
    for attempt in range(3):
        try:
            result = _call_ollama_direct(prompt)
            if result:
                return result
        except Exception as e:
            metrics.record_error("llm_invoke_error")
            logging.warning(f"LLM invoke attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)  # 指数退避: 1s, 2s
    raise LLMServiceError(detail="LLM 服务在 3 次重试后仍无响应")

def context_analyzer(state: AgentState):
    """
    MedCAC 核心节点：指代消除 + 意图拆解
    """
    t0 = time.time()
    query = state["original_query"]
    history = state.get("history", [])
    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in history[-5:]]) # 取最近5轮
    
    import json
    import re
    try:
        # 1. 指代消除与拆解
        prompt = CONTEXT_ANALYZER_PROMPT.format(query=query, history=history_str)
        response = _safe_llm_invoke(prompt)
        
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            res = json.loads(json_match.group(0))
            state['resolved_query'] = res.get("resolved_query", query)
            state['decomposed_queries'] = res.get("decomposed_queries", [{"query": query, "intent": "DIAG"}])
        else:
            state['resolved_query'] = query
            state['decomposed_queries'] = [{"query": query, "intent": "DIAG"}]
            
        # 2. 确定主意图（用于向后兼容和日志）
        if state['decomposed_queries']:
            state['intent'] = state['decomposed_queries'][0]['intent']
        
        # 3. 如果包含红线意图，立即标记
        if any(q['intent'] == "VIOLATION" for q in state['decomposed_queries']):
            state['intent'] = "VIOLATION"
            state['final_answer'] = "抱歉，作为 AI 科普助手，我无法为您开具处方、确诊症状或提供涉及违禁药物的建议。请务必前往正规医院线下就诊。"

    except Exception as e:
        logging.error(f"Context Analyzer error: {str(e)}")
        state['resolved_query'] = query
        state['decomposed_queries'] = [{"query": query, "intent": "DIAG"}]
    finally:
        metrics.record_node_time("context_analyzer", (time.time() - t0) * 1000)
    return state



def extract_patient_profile(state: AgentState):
    """
    Step 2: Patient Profile Extraction & Persistence
    """
    if state['intent'] == "VIOLATION": return state
    
    t0 = time.time()
    try:
        import json
        from backend.repository import mysql_mgr as db_mgr
        
        # 1. 加载历史画像
        current_sid = state.get('session_id') or 'default_user'
        existing_profile = db_mgr.get_patient_profile(current_sid)
        
        # 2. 从当前对话提取新信息
        history_str = "\n".join([f"{m['role']}: {m['content']}" for m in state.get('history', [])[-3:]])
        prompt = PROFILE_EXTRACTOR_PROMPT.format(history=history_str, query=state['original_query'])
        raw_res = _safe_llm_invoke(prompt)
        
        new_info = {}
        try:
            # NOTE: 清理 LLM 可能附带的 markdown 代码块标记后再解析
            cleaned = raw_res
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            # 提取第一个合法 JSON 对象
            import re
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                new_info = json.loads(match.group(0))
        except (json.JSONDecodeError, Exception) as parse_err:
            logging.warning(f"Profile JSON parse failed: {parse_err}")
        
        # 3. 合并画像
        for k, v in new_info.items():
            if v and (not existing_profile.get(k) or existing_profile[k] == "null"):
                existing_profile[k] = v
        
        state['patient_profile'] = existing_profile
        
        # 4. 异步/同步持久化
        db_mgr.save_patient_profile(current_sid, json.dumps(existing_profile, ensure_ascii=False))
        logging.info(f"Patient profile updated for {current_sid}: {existing_profile}")
        
    except Exception as e:
        logging.warning(f"Profile extraction failed: {e}")
        state['patient_profile'] = {}
    finally:
        metrics.record_node_time("profile_extractor", (time.time() - t0) * 1000)
    return state

def route_intent(state: AgentState):
    """
    独立于 Graph 的工具函数，供管理端沙盒调用，仅执行意图路由推演。
    """
    try:
        import json
        import re
        query = state["original_query"]
        history_str = "\n".join([f"{m['role']}: {m['content']}" for m in state.get("history", [])])
        
        prompt = CONTEXT_ANALYZER_PROMPT.format(query=query, history=history_str)
        response = _safe_llm_invoke(prompt)
        
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            res = json.loads(json_match.group(0))
            # 这里的推理逻辑需要与 context_analyzer 保持同步
            return {
                "intent": res.get("intent", res.get("decomposed_queries", [{"intent": "DIAG"}])[0]["intent"]),
                "reasoning": res.get("reasoning", "模型未提供推理过程"),
                "confidence": res.get("confidence", 0.9) # 默认高置信度
            }
    except Exception as e:
        logging.error(f"Sandbox route_intent error: {e}")
        return {"intent": "DIAG", "reasoning": f"解析失败: {str(e)}", "confidence": 0.0}
    return {"intent": "DIAG", "reasoning": "未命中解析逻辑", "confidence": 0.0}

def rewrite_query(state: AgentState):
    """
    Step 2: Query Rewriting
    Converts colloquial terms to standard medical terms using the MySQL synonym dictionary.
    使用 TTL 缓存避免每次查询都访问数据库。
    """
    t0 = time.time()
    query = state['original_query']
    applied = []
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backend.repository import mysql_mgr as db_mgr
        
        # 优先使用缓存
        rules = _rules_cache.get("all_rules")
        if rules is None:
            rules = db_mgr.get_all_rules()  # [(id, colloquial, standard), ...]
            _rules_cache.set("all_rules", rules)
            logging.info(f"Rules cache refreshed: {len(rules)} rules loaded")
        
        # NOTE: get_all_rules() 返回 dict 列表，需按 key 访问，不能用 tuple 解包
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            colloquial = rule.get('case_word', '')
            standard = rule.get('standard_word', '')
            if colloquial and colloquial in query:
                query = query.replace(colloquial, standard)
                applied.append(f"{colloquial} → {standard}")
        logging.info(f"Query rewrite applied {len(applied)} rules: {applied}")
    except Exception as e:
        logging.warning(f"Query rewrite skipped (dict load error): {e}")
        metrics.record_error("rewrite_error")
    finally:
        metrics.record_node_time("rewriter", (time.time() - t0) * 1000)
    state['rewritten_query'] = query
    state['applied_rules'] = applied  # type: ignore[typeddict-item]
    return state

def identify_l3_category(state: AgentState):
    """
    Step 2.5: Identify which L3 knowledge category this query belongs to
    使用 TTL 缓存 L3 分类列表，减少数据库遍历次数。
    """
    t0 = time.time()
    if state['intent'] == 'violation':
        state['l3_category'] = None
        return state
    
    query = state['rewritten_query']
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backend.repository import mysql_mgr as db_mgr
        
        # 缓存 L3 名称列表
        all_l3_names = _l3_cache.get("all_l3_names")
        if all_l3_names is None:
            l1_list = db_mgr.get_categories_by_level(1)
            all_l3_names = []
            for l1 in l1_list:
                l2_list = db_mgr.get_children(l1['id'])
                for l2 in l2_list:
                    l3_list = db_mgr.get_children(l2['id'])
                    for l3 in l3_list:
                        all_l3_names.append(l3['name'])
            _l3_cache.set("all_l3_names", all_l3_names)
            logging.info(f"L3 cache refreshed: {len(all_l3_names)} categories loaded")
        
        # 简单关键词匹配
        matched_l3 = None
        for l3_name in all_l3_names:
            if l3_name in query or any(word in query for word in l3_name.split()):
                matched_l3 = l3_name
                break
        
        if matched_l3:
            state['l3_category'] = matched_l3
            logging.info(f"L3 category matched via keyword: {matched_l3}")
        else:
            # 使用LLM进行更精确的识别（带重试）
            prompt = L3_CATEGORY_PROMPT.format(query=query)
            l3_res = _safe_llm_invoke(prompt)
            state['l3_category'] = l3_res.strip()
            logging.info(f"L3 category identified by LLM: {state['l3_category']}")
            
    except Exception as e:
        logging.warning(f"L3 category identification failed: {e}")
        metrics.record_error("l3_identify_error")
        state['l3_category'] = "通用科普知识"
    finally:
        metrics.record_node_time("l3_identifier", (time.time() - t0) * 1000)
    
    return state

v_processor = VectorProcessor()
v_mapper = VectorGraphMapper()

def admin_expert(state: AgentState):
    """行政/导诊专家：仅使用向量库检索规章制度 (Expert: ADMIN)"""
    t0 = time.time()
    # 🎯 资源绑定检索
    state = retrieve_knowledge(state, expert="ADMIN")
    
    docs = state['retrieved_docs'][-2:]
    advice = f"【行政专家建议】: 根据医院制度，相关的规定如下: { ' '.join(docs) }"
    state['expert_advice'].append(advice)
    
    metrics.record_node_time("admin_expert", (time.time() - t0) * 1000)
    return state

def pharma_expert(state: AgentState):
    """药理专家：侧重图谱知识，查询药物关系 (Expert: PHARMA)"""
    t0 = time.time()
    # 🎯 资源绑定检索
    state = retrieve_knowledge(state, expert="PHARMA")
    
    # 查找关联实体（从本次检索到的 vector_ids 中提取）
    # Note: retrieve_knowledge 已经将 vector_ids 分批处理并记录在了内部逻辑中，
    # 这里我们假设 state['graph_context'] 会被 retrieve_knowledge 自动填充。
    # 为了保证逻辑连贯，我们从 state 中获取最近的图谱上下文。
    
    graph_paths = state.get('graph_context', [])
    advice = f"【药理专家建议】: 发现以下药物关联逻辑: { '; '.join(graph_paths) if graph_paths else '未发现直接交互风险，请遵循医嘱。' }"
    state['expert_advice'].append(advice)
    
    metrics.record_node_time("pharma_expert", (time.time() - t0) * 1000)
    return state

def diag_expert(state: AgentState):
    """诊断科普专家：混合检索（L3 分类 + 图谱） (Expert: DIAG)"""
    t0 = time.time()
    # 1. 识别三级分类 (使用解析后的查询)
    state = identify_l3_category(state)
    # 2. 执行资源绑定检索
    state = retrieve_knowledge(state, expert="DIAG")
    
    docs = state['retrieved_docs'][-2:] # 取最近检索的
    advice = f"【科普专家建议】: 结合医学指南，该症状可能涉及: { ' '.join(docs) }"
    state['expert_advice'].append(advice)
    
    metrics.record_node_time("diag_expert", (time.time() - t0) * 1000)
    return state

def retrieve_knowledge(state: AgentState, expert: str = None):
    """
    Step 3: Enterprise Hybrid Retrieval (Vector + Graph Mapping + Windowed Context)
    🎯 支持 Multi-Query (多意图分发) 和 Relevance Score 过滤
    """
    t0 = time.time()
    # 🎯 只有 DIAG 专家才执行 L3 精准过滤
    l3_category = state.get('l3_category') if expert == "DIAG" else None
    
    # 获取当前专家的所有相关子问题
    subs = state.get('decomposed_queries', [])
    target_queries = [s['query'] for s in subs if s['intent'] == expert or expert is None]
    if not target_queries:
        target_queries = [state.get('resolved_query', state['original_query'])]
    
    threshold = 0.6  # ⚠️ 相关性阈值 (Cosine Distance, 越小越相关)
    high_conf_docs = []
    high_conf_sources = []
    high_conf_vids = []
    
    try:
        for q in target_queries:
            results = v_processor.hierarchical_semantic_search(
                q, expert=expert, l3_name=l3_category, top_k=3
            )
            
            docs = results.get('documents', [])
            metas = results.get('metadatas', [[]])[0] if 'metadatas' in results else []
            distances = results.get('distances', [])
            sources = results.get('sources', [])
            vids = results.get('vector_ids', [])
            
            # 过滤低相关性切片
            for i, dist in enumerate(distances):
                if dist <= threshold:
                    high_conf_docs.append(docs[i])
                    # 安全获取 metadata
                    meta = metas[i] if i < len(metas) else {}
                    high_conf_sources.append(meta.get('source', '未知文档'))
                    high_conf_vids.append(vids[i] if i < len(vids) else f"unknown_{i}")
                    
                    # Windowed Context
                    idx = meta.get('chunk_index')
                    src = meta.get('source')
                    if idx is not None and src:
                        window_text = v_processor.fetch_windowed_context(src, idx, window=1)
                        if window_text: high_conf_docs[-1] = window_text
                else:
                    logging.warning(f"Discarding low-relevance chunk (dist={dist:.4f}) for query: {q}")
                    
        state['retrieved_docs'].extend(high_conf_docs)
        state['doc_sources'].extend(list(set(high_conf_sources)))
        
        # 标记是否全军没顶 (用于拒答逻辑)
        if not high_conf_docs:
            state['low_relevance'] = True
        else:
            state['low_relevance'] = False
            
        # 2. 图谱扩展 (仅针对高置信度向量)
        linked_entities = set()
        for vid in high_conf_vids:
            linked_entities.update(v_mapper.find_entities_by_vector(vid))
            
        if linked_entities:
            from data.graph_store.neo4j_processor import GraphStoreProcessor
            g_processor = GraphStoreProcessor()
            with g_processor.driver.session() as session:
                names = list(linked_entities)
                res = session.run("UNWIND $names as name MATCH (n {name: name})-[r]->(m) RETURN n.name, type(r), m.name LIMIT 3", names=names)
                state['graph_context'].extend([f"{record['n.name']} --{record['type(r)']}--> {record['m.name']}" for record in res])
                
    except Exception as e:
        logging.error(f"Retrieval error: {e}")
    finally:
        metrics.record_node_time("retriever", (time.time() - t0) * 1000)
    return state

def generate_answer(state: AgentState):
    """
    Step 4: Supervisor Synthesis (Context-Aware)
    """
    # NOTE: 知识库检索相关性过低时，不直接拒答，而是降级到 LLM 凭借自身医学训练知识作答，
    # 同时在回答前加标注，让用户知晓本次回答未能从专属知识库中引用来源。
    if state.get('low_relevance'):
        try:
            from prompts.system_prompts import GENERATION_PROMPT
            profile = state.get('patient_profile', {})
            profile_str = json.dumps(profile, ensure_ascii=False) if any(profile.values()) else "[]"
            fallback_advice = "【通用医学知识】: 知识库中暂未找到精确匹配的参考文献，以下回答基于大模型自身的医学训练知识。"
            prompt = GENERATION_PROMPT.format(
                query=state['original_query'],
                profile=profile_str,
                expert_advice=fallback_advice
            )
            reply = _safe_llm_invoke(prompt)
            state['final_answer'] = reply + "\n\n> ⚠️ *本次回答未能从专属知识库中检索到直接参考资料，建议结合医生意见。*"
            state['error_or_warning'] = "低置信度检索，已降级为通用LLM回答"
        except Exception as e:
            logging.error(f"LLM fallback error: {e}")
            state['final_answer'] = "抱歉，我在知识库中暂时没有找到与您的问题直接相关的专业内容，建议您咨询专业医生或前往医院就诊。"
        return state
    
    t0 = time.time()
    try:
        import json
        from prompts.system_prompts import GENERATION_PROMPT
        
        # 只有在画像不为空时才注入
        profile = state.get('patient_profile', {})
        profile_str = json.dumps(profile, ensure_ascii=False) if any(profile.values()) else "[]"
        
        expert_advice_str = "\n".join(state.get('expert_advice', []))
        
        prompt = GENERATION_PROMPT.format(
            query=state['original_query'],
            profile=profile_str,
            expert_advice=expert_advice_str
        )
        
        reply = _safe_llm_invoke(prompt)
        state['final_answer'] = reply
        
    except Exception as e:
        logging.error(f"Supervisor error: {str(e)}")
        state['final_answer'] = "抱歉，由于内部逻辑冲突，暂时无法生成回答。"
    finally:
        metrics.record_node_time("supervisor", (time.time() - t0) * 1000)
    return state

def response_refiner(state: AgentState):
    """
    Step 5: Response Refinement (Anti-hallucination & Coverage Check)
    """
    if state['intent'] == "VIOLATION" or not state.get('final_answer'): return state
    
    t0 = time.time()
    try:
        from prompts.system_prompts import RESPONSE_REFINER_PROMPT
        expert_advice_str = "\n".join(state.get('expert_advice', []))
        
        prompt = RESPONSE_REFINER_PROMPT.format(
            query=state['resolved_query'],
            answer=state['final_answer'],
            expert_advice=expert_advice_str
        )
        
        refined_reply = _safe_llm_invoke(prompt)
        state['final_answer'] = refined_reply
        
        # 记录日志
        try:
            from backend.repository import mysql_mgr as db_mgr
            sources = list(set(state.get('doc_sources', [])))
            final_res = refined_reply
            if sources:
                final_res += f"\n\n---\n**参考资料**:\n" + "\n".join([f"[{i+1}] {s}" for i, s in enumerate(sources)])
            
            ms = int((time.time() - t0) * 1000)
            log_id = db_mgr.log_interaction(
                session_id=state.get('session_id', 'admin_debug'),
                query=state['original_query'],
                rewritten=state.get('resolved_query', state['original_query']),
                intent=state.get('intent', 'DIAG'),
                confidence=state.get('confidence', 0.0),
                reasoning=state.get('reasoning', ''),
                docs=state['retrieved_docs'],
                graphs=state['graph_context'],
                response=final_res,
                time_ms=ms,
                is_consistent=state.get('is_factually_consistent', True),
                feedback=state.get('fact_check_feedback', '')
            )
            state['log_id'] = log_id
            state['final_answer'] = final_res
        except Exception as log_err:
            # FIXME: 之前此处使用 except: pass 导致日志写入失败完全静默，现已改为记录警告
            logging.warning(f"Interaction log write failed (non-critical): {log_err}")

    except Exception as e:
        logging.error(f"Refiner error: {str(e)}")
    finally:
        metrics.record_node_time("refiner", (time.time() - t0) * 1000)
    return state

def fact_checker(state: AgentState):
    """
    商业化增强节点：合规性审计 (Fact Check)
    核对生成的回答是否与检索到的参考资料存在矛盾。
    """
    t0 = time.time()
    try:
        context = "\n".join(state.get('retrieved_docs', []))
        answer = state.get('final_answer', '')
        
        if not context or not answer:
            state['is_factually_consistent'] = True
            return state

        prompt = FACT_CHECK_PROMPT.format(context=context, answer=answer)
        audit_res = _safe_llm_invoke(prompt)
        
        if "CONSISTENT" in audit_res.upper():
            state['is_factually_consistent'] = True
            state['fact_check_feedback'] = ""
        else:
            state['is_factually_consistent'] = False
            state['fact_check_feedback'] = audit_res
            logging.warning(f"Fact check failed: {audit_res}")
            # 如果不一致，可以在这里标记 warning
            state['error_or_warning'] = f"审计提示：建议内容与参考资料存在潜在偏差。{audit_res}"
            
    except Exception as e:
        logging.error(f"Fact checker error: {str(e)}")
        state['is_factually_consistent'] = True # 降级处理
    finally:
        metrics.record_node_time("fact_checker", (time.time() - t0) * 1000)
    return state

def build_workflow():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("context_analyzer", context_analyzer)
    workflow.add_node("profile_extractor", extract_patient_profile)
    workflow.add_node("rewriter", rewrite_query)
    workflow.add_node("admin_expert", admin_expert)
    workflow.add_node("pharma_expert", pharma_expert)
    workflow.add_node("diag_expert", diag_expert)
    workflow.add_node("supervisor", generate_answer)
    workflow.add_node("fact_checker", fact_checker)
    workflow.add_node("refiner", response_refiner)
    
    workflow.set_entry_point("context_analyzer")
    
    def decide_after_analyzer(state: AgentState):
        if state['intent'] == "VIOLATION":
            return END
        return "profile_extractor"
    
    def route_to_experts(state: AgentState):
        # MedCAC: 支持多意图并行/顺序触发
        # 为简化，返回一个列表，但在当前 Graph 结构下，我们先用简单逻辑
        intents = [q['intent'] for q in state.get('decomposed_queries', [])]
        next_nodes = []
        if "ADMIN" in intents: next_nodes.append("admin_expert")
        if "PHARMA" in intents: next_nodes.append("pharma_expert")
        if "DIAG" in intents or not next_nodes: next_nodes.append("diag_expert")
        
        # 返回第一个匹配的专家，或者如果是并行路径则需要更复杂的 Graph
        # 这里我们先让它支持条件分支
        return next_nodes[0]
        
    workflow.add_conditional_edges("context_analyzer", decide_after_analyzer)
    workflow.add_edge("profile_extractor", "rewriter")
    workflow.add_conditional_edges("rewriter", route_to_experts)
    
    # 专家节点都汇聚到 supervisor
    workflow.add_edge("admin_expert", "supervisor")
    workflow.add_edge("pharma_expert", "supervisor")
    workflow.add_edge("diag_expert", "supervisor")
    
    workflow.add_edge("supervisor", "fact_checker")
    workflow.add_edge("fact_checker", "refiner")
    workflow.add_edge("refiner", END)
    
    return workflow.compile()

medical_agent_app = build_workflow()

if __name__ == "__main__":
    test_state = {
        "session_id": "test_123",
        "original_query": "孕晚期肚子硬怎么办", 
        "rewritten_query": "", 
        "history": [],
        "intent": "", 
        "expert_advice": [],
        "retrieved_docs": [], 
        "doc_sources": [],
        "graph_context": [], 
        "final_answer": "", 
        "error_or_warning": ""
    }
    result = medical_agent_app.invoke(test_state) # type: ignore
    print(result.get('final_answer', 'Fail'))
