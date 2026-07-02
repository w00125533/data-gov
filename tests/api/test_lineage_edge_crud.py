from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import metadata
from backend.metadata.models import LineageEdge


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(metadata.router)
    return TestClient(app)


def _edge(transform_expr: str = "raw_value * 100") -> LineageEdge:
    return LineageEdge(
        edge_id="edge-1",
        from_table="tmp_lineage_src",
        from_field="raw_value",
        to_table="tmp_lineage_mid",
        to_field="normalized_value",
        transform_expr=transform_expr,
        created_at="2026-07-02T12:00:00Z",
    )


def test_create_edge_persists_transform_expr(monkeypatch):
    captured = {}

    def fake_create_lineage_edge(req):
        captured["req"] = req
        return _edge(req.transform_expr)

    monkeypatch.setattr(metadata.service, "create_lineage_edge", fake_create_lineage_edge)

    res = _client().post("/api/lineage/edges", json={
        "from_table": "tmp_lineage_src",
        "from_field": "raw_value",
        "to_table": "tmp_lineage_mid",
        "to_field": "normalized_value",
        "transform_expr": "raw_value * 100",
    })

    assert res.status_code == 201
    assert captured["req"].from_table == "tmp_lineage_src"
    assert captured["req"].to_field == "normalized_value"
    assert captured["req"].transform_expr == "raw_value * 100"
    assert res.json() == {
        "edge_id": "edge-1",
        "from_table": "tmp_lineage_src",
        "from_field": "raw_value",
        "to_table": "tmp_lineage_mid",
        "to_field": "normalized_value",
        "transform_expr": "raw_value * 100",
        "created_at": "2026-07-02T12:00:00Z",
    }


def test_lineage_query_returns_transform_expr(monkeypatch):
    captured = {}

    def fake_get_lineage(table: str, direction: str, depth: int):
        captured["args"] = {"table": table, "direction": direction, "depth": depth}
        return [_edge("raw_value * 100")]

    monkeypatch.setattr(metadata.service, "get_lineage", fake_get_lineage)

    res = _client().get("/api/lineage", params={
        "table": "tmp_lineage_src",
        "direction": "down",
        "depth": 1,
    })

    assert res.status_code == 200
    assert captured["args"] == {"table": "tmp_lineage_src", "direction": "down", "depth": 1}
    assert res.json()["edges"] == [{
        "edge_id": "edge-1",
        "from_table": "tmp_lineage_src",
        "from_field": "raw_value",
        "to_table": "tmp_lineage_mid",
        "to_field": "normalized_value",
        "transform_expr": "raw_value * 100",
        "created_at": "2026-07-02T12:00:00Z",
    }]


def test_update_edge_changes_expression(monkeypatch):
    captured = {}

    def fake_update_lineage_edge(edge_id, req):
        captured["edge_id"] = edge_id
        captured["req"] = req
        return _edge(req.transform_expr)

    monkeypatch.setattr(metadata.service, "update_lineage_edge", fake_update_lineage_edge)

    res = _client().put(
        "/api/lineage/edges/edge-1",
        json={"transform_expr": "coalesce(raw_value, 0) * 100"},
    )

    assert res.status_code == 200
    assert captured["edge_id"] == "edge-1"
    assert captured["req"].transform_expr == "coalesce(raw_value, 0) * 100"
    assert res.json()["transform_expr"] == "coalesce(raw_value, 0) * 100"


def test_delete_edge_removes_it(monkeypatch):
    captured = {}

    def fake_delete_lineage_edge(edge_id):
        captured["edge_id"] = edge_id

    monkeypatch.setattr(metadata.service, "delete_lineage_edge", fake_delete_lineage_edge)

    res = _client().delete("/api/lineage/edges/edge-1")

    assert res.status_code == 204
    assert captured["edge_id"] == "edge-1"


def test_cycle_attempt_returns_conflict(monkeypatch):
    def fake_create_lineage_edge(_req):
        raise metadata.service.CycleDetected([
            {"table": "tmp_lineage_src", "field": "raw_value", "field_id": "field-src"},
            {"table": "tmp_lineage_mid", "field": "normalized_value", "field_id": "field-mid"},
        ])

    monkeypatch.setattr(metadata.service, "create_lineage_edge", fake_create_lineage_edge)

    res = _client().post("/api/lineage/edges", json={
        "from_table": "tmp_lineage_mid",
        "from_field": "normalized_value",
        "to_table": "tmp_lineage_src",
        "to_field": "raw_value",
        "transform_expr": "normalized_value / 100",
    })

    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["error"] == "lineage cycle detected"
    assert detail["path"] == [
        {"table": "tmp_lineage_src", "field": "raw_value", "field_id": "field-src"},
        {"table": "tmp_lineage_mid", "field": "normalized_value", "field_id": "field-mid"},
    ]
