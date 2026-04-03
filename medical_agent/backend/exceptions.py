"""
自定义异常体系 - 医疗问答 Agent
提供分层异常分类，便于精确捕获和降级处理。
"""


class MedicalAgentError(Exception):
    """所有医疗 Agent 异常的基类"""
    def __init__(self, message: str = "医疗问答系统发生未知错误", detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class LLMServiceError(MedicalAgentError):
    """大模型调用服务异常（超时、连接失败、返回格式异常等）"""
    def __init__(self, message: str = "大模型服务暂时不可用", detail: str = ""):
        super().__init__(message, detail)


class RetrievalError(MedicalAgentError):
    """知识检索异常（向量库、图谱查询异常）"""
    def __init__(self, message: str = "知识检索服务异常", detail: str = ""):
        super().__init__(message, detail)


class DatabaseError(MedicalAgentError):
    """数据库操作异常（MySQL/SQLite 连接、查询异常）"""
    def __init__(self, message: str = "数据库服务异常", detail: str = ""):
        super().__init__(message, detail)
