"""tests/sandbox/test_hdfs.py -- monkeypatch subprocess.run."""
from unittest.mock import MagicMock

import pytest

from backend.sandbox.hdfs import HdfsError, hdfs_cat, hdfs_mkdir, hdfs_put, hdfs_rm


def _run_ok(stdout: str = "", stderr: str = ""):
    m = MagicMock()
    m.returncode = 0
    m.stdout = stdout
    m.stderr = stderr
    return m


def _run_fail(stderr: str = "boom", code: int = 1):
    m = MagicMock()
    m.returncode = code
    m.stdout = ""
    m.stderr = stderr
    return m


def test_hdfs_put_builds_correct_cmd(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output=True, text=True, timeout=None, check=False):
        captured["cmd"] = cmd
        return _run_ok()

    monkeypatch.setattr("backend.sandbox.hdfs.subprocess.run", fake_run)
    hdfs_put("/local/x.jar", "/tmp/x.jar")
    assert "dfs" in captured["cmd"]
    assert "-put" in captured["cmd"]
    assert "/local/x.jar" in captured["cmd"]
    assert "/tmp/x.jar" in captured["cmd"]


def test_hdfs_put_raises_on_nonzero(monkeypatch):
    monkeypatch.setattr("backend.sandbox.hdfs.subprocess.run",
                        lambda *a, **kw: _run_fail("permission denied"))
    with pytest.raises(HdfsError, match="permission denied"):
        hdfs_put("/x", "/y")


def test_hdfs_cat_returns_stdout(monkeypatch):
    monkeypatch.setattr("backend.sandbox.hdfs.subprocess.run",
                        lambda *a, **kw: _run_ok(stdout='{"a":1}\n'))
    text = hdfs_cat("/tmp/out/part-0.json")
    assert text == '{"a":1}\n'


def test_hdfs_mkdir_uses_p_flag(monkeypatch):
    captured = {}
    monkeypatch.setattr("backend.sandbox.hdfs.subprocess.run",
                        lambda cmd, **kw: (captured.setdefault("cmd", cmd), _run_ok())[1])
    hdfs_mkdir("/tmp/sandbox/jars")
    assert "-mkdir" in captured["cmd"]
    assert "-p" in captured["cmd"]


def test_hdfs_rm_recursive(monkeypatch):
    captured = {}
    monkeypatch.setattr("backend.sandbox.hdfs.subprocess.run",
                        lambda cmd, **kw: (captured.setdefault("cmd", cmd), _run_ok())[1])
    hdfs_rm("/tmp/sandbox/out/abc", recursive=True)
    assert "-rm" in captured["cmd"] and "-r" in captured["cmd"]
