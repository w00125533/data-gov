"""Tests for forward_etl node."""
from __future__ import annotations
import json
from unittest.mock import MagicMock

import pytest

from backend.agent.nodes.forward_etl import forward_etl
from backend.agent.tools import SearchResult


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def searcher():
    """Mock searcher that returns a known table for known keywords."""
    _searcher = MagicMock()

    def _search(keyword, k=10, use_rerank=False):
        lookup = {
            "user": [{"table": "dim_user", "score": 0.95, "doc": MagicMock()}],
            "subscriber": [{"table": "dim_user", "score": 0.92, "doc": MagicMock()}],
            "usage": [{"table": "dwd_usage_h", "score": 0.88, "doc": MagicMock()}],
            "traffic": [{"table": "dwd_usage_h", "score": 0.85, "doc": MagicMock()}],
            "unknown_entity": [],
        }
        return lookup.get(keyword, [])

    _searcher.search.side_effect = _search
    return _searcher


@pytest.fixture
def llm_client():
    """Mock LLM client that returns a valid JSON response."""
    _client = MagicMock()
    _client.invoke.return_value = MagicMock(
        content=json.dumps(
            {
                "target_entities": ["user", "usage"],
                "source_hints": ["subscriber", "traffic"],
                "code_type_hint": "spark_sql",
            }
        )
    )
    return _client


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_forward_etl_happy_path(llm_client, searcher):
    """Basic flow: LLM returns valid JSON, searcher resolves tables."""
    state = {"messages": [{"role": "user", "content": "aggregate daily usage per user"}]}
    result = forward_etl(state, llm_client=llm_client, searcher=searcher)

    assert result["target_tables"] == ["dim_user", "dwd_usage_h"]
    assert result["source_tables"] == ["dim_user", "dwd_usage_h"]
    assert result["code_type"] == "spark_sql"


def test_forward_etl_code_type_auto_becomes_none(llm_client, searcher):
    """When code_type_hint is 'auto' the node returns None."""
    llm_client.invoke.return_value = MagicMock(
        content=json.dumps(
            {
                "target_entities": ["usage"],
                "source_hints": [],
                "code_type_hint": "auto",
            }
        )
    )
    state = {"messages": [{"role": "user", "content": "run query"}]}
    result = forward_etl(state, llm_client=llm_client, searcher=searcher)

    assert result["target_tables"] == ["dwd_usage_h"]
    assert result["code_type"] is None


def test_forward_etl_empty_message(searcher):
    """If messages list has no content, LLM returns empty entities."""
    empty_client = MagicMock()
    empty_client.invoke.return_value = MagicMock(
        content=json.dumps(
            {"target_entities": [], "source_hints": [], "code_type_hint": "auto"}
        )
    )
    state = {"messages": [{"role": "user", "content": ""}]}
    result = forward_etl(state, llm_client=empty_client, searcher=searcher)

    assert result["target_tables"] == []
    assert result["source_tables"] == []
    assert result["code_type"] is None


def test_forward_etl_no_messages_key(searcher):
    """Absent 'messages' key should not crash — LLM returns empty entities."""
    empty_client = MagicMock()
    empty_client.invoke.return_value = MagicMock(
        content=json.dumps(
            {"target_entities": [], "source_hints": [], "code_type_hint": "auto"}
        )
    )
    state = {}
    result = forward_etl(state, llm_client=empty_client, searcher=searcher)

    assert result["target_tables"] == []
    assert result["source_tables"] == []
    assert result["code_type"] is None


def test_forward_etl_llm_returns_invalid_json(searcher):
    """If LLM returns non-JSON, the node returns empty defaults."""
    bad_client = MagicMock()
    bad_client.invoke.return_value = MagicMock(content="not json at all")

    state = {"messages": [{"role": "user", "content": "do something"}]}
    result = forward_etl(state, llm_client=bad_client, searcher=searcher)

    assert result["target_tables"] == []
    assert result["source_tables"] == []
    assert result["code_type"] is None


def test_forward_etl_unresolvable_keywords(llm_client, searcher):
    """Entities that do not match any table produce empty resolved lists."""
    llm_client.invoke.return_value = MagicMock(
        content=json.dumps(
            {
                "target_entities": ["unknown_entity"],
                "source_hints": ["unknown_entity"],
                "code_type_hint": "flink_sql",
            }
        )
    )
    state = {"messages": [{"role": "user", "content": "query foo"}]}
    result = forward_etl(state, llm_client=llm_client, searcher=searcher)

    assert result["target_tables"] == []
    assert result["source_tables"] == []
    assert result["code_type"] == "flink_sql"
