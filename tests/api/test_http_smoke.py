"""Smoke test: FastAPI app boots, /api/health returns 200."""
from fastapi.testclient import TestClient

from backend.main import create_app


def test_health_endpoint_returns_ok():
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "neo4j" in body["components"]
