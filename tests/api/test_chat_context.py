from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent.chat_session import ChatSessionStore
from backend.api.chat import router


def test_chat_start_persists_context():
    app = FastAPI()
    app.state.chat_store = ChatSessionStore()
    app.include_router(router)

    res = TestClient(app).post(
        "/api/chat/start",
        json={"context": "lineage", "table": "dws_cell_hourly", "field": "drop_rate"},
    )

    assert res.status_code == 200
    payload = res.json()
    sess = app.state.chat_store.get(payload["session_id"])
    assert payload["context"] == {
        "context": "lineage",
        "table": "dws_cell_hourly",
        "field": "drop_rate",
    }
    assert sess.state["context"]["table"] == "dws_cell_hourly"
