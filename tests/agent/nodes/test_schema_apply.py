"""tests/agent/nodes/test_schema_apply.py"""
from unittest.mock import patch, ANY
from backend.agent.nodes.schema_apply import schema_apply


ADD_TABLE_OP = {
    "operation": "ADD_TABLE",
    "table": "dwd_session_qos",
    "layer": "DWD",
    "storage_type": "delta",
    "fields": [],
}

ADD_FIELD_OP = {
    "operation": "ADD_FIELD",
    "table": "dwd_session_qos",
    "field": "rsrp",
    "data_type": "INT",
}

DELETE_FIELD_OP = {
    "operation": "DELETE_FIELD",
    "table": "dwd_session_qos",
    "field": "old_col",
}


def test_schema_apply_dispatches_add_table():
    """ADD_TABLE in schema_diff dispatches to add_table and returns applied_changes."""
    with (
        patch("backend.agent.nodes.schema_apply.tools.add_table") as mock_add_table,
        patch("backend.agent.nodes.schema_apply._record_change") as mock_record,
        patch("backend.agent.nodes.schema_apply._update_change_commit") as mock_update,
        patch("backend.agent.nodes.schema_apply.yaml_sync.sync_yaml"),
        patch("backend.agent.nodes.schema_apply.yaml_sync.git_commit") as mock_git,
    ):
        mock_record.return_value = {
            "change_id": "chg_abc123",
            "operation": "ADD_TABLE",
            "table": "dwd_session_qos",
            "field": None,
            "commit_hash": None,
        }
        mock_git.return_value = "abc123def456"

        state = {"schema_diff": [ADD_TABLE_OP]}
        result = schema_apply(state)

    mock_add_table.assert_called_once_with(ADD_TABLE_OP)
    mock_update.assert_called_once_with("chg_abc123", "abc123def456")
    assert len(result["applied_changes"]) == 1
    ch = result["applied_changes"][0]
    assert ch["operation"] == "ADD_TABLE"
    assert ch["table"] == "dwd_session_qos"
    assert ch["commit_hash"] == "abc123def456"


def test_schema_apply_collects_affected_tables():
    """sync_yaml is called with deduplicated sorted table names from all ops."""
    with (
        patch("backend.agent.nodes.schema_apply.tools.add_table"),
        patch("backend.agent.nodes.schema_apply.tools.add_field"),
        patch("backend.agent.nodes.schema_apply.tools.remove_field"),
        patch("backend.agent.nodes.schema_apply._record_change") as mock_record,
        patch("backend.agent.nodes.schema_apply.yaml_sync.sync_yaml") as mock_sync,
        patch("backend.agent.nodes.schema_apply.yaml_sync.git_commit") as mock_git,
    ):
        mock_record.return_value = {
            "change_id": "chg_xyz",
            "operation": "ADD_TABLE",
            "table": "whatever",
            "field": None,
            "commit_hash": None,
        }
        mock_git.return_value = ""

        state = {
            "schema_diff": [
                {"operation": "ADD_TABLE", "table": "ods_signal"},
                {"operation": "DELETE_FIELD", "table": "dwd_session_qos", "field": "old_col"},
                {"operation": "ADD_FIELD", "table": "ods_signal"},
            ]
        }
        schema_apply(state)

    # Sorted, deduplicated table names
    mock_sync.assert_called_once_with(["dwd_session_qos", "ods_signal"])


def test_schema_apply_returns_empty_when_diff_empty():
    """Empty schema_diff returns empty applied_changes and no side effects."""
    with (
        patch("backend.agent.nodes.schema_apply.tools.add_table") as mock_add_table,
        patch("backend.agent.nodes.schema_apply.yaml_sync.sync_yaml") as mock_sync,
        patch("backend.agent.nodes.schema_apply.yaml_sync.git_commit") as mock_git,
    ):
        result = schema_apply({"schema_diff": []})

    assert result == {"applied_changes": []}
    mock_add_table.assert_not_called()
    mock_sync.assert_not_called()
    mock_git.assert_not_called()
