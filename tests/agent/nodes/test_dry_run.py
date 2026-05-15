"""tests/agent/nodes/test_dry_run.py — slice 2c 修订版。"""
from unittest.mock import MagicMock

from backend.agent.nodes.dry_run import dry_run
from backend.sandbox.models import DryRunResult


def test_dry_run_success_clears_error_feedback(monkeypatch):
    monkeypatch.setattr("backend.agent.nodes.dry_run.execute_with_retry",
                        lambda code, code_type, llm_client, max_retries:
                        DryRunResult(success=True, preview_row={"a": 1}))
    monkeypatch.setattr("backend.agent.nodes.dry_run.build_chat_client",
                        lambda **kw: MagicMock())
    out = dry_run({"generated_code": "SELECT 1", "code_type": "spark_sql"})
    assert out["dry_run_result"]["success"] is True
    assert out["error_feedback"] is None


def test_dry_run_failure_writes_error_feedback_truncated(monkeypatch):
    monkeypatch.setattr("backend.agent.nodes.dry_run.execute_with_retry",
                        lambda *a, **kw: DryRunResult(success=False, error_log="x" * 3000))
    monkeypatch.setattr("backend.agent.nodes.dry_run.build_chat_client",
                        lambda **kw: MagicMock())
    out = dry_run({"generated_code": "BAD", "code_type": "spark_sql"})
    assert out["dry_run_result"]["success"] is False
    assert len(out["error_feedback"]) <= 2000


def test_dry_run_unknown_code_type_returns_error():
    out = dry_run({"generated_code": "x", "code_type": "no_such_type"})
    assert out["dry_run_result"]["success"] is False
    assert "code_type" in out["error_feedback"]
