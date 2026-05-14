"""tests/agent/test_graph_e2e.py - 三条主路径打通 (mock LLM + sandbox)。"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.agent.graph import build_graph
from backend.agent.sandbox_stub import DryRunResult


def _llm_seq(*payloads):
    client = MagicMock()
    msgs = []
    for p in payloads:
        m = MagicMock()
        m.content = json.dumps(p) if not isinstance(p, str) else p
        msgs.append(m)
    client.invoke.side_effect = msgs
    return client


def _stub_searcher(table="dws_cell_hourly", score=0.9):
    s = MagicMock()
    s.search.return_value = [
        {
            "doc": MagicMock(metadata={"table_name": table, "field_name": None}),
            "score": score,
            "table": table,
        }
    ]
    return s


def _mock_table(**attrs):
    """SimpleNamespace so json.dumps in nodes (e.g. code_generate) works."""
    return SimpleNamespace(**attrs)


def test_p2_1_forward_etl_spark_sql_path(monkeypatch):
    """P2-1: forward_etl -> spark_sql path."""
    client = _llm_seq(
        {"intent": "forward_etl", "confidence": 0.95},
        {
            "target_entities": ["dws_cell_hourly"],
            "source_hints": ["ods_ue_signal"],
            "code_type_hint": "spark_sql",
        },
        [{"keyword": "覆盖", "field_specified": False}],
        "```spark-sql\nSELECT cell_id FROM ods_ue_signal\n```",
        "OK",
    )
    searcher = _stub_searcher()
    monkeypatch.setattr(
        "backend.agent.nodes.dry_run.sandbox.execute",
        lambda code, code_type: DryRunResult(
            success=True, preview_row={"cell_id": "1"}
        ),
    )
    with patch("backend.agent.tools.metadata_service.get_table_by_name") as gt:
        gt.return_value = _mock_table(
            name="dws_cell_hourly", layer="DWS", storage_type="HIVE", fields=[]
        )
        g = build_graph(llm_client=client, searcher=searcher)
        final = g.invoke({"messages": [{"role": "user", "content": "求平均 RSRP"}]})
    assert final["code_type"] == "spark_sql"
    assert "SELECT" in final["generated_code"]
    assert final["dry_run_result"]["success"] is True


def test_p2_8_schema_evolve_add_jitter_path():
    """P2-8: add jitter field via schema_evolve -> validate -> apply."""
    client = _llm_seq(
        {"intent": "schema_evolve", "confidence": 0.9},
        [
            {
                "operation": "ADD_FIELD",
                "table": "dwd_session_qos",
                "field": "jitter",
                "data_type": "DOUBLE",
                "expression": "STDDEV(latency)",
                "upstream": [],
            }
        ],
    )
    searcher = _stub_searcher("dwd_session_qos")
    with (
        patch("backend.agent.tools.metadata_service.get_table_by_name") as gt,
        patch("backend.agent.tools.metadata_service.create_field") as cf,
        patch("backend.agent.tools.metadata_service.get_lineage", return_value=[]),
        patch(
            "backend.agent.nodes.schema_apply.yaml_sync.sync_yaml", return_value=[]
        ),
        patch(
            "backend.agent.nodes.schema_apply.yaml_sync.git_commit", return_value="sha"
        ),
        patch(
            "backend.agent.nodes.schema_apply._record_change",
            side_effect=lambda op, commit_hash=None: {
                "change_id": "c1",
                "operation": op["operation"],
                "table": op["table"],
                "field": op.get("field"),
                "commit_hash": commit_hash,
            },
        ),
        patch("backend.agent.nodes.schema_apply._update_change_commit"),
    ):
        gt.return_value = _mock_table(
            id="t1",
            name="dwd_session_qos",
            layer="DWD",
            storage_type="HIVE",
            fields=[],
        )
        cf.return_value = MagicMock(id="f_jitter")
        g = build_graph(llm_client=client, searcher=searcher)
        final = g.invoke(
            {
                "messages": [{"role": "user", "content": "加 jitter"}],
                "target_tables": ["dwd_session_qos"],
            }
        )
    assert final["validation_result"]["passed"] is True
    assert any(
        c["operation"] == "ADD_FIELD" for c in final["applied_changes"]
    )


def test_p2_9_schema_validate_blocks_break_downstream():
    """P2-9: delete field with downstream -> validate rejects."""
    client = _llm_seq(
        {"intent": "schema_evolve", "confidence": 0.92},
        [
            {
                "operation": "DELETE_FIELD",
                "table": "ods_ue_signal",
                "field": "rsrp",
            }
        ],
    )
    searcher = _stub_searcher("ods_ue_signal")
    with (
        patch("backend.agent.tools.metadata_service.get_table_by_name") as gt,
        patch("backend.agent.tools.metadata_service.get_lineage") as m,
    ):
        gt.return_value = _mock_table(
            name="ods_ue_signal",
            layer="ODS",
            storage_type="HIVE",
            fields=[],
        )
        m.return_value = [
            MagicMock(
                from_table="ods_ue_signal",
                from_field="rsrp",
                to_table="dwd_session_qos",
                to_field="avg_rsrp",
            )
        ]
        g = build_graph(llm_client=client, searcher=searcher)
        final = g.invoke(
            {
                "messages": [{"role": "user", "content": "删 rsrp"}],
                "target_tables": ["ods_ue_signal"],
            }
        )
    assert final["validation_result"]["passed"] is False
    assert any(
        e[0] == "BREAK_DOWNSTREAM"
        for e in final["validation_result"]["errors"]
    )


def test_p2_11_gap_check_missing_table():
    """P2-11: gap_check detects missing table -> gap_proposal -> presenter card."""
    client = _llm_seq(
        {"intent": "forward_etl", "confidence": 0.92},
        {
            "target_entities": ["小区小时画像"],
            "source_hints": [],
            "code_type_hint": "spark_sql",
        },
        [
            {"keyword": "基站负载", "field_specified": False},
            {"keyword": "信号质量", "field_specified": False},
        ],
        [
            {
                "operation": "ADD_TABLE",
                "table": "ods_gnb_load",
                "layer": "ODS",
                "storage_type": "KAFKA",
                "fields": [],
            }
        ],
    )

    def search_side(query, k=10, use_rerank=False):
        if "负载" in query:
            return [
                {
                    "doc": MagicMock(
                        metadata={
                            "table_name": "ods_ue_signal",
                            "field_name": None,
                        }
                    ),
                    "score": 0.05,
                    "table": "ods_ue_signal",
                }
            ]
        return [
            {
                "doc": MagicMock(
                    metadata={
                        "table_name": "dws_cell_hourly",
                        "field_name": None,
                    }
                ),
                "score": 0.92,
                "table": "dws_cell_hourly",
            }
        ]

    searcher = MagicMock()
    searcher.search.side_effect = search_side
    with patch("backend.agent.tools.metadata_service.get_table_by_name") as gt:
        gt.return_value = _mock_table(
            name="dws_cell_hourly",
            layer="DWS",
            storage_type="HIVE",
            fields=[],
        )
        g = build_graph(llm_client=client, searcher=searcher)
        final = g.invoke(
            {
                "messages": [
                    {"role": "user", "content": "需要基站负载和信号质量"}
                ]
            }
        )
    assert final["has_gaps"] is True
    assert any(
        g_["type"] == "missing_table" and g_["keyword"] == "基站负载"
        for g_ in final["gaps"]
    )
    assert final["presenter_payload"]["type"] == "gap_proposal_card"
