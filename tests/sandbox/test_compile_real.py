"""tests/sandbox/test_compile_real.py — 真实 mvn 编译测试。仅在容器内（有 mvn）通过。"""
import pathlib

import pytest

from backend.sandbox.compile import maven_compile
from backend.sandbox.templates import inject

pytestmark = pytest.mark.infra


def test_compile_real_spark_sql_template(tmp_path):
    dest = tmp_path / "proj"
    inject(code_type="spark_sql", dest_dir=dest, user_code="SELECT 1 AS x", sandbox_uuid="t1")
    r = maven_compile(dest)
    assert r.success is True, r.error_log
    assert pathlib.Path(r.jar_path).exists()
