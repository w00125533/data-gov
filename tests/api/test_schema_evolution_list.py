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
                "version": 2,
                "field_version": None,
                "old_value": '{"expression": "AVG(latency)"}',
                "new_value": '{"expression": "STDDEV(latency)", "field_type": "DOUBLE"}',
                "downstream": '[{"table": "eval_net_health", "field": "health_index"}]',
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
    assert "c.version AS version" in captured["cypher"]
    assert "c.old_value AS old_value" in captured["cypher"]
    change = res.json()["changes"][0]
    assert change["table_name"] == "dwd_session_qos"
    assert change["version"] == 2
    assert change["previous_version"] == 1
    assert change["old_value"] == {"expression": "AVG(latency)"}
    assert change["new_value"] == {"expression": "STDDEV(latency)", "field_type": "DOUBLE"}
    assert change["downstream"] == [{"table": "eval_net_health", "field": "health_index"}]


def test_schema_evolution_table_route_preserves_deleted_target_names(monkeypatch):
    def fake_run_query(_cypher, **_params):
        return [
            {
                "id": "chg_delete",
                "operation": "DELETE_FIELD",
                "table_name": "ods_ue_signal",
                "field_name": "rsrp",
                "version": None,
                "field_version": 3,
                "old_value": '{"field_type": "DOUBLE"}',
                "new_value": None,
                "downstream": None,
                "changed_at": "2026-06-03T11:00:00",
                "commit_hash": None,
            }
        ]

    monkeypatch.setattr(schema_evolution, "run_query", fake_run_query)
    app = FastAPI()
    app.include_router(schema_evolution.router)

    res = TestClient(app).get("/api/schema/evolution/ods_ue_signal")

    assert res.status_code == 200
    change = res.json()["changes"][0]
    assert change["table_name"] == "ods_ue_signal"
    assert change["field_name"] == "rsrp"
    assert change["version"] == 3
    assert change["previous_version"] == 2
    assert change["old_value"] == {"field_type": "DOUBLE"}
    assert change["new_value"] is None
    assert change["downstream"] == []
