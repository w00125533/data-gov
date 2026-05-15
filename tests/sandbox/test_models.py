"""tests/sandbox/test_models.py"""
from backend.sandbox.models import CompileResult, DryRunResult, SubmitResult


def test_compile_result_defaults():
    r = CompileResult(success=True, jar_path="/tmp/x.jar")
    assert r.success
    assert r.error_log is None


def test_dry_run_result_compatible_with_slice2b_stub():
    """slice 2b 期望的字段必须存在。"""
    r = DryRunResult(success=True, preview_row={"a": 1}, error_log=None, application_id="app_1")
    assert r.success and r.preview_row == {"a": 1}


def test_submit_result_fields():
    s = SubmitResult(application_id="app_1", final_state="FINISHED", diagnostics="")
    assert s.application_id == "app_1"
    assert s.final_state == "FINISHED"


def test_config_sandbox_defaults(monkeypatch):
    from backend.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    assert s.sandbox_base_dir == "/tmp/sandbox"
    assert s.sandbox_hdfs_base == "/tmp/sandbox"
    assert s.sandbox_total_timeout == 60
    assert s.sandbox_compile_timeout == 20
    assert s.sandbox_spark_timeout == 30
    assert s.sandbox_flink_timeout == 45
    assert s.sandbox_max_retries == 2
    assert s.yarn_rm_url == "http://resourcemanager:8088"
    assert s.hdfs_defaultfs == "hdfs://namenode:8020"
