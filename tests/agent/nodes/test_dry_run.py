"""Tests for dry_run node - spec §4.1."""
from __future__ import annotations

from unittest import mock

import pytest

from backend.agent.nodes.dry_run import VALID_CODE_TYPES, dry_run
from backend.agent.sandbox_stub import DryRunResult


def _fake_success(preview: dict | None = None) -> DryRunResult:
    return DryRunResult(
        success=True,
        preview_row=preview or {"col1": "val1"},
        error_log=None,
        application_id="app-001",
    )


def _fake_failure(error_log: str) -> DryRunResult:
    return DryRunResult(
        success=False,
        preview_row=None,
        error_log=error_log,
        application_id=None,
    )


class TestDryRunSuccess:
    """dry_run 成功分支。"""

    def test_success_clears_error_feedback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "backend.agent.nodes.dry_run.sandbox.execute",
            lambda code, ct: _fake_success({"cnt": 42}),
        )
        state = {
            "code_type": "spark_sql",
            "generated_code": "SELECT 1",
            "error_feedback": "previous error",
        }
        result = dry_run(state)
        assert result["error_feedback"] is None
        assert result["dry_run_result"]["success"] is True
        assert result["dry_run_result"]["application_id"] == "app-001"
        assert result["dry_run_result"]["preview_row"] == {"cnt": 42}


class TestDryRunFailure:
    """dry_run 失败分支。"""

    def test_truncates_error_log_to_2000(self, monkeypatch: pytest.MonkeyPatch) -> None:
        long_error = "ERROR: " + "x" * 3000
        monkeypatch.setattr(
            "backend.agent.nodes.dry_run.sandbox.execute",
            lambda code, ct: _fake_failure(long_error),
        )
        state = {
            "code_type": "spark_sql",
            "generated_code": "SELECT BAD",
            "error_feedback": None,
        }
        result = dry_run(state)
        assert result["error_feedback"] is not None
        assert len(result["error_feedback"]) == 2000
        assert result["dry_run_result"]["success"] is False
        assert result["dry_run_result"]["error_log"] == long_error  # 原始 log 不截断

    def test_short_error_not_truncated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        short_error = "Syntax error at line 1"
        monkeypatch.setattr(
            "backend.agent.nodes.dry_run.sandbox.execute",
            lambda code, ct: _fake_failure(short_error),
        )
        state = {
            "code_type": "spark_sql",
            "generated_code": "SELECT BAD",
            "error_feedback": None,
        }
        result = dry_run(state)
        assert result["error_feedback"] == short_error

    def test_none_error_log(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """error_log 为 None 时返回空字符串。"""
        monkeypatch.setattr(
            "backend.agent.nodes.dry_run.sandbox.execute",
            lambda code, ct: DryRunResult(
                success=False, preview_row=None, error_log=None, application_id=None
            ),
        )
        state = {
            "code_type": "spark_sql",
            "generated_code": "SELECT BAD",
            "error_feedback": "old",
        }
        result = dry_run(state)
        assert result["error_feedback"] == ""


class TestDryRunUnknownCodeType:
    """未知 code_type 的校验。"""

    def test_unknown_code_type_returns_error(self) -> None:
        state = {
            "code_type": "unknown_type",
            "generated_code": "SELECT 1",
        }
        result = dry_run(state)
        assert result["error_feedback"] == "unknown code_type: 'unknown_type'"
        assert result["dry_run_result"]["success"] is False
        assert result["dry_run_result"]["application_id"] is None

    def test_empty_code_type(self) -> None:
        state = {
            "code_type": "",
            "generated_code": "SELECT 1",
        }
        result = dry_run(state)
        assert result["dry_run_result"]["success"] is False

    def test_valid_code_types_not_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for ct in VALID_CODE_TYPES:
            monkeypatch.setattr(
                "backend.agent.nodes.dry_run.sandbox.execute",
                lambda code, ct=ct: _fake_success(),
            )
            state = {
                "code_type": ct,
                "generated_code": "SELECT 1",
            }
            result = dry_run(state)
            assert result["dry_run_result"]["success"] is True, f"failed for {ct}"

    def test_does_not_call_sandbox_for_unknown_type(self) -> None:
        """未知类型时不应调用 sandbox.execute。"""
        with mock.patch("backend.agent.nodes.dry_run.sandbox.execute") as mock_exec:
            state = {
                "code_type": "bad_type",
                "generated_code": "SELECT 1",
            }
            dry_run(state)
            mock_exec.assert_not_called()
