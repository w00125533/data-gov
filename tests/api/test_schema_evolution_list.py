from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import schema_evolution


def test_schema_evolution_list_filters(monkeypatch):
    captured = {}

    def fake_run_query(cypher, **params):
        captured["cypher"] = cypher
        captured["params"] = params
        return [
            {
                "id": "chg_1",
                "operation": "ADD_FIELD",
                "table_name": "dwd_session_qos",
                "field_name": "jitter",
                "changed_at": "2026-06-03T10:00:00",
                "commit_hash": "abc123",
            }
        ]

    monkeypatch.setattr(schema_evolution, "run_query", fake_run_query)
    app = FastAPI()
    app.include_router(schema_evolution.router)

    res = TestClient(app).get("/api/schema/evolution?table=dwd_session_qos&operation=ADD_FIELD&q=jit")

    assert res.status_code == 200
    assert captured["params"] == {"table": "dwd_session_qos", "operation": "ADD_FIELD", "q": "jit"}
    assert res.json()["changes"][0]["table_name"] == "dwd_session_qos"
