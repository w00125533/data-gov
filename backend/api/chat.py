"""/api/chat/* - SSE 流式对话 (spec §6.7)。"""
from __future__ import annotations
import asyncio, json
from queue import Empty, Queue
from threading import Thread
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from backend.agent.graph import build_graph
from backend.clients.deepseek import build_chat_client

router = APIRouter()


class ChatStartRequest(BaseModel):
    context: str | None = None
    table: str | None = None
    field: str | None = None
    mode: str | None = None


class ChatMessageRequest(BaseModel):
    session_id: str
    content: str


@router.post("/api/chat/start")
def chat_start(request: Request, payload: ChatStartRequest | None = None) -> dict:
    context = payload.model_dump(exclude_none=True) if payload else {}
    sess = request.app.state.chat_store.new(state={"context": context})
    return {"session_id": sess.id, "context": context}


@router.post("/api/chat/message")
async def chat_message(request: Request, payload: ChatMessageRequest):
    store = request.app.state.chat_store
    searcher = request.app.state.searcher
    try:
        sess = store.get(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session_id")
    store.append_message(sess.id, role="user", content=payload.content)
    llm_client = build_chat_client(temperature=0.0)
    graph = build_graph(llm_client=llm_client, searcher=searcher)
    initial_state = {"messages": list(sess.messages), **sess.state}
    queue: Queue = Queue()

    def runner():
        try:
            for chunk in graph.stream(initial_state, stream_mode="updates"):
                for node, partial in chunk.items():
                    safe_partial = {k: (str(v) if not isinstance(v, (dict, list, str, int, float, bool, type(None))) else v) for k, v in partial.items()}
                    queue.put({"event": "node_complete", "node": node, "partial": safe_partial})
                    if node == "presenter" and partial.get("final_message"):
                        presenter_payload = partial.get("presenter_payload") or {"type": "presenter", "summary": partial.get("final_message")}
                        store.set_last_result(sess.id, presenter_payload)
                        queue.put({"event": "presenter_payload", "summary": partial.get("final_message"), "payload": presenter_payload})
            queue.put({"event": "done"})
        except Exception as e:
            queue.put({"event": "error", "detail": str(e)})

    Thread(target=runner, daemon=True).start()

    async def event_gen():
        while True:
            try:
                item = queue.get(timeout=0.05)
            except Empty:
                await asyncio.sleep(0.05)
                continue
            yield {"event": "message", "data": json.dumps(item, ensure_ascii=False)}
            if item.get("event") in {"done", "error"}:
                return

    return EventSourceResponse(event_gen())


@router.get("/api/chat/{session_id}/history")
def chat_history(session_id: str, request: Request) -> dict:
    try:
        sess = request.app.state.chat_store.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session_id")
    return {"session_id": session_id, "messages": sess.messages}


@router.get("/api/chat/{session_id}/result")
def chat_result(session_id: str, request: Request) -> dict:
    try:
        sess = request.app.state.chat_store.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session_id")
    return sess.last_result or {"type": "empty"}
