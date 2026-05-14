"""tests/agent/nodes/test_schema_validate.py"""
from __future__ import annotations
from unittest.mock import patch

from backend.agent.nodes.schema_validate import schema_validate


class TestSchemaValidate:
    """schema_validate 节点测试 (spec §4.1)。"""

    def test_schema_validate_passes_clean_add(self):
        """合法的 ADD_FIELD 通过校验。"""
        diff = [
            {
                "operation": "ADD_FIELD",
                "table": "dwd_session_qos",
                "field": "sinr",
                "data_type": "DOUBLE",
            }
        ]
        expected = {"errors": [], "warnings": [], "passed": True}

        with patch("backend.agent.nodes.schema_validate.validate_change",
                   return_value=expected) as mock_validate:
            result = schema_validate({"schema_diff": diff})

        mock_validate.assert_called_once_with(diff)
        assert result["validation_result"] == expected

    def test_schema_validate_fails_break_downstream(self):
        """删除字段触发 BREAK_DOWNSTREAM 错误。"""
        diff = [
            {
                "operation": "DELETE_FIELD",
                "table": "dwd_session_qos",
                "field": "rsrp",
            }
        ]
        error = ("BREAK_DOWNSTREAM", diff[0], [("dwd_agg_qos", "avg_rsrp")])
        expected = {"errors": [error], "warnings": [], "passed": False}

        with patch("backend.agent.nodes.schema_validate.validate_change",
                   return_value=expected) as mock_validate:
            result = schema_validate({"schema_diff": diff})

        mock_validate.assert_called_once_with(diff)
        assert result["validation_result"] == expected
