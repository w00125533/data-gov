"""tests/sandbox/test_controller.py -- 全链路 mock 单测。"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.sandbox.controller import SandboxController, execute
from backend.sandbox.models import CompileResult, DryRunResult, SubmitResult


def _ok_compile(_dir):
    return CompileResult(success=True, jar_path="/tmp/x.jar")


def _ok_submit_spark(_jar, main_class=None):
    return "application_x_0001"


def _ok_submit_flink(_jar, main_class=None):
    return "application_x_0002"


def _ok_wait(_app, **kw):
    return SubmitResult(application_id=_app, final_state="FINISHED")


def _cat_one_row(_path):
    return '{"cell_id":"1","avg_rsrp":-95.0}\n'


def _ls(_path):
    return ["/tmp/sandbox/out/x/part-00000-xxx.json"]


def test_execute_spark_sql_happy_path(monkeypatch, tmp_path):
    monkeypatch.setenv("SANDBOX_BASE_DIR", str(tmp_path))
    from backend.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setattr("backend.sandbox.controller.maven_compile", _ok_compile)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_mkdir", lambda p: None)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_put", lambda l, r: None)
    monkeypatch.setattr("backend.sandbox.controller.spark_submit", _ok_submit_spark)
    monkeypatch.setattr("backend.sandbox.controller.wait_for_app", _ok_wait)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_ls", _ls)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_cat", _cat_one_row)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_rm", lambda p, recursive=True: None)
    monkeypatch.setattr("backend.sandbox.controller.inject", lambda **kw: kw["dest_dir"])

    result = execute("SELECT * FROM dwd_session_qos", "spark_sql")
    assert isinstance(result, DryRunResult)
    assert result.success is True
    assert result.preview_row["cell_id"] == "1"
    assert result.application_id == "application_x_0001"


def test_execute_compile_failure_returns_dry_run_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("SANDBOX_BASE_DIR", str(tmp_path))
    from backend.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setattr("backend.sandbox.controller.maven_compile",
                        lambda d: CompileResult(success=False, error_log="cannot find symbol"))
    monkeypatch.setattr("backend.sandbox.controller.hdfs_rm", lambda p, recursive=True: None)
    monkeypatch.setattr("backend.sandbox.controller.inject", lambda **kw: kw["dest_dir"])

    result = execute("BAD SQL", "spark_sql")
    assert result.success is False
    assert "cannot find symbol" in result.error_log
    assert result.application_id is None


def test_execute_yarn_failure_returns_dry_run_failure(monkeypatch, tmp_path):
    from backend.sandbox.yarn import YarnError
    monkeypatch.setenv("SANDBOX_BASE_DIR", str(tmp_path))
    from backend.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setattr("backend.sandbox.controller.maven_compile", _ok_compile)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_mkdir", lambda p: None)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_put", lambda l, r: None)
    monkeypatch.setattr("backend.sandbox.controller.spark_submit", _ok_submit_spark)

    def boom(*a, **kw):
        raise YarnError("FAILED: NullPointerException")
    monkeypatch.setattr("backend.sandbox.controller.wait_for_app", boom)
    monkeypatch.setattr("backend.sandbox.controller.fetch_app_diagnostics",
                        lambda a, **kw: "java.lang.NullPointerException\n\tat Foo.bar(Foo.java:17)")
    monkeypatch.setattr("backend.sandbox.controller.hdfs_rm", lambda p, recursive=True: None)
    monkeypatch.setattr("backend.sandbox.controller.inject", lambda **kw: kw["dest_dir"])

    result = execute("SELECT 1", "spark_sql")
    assert result.success is False
    assert "NullPointerException" in result.error_log


def test_execute_dispatches_flink_sql(monkeypatch, tmp_path):
    monkeypatch.setenv("SANDBOX_BASE_DIR", str(tmp_path))
    from backend.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setattr("backend.sandbox.controller.maven_compile", _ok_compile)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_mkdir", lambda p: None)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_put", lambda l, r: None)
    captured = {}
    def fake_flink(jar, main_class=None):
        captured["called_flink"] = True
        return "application_x_0002"
    monkeypatch.setattr("backend.sandbox.controller.flink_run", fake_flink)
    monkeypatch.setattr("backend.sandbox.controller.wait_for_app", _ok_wait)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_ls", _ls)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_cat", _cat_one_row)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_rm", lambda p, recursive=True: None)
    monkeypatch.setattr("backend.sandbox.controller.inject", lambda **kw: kw["dest_dir"])

    result = execute("INSERT INTO sandbox_sink SELECT 1", "flink_sql")
    assert result.success is True
    assert captured.get("called_flink") is True


def test_execute_unknown_code_type_raises():
    with pytest.raises(ValueError, match="code_type"):
        execute("x", "python")
