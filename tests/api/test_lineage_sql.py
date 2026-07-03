import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import metadata
from backend.metadata import service

from backend.metadata.lineage_sql import (
    UnsupportedSqlError,
    generate_select_sql,
    parse_select_preview,
)
from backend.metadata.models import (
    FieldResponse,
    LineageEdge,
    LineageSqlPreviewResponse,
    TableResponse,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(metadata.router)
    return TestClient(app)


def _field(name: str) -> FieldResponse:
    return FieldResponse(
        id=f"field-{name}",
        name=name,
        field_type="STRING",
        is_nullable=True,
        is_partition=False,
        expression=None,
        description="",
        version=1,
        upstream=[],
    )


def test_preview_lineage_sql_service_uses_table_fields_and_upstream_edges(monkeypatch):
    detail = TableResponse(
        id="table-dws",
        name="dws_cell_hourly",
        layer="DWS",
        layer_priority=3,
        storage_type="HIVE",
        description="",
        fields=[_field("cell_id"), _field("avg_rsrp")],
        sql_logic="SELECT old_sql FROM old_table",
    )
    edge = LineageEdge(
        from_table="dwd_session_qos",
        from_field="avg_rsrp",
        to_table="dws_cell_hourly",
        to_field="avg_rsrp",
        transform_expr="AVG(dwd_session_qos.avg_rsrp)",
        calc_type="AGGREGATE",
        calc_params={"group_by": ["cell_id"]},
    )

    monkeypatch.setattr(service, "get_table_by_name", lambda table: detail)
    monkeypatch.setattr(service, "get_lineage", lambda table, direction, depth: [edge])

    preview = service.preview_lineage_sql("dws_cell_hourly")

    assert preview.table == "dws_cell_hourly"
    assert "AVG(dwd_session_qos.avg_rsrp) AS avg_rsrp" in preview.sql
    assert preview.saved_sql == "SELECT old_sql FROM old_table"
    assert preview.changed is True


def test_lineage_sql_preview_route_delegates_to_service(monkeypatch):
    captured = {}

    def fake_preview_lineage_sql(table, field_edges=None):
        captured["table"] = table
        captured["field_edges"] = field_edges
        return LineageSqlPreviewResponse(
            table=table,
            sql="SELECT cell_id FROM dwd_session_qos",
            complete=True,
            warnings=[],
            saved_sql=None,
            changed=True,
        )

    monkeypatch.setattr(metadata.service, "preview_lineage_sql", fake_preview_lineage_sql)

    res = _client().post("/api/lineage/sql/preview", json={"table": "dws_cell_hourly"})

    assert res.status_code == 200
    assert captured == {"table": "dws_cell_hourly", "field_edges": None}
    assert res.json()["sql"] == "SELECT cell_id FROM dwd_session_qos"


def test_lineage_sql_import_preview_parse_failure_returns_422(monkeypatch):
    def fake_preview_sql_import(_table, _sql):
        raise UnsupportedSqlError("bad select")

    monkeypatch.setattr(metadata.service, "preview_sql_import", fake_preview_sql_import)

    res = _client().post(
        "/api/lineage/sql/import/preview",
        json={"table": "dws_cell_hourly", "sql": "SELECT FROM"},
    )

    assert res.status_code == 422
    assert res.json()["detail"] == {"error": "sql parse failed", "message": "bad select"}


def test_lineage_sql_import_preview_route_returns_422_for_unsupported_shape(monkeypatch):
    detail = TableResponse(
        id="table-dws",
        name="dws_cell_hourly",
        layer="DWS",
        layer_priority=3,
        storage_type="HIVE",
        description="",
        fields=[_field("cell_id")],
    )
    monkeypatch.setattr(metadata.service, "get_table_by_name", lambda table: detail)

    res = _client().post(
        "/api/lineage/sql/import/preview",
        json={
            "table": "dws_cell_hourly",
            "sql": (
                "SELECT q.cell_id, c.city FROM dwd_session_qos q "
                "JOIN dim_cell c ON q.cell_id = c.cell_id"
            ),
        },
    )

    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "sql parse failed"
    assert "JOIN" in res.json()["detail"]["message"]


def test_generate_select_sql_uses_aggregate_calc_type_and_group_by():
    edges = [
        LineageEdge(
            edge_id="edge-avg",
            from_table="dwd_session_qos",
            from_field="avg_rsrp",
            to_table="dws_cell_hourly",
            to_field="avg_rsrp",
            transform_expr="AVG(dwd_session_qos.avg_rsrp)",
            calc_type="AGGREGATE",
            calc_params={"function": "AVG", "group_by": ["cell_id", "hour_bucket"]},
        ),
        LineageEdge(
            edge_id="edge-cell",
            from_table="dwd_session_qos",
            from_field="cell_id",
            to_table="dws_cell_hourly",
            to_field="cell_id",
            transform_expr="dwd_session_qos.cell_id",
            calc_type="DIRECT",
        ),
    ]

    sql, complete, warnings = generate_select_sql(
        table="dws_cell_hourly",
        fields=["cell_id", "hour_bucket", "avg_rsrp"],
        saved_sql=None,
        edges=edges,
    )

    assert complete is True
    assert warnings == []
    assert sql.startswith("SELECT")
    assert "AVG(dwd_session_qos.avg_rsrp) AS avg_rsrp" in sql
    assert "FROM dwd_session_qos" in sql
    assert "GROUP BY cell_id, hour_bucket" in sql


def test_generate_select_sql_without_usable_edges_returns_safe_incomplete_sql():
    sql, complete, warnings = generate_select_sql(
        table="dws_cell_hourly",
        fields=["cell_id", "avg_rsrp"],
        saved_sql=None,
        edges=[],
    )

    assert complete is False
    assert "SELECT\n  NULL AS placeholder\nFROM dws_cell_hourly" == sql
    assert "Unable to generate SQL for field cell_id: no upstream lineage edge" in warnings
    assert "Generated placeholder SQL because no selectable expressions were available" in warnings


def test_generate_select_sql_with_multiple_source_tables_returns_safe_incomplete_sql():
    edges = [
        LineageEdge(
            from_table="dwd_session_qos",
            from_field="cell_id",
            to_table="dws_cell_hourly",
            to_field="cell_id",
            transform_expr="dwd_session_qos.cell_id",
        ),
        LineageEdge(
            from_table="dim_cell",
            from_field="region",
            to_table="dws_cell_hourly",
            to_field="region",
            transform_expr="dim_cell.region",
        ),
    ]

    sql, complete, warnings = generate_select_sql(
        table="dws_cell_hourly",
        fields=["cell_id", "region"],
        saved_sql=None,
        edges=edges,
    )

    assert complete is False
    assert sql == "SELECT\n  NULL AS placeholder\nFROM dwd_session_qos"
    assert "Unsupported multiple upstream tables for SQL preview: dim_cell, dwd_session_qos" in warnings


def test_parse_select_preview_extracts_fields_and_edges_with_alias_and_case():
    sql = (
        "SELECT cell_id, AVG(q.avg_rsrp) AS avg_rsrp, "
        "CASE WHEN AVG(q.avg_sinr) > 10 THEN 1 ELSE 0 END AS good_signal "
        "FROM dwd_session_qos q GROUP BY cell_id"
    )

    preview = parse_select_preview("dws_cell_hourly", sql)

    assert [field.field for field in preview.fields] == ["cell_id", "avg_rsrp", "good_signal"]
    avg_edge = next(edge.edge for edge in preview.edges if edge.edge.to_field == "avg_rsrp")
    assert avg_edge.from_table == "dwd_session_qos"
    assert avg_edge.from_field == "avg_rsrp"
    assert avg_edge.calc_type == "AGGREGATE"
    condition_edge = next(edge.edge for edge in preview.edges if edge.edge.to_field == "good_signal")
    assert condition_edge.calc_type == "CONDITION"


@pytest.mark.parametrize(
    "sql, message",
    [
        (
            "SELECT q.cell_id, c.city FROM dwd_session_qos q "
            "JOIN dim_cell c ON q.cell_id = c.cell_id",
            "JOIN",
        ),
        (
            "SELECT q.cell_id FROM dwd_session_qos q, dim_cell c",
            "multiple source tables",
        ),
    ],
)
def test_parse_select_preview_rejects_join_or_multiple_source_sql(sql, message):
    with pytest.raises(UnsupportedSqlError, match=message):
        parse_select_preview("dws_cell_hourly", sql)


@pytest.mark.parametrize(
    "sql, message",
    [
        (
            "WITH source AS (SELECT cell_id FROM dwd_session_qos) SELECT cell_id FROM source",
            "CTE",
        ),
        (
            "SELECT cell_id FROM (SELECT cell_id FROM dwd_session_qos) q",
            "subquery",
        ),
        (
            "SELECT cell_id FROM dwd_session_qos UNION SELECT cell_id FROM dwd_session_qos_archive",
            "set operation",
        ),
        (
            "INSERT INTO dws_cell_hourly SELECT cell_id FROM dwd_session_qos",
            "only SELECT statements are supported",
        ),
    ],
)
def test_parse_select_preview_rejects_cte_subquery_set_and_non_select(sql, message):
    with pytest.raises(UnsupportedSqlError, match=message):
        parse_select_preview("dws_cell_hourly", sql)


def test_parse_select_preview_reports_unknown_source_alias():
    sql = "SELECT missing_alias.rsrp AS avg_rsrp FROM dwd_session_qos q"

    preview = parse_select_preview("dws_cell_hourly", sql)

    assert preview.warnings == [
        "Unable to resolve table alias missing_alias for field avg_rsrp",
    ]
    assert preview.edges == []
