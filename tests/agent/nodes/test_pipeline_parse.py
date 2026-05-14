"""tests/agent/nodes/test_pipeline_parse.py"""
from unittest.mock import MagicMock, patch
from backend.agent.nodes.pipeline_parse import pipeline_parse


def test_single_level_upstream_traversal():
    """
    root = dwd_session_qos, lookup_lineage returns one upstream (ods_ue_signal).
    Verify source_tables and pipeline_chain are correct.
    """
    mock_edges = [
        MagicMock(from_table="ods_ue_signal", from_field="rsrp"),
        MagicMock(from_table="ods_ue_signal", from_field="snr"),
    ]

    def fake_lineage(table, direction="up", depth=1):
        if table == "dwd_session_qos":
            return mock_edges
        return []

    with patch("backend.agent.nodes.pipeline_parse.lookup_lineage",
               side_effect=fake_lineage) as mock_lookup:
        state = {"target_tables": ["dwd_session_qos"]}
        result = pipeline_parse(state)

    assert mock_lookup.call_count == 2
    mock_lookup.assert_any_call("dwd_session_qos", direction="up", depth=1)
    mock_lookup.assert_any_call("ods_ue_signal", direction="up", depth=1)
    assert result["source_tables"] == ["ods_ue_signal"]
    assert len(result["pipeline_chain"]) == 2

    # Chain is reversed: furthest upstream first
    assert result["pipeline_chain"][0]["table"] == "ods_ue_signal"
    assert result["pipeline_chain"][0]["fields"] == []
    assert result["pipeline_chain"][0]["upstream"] == []

    assert result["pipeline_chain"][1]["table"] == "dwd_session_qos"
    assert result["pipeline_chain"][1]["fields"] == ["rsrp", "snr"]
    assert result["pipeline_chain"][1]["upstream"] == ["ods_ue_signal"]


def test_multi_level_upstream_traversal():
    """
    root = dws_cell_hourly -> dwd_session_qos -> ods_ue_signal.
    Each table has exactly one upstream reference.
    Verify the full chain is traversed.
    """
    def fake_lineage(table, direction="down", depth=5):
        edges = {
            "dws_cell_hourly": [MagicMock(from_table="dwd_session_qos", from_field="avg_rsrp")],
            "dwd_session_qos": [MagicMock(from_table="ods_ue_signal", from_field="rsrp")],
            "ods_ue_signal": [],
        }
        return edges.get(table, [])

    with patch("backend.agent.nodes.pipeline_parse.lookup_lineage",
               side_effect=fake_lineage):
        state = {"target_tables": ["dws_cell_hourly"]}
        result = pipeline_parse(state)

    assert sorted(result["source_tables"]) == ["dwd_session_qos", "ods_ue_signal"]
    assert len(result["pipeline_chain"]) == 3

    # Chain is reversed: furthest upstream first
    assert result["pipeline_chain"][0]["table"] == "ods_ue_signal"
    assert result["pipeline_chain"][0]["upstream"] == []

    assert result["pipeline_chain"][1]["table"] == "dwd_session_qos"
    assert result["pipeline_chain"][1]["upstream"] == ["ods_ue_signal"]

    assert result["pipeline_chain"][2]["table"] == "dws_cell_hourly"
    assert result["pipeline_chain"][2]["upstream"] == ["dwd_session_qos"]


def test_empty_target_tables_returns_empty():
    """When target_tables is empty, return empty lists."""
    result = pipeline_parse({"target_tables": []})
    assert result == {"source_tables": [], "pipeline_chain": []}


def test_no_upstream_returns_root_only():
    """A root with no lineage edges produces chain with just the root."""
    with patch("backend.agent.nodes.pipeline_parse.lookup_lineage",
               return_value=[]):
        state = {"target_tables": ["dwd_session_qos"]}
        result = pipeline_parse(state)

    assert result["source_tables"] == []
    assert len(result["pipeline_chain"]) == 1
    assert result["pipeline_chain"][0]["table"] == "dwd_session_qos"
