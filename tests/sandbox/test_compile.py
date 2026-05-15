"""tests/sandbox/test_compile.py"""
from unittest.mock import MagicMock

import pytest

from backend.sandbox.compile import maven_compile


def _r(returncode=0, stdout="", stderr=""):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


def test_compile_success_returns_jar_path(monkeypatch, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "sandbox-spark-sql.jar").write_bytes(b"\x00")

    monkeypatch.setattr("backend.sandbox.compile.subprocess.run",
                        lambda *a, **kw: _r(0, "BUILD SUCCESS"))
    r = maven_compile(tmp_path)
    assert r.success is True
    assert r.jar_path.endswith(".jar")


def test_compile_failure_returns_parsed_error(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.sandbox.compile.subprocess.run",
                        lambda *a, **kw: _r(1, "[INFO] xxx\n[ERROR] /x.java:[10,5] cannot find symbol\n[INFO] BUILD FAILURE"))
    r = maven_compile(tmp_path)
    assert r.success is False
    assert "cannot find symbol" in r.error_log


def test_compile_picks_first_jar_under_target(monkeypatch, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "sandbox-flink-sql.jar").write_bytes(b"\x00")
    monkeypatch.setattr("backend.sandbox.compile.subprocess.run",
                        lambda *a, **kw: _r(0))
    r = maven_compile(tmp_path)
    assert r.jar_path.endswith("sandbox-flink-sql.jar")
