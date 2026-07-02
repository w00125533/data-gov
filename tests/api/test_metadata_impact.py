from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import metadata
from backend.metadata.models import ImpactResponse, LineageEdge


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(metadata.router)
    return TestClient(app)


def _impact(field: str | None) -> ImpactResponse:
    return ImpactResponse(
        table="tmp_impact_src",
        field=field,
        has_downstream=True,
        affected_tables=["tmp_impact_dst"],
        downstream=[
            LineageEdge(
                edge_id="edge-impact-1",
                from_table="tmp_impact_src",
                from_field="raw_value",
                to_table="tmp_impact_dst",
                to_field="metric_value",
                transform_expr="avg(raw_value)",
                created_at="2026-07-02T12:00:00Z",
            )
        ],
    )


def test_field_downstream_impact_precheck(monkeypatch):
    captured = {}

    def fake_get_downstream_impact(table: str, field: str | None = None):
        captured["args"] = {"table": table, "field": field}
        return _impact(field)

    monkeypatch.setattr(metadata.service, "get_downstream_impact", fake_get_downstream_impact)

    res = _client().get("/api/metadata/impact", params={
        "table": "tmp_impact_src",
        "field": "raw_value",
    })

    assert res.status_code == 200
    assert captured["args"] == {"table": "tmp_impact_src", "field": "raw_value"}
    assert res.json() == {
        "table": "tmp_impact_src",
        "field": "raw_value",
        "has_downstream": True,
        "affected_tables": ["tmp_impact_dst"],
        "downstream": [{
            "edge_id": "edge-impact-1",
            "from_table": "tmp_impact_src",
            "from_field": "raw_value",
            "to_table": "tmp_impact_dst",
            "to_field": "metric_value",
            "transform_expr": "avg(raw_value)",
            "created_at": "2026-07-02T12:00:00Z",
        }],
    }


def test_table_downstream_impact_precheck(monkeypatch):
    captured = {}

    def fake_get_downstream_impact(table: str, field: str | None = None):
        captured["args"] = {"table": table, "field": field}
        return _impact(field)

    monkeypatch.setattr(metadata.service, "get_downstream_impact", fake_get_downstream_impact)

    res = _client().get("/api/metadata/impact", params={"table": "tmp_impact_src"})

    assert res.status_code == 200
    assert captured["args"] == {"table": "tmp_impact_src", "field": None}
    payload = res.json()
    assert payload["table"] == "tmp_impact_src"
    assert payload["field"] is None
    assert payload["has_downstream"] is True
    assert payload["affected_tables"] == ["tmp_impact_dst"]
    assert payload["downstream"][0]["from_field"] == "raw_value"
    assert payload["downstream"][0]["to_table"] == "tmp_impact_dst"
