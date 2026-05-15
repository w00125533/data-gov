"""tests/sandbox/test_submit.py -- monkeypatch subprocess.run; 解析 app_id."""
from unittest.mock import MagicMock

import pytest

from backend.sandbox.submit import (
    SubmitError, flink_run, parse_app_id_from_flink, parse_app_id_from_spark, spark_submit,
)


def _r(rc=0, stdout="", stderr=""):
    m = MagicMock()
    m.returncode = rc
    m.stdout = stdout
    m.stderr = stderr
    return m


SPARK_STDERR = """24/05/14 10:00:01 INFO yarn.Client: Submitting application application_1715680000000_0042 to ResourceManager
24/05/14 10:00:02 INFO yarn.Client: Application report for application_1715680000000_0042 (state: SUBMITTED)
"""

FLINK_STDOUT = """SLF4J: Class path contains multiple SLF4J bindings.
Job has been submitted with JobID 1234abcd
2024-05-14 10:00:05,123 INFO  org.apache.flink.yarn.YarnClusterClientFactory  [] - Submitting application_1715680000000_0099 to YARN
"""


def test_parse_app_id_from_spark():
    assert parse_app_id_from_spark(SPARK_STDERR) == "application_1715680000000_0042"


def test_parse_app_id_from_flink():
    assert parse_app_id_from_flink(FLINK_STDOUT) == "application_1715680000000_0099"


def test_parse_app_id_returns_empty_when_absent():
    assert parse_app_id_from_spark("nothing here") == ""
    assert parse_app_id_from_flink("nothing here") == ""


def test_spark_submit_returns_app_id(monkeypatch):
    monkeypatch.setattr("backend.sandbox.submit.subprocess.run",
                        lambda *a, **kw: _r(stdout="", stderr=SPARK_STDERR))
    app_id = spark_submit("hdfs:///tmp/x.jar")
    assert app_id == "application_1715680000000_0042"


def test_spark_submit_raises_on_failure(monkeypatch):
    monkeypatch.setattr("backend.sandbox.submit.subprocess.run",
                        lambda *a, **kw: _r(rc=1, stderr="ClassNotFoundException"))
    with pytest.raises(SubmitError, match="ClassNotFoundException"):
        spark_submit("hdfs:///tmp/x.jar")


def test_flink_run_returns_app_id(monkeypatch):
    monkeypatch.setattr("backend.sandbox.submit.subprocess.run",
                        lambda *a, **kw: _r(stdout=FLINK_STDOUT, stderr=""))
    assert flink_run("hdfs:///tmp/x.jar") == "application_1715680000000_0099"
