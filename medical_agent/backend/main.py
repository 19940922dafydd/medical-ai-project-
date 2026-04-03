import time
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from typing import List, Dict
from backend.schema.schemas import ChatRequest, FeedbackRequest
from fastapi.middleware.cors import CORSMiddleware

from backend.exceptions import MedicalAgentError, LLMServiceError, RetrievalError, DatabaseError
from backend.metrics import metrics

app = FastAPI(title="Medical Q&A Agent API", version="1.1.0")

# Configure logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Enable CORS for the Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全局异常处理器 ────────────────────────────────────────────────────────────
@app.exception_handler(MedicalAgentError)
async def medical_agent_error_handler(request: Request, exc: MedicalAgentError):
    metrics.record_error(type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "error": exc.message,
            "detail": exc.detail,
            "type": type(exc).__name__,
        }
    )

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    metrics.record_error("unhandled_exception")
    logging.error(f"Unhandled exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "服务器内部错误",
            "detail": str(exc),
            "type": "InternalServerError",
        }
    )

# ── 请求计时中间件 ────────────────────────────────────────────────────────────
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    success = response.status_code < 400
    metrics.record_request(request.url.path, duration_ms, success)
    response.headers["X-Response-Time-Ms"] = str(round(duration_ms, 1))
    return response

# 数据模型已迁移至 backend/schema/schemas.py

# ── 增强版健康检查 ────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    """组件级健康检查：分别检测 MySQL、ChromaDB、Neo4j 连通性"""
    components = {}
    overall = "healthy"
    
    # 1. MySQL
    try:
        from backend.repository import mysql_mgr as db_mgr
        conn = db_mgr.get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        conn.close()
        components["mysql"] = {"status": "ok"}
    except Exception as e:
        components["mysql"] = {"status": "error", "detail": str(e)[:100]}
        overall = "degraded"
    
    # 2. ChromaDB
    try:
        import chromadb
        from config.settings import CHROMA_DB_PATH
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        count = client.count_collections()
        components["chromadb"] = {"status": "ok", "collections": count}
    except Exception as e:
        components["chromadb"] = {"status": "error", "detail": str(e)[:100]}
        overall = "degraded"
    
    # 3. Neo4j
    try:
        from data.graph_store.neo4j_processor import GraphStoreProcessor
        g = GraphStoreProcessor()
        with g.driver.session() as session:
            session.run("RETURN 1")
        components["neo4j"] = {"status": "ok"}
    except Exception as e:
        components["neo4j"] = {"status": "error", "detail": str(e)[:100]}
        overall = "degraded"
    
    # 4. LLM (Ollama)
    try:
        from langchain_ollama import OllamaLLM
        from config.settings import LLM_MODEL
        test_llm = OllamaLLM(model=LLM_MODEL)
        test_llm.invoke("你好")
        components["llm"] = {"status": "ok", "model": LLM_MODEL}
    except Exception as e:
        components["llm"] = {"status": "error", "detail": str(e)[:100]}
        overall = "degraded"
    
    return {
        "status": overall,
        "message": "Medical Q&A Agent API is running.",
        "components": components,
    }

# ── 指标端点 ──────────────────────────────────────────────────────────────────
@app.get("/metrics")
def get_metrics():
    """返回应用运行指标快照"""
    return metrics.get_snapshot()

# ── Chat 端点 ─────────────────────────────────────────────────────────────────
@app.post("/chat")
def chat(request: ChatRequest):
    try:
        from backend.agent import medical_agent_app
        initial_state = {
            "session_id": request.session_id,
            "original_query": request.query,
            "rewritten_query": "",
            "history": request.history,
            "intent": "",
            "expert_advice": [],
            "retrieved_docs": [],
            "doc_sources": [],
            "graph_context": [],
            "final_answer": "",
            "error_or_warning": ""
        }
        result = medical_agent_app.invoke(initial_state)
        
        return {
            "reply": result.get('final_answer', '系统异常，无返回结果。'),
            "session_id": request.session_id,
            "intent": result.get('intent', 'unknown'),
            "warning": result.get('error_or_warning', ''),
            "log_id": result.get('log_id', -1)
        }
    except MedicalAgentError as e:
        metrics.record_error(type(e).__name__)
        return {"reply": f"服务异常: {e.message}", "warning": "异常"}
    except Exception as e:
        metrics.record_error("chat_unhandled")
        logging.error(f"Chat endpoint error: {e}")
        return {"reply": f"服务器内部错误: {e}", "warning": "异常"}

# ── Streaming 端点 ────────────────────────────────────────────────────────────
from fastapi.responses import StreamingResponse
import json

@app.post("/stream")
def stream_chat(request: ChatRequest):
    """
    Streaming endpoint using LangGraph's stream capability
    """
    from backend.agent import medical_agent_app
    initial_state = {
        "session_id": request.session_id,
        "original_query": request.query,
        "rewritten_query": "",
        "history": request.history,
        "intent": "",
        "patient_profile": {},
        "expert_advice": [],
        "retrieved_docs": [],
        "doc_sources": [],
        "graph_context": [],
        "final_answer": "",
        "error_or_warning": ""
    }
    
    def event_generator():
        try:
            for output in medical_agent_app.stream(initial_state):
                for node_name, state_update in output.items():
                    # 1. 路由与画像提取提示
                    if node_name in ["router", "profile_extractor"]:
                        yield f"data: {json.dumps({'node': node_name, 'intent': state_update.get('intent'), 'profile': state_update.get('patient_profile')}, ensure_ascii=False)}\n\n"
                    
                    # 2. 专家检索调试信息
                    if node_name in ["admin_expert", "pharma_expert", "diag_expert"]:
                        yield f"data: {json.dumps({'node': 'debug', 'expert': node_name, 'docs': state_update.get('retrieved_docs', []), 'graph': state_update.get('graph_context', [])}, ensure_ascii=False)}\n\n"
                        
                    # 3. 最终汇总生成
                    if node_name == "supervisor":
                        payload = {
                            'node': 'generator', 
                            'message': state_update.get('final_answer', '生成中...')
                        }
                        if 'log_id' in state_update:
                            payload['log_id'] = state_update['log_id']
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    
        except Exception as e:
            metrics.record_error("stream_error")
            logging.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'node': 'error', 'message': f'流式处理出错: {str(e)}'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Feedback 端点 ─────────────────────────────────────────────────────────────
@app.post("/feedback")
def submit_feedback(request: FeedbackRequest):
    """
    接收用户对 AI 回答的满意度反馈。
    - 正向反馈：仅更新 interaction_logs.user_feedback = 'positive'
    - 负向反馈：同时更新日志并将完整原因写入 bad_cases 表，进入数据飞轮
    """
    try:
        from backend.repository import mysql_mgr as db_mgr

        # 无论正负，先更新 interaction_log 中的反馈标记
        db_mgr.update_interaction_feedback(request.log_id, request.feedback_type)
        logging.info(f"Feedback received: log_id={request.log_id}, type={request.feedback_type}")

        if request.feedback_type == "negative":
            # 将原因拼接为完整的反馈内容写入 Bad Case 表
            full_feedback = request.reason
            if request.detail:
                full_feedback += f"；补充说明：{request.detail}"

            db_mgr.add_bad_case(
                query=request.query,
                response=request.ai_response,
                feedback=full_feedback,
                log_id=request.log_id,
            )
            logging.info(f"Bad case created for log_id={request.log_id}, reason={request.reason}")

        return {"success": True, "message": "反馈已记录，感谢您的贡献！"}

    except Exception as e:
        logging.error(f"Feedback submission error: {e}")
        metrics.record_error("feedback_error")
        return {"success": False, "message": f"反馈记录失败: {str(e)[:100]}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
