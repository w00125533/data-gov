"""Tests for reverse_synth node."""
from __future__ import annotations
import json
from unittest.mock import MagicMock

import pytest

from backend.agent.nodes.reverse_synth import reverse_synth
from backend.agent.tools import SearchResult


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def searcher():
    _searcher = MagicMock()

    def _search(keyword, k=10, use_rerank=False):
        lookup = {
            "kpi_summary": [{"table": "ads_kpi_summary", "score": 0.93, "doc": MagicMock()}],
            "coverage": [{"table": "ads_coverage_d", "score": 0.90, "doc": MagicMock()}],
            "no_match": [],
        }
        return lookup.get(keyword, [])

    _searcher.search.side_effect = _search
    return _searcher


@pytest.fixture
def llm_client():
    _client = MagicMock()
    _client.invoke.return_value = MagicMock(
        content=json.dumps(
            {
                "eval_target": "kpi_summary",
                "row_count_hint": 50,
                "buckets_hint": [
                    {"label": "优", "range": [80, 100]},
                    {"label": "差", "range": [0, 60]},
                ],
            }
        )
    )
    return _client


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_reverse_synth_happy_path(llm_client, searcher):
    """Basic flow: eval_target resolved, hints carried through."""
    state = {"messages": [{"role": "user", "content": "generate data for kpi summary"}]}
    result = reverse_synth(state, llm_client=llm_client, searcher=searcher)

    assert result["target_tables"] == ["ads_kpi_summary"]
    assert result["source_tables"] == []
    assert result["row_count_hint"] == 50
    assert result["buckets_hint"] == [
        {"label": "优", "range": [80, 100]},
        {"label": "差", "range": [0, 60]},
    ]


def test_reverse_synth_empty_eval_target(searcher):
    """Empty eval_target produces empty target_tables with defaults."""
    client = MagicMock()
    client.invoke.return_value = MagicMock(
        content=json.dumps({"eval_target": "", "row_count_hint": 5, "buckets_hint": []})
    )
    state = {"messages": [{"role": "user", "content": "generate data"}]}
    result = reverse_synth(state, llm_client=client, searcher=searcher)

    assert result["target_tables"] == []
    assert result["source_tables"] == []
    assert result["row_count_hint"] == 5
    assert result["buckets_hint"] == []


def test_reverse_synth_llm_returns_invalid_json(searcher):
    """Non-JSON LLM response falls back to empty parsed dict, all defaults."""
    bad_client = MagicMock()
    bad_client.invoke.return_value = MagicMock(content="broken")

    state = {"messages": [{"role": "user", "content": "hello"}]}
    result = reverse_synth(state, llm_client=bad_client, searcher=searcher)

    assert result["target_tables"] == []
    assert result["source_tables"] == []
    assert result["row_count_hint"] == 10  # default
    assert result["buckets_hint"] == []  # default


def test_reverse_synth_unresolvable_eval_target(llm_client, searcher):
    """eval_target that doesn't match any table => empty target_tables."""
    llm_client.invoke.return_value = MagicMock(
        content=json.dumps(
            {
                "eval_target": "no_match",
                "row_count_hint": 20,
                "buckets_hint": [],
            }
        )
    )
    state = {"messages": [{"role": "user", "content": "gen data for no_match"}]}
    result = reverse_synth(state, llm_client=llm_client, searcher=searcher)

    assert result["target_tables"] == []
    assert result["source_tables"] == []
    assert result["row_count_hint"] == 20
