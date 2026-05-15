"""tests/search/test_api_search.py — 走 FastAPI TestClient 黑盒。"""
import numpy as np
import pytest


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    """Stub out embedder + Neo4j so the full lifespan can run standalone."""

    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            return np.array([[hash(t) % 100 / 100.0] * 16 for t in texts])

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer",
        lambda name: StubEncoder(),
    )

    # Stub Neo4j driver — get_driver() calls GraphDatabase.driver() internally.
    class StubDriver:
        def verify_connectivity(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(
        "backend.metadata.graph.GraphDatabase.driver",
        lambda uri, auth: StubDriver(),
    )

    # Stub run_query so the health endpoint doesn't need a real Neo4j.
    monkeypatch.setattr(
        "backend.metadata.graph.run_query",
        lambda cypher, **params: [{"n": 10}],
    )

    monkeypatch.setenv("SEARCH_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("SEARCH_BOOTSTRAP_FROM_SEED", "1")
    from backend.config import get_settings

    get_settings.cache_clear()

    from backend.main import create_app

    app = create_app()
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client


class TestSearchEndpoint:
    def test_get_search_returns_results_for_known_table(self, api_client):
        r = api_client.get("/api/search", params={"q": "dws_cell_hourly", "k": 5})
        assert r.status_code == 200
        body = r.json()
        assert "query" in body and "results" in body
        assert len(body["results"]) > 0
        assert any(item["table"] == "dws_cell_hourly" for item in body["results"])

    def test_get_search_query_required(self, api_client):
        r = api_client.get("/api/search")
        assert r.status_code == 422

    def test_get_search_type_filter(self, api_client):
        r = api_client.get("/api/search", params={"q": "rsrp", "type": "field", "k": 5})
        assert r.status_code == 200
        body = r.json()
        for item in body["results"]:
            assert item["doc"]["type"] == "field"


class TestHealthIntegration:
    def test_health_now_includes_search_component(self, api_client):
        r = api_client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert "search" in body["components"]
        status = body["components"]["search"]["status"]
        assert status in ("ok", "degraded", "error")
        if status == "ok":
            assert body["components"]["search"]["index_version"] > 0

    def test_health_includes_sandbox_components(self, api_client):
        r = api_client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        # YARN and HDFS won't be available in unit tests, but the keys must exist
        assert "yarn" in body["components"]
        assert "hdfs" in body["components"]
