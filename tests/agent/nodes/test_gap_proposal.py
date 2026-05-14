"""tests/agent/nodes/test_gap_proposal.py"""
from __future__ import annotations
from unittest.mock import MagicMock, patch

from backend.agent.nodes.gap_proposal import gap_proposal


class TestGapProposal:
    """gap_proposal 节点测试 (spec §4.1)。"""

    def test_builds_schema_diff_and_sub_flow_state(self):
        gaps = [
            {
                "type": "missing_table",
                "keyword": "退服率",
                "suggestion": "建议新建表覆盖 '退服率'",
            }
        ]
        state = {
            "gaps": gaps,
            "messages": [{"role": "user", "content": "我想分析基站退服率"}],
        }
        draft = [
            {
                "operation": "ADD_TABLE",
                "table": "rno_drop_rate",
                "layer": "DWD",
                "storage_type": "HIVE",
                "fields": [{"name": "rate", "data_type": "DOUBLE"}],
            }
        ]
        llm = MagicMock()
        llm.invoke.return_value.content = __import__("json").dumps(draft)

        result = gap_proposal(state, llm_client=llm)

        assert result["schema_diff"] == draft
        assert result["sub_flow_active"] is True
        assert result["sub_flow_return_point"] == "code_generate"
        payload = result["presenter_payload"]
        assert payload["type"] == "gap_proposal_card"
        assert payload["draft"] == draft
        assert payload["gaps"] == gaps

    def test_handles_invalid_json(self):
        state = {
            "gaps": [],
            "messages": [{"role": "user", "content": "测试"}],
        }
        llm = MagicMock()
        llm.invoke.return_value.content = "not valid json"

        result = gap_proposal(state, llm_client=llm)

        assert result["schema_diff"] == []
        assert result["sub_flow_active"] is True
        assert result["sub_flow_return_point"] == "code_generate"
        assert result["presenter_payload"]["draft"] == []

    def test_handles_non_list_draft(self):
        state = {
            "gaps": [],
            "messages": [{"role": "user", "content": "测试"}],
        }
        llm = MagicMock()
        llm.invoke.return_value.content = '{"not": "a list"}'

        result = gap_proposal(state, llm_client=llm)

        assert result["schema_diff"] == []
        assert result["sub_flow_active"] is True

    def test_llm_failure_returns_empty_diff(self):
        state = {
            "gaps": [],
            "messages": [{"role": "user", "content": "测试"}],
        }
        llm = MagicMock()
        llm.invoke.side_effect = ValueError("LLM down")

        result = gap_proposal(state, llm_client=llm)

        assert result["schema_diff"] == []
        assert result["sub_flow_active"] is True
        assert result["sub_flow_return_point"] == "code_generate"

    def test_missing_gaps_in_state(self):
        state = {
            "messages": [{"role": "user", "content": "测试"}],
        }
        llm = MagicMock()
        llm.invoke.return_value.content = "[]"

        result = gap_proposal(state, llm_client=llm)

        assert result["schema_diff"] == []
        assert result["sub_flow_active"] is True
