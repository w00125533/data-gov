from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import metadata
from backend.metadata.models import (
    FieldResponse,
    LineageEdge,
    LineageGraphResponse,
    LineageTableEdge,
    LineageTableNode,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(metadata.router)
    return TestClient(app)


def _edge(**overrides) -> LineageEdge:
    data = {
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
    data.update(overrides)
    return LineageEdge(**data)


def _field(name: str) -> FieldResponse:
    return FieldResponse(
        id=f"field-{name}",
        name=name,
        field_type="DOUBLE",
        is_nullable=True,
        is_partition=False,
        expression=None,
        description="",
        version=1,
        upstream=[],
    )


def test_update_lineage_edge_accepts_and_returns_calc_metadata(monkeypatch):
    captured = {}

    def fake_update_lineage_edge(edge_id, req):
        captured["edge_id"] = edge_id
        captured["req"] = req
        return _edge(
            edge_id=edge_id,
            transform_expr=req.transform_expr,
            calc_type=req.calc_type,
            calc_params=req.calc_params,
        )

    monkeypatch.setattr(metadata.service, "update_lineage_edge", fake_update_lineage_edge)

    res = _client().put(
        "/api/lineage/edges/edge-structured",
        json={
            "transform_expr": "AVG(rsrp)",
            "calc_type": "AGGREGATE",
            "calc_params": {"function": "AVG", "window": "1h"},
        },
    )

    assert res.status_code == 200
    assert captured["edge_id"] == "edge-structured"
    assert captured["req"].transform_expr == "AVG(rsrp)"
    assert captured["req"].calc_type == "AGGREGATE"
    assert captured["req"].calc_params == {"function": "AVG", "window": "1h"}
    payload = res.json()
    assert payload["calc_type"] == "AGGREGATE"
    assert payload["calc_params"] == {"function": "AVG", "window": "1h"}
    assert payload["updated_at"] == "2026-07-03T10:30:00Z"


def test_update_lineage_edge_endpoints_passes_endpoint_request_and_returns_moved_edge(monkeypatch):
    captured = {}

    def fake_update_lineage_edge_endpoints(edge_id, req):
        captured["edge_id"] = edge_id
        captured["req"] = req
        return _edge(
            edge_id=edge_id,
            from_table=req.from_table,
            from_field=req.from_field,
            to_table=req.to_table,
            to_field=req.to_field,
        )

    monkeypatch.setattr(metadata.service, "update_lineage_edge_endpoints", fake_update_lineage_edge_endpoints)

    res = _client().patch(
        "/api/lineage/edges/edge-1/endpoints",
        json={
            "from_table": "dwd_session_qos",
            "from_field": "sinr",
            "to_table": "dws_cell_hourly",
            "to_field": "avg_sinr",
        },
    )

    assert res.status_code == 200
    assert captured["edge_id"] == "edge-1"
    assert captured["req"].from_table == "dwd_session_qos"
    assert captured["req"].from_field == "sinr"
    assert captured["req"].to_table == "dws_cell_hourly"
    assert captured["req"].to_field == "avg_sinr"
    assert res.json()["from_field"] == "sinr"
    assert res.json()["to_field"] == "avg_sinr"


def test_update_lineage_edge_endpoints_conflict_returns_409(monkeypatch):
    assert hasattr(metadata.service, "LineageEndpointConflict")

    def fake_update_lineage_edge_endpoints(_edge_id, _req):
        raise metadata.service.LineageEndpointConflict("edge-existing")

    monkeypatch.setattr(metadata.service, "update_lineage_edge_endpoints", fake_update_lineage_edge_endpoints)

    res = _client().patch(
        "/api/lineage/edges/edge-1/endpoints",
        json={
            "from_table": "dwd_session_qos",
            "from_field": "sinr",
            "to_table": "dws_cell_hourly",
            "to_field": "avg_sinr",
        },
    )

    assert res.status_code == 409
    assert res.json()["detail"] == {
        "error": "lineage endpoint already exists",
        "edge_id": "edge-existing",
    }


def test_get_lineage_graph_passes_query_and_returns_workspace_contract(monkeypatch):
    captured = {}

    def fake_get_lineage_graph(table, depth, include_upstream, include_downstream):
        captured["args"] = {
            "table": table,
            "depth": depth,
            "include_upstream": include_upstream,
            "include_downstream": include_downstream,
        }
        return LineageGraphResponse(
            root_table=table,
            depth=depth,
            include_upstream=include_upstream,
            include_downstream=include_downstream,
            graph_version="edges:1:123",
            tables=[
                LineageTableNode(
                    id="table-dwd",
                    name="dwd_session_qos",
                    layer="DWD",
                    layer_priority=2,
                    storage_type="HIVE",
                    description="Session QoS",
                    field_count=1,
                    fields=[_field("rsrp")],
                ),
                LineageTableNode(
                    id="table-dws",
                    name="dws_cell_hourly",
                    layer="DWS",
                    layer_priority=3,
                    storage_type="HIVE",
                    description="Hourly cell metrics",
                    field_count=1,
                    fields=[_field("avg_rsrp")],
                    sql_logic="SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos",
                    sql_dialect="hive",
                    sql_source="generated",
                    sql_updated_at="2026-07-03T10:30:00Z",
                ),
            ],
            table_edges=[
                LineageTableEdge(
                    source="dwd_session_qos",
                    target="dws_cell_hourly",
                    direction="upstream",
                    field_edge_count=1,
                    calc_type_counts={"AGGREGATE": 1},
                    fields=["avg_rsrp"],
                )
            ],
            field_edges=[_edge()],
            saved_sql="SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos",
        )

    monkeypatch.setattr(metadata.service, "get_lineage_graph", fake_get_lineage_graph)

    res = _client().get(
        "/api/lineage/graph",
        params={
            "table": "dws_cell_hourly",
            "depth": 2,
            "include_upstream": True,
            "include_downstream": False,
        },
    )

    assert res.status_code == 200
    assert captured["args"] == {
        "table": "dws_cell_hourly",
        "depth": 2,
        "include_upstream": True,
        "include_downstream": False,
    }
    payload = res.json()
    assert payload["root_table"] == "dws_cell_hourly"
    assert payload["include_upstream"] is True
    assert payload["include_downstream"] is False
    assert payload["tables"][1]["sql_logic"] == "SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos"
    assert payload["table_edges"][0]["calc_type_counts"] == {"AGGREGATE": 1}
    assert payload["field_edges"][0]["calc_type"] == "AGGREGATE"
