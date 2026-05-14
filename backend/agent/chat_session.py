"""进程内 chat session 存储 - 单进程 FastAPI 验证场景够用。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional


@dataclass
class ChatSession:
    id: str
    messages: list[dict] = field(default_factory=list)
    state: dict = field(default_factory=dict)
    last_result: Optional[dict] = None


class ChatSessionStore:
    def __init__(self):
        self._sessions: dict[str, ChatSession] = {}
        self._lock = Lock()

    def new(self) -> ChatSession:
        with self._lock:
            sid = f"chat_{uuid.uuid4().hex[:12]}"
            s = ChatSession(id=sid)
            self._sessions[sid] = s
            return s

    def get(self, session_id: str) -> ChatSession:
        with self._lock:
            return self._sessions[session_id]

    def append_message(self, session_id: str, *, role: str, content: str) -> None:
        with self._lock:
            self._sessions[session_id].messages.append({"role": role, "content": content})

    def set_last_result(self, session_id: str, result: dict) -> None:
        with self._lock:
            self._sessions[session_id].last_result = result
