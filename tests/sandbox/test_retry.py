"""tests/sandbox/test_retry.py -- mock controller.execute + LLM client."""
from unittest.mock import MagicMock

from backend.sandbox.models import DryRunResult
from backend.sandbox.retry import execute_with_retry


def _llm_returns(*responses):
    client = MagicMock()
    msgs = []
    for r in responses:
        m = MagicMock()
        m.content = r
        msgs.append(m)
    client.invoke.side_effect = msgs
    return client


def test_retry_returns_success_on_first_try(monkeypatch):
    monkeypatch.setattr(
        "backend.sandbox.retry.execute",
        lambda code, code_type: DryRunResult(success=True, preview_row={"a": 1}),
    )
    client = MagicMock()
    out = execute_with_retry("SELECT 1", "spark_sql", llm_client=client, max_retries=2)
    assert out.success is True
    client.invoke.assert_not_called()


def test_retry_invokes_llm_once_on_first_failure_then_succeeds(monkeypatch):
    calls = []

    def fake_exec(code, code_type):
        calls.append(code)
        if len(calls) == 1:
            return DryRunResult(success=False, error_log="cannot find symbol Dataset2")
        return DryRunResult(success=True, preview_row={"x": 1})

    monkeypatch.setattr("backend.sandbox.retry.execute", fake_exec)
    fixed = "```spark-sql\nSELECT 1 AS fixed\n```"
    client = _llm_returns(fixed)
    out = execute_with_retry("BAD", "spark_sql", llm_client=client, max_retries=2)
    assert out.success is True
    assert client.invoke.call_count == 1
    # 第二次 execute 接收到 LLM 修正后的代码
    assert "SELECT 1 AS fixed" in calls[1]


def test_retry_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(
        "backend.sandbox.retry.execute",
        lambda code, code_type: DryRunResult(success=False, error_log="always broken"),
    )
    client = _llm_returns("```\nSELECT FIX 1\n```", "```\nSELECT FIX 2\n```")
    out = execute_with_retry("BAD", "spark_sql", llm_client=client, max_retries=2)
    assert out.success is False
    assert client.invoke.call_count == 2


def test_retry_passes_error_log_to_prompt(monkeypatch):
    captured_prompts = []

    def fake_exec(code, code_type):
        return DryRunResult(success=False, error_log="exception XYZ at line 17")

    def fake_invoke(prompt):
        captured_prompts.append(prompt)
        m = MagicMock()
        m.content = "```\nFIXED\n```"
        return m

    client = MagicMock()
    client.invoke.side_effect = fake_invoke
    monkeypatch.setattr("backend.sandbox.retry.execute", fake_exec)
    execute_with_retry("X", "spark_sql", llm_client=client, max_retries=1)
    assert any("exception XYZ" in p for p in captured_prompts)
