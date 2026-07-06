"""tests/agent/test_tools.py"""
from unittest.mock import MagicMock, patch
from backend.agent import tools


def test_search_tables_by_keyword_delegates_to_searcher():
    fake_searcher = MagicMock()
    fake_searcher.search.return_value = [
        {"doc": MagicMock(metadata={"table_name": "dws_cell_hourly", "field_name": None}), "score": 0.9, "table": "dws_cell_hourly"},
    ]
    r = tools.search_tables_by_keyword("覆盖强度", searcher=fake_searcher)
    assert r.top_table == "dws_cell_hourly"
    assert r.top_score == 0.9


def test_lookup_table_schema_ignores_unknown_tables():
    with patch("backend.agent.tools.metadata_service.get_table_by_name") as m:
        from backend.metadata.service import TableNotFound
        m.side_effect = TableNotFound()
        out = tools.lookup_table_schema(["unknown"])
        assert "unknown" not in out


def test_validate_change_detects_break_downstream():
    with patch("backend.agent.tools.metadata_service.get_lineage") as m:
        m.return_value = [MagicMock(from_table="ods_ue_signal", from_field="rsrp", to_table="dwd_session_qos", to_field="avg_rsrp")]
        diff = [{"operation": "DELETE_FIELD", "table": "ods_ue_signal", "field": "rsrp"}]
        result = tools.validate_change(diff)
        assert result["passed"] is False
        assert any(e[0] == "BREAK_DOWNSTREAM" for e in result["errors"])


def test_add_field_delegates_to_create_field():
    with patch("backend.agent.tools.metadata_service.get_table_by_name") as gt, \
         patch("backend.agent.tools.metadata_service.create_field") as cf:
        gt.return_value = MagicMock(id="t1")
        cf.return_value = MagicMock(id="f1", name="jitter")
        op = {"operation": "ADD_FIELD", "table": "dwd_session_qos", "field": "jitter", "data_type": "DOUBLE", "expression": "STDDEV(latency)", "upstream": []}
        out = tools.add_field(op)
        assert out["field_id"] == "f1"


def test_dry_run_dispatches_by_code_type(monkeypatch):
    captured = []
    def fake_execute(code, code_type):
        captured.append(code_type)
        from backend.agent.sandbox_stub import DryRunResult
        return DryRunResult(success=True, preview_row={"x": 1})
    monkeypatch.setattr("backend.agent.tools.sandbox.execute", fake_execute)
    tools.dry_run_spark_sql("SELECT 1")
    tools.dry_run_flink_sql("INSERT ...")
    tools.dry_run_java_flink("class Job {}")
    assert captured == ["spark_sql", "flink_sql", "java_flink"]


def test_search_tables_by_keyword_empty_result():
    fake_searcher = MagicMock()
    fake_searcher.search.return_value = []
    r = tools.search_tables_by_keyword("nothing", searcher=fake_searcher)
    assert r.top_table is None
    assert r.top_score == 0.0
    assert r.top_field is None


def test_lookup_lineage_delegates():
    with patch("backend.agent.tools.metadata_service.get_lineage") as m:
        m.return_value = []
        result = tools.lookup_lineage("dwd_session_qos", direction="up", depth=3)
        assert result == []
        m.assert_called_once_with("dwd_session_qos", direction="up", depth=3)


def test_validate_change_duplicate_field():
    with patch("backend.agent.tools.metadata_service.get_table_by_name") as gt:
        field_mock = MagicMock()
        field_mock.name = "rsrp"
        gt.return_value = MagicMock(fields=[field_mock])
        diff = [{"operation": "ADD_FIELD", "table": "ods_ue_signal", "field": "rsrp"}]
        result = tools.validate_change(diff)
        assert result["passed"] is False
        assert any(e[0] == "DUPLICATE" for e in result["errors"])


def test_validate_change_add_table_duplicate():
    with patch("backend.agent.tools.metadata_service.get_table_by_name") as gt:
        from backend.metadata.service import TableNotFound
        gt.side_effect = [None, None]
        # First call succeeds (table already exists)
        gt.side_effect = None
        gt.return_value = MagicMock()
        diff = [{"operation": "ADD_TABLE", "table": "dwd_session_qos"}]
        result = tools.validate_change(diff)
        assert result["passed"] is False
        assert any(e[0] == "DUPLICATE_TABLE" for e in result["errors"])


def test_validate_change_add_table_requires_explicit_category():
    with patch("backend.agent.tools.metadata_service.get_table_by_name") as gt:
        from backend.metadata.service import TableNotFound
        gt.side_effect = TableNotFound("new_table")

        result = tools.validate_change([
            {
                "operation": "ADD_TABLE",
                "table": "new_table",
                "layer": "ODS",
                "storage_type": "HIVE",
                "fields": [],
            }
        ])

    assert result["passed"] is False
    assert any(e[0] == "MISSING_CATEGORY" for e in result["errors"])


def test_check_gaps_returns_suggestions():
    fake_searcher = MagicMock()
    fake_searcher.search.side_effect = [
        [],  # first keyword: no results -> gap
        [{"doc": MagicMock(), "score": 0.9, "table": "dwd_session_qos"}],  # second: above threshold
    ]
    gaps = tools.check_gaps(["业务概念A", "业务概念B"], searcher=fake_searcher, threshold=0.6)
    assert len(gaps) == 1
    assert gaps[0]["type"] == "missing_table"
    assert gaps[0]["keyword"] == "业务概念A"
