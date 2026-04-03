"""
Agent 核心逻辑单元测试
"""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRouteIntent:
    """测试意图识别路由"""

    @patch("backend.agent.llm")
    def test_normal_qa_intent(self, mock_llm, sample_state):
        """普通科普问题应识别为 QA"""
        mock_llm.invoke.return_value = "2"
        from backend.agent import route_intent
        result = route_intent(sample_state)
        assert result["intent"] == "QA"

    @patch("backend.agent.llm")
    def test_violation_intent(self, mock_llm, violation_query_state):
        """违规诊断请求应识别为 violation"""
        mock_llm.invoke.return_value = "1"
        from backend.agent import route_intent
        result = route_intent(violation_query_state)
        assert result["intent"] == "violation"
        assert "违规" in result["error_or_warning"]

    @patch("backend.agent.llm")
    def test_llm_failure_fallback(self, mock_llm, sample_state):
        """LLM 服务异常时应降级为 violation (安全兜底)"""
        mock_llm.invoke.side_effect = ConnectionError("LLM down")
        from backend.agent import route_intent
        result = route_intent(sample_state)
        assert result["intent"] == "violation"
        assert "不可用" in result["error_or_warning"]


class TestRewriteQuery:
    """测试查询改写"""

    @patch("backend.agent._rules_cache")
    def test_rewrite_with_rules(self, mock_cache, sample_state, mock_rules):
        """有匹配规则时应正确替换口语词"""
        mock_cache.get.return_value = mock_rules
        with patch("backend.agent.metrics"):
            from backend.agent import rewrite_query
            result = rewrite_query(sample_state)
            assert "假性宫缩" in result["rewritten_query"]
            assert len(result["applied_rules"]) > 0

    @patch("backend.agent._rules_cache")
    def test_rewrite_no_match(self, mock_cache, sample_state, mock_rules):
        """无匹配规则时原始查询不变"""
        sample_state["original_query"] = "什么是糖尿病"
        mock_cache.get.return_value = mock_rules
        with patch("backend.agent.metrics"):
            from backend.agent import rewrite_query
            result = rewrite_query(sample_state)
            assert result["rewritten_query"] == "什么是糖尿病"
            assert len(result["applied_rules"]) == 0


class TestTTLCache:
    """测试 TTL 缓存"""

    def test_cache_set_and_get(self):
        from backend.agent import TTLCache
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_expired(self):
        from backend.agent import TTLCache
        import time
        cache = TTLCache(ttl_seconds=1)
        cache.set("key2", "value2")
        time.sleep(1.1)
        assert cache.get("key2") is None

    def test_cache_invalidate(self):
        from backend.agent import TTLCache
        cache = TTLCache(ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.invalidate()
        assert cache.get("a") is None
        assert cache.get("b") is None


class TestMetricsCollector:
    """测试指标收集器"""

    def test_record_request(self):
        from backend.metrics import MetricsCollector
        m = MetricsCollector.__new__(MetricsCollector)
        m._initialized = False
        m.__init__()
        m.record_request("/test", 100.5, True)
        snap = m.get_snapshot()
        assert snap["total_requests"] == 1
        assert snap["response_time"]["avg_ms"] == 100.5

    def test_record_error(self):
        from backend.metrics import MetricsCollector
        m = MetricsCollector.__new__(MetricsCollector)
        m._initialized = False
        m.__init__()
        m.record_error("test_error")
        m.record_error("test_error")
        snap = m.get_snapshot()
        assert snap["total_errors"] == 2
        assert snap["errors_by_type"]["test_error"] == 2

    def test_record_node_time(self):
        from backend.metrics import MetricsCollector
        m = MetricsCollector.__new__(MetricsCollector)
        m._initialized = False
        m.__init__()
        m.record_node_time("router", 50.0)
        m.record_node_time("router", 150.0)
        snap = m.get_snapshot()
        assert snap["node_avg_ms"]["router"] == 100.0


class TestExceptions:
    """测试自定义异常"""

    def test_base_exception(self):
        from backend.exceptions import MedicalAgentError
        err = MedicalAgentError("test", "detail info")
        assert str(err) == "test"
        assert err.detail == "detail info"

    def test_llm_service_error(self):
        from backend.exceptions import LLMServiceError
        err = LLMServiceError()
        assert "不可用" in err.message

    def test_retrieval_error(self):
        from backend.exceptions import RetrievalError
        err = RetrievalError()
        assert "检索" in err.message

    def test_database_error(self):
        from backend.exceptions import DatabaseError
        err = DatabaseError()
        assert "数据库" in err.message
