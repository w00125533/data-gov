"""Tests for the classifier node (spec §4.1)."""
from __future__ import annotations

import json

import pytest

from backend.agent.nodes.classifier import (
    VALID_INTENTS,
    _keyword_fallback,
    classifier,
)


class _FakeClient:
    """Stand-in for an LLM client.  Return whatever content is assigned."""

    def __init__(self) -> None:
        self.content = ""

    def invoke(self, prompt: str) -> object:  # noqa: ARG002
        return type("Resp", (), {"content": self.content})()


# ---------------------------------------------------------------------------
# _keyword_fallback unit tests
# ---------------------------------------------------------------------------


class TestKeywordFallback:
    def test_reverse_synth_keywords(self) -> None:
        for kw in ("造数据", "造点", "合成数据", "生成测试数据"):
            assert _keyword_fallback(kw) == "reverse_synth"

    def test_schema_evolve_keywords(self) -> None:
        for kw in ("加字段", "加个字段", "加一个", "新增字段", "删除字段", "改字段", "新建表", "演进"):
            assert _keyword_fallback(kw) == "schema_evolve"

    def test_default_forward_etl(self) -> None:
        assert _keyword_fallback("嗯") == "forward_etl"
        assert _keyword_fallback("") == "forward_etl"
        assert _keyword_fallback("hello world") == "forward_etl"


# ---------------------------------------------------------------------------
# classifier node tests
# ---------------------------------------------------------------------------


class TestClassifier:
    def test_returns_forward_etl_on_high_confidence(self) -> None:
        client = _FakeClient()
        client.content = json.dumps(
            {"intent": "forward_etl", "confidence": 0.95, "reason": "ok"}
        )
        state = {"messages": [{"role": "user", "content": "查一下昨天的流量"}]}
        result = classifier(state, llm_client=client)
        assert result["intent"] == "forward_etl"
        assert result["needs_clarification"] is False

    def test_sets_needs_clarification_when_low_confidence(self) -> None:
        client = _FakeClient()
        client.content = json.dumps(
            {"intent": "reverse_synth", "confidence": 0.4, "reason": "unclear"}
        )
        state = {"messages": [{"role": "user", "content": "不确定的需求"}]}
        result = classifier(state, llm_client=client)
        assert result["needs_clarification"] is True
        assert result["intent"] == "forward_etl"

    def test_low_confidence_preserves_existing_intent(self) -> None:
        """When state already has an intent, low-confidence keeps it."""
        client = _FakeClient()
        client.content = json.dumps(
            {"intent": "schema_evolve", "confidence": 0.3, "reason": "unclear"}
        )
        state = {
            "messages": [{"role": "user", "content": "改点东西"}],
            "intent": "schema_evolve",
        }
        result = classifier(state, llm_client=client)
        assert result["intent"] == "schema_evolve"
        assert result["needs_clarification"] is True

    def test_falls_back_to_keyword_reverse_synth(self) -> None:
        client = _FakeClient()
        client.content = "not json"
        state = {"messages": [{"role": "user", "content": "帮我造数据"}]}
        result = classifier(state, llm_client=client)
        assert result["intent"] == "reverse_synth"
        assert result["needs_clarification"] is False

    def test_falls_back_to_keyword_schema_evolve(self) -> None:
        client = _FakeClient()
        client.content = "not json"
        state = {"messages": [{"role": "user", "content": "给表加个字段"}]}
        result = classifier(state, llm_client=client)
        assert result["intent"] == "schema_evolve"
        assert result["needs_clarification"] is False

    def test_default_keyword_fallback_is_forward_etl(self) -> None:
        client = _FakeClient()
        client.content = "not json"
        state = {"messages": [{"role": "user", "content": "嗯"}]}
        result = classifier(state, llm_client=client)
        assert result["intent"] == "forward_etl"
        assert result["needs_clarification"] is False

    def test_valid_intents_constant(self) -> None:
        assert VALID_INTENTS == {"forward_etl", "reverse_synth", "schema_evolve"}
