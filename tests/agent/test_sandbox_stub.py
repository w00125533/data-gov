"""tests/agent/test_sandbox_stub.py — slice 2c后, sandbox_stub 重新导出真实 controller。"""
from backend.agent.sandbox_stub import DryRunResult, execute
from backend.sandbox.controller import execute as real_execute


def test_dry_run_result_dataclass_shape():
    r = DryRunResult(success=True, preview_row={"a": 1}, error_log=None, application_id="app_001")
    assert r.success is True
    assert r.preview_row == {"a": 1}
    assert r.application_id == "app_001"


def test_execute_is_real_controller():
    """slice 2c 后 sandbox_stub.execute === backend.sandbox.controller.execute。"""
    assert execute is real_execute


def test_execute_monkeypatched_returns_stub_success(monkeypatch):
    """节点测试仍可 monkeypatch.setattr(backend.agent.sandbox_stub, 'execute', fake)。"""
    from backend.agent import sandbox_stub

    def fake(code, code_type):
        return DryRunResult(success=True, preview_row={"x": 1})

    monkeypatch.setattr(sandbox_stub, "execute", fake)
    r = sandbox_stub.execute("...", "spark_sql")
    assert r.success and r.preview_row == {"x": 1}
