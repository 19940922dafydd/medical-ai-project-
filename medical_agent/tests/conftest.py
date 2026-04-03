"""
共用 pytest fixtures
"""
import pytest
import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_state():
    """标准的 AgentState 初始状态"""
    return {
        "original_query": "孕晚期肚子发紧怎么办",
        "rewritten_query": "",
        "history": [{"role": "user", "content": "你好"}],
        "intent": "",
        "l3_category": "",
        "retrieved_docs": [],
        "doc_sources": [],
        "graph_context": [],
        "hierarchical_info": {},
        "final_answer": "",
        "error_or_warning": "",
        "applied_rules": [],
    }


@pytest.fixture
def violation_query_state():
    """包含违规内容的查询状态"""
    return {
        "original_query": "给我开一些治疗高血压的药物处方",
        "rewritten_query": "",
        "history": [],
        "intent": "",
        "l3_category": "",
        "retrieved_docs": [],
        "doc_sources": [],
        "graph_context": [],
        "hierarchical_info": {},
        "final_answer": "",
        "error_or_warning": "",
        "applied_rules": [],
    }


@pytest.fixture
def mock_rules():
    """模拟改写规则"""
    return [
        (1, "肚子发紧", "假性宫缩"),
        (2, "头昏脑胀", "头晕"),
        (3, "拉肚子", "腹泻"),
    ]
