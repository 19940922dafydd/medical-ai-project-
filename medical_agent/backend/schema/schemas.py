from pydantic import BaseModel
from typing import List, Dict, Optional

class ChatRequest(BaseModel):
    query: str
    history: List[Dict[str, str]] = []
    session_id: str = "default_session"
    user_id: str = "user_1"


class FeedbackRequest(BaseModel):
    """用户对单条 AI 回答的反馈载体"""
    log_id: int
    feedback_type: str          # "positive" | "negative"
    reason: str = ""            # 负向反馈原因（单选项文本）
    detail: str = ""            # 补充说明（可选自由文本）
    query: str = ""             # 用户原始提问（用于 Bad Case 上报）
    ai_response: str = ""       # AI 原始回答（用于 Bad Case 上报）


class HealthResponse(BaseModel):
    status: str
    message: str
    components: Dict[str, dict]
