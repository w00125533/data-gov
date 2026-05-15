"""tests/agent/nodes/test_dry_run_retry_integration.py"""
from unittest.mock import MagicMock

from backend.agent.nodes.dry_run import dry_run
from backend.sandbox.models import DryRunResult


def test_dry_run_node_uses_execute_with_retry(monkeypatch):
    calls = []

    def fake_retry(code, code_type, llm_client, max_retries):
        calls.append((code, code_type, max_retries))
        return DryRunResult(success=True, preview_row={"a": 1})

    monkeypatch.setattr("backend.agent.nodes.dry_run.execute_with_retry", fake_retry)
    monkeypatch.setattr("backend.agent.nodes.dry_run.build_chat_client",
                        lambda **kw: MagicMock())
    out = dry_run({"generated_code": "SELECT 1", "code_type": "spark_sql"})
    assert out["dry_run_result"]["success"] is True
    assert calls and calls[0][1] == "spark_sql"
    assert calls[0][2] == 2  # spec §4.5 沙箱层 2 轮


def test_dry_run_node_unknown_code_type_still_returns_error():
    out = dry_run({"generated_code": "x", "code_type": "py"})
    assert out["dry_run_result"]["success"] is False
    assert "code_type" in out["error_feedback"]
