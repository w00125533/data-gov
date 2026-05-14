"""tests/agent/test_chat_session.py"""
import pytest
from backend.agent.chat_session import ChatSession, ChatSessionStore


def test_new_session_has_unique_id_and_empty_messages():
    store = ChatSessionStore()
    s1 = store.new()
    s2 = store.new()
    assert s1.id != s2.id
    assert s1.messages == []


def test_get_returns_same_session():
    store = ChatSessionStore()
    s = store.new()
    assert store.get(s.id) is s


def test_get_unknown_id_raises():
    store = ChatSessionStore()
    with pytest.raises(KeyError):
        store.get("does-not-exist")


def test_append_message_persists():
    store = ChatSessionStore()
    s = store.new()
    store.append_message(s.id, role="user", content="hi")
    store.append_message(s.id, role="assistant", content="hello")
    msgs = store.get(s.id).messages
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "hi"
