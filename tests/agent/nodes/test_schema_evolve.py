"""tests/agent/nodes/test_schema_evolve.py"""
from __future__ import annotations
from unittest.mock import MagicMock, patch

from backend.agent.nodes.schema_evolve import schema_evolve


class TestSchemaEvolve:
    """schema_evolve 节点测试 (spec §4.1)。"""

    def test_schema_evolve_main_flow_uses_llm(self):
        """主流程调用 LLM 并返回有效的 schema_diff。"""
        state = {
            "messages": [{"role": "user", "content": "为 dwd_session_qos 增加字段 sinr"}],
            "target_tables": ["dwd_session_qos"],
        }
        draft = [
            {
                "operation": "ADD_FIELD",
                "table": "dwd_session_qos",
                "field": "sinr",
                "data_type": "DOUBLE",
                "expression": None,
                "upstream": [],
                "layer": "DWD",
                "storage_type": "HIVE",
            }
        ]
        llm = MagicMock()
        llm.invoke.return_value.content = __import__("json").dumps(draft)

        fake_schema = {"dwd_session_qos": {"name": "dwd_session_qos", "layer": "DWD", "storage_type": "HIVE", "fields": []}}
        with patch("backend.agent.nodes.schema_evolve.lookup_table_schema",
                   return_value=fake_schema) as mock_lookup:
            result = schema_evolve(state, llm_client=llm)

        mock_lookup.assert_called_once_with(["dwd_session_qos"])
        assert result["schema_diff"] == draft

    def test_schema_evolve_sub_flow_reuses_draft(self):
        """子流程 (sub_flow_active=True) 直接重用已有 schema_diff, 不调用 LLM。"""
        existing_diff = [
            {
                "operation": "ADD_TABLE",
                "table": "rno_drop_rate",
                "layer": "DWD",
                "storage_type": "HIVE",
                "fields": [{"name": "rate", "data_type": "DOUBLE"}],
            }
        ]
        state = {
            "sub_flow_active": True,
            "schema_diff": existing_diff,
        }
        llm = MagicMock()

        with patch("backend.agent.nodes.schema_evolve.lookup_table_schema") as mock_lookup:
            result = schema_evolve(state, llm_client=llm)

        mock_lookup.assert_not_called()
        llm.invoke.assert_not_called()
        assert result["schema_diff"] == existing_diff

    def test_schema_evolve_retries_once_on_invalid_json(self):
        """第一次 LLM 返回垃圾 JSON, 第二次返回有效 diff。"""
        state = {
            "messages": [{"role": "user", "content": "增加字段 sinr"}],
            "target_tables": ["dwd_session_qos"],
        }
        draft = [
            {
                "operation": "ADD_FIELD",
                "table": "dwd_session_qos",
                "field": "sinr",
                "data_type": "DOUBLE",
                "expression": None,
                "upstream": [],
                "layer": "DWD",
                "storage_type": "HIVE",
            }
        ]
        llm = MagicMock()
        llm.invoke.side_effect = [
            type("Resp", (), {"content": "not valid json"})(),
            type("Resp", (), {"content": __import__("json").dumps(draft)})(),
        ]

        fake_schema = {"dwd_session_qos": {"name": "dwd_session_qos", "layer": "DWD", "storage_type": "HIVE", "fields": []}}
        with patch("backend.agent.nodes.schema_evolve.lookup_table_schema",
                   return_value=fake_schema):
            result = schema_evolve(state, llm_client=llm)

        assert result["schema_diff"] == draft
