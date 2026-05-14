"""tests/agent/test_sandbox_stub.py"""
import pytest

from backend.agent.sandbox_stub import DryRunResult, execute


def test_dry_run_result_dataclass_shape():
    r = DryRunResult(success=True, preview_row={"a": 1}, error_log=None, application_id="app_001")
    assert r.success is True
    assert r.preview_row == {"a": 1}
    assert r.error_log is None
    assert r.application_id == "app_001"


def test_execute_raises_not_implemented_by_default():
    with pytest.raises(NotImplementedError, match="slice 2c"):
        execute("SELECT 1", "spark_sql")


def test_execute_monkeypatched_returns_stub_success(monkeypatch):
    from backend.agent import sandbox_stub

    def fake(code, code_type):
        return DryRunResult(success=True, preview_row={"x": 1})

    monkeypatch.setattr(sandbox_stub, "execute", fake)
    r = sandbox_stub.execute("...", "spark_sql")
    assert r.success and r.preview_row == {"x": 1}
