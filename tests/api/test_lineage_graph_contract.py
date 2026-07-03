import pytest
from pydantic import ValidationError

from backend.metadata.models import (
    CalcType,
    FieldResponse,
    LineageEdge,
    LineageEdgeEndpointUpdateRequest,
    LineageEdgeUpdateRequest,
    LineageGraphResponse,
    LineageSqlApplyRequest,
    LineageSqlImportPreviewResponse,
    LineageSqlImportPreviewRequest,
    LineageSqlPreviewRequest,
    LineageSqlPreviewResponse,
    LineageTableEdge,
    LineageTableNode,
)


def test_calc_type_contract_is_exact():
    assert CalcType.__args__ == (
        "DIRECT",
        "EXPRESSION",
        "AGGREGATE",
        "JOIN",
        "WINDOW",
        "CONDITION",
        "CONSTANT",
    )


def test_lineage_edge_supports_calc_metadata():
    edge = LineageEdge(
        edge_id="edge-1",
        from_table="dwd_session_qos",
        from_field="rsrp",
        to_table="dws_cell_hourly",
        to_field="avg_rsrp",
        transform_expr="AVG(rsrp)",
        calc_type="AGGREGATE",
        calc_params={"function": "AVG"},
        created_at="2026-07-03T10:00:00Z",
        updated_at="2026-07-03T10:30:00Z",
    )

    assert edge.model_dump() == {
        "edge_id": "edge-1",
        "from_table": "dwd_session_qos",
        "from_field": "rsrp",
        "to_table": "dws_cell_hourly",
        "to_field": "avg_rsrp",
        "transform_expr": "AVG(rsrp)",
        "calc_type": "AGGREGATE",
        "calc_params": {"function": "AVG"},
        "created_at": "2026-07-03T10:00:00Z",
        "updated_at": "2026-07-03T10:30:00Z",
    }


def test_lineage_edge_update_request_only_contains_mutable_calc_contract():
    assert tuple(LineageEdgeUpdateRequest.model_fields) == (
        "transform_expr",
        "calc_type",
        "calc_params",
    )


def test_lineage_edge_endpoint_update_request_only_contains_endpoint_fields():
    assert tuple(LineageEdgeEndpointUpdateRequest.model_fields) == (
        "from_table",
        "from_field",
        "to_table",
        "to_field",
    )


def test_lineage_graph_response_contains_table_sql_and_edge_summary():
    field = FieldResponse(
        id="field-1",
        name="avg_rsrp",
        field_type="DOUBLE",
        is_nullable=True,
        is_partition=False,
        expression="AVG(rsrp)",
        description="Average RSRP",
        version=1,
        upstream=[{"table": "dwd_session_qos", "field": "rsrp"}],
    )
    table = LineageTableNode(
        id="table-1",
        name="dws_cell_hourly",
        layer="DWS",
        layer_priority=3,
        storage_type="HIVE",
        description="Hourly cell metrics",
        field_count=1,
        fields=[field],
        sql_logic="SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos",
        sql_dialect="hive",
        sql_source="generated",
        sql_updated_at="2026-07-03T10:30:00Z",
    )
    field_edge = LineageEdge(
        edge_id="edge-1",
        from_table="dwd_session_qos",
        from_field="rsrp",
        to_table="dws_cell_hourly",
        to_field="avg_rsrp",
        transform_expr="AVG(rsrp)",
        calc_type="AGGREGATE",
        calc_params={"function": "AVG"},
        created_at="2026-07-03T10:00:00Z",
        updated_at="2026-07-03T10:30:00Z",
    )
    table_edge = LineageTableEdge(
        source="dwd_session_qos",
        target="dws_cell_hourly",
        direction="upstream",
        field_edge_count=1,
        calc_type_counts={"AGGREGATE": 1},
        fields=["avg_rsrp"],
    )

    response = LineageGraphResponse(
        root_table="dws_cell_hourly",
        depth=1,
        include_upstream=True,
        include_downstream=False,
        graph_version="v1",
        tables=[table],
        table_edges=[table_edge],
        field_edges=[field_edge],
        saved_sql="SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos",
    )

    dumped = response.model_dump()
    assert dumped["root_table"] == "dws_cell_hourly"
    assert dumped["depth"] == 1
    assert dumped["include_upstream"] is True
    assert dumped["include_downstream"] is False
    assert dumped["graph_version"] == "v1"
    assert dumped["tables"][0]["sql_logic"] == "SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos"
    assert dumped["tables"][0]["fields"][0]["name"] == "avg_rsrp"
    assert dumped["table_edges"][0]["direction"] == "upstream"
    assert dumped["table_edges"][0]["calc_type_counts"] == {"AGGREGATE": 1}
    assert dumped["field_edges"][0]["calc_type"] == "AGGREGATE"
    assert dumped["saved_sql"] == "SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos"


def test_lineage_graph_response_defaults_saved_sql_to_none():
    response = LineageGraphResponse(
        root_table="dws_cell_hourly",
        depth=1,
        include_upstream=True,
        include_downstream=False,
        graph_version="v1",
        tables=[],
        table_edges=[],
        field_edges=[],
    )

    assert response.saved_sql is None


def test_lineage_sql_preview_response_defaults_optional_fields():
    response = LineageSqlPreviewResponse(
        table="dws_cell_hourly",
        sql="SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos",
        complete=True,
        changed=False,
    )

    assert response.model_dump() == {
        "table": "dws_cell_hourly",
        "sql": "SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos",
        "complete": True,
        "warnings": [],
        "saved_sql": None,
        "changed": False,
    }


def test_sql_preview_request_validates_table_name():
    with pytest.raises(ValidationError):
        LineageSqlPreviewRequest(table="")

    with pytest.raises(ValidationError):
        LineageSqlPreviewRequest(table="x" * 129)


def test_sql_import_preview_request_validates_table_and_sql():
    with pytest.raises(ValidationError):
        LineageSqlImportPreviewRequest(table="", sql="SELECT 1")

    with pytest.raises(ValidationError):
        LineageSqlImportPreviewRequest(table="dws_cell_hourly", sql="")


def test_sql_import_preview_response_defaults_warnings():
    response = LineageSqlImportPreviewResponse(
        table="dws_cell_hourly",
        sql="SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos",
        fields=[],
        edges=[],
    )

    assert response.warnings == []


def test_sql_apply_request_validates_table_and_sql_and_uses_string_graph_version():
    request = LineageSqlApplyRequest(
        table="dws_cell_hourly",
        sql="SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos",
        fields=[],
        edges=[],
        expected_graph_version="v1",
    )

    assert request.expected_graph_version == "v1"

    with pytest.raises(ValidationError):
        LineageSqlApplyRequest(table="", sql="SELECT 1", fields=[], edges=[])

    with pytest.raises(ValidationError):
        LineageSqlApplyRequest(table="dws_cell_hourly", sql="", fields=[], edges=[])
