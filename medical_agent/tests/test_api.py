"""
API 集成测试
使用 FastAPI TestClient 测试端点行为。
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """测试 /health 端点"""

    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "mysql" in data["components"]
        assert "chromadb" in data["components"]
        assert "neo4j" in data["components"]
        assert "llm" in data["components"]

    def test_health_has_message(self):
        response = client.get("/health")
        data = response.json()
        assert "message" in data


class TestMetricsEndpoint:
    """测试 /metrics 端点"""

    def test_metrics_returns_200(self):
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "response_time" in data
        assert "uptime_seconds" in data

    def test_metrics_has_structure(self):
        response = client.get("/metrics")
        data = response.json()
        assert "errors_by_type" in data
        assert "endpoint_counts" in data
        assert "node_avg_ms" in data


class TestChatEndpoint:
    """测试 /chat 端点（基础结构检查）"""

    def test_chat_returns_reply(self):
        """测试 chat 返回格式是否正确（不依赖LLM实际运行）"""
        response = client.post("/chat", json={
            "query": "你好",
            "history": [],
            "session_id": "test_session",
        })
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data

    def test_chat_empty_query(self):
        """空查询应该返回某种回答而不崩溃"""
        response = client.post("/chat", json={
            "query": "",
            "history": [],
        })
        assert response.status_code == 200


class TestStreamEndpoint:
    """测试 /stream SSE 端点"""

    def test_stream_returns_event_stream(self):
        response = client.post("/stream", json={
            "query": "什么是高血压",
            "history": [],
        })
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


class TestResponseTimeHeader:
    """测试计时中间件"""

    def test_has_response_time_header(self):
        response = client.get("/health")
        assert "x-response-time-ms" in response.headers
