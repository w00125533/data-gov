"""tests/agent/nodes/test_gap_check.py"""
from __future__ import annotations
from unittest.mock import MagicMock

from backend.agent.nodes.gap_check import gap_check, _extract_required_entities


class TestGapCheck:
    """gap_check 节点测试 (spec §4.1)。"""

    def test_detects_missing_table(self):
        state = {"messages": [{"role": "user", "content": "我想分析基站退服率"}]}
        llm = MagicMock()
        llm.invoke.return_value.content = (
            '[{"keyword": "退服率", "field_specified": false, "field": null}]'
        )
        searcher = MagicMock()
        searcher.search.return_value = [{"score": 0.35, "doc": None, "table": None}]

        result = gap_check(state, llm_client=llm, searcher=searcher, threshold=0.6)

        assert result["has_gaps"] is True
        assert len(result["gaps"]) == 1
        g = result["gaps"][0]
        assert g["type"] == "missing_table"
        assert g["keyword"] == "退服率"
        assert "新建表" in g["suggestion"]

    def test_no_gaps_when_high_score(self):
        state = {"messages": [{"role": "user", "content": "查一下基站覆盖"}]}
        llm = MagicMock()
        llm.invoke.return_value.content = (
            '[{"keyword": "基站覆盖", "field_specified": false, "field": null}]'
        )
        searcher = MagicMock()
        searcher.search.return_value = [{"score": 0.85, "doc": None, "table": "rno_cell"}]

        result = gap_check(state, llm_client=llm, searcher=searcher, threshold=0.6)

        assert result["has_gaps"] is False
        assert len(result["gaps"]) == 0

    def test_llm_failure_returns_no_gaps(self):
        state = {"messages": [{"role": "user", "content": "随便看看"}]}
        llm = MagicMock()
        llm.invoke.side_effect = ValueError("LLM unavailable")

        result = gap_check(state, llm_client=llm, searcher=MagicMock(), threshold=0.6)

        assert result["has_gaps"] is False
        assert len(result["gaps"]) == 0

    def test_gap_check_multiple_keywords(self):
        state = {"messages": [{"role": "user", "content": "查退服率和干扰"}]}
        llm = MagicMock()
        llm.invoke.return_value.content = (
            '[{"keyword": "退服率", "field_specified": false, "field": null},'
            '{"keyword": "干扰", "field_specified": false, "field": null}]'
        )
        searcher = MagicMock()
        searcher.search.side_effect = [
            [{"score": 0.35, "doc": None, "table": None}],
            [{"score": 0.88, "doc": None, "table": "rno_interference"}],
        ]

        result = gap_check(state, llm_client=llm, searcher=searcher, threshold=0.6)

        assert result["has_gaps"] is True
        assert len(result["gaps"]) == 1
        assert result["gaps"][0]["keyword"] == "退服率"

    def test_detects_missing_field_when_table_matches_but_field_is_absent(self):
        state = {"messages": [{"role": "user", "content": "from session QoS query SINR distribution"}]}
        llm = MagicMock()
        llm.invoke.return_value.content = (
            '[{"keyword": "SINR", "field_specified": true, '
            '"table": "dwd_session_qos", "field": "avg_sinr"}]'
        )
        doc = MagicMock()
        doc.type = "table"
        doc.metadata = {"table_name": "dwd_session_qos"}
        searcher = MagicMock()
        searcher.search.return_value = [{"score": 0.91, "doc": doc, "table": "dwd_session_qos"}]

        result = gap_check(state, llm_client=llm, searcher=searcher, threshold=0.6)

        assert result["has_gaps"] is True
        assert result["gaps"] == [
            {
                "type": "missing_field",
                "keyword": "SINR",
                "table": "dwd_session_qos",
                "field": "avg_sinr",
                "suggestion": "建议在表 dwd_session_qos 补回字段 avg_sinr",
            }
        ]

    def test_extract_required_entities_invalid_json(self):
        llm = MagicMock()
        llm.invoke.return_value.content = "not json"

        entities = _extract_required_entities("hello", llm)
        assert entities == []

    def test_extract_required_entities_empty_message(self):
        llm = MagicMock()
        llm.invoke.return_value.content = "[]"

        entities = _extract_required_entities("", llm)
        assert entities == []

    def test_empty_message_no_crash(self):
        state = {"messages": [{"role": "user", "content": ""}]}
        llm = MagicMock()
        llm.invoke.return_value.content = "[]"
        searcher = MagicMock()

        result = gap_check(state, llm_client=llm, searcher=searcher, threshold=0.6)

        assert result["has_gaps"] is False
        assert result["gaps"] == []
