"""tests/agent/test_api_chat.py - /api/chat/* SSE 流式对话 endpoints."""
import json
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_mocks(monkeypatch, tmp_path):
    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            return np.array([[hash(t) % 100 / 100.0] * 16 for t in texts])

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer", lambda name: StubEncoder()
    )
    monkeypatch.setenv("SEARCH_BOOTSTRAP_FROM_SEED", "1")
    monkeypatch.setenv("SEARCH_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    from backend.config import get_settings

    get_settings.cache_clear()

    class StubDriver:
        def verify_connectivity(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(
        "backend.metadata.graph.GraphDatabase.driver",
        lambda uri, auth: StubDriver(),
    )
    monkeypatch.setattr(
        "backend.metadata.graph.run_query", lambda cypher, **params: [{"n": 10}]
    )

    fake_llm = MagicMock()
    msgs = [
        MagicMock(
            content=json.dumps({"intent": "forward_etl", "confidence": 0.95})
        ),
        MagicMock(
            content=json.dumps(
                {
                    "target_entities": ["x"],
                    "source_hints": [],
                    "code_type_hint": "spark_sql",
                }
            )
        ),
        MagicMock(content=json.dumps([])),
        MagicMock(content="```spark-sql\nSELECT 1\n```"),
    ]
    fake_llm.invoke.side_effect = msgs * 5
    monkeypatch.setattr(
        "backend.api.chat.build_chat_client", lambda **kw: fake_llm
    )
    from backend.agent.sandbox_stub import DryRunResult

    monkeypatch.setattr(
        "backend.agent.nodes.dry_run.sandbox.execute",
        lambda code, code_type: DryRunResult(
            success=True, preview_row={"a": 1}
        ),
    )

    from backend.main import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client


def test_post_chat_start_returns_session_id(app_with_mocks):
    r = app_with_mocks.post("/api/chat/start")
    assert r.status_code == 200
    assert r.json()["session_id"].startswith("chat_")


def test_post_chat_message_streams_sse(app_with_mocks):
    sid = app_with_mocks.post("/api/chat/start").json()["session_id"]
    with app_with_mocks.stream(
        "POST",
        "/api/chat/message",
        json={"session_id": sid, "content": "求平均 RSRP"},
    ) as resp:
        assert resp.status_code == 200
        events = []
        for line in resp.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    assert events


def test_get_chat_history(app_with_mocks):
    sid = app_with_mocks.post("/api/chat/start").json()["session_id"]
    r = app_with_mocks.get(f"/api/chat/{sid}/history")
    assert r.status_code == 200
    assert "messages" in r.json()


def test_get_chat_result(app_with_mocks):
    sid = app_with_mocks.post("/api/chat/start").json()["session_id"]
    r = app_with_mocks.get(f"/api/chat/{sid}/result")
    assert r.status_code == 200
    assert "type" in r.json()
