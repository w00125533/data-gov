"""tests/agent/test_api_schema.py - /api/schema/* endpoints."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI


@pytest.fixture
def client(monkeypatch):
    """Build a minimal app with mocked schema dependencies."""
    # Mock validate_change
    def fake_validate_pass(diff):
        return {"passed": True, "errors": [], "warnings": []}
    monkeypatch.setattr(
        "backend.api.schema_evolution.validate_change", fake_validate_pass
    )

    # Mock schema_apply
    def fake_schema_apply(state):
        return {
            "applied_changes": [
                {
                    "change_id": "chg_abc123",
                    "operation": "ADD_FIELD",
                    "table": "dim_cell",
                    "field": "rsrp_mean",
                    "commit_hash": "abc1234",
                }
            ]
        }
    monkeypatch.setattr(
        "backend.api.schema_evolution.schema_apply", fake_schema_apply
    )

    # Mock run_query
    def fake_run_query(cypher, **params):
        return [
            {
                "id": "chg_def456",
                "operation": "ADD_FIELD",
                "table_name": "dim_cell",
                "field_name": "rsrp_mean",
                "changed_at": "2026-05-14T12:00:00",
                "commit_hash": "def5678",
            }
        ]
    monkeypatch.setattr(
        "backend.api.schema_evolution.run_query", fake_run_query
    )

    from backend.api.schema_evolution import router

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


class TestSchemaApply:
    def test_post_schema_apply_executes_diff(self, client):
        """验证 /api/schema/apply 正常执行 diff 并返回 applied_changes。"""
        resp = client.post(
            "/api/schema/apply",
            json={"diff": [{"operation": "ADD_FIELD", "table": "dim_cell", "field": "rsrp_mean"}]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["passed"] is True
        assert body["errors"] == []
        assert len(body["applied"]) == 1
        assert body["applied"][0]["change_id"] == "chg_abc123"
        assert body["applied"][0]["operation"] == "ADD_FIELD"

    def test_post_schema_apply_rejects_invalid_diff(self, monkeypatch):
        """验证 validate_change 不通过时直接返回错误，不调用 schema_apply。"""
        def fake_validate_fail(diff):
            return {"passed": False, "errors": [("TABLE_NOT_FOUND", diff[0])], "warnings": []}
        monkeypatch.setattr(
            "backend.api.schema_evolution.validate_change", fake_validate_fail
        )
        # schema_apply should NOT be called — make it fail if called
        monkeypatch.setattr(
            "backend.api.schema_evolution.schema_apply",
            lambda state: (_ for _ in ()).throw(RuntimeError("should not be called")),
        )
        monkeypatch.setattr(
            "backend.api.schema_evolution.run_query",
            lambda cypher, **params: [],
        )

        from backend.api.schema_evolution import router
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            resp = client.post(
                "/api/schema/apply",
                json={"diff": [{"operation": "ADD_FIELD", "table": "nonexistent", "field": "x"}]},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["passed"] is False
        assert len(body["errors"]) == 1
        assert body["applied"] == []


class TestSchemaEvolution:
    def test_get_schema_evolution_by_table(self, client):
        """验证 /api/schema/evolution/{table} 返回正确的 changes 结构。"""
        resp = client.get("/api/schema/evolution/dim_cell")
        assert resp.status_code == 200
        body = resp.json()
        assert body["table"] == "dim_cell"
        assert len(body["changes"]) == 1
        ch = body["changes"][0]
        assert ch["change_id"] == "chg_def456"
        assert ch["operation"] == "ADD_FIELD"
        assert ch["field_name"] == "rsrp_mean"
        assert ch["changed_at"] == "2026-05-14T12:00:00"
        assert ch["commit_hash"] == "def5678"
