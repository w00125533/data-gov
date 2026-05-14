"""tests/agent/nodes/test_schema_lookup.py"""
from unittest.mock import patch
from backend.agent.nodes.schema_lookup import schema_lookup


FAKE_SCHEMA = {
    "dwd_session_qos": {
        "name": "dwd_session_qos",
        "layer": "dwd",
        "storage_type": "delta",
        "fields": [
            {"name": "rsrp", "type": "INT", "description": "RSRP", "expression": None},
        ],
    },
    "ods_ue_signal": {
        "name": "ods_ue_signal",
        "layer": "ods",
        "storage_type": "delta",
        "fields": [
            {"name": "rsrp", "type": "INT", "description": "RSRP raw", "expression": None},
        ],
    },
}


def test_resolve_schemas_from_target_and_source():
    """schemas_resolved contains schemas for both target_tables and source_tables."""
    with patch("backend.agent.nodes.schema_lookup.lookup_table_schema",
               return_value=FAKE_SCHEMA) as mock_lookup:
        state = {
            "target_tables": ["dwd_session_qos"],
            "source_tables": ["ods_ue_signal"],
        }
        result = schema_lookup(state)

    mock_lookup.assert_called_once()
    assert sorted(mock_lookup.call_args[0][0]) == ["dwd_session_qos", "ods_ue_signal"]
    assert result["schemas_resolved"] == FAKE_SCHEMA
    assert "sub_flow_active" not in result


def test_sub_flow_active_cleared():
    """When sub_flow_active is True in state, it is set to False in output."""
    with patch("backend.agent.nodes.schema_lookup.lookup_table_schema",
               return_value=FAKE_SCHEMA):
        state = {
            "target_tables": ["dwd_session_qos"],
            "source_tables": ["ods_ue_signal"],
            "sub_flow_active": True,
        }
        result = schema_lookup(state)

    assert result["sub_flow_active"] is False


def test_no_source_tables_still_fetches_target():
    """When source_tables is empty, only target_tables are resolved."""
    schema_subset = {"dwd_session_qos": FAKE_SCHEMA["dwd_session_qos"]}
    with patch("backend.agent.nodes.schema_lookup.lookup_table_schema",
               return_value=schema_subset):
        state = {"target_tables": ["dwd_session_qos"]}
        result = schema_lookup(state)

    assert "dwd_session_qos" in result["schemas_resolved"]
    assert "sub_flow_active" not in result
