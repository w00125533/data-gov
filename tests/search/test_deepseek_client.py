"""tests for backend.clients.deepseek -- DeepSeek ChatOpenAI shared client."""
from unittest.mock import MagicMock

import pytest
from backend.clients.deepseek import get_deepseek_client, build_chat_client


def test_build_chat_client_uses_settings(monkeypatch):
    captured = {}

    def fake_chat(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="ChatOpenAI")

    monkeypatch.setattr("backend.clients.deepseek.ChatOpenAI", fake_chat)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-zzz")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    from backend.config import get_settings

    get_settings.cache_clear()

    client = build_chat_client(temperature=0.3)
    assert captured["api_key"] == "sk-zzz"
    assert captured["base_url"] == "https://api.deepseek.test"
    assert captured["model"] == "deepseek-chat"
    assert captured["temperature"] == 0.3


def test_get_deepseek_client_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    from backend.config import get_settings

    get_settings.cache_clear()
    get_deepseek_client.cache_clear()
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        get_deepseek_client()
