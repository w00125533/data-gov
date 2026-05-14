"""tests/agent/test_settings.py"""
from backend.config import get_settings


def test_agent_settings_defaults(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("AGENT_MAX_ITERATIONS", raising=False)
    monkeypatch.delenv("GIT_AUTHOR_NAME", raising=False)
    monkeypatch.delenv("GIT_AUTHOR_EMAIL", raising=False)
    s = get_settings()
    assert s.agent_max_iterations == 3
    assert s.git_author_name == "Data-Gov Agent"
    assert s.git_author_email == "agent@data-gov.local"


def test_agent_settings_env_overrides(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", "5")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test Bot")
    s = get_settings()
    assert s.agent_max_iterations == 5
    assert s.git_author_name == "Test Bot"
