"""tests/sandbox/test_error_parser.py"""
from backend.sandbox.error_parser import parse_maven_error, parse_yarn_diagnostics


MVN_STDERR_COMPILE_FAIL = """[INFO] --- maven-compiler-plugin:3.10.1:compile ---
[ERROR] /tmp/sandbox/abc/src/main/java/SandboxSparkJob.java:[24,16] cannot find symbol
  symbol:   class Dataset2
  location: package org.apache.spark.sql
[INFO] 1 error
[INFO] BUILD FAILURE
"""

YARN_DIAG_NULL_POINTER = """Application application_1234_0001 failed 2 times due to AM Container for appattempt_xxx exited with  exitCode: 1
For more detailed output, check application tracking page:http://rm:8088/cluster/app/application_1234_0001Then click on links to logs of each attempt.
Diagnostics: Exception from container-launch.
Container exited with a non-zero exit code 1
java.lang.NullPointerException
\tat org.example.UserJob.main(UserJob.java:17)
"""


def test_parse_maven_error_extracts_first_error_line():
    summary = parse_maven_error(MVN_STDERR_COMPILE_FAIL)
    assert "cannot find symbol" in summary
    assert "Dataset2" in summary
    assert "SandboxSparkJob.java" in summary


def test_parse_maven_error_truncates_to_2000_chars():
    big = MVN_STDERR_COMPILE_FAIL + ("x" * 5000)
    assert len(parse_maven_error(big)) <= 2000


def test_parse_yarn_diagnostics_extracts_exception_name():
    summary = parse_yarn_diagnostics(YARN_DIAG_NULL_POINTER)
    assert "NullPointerException" in summary
    assert "UserJob.java:17" in summary or "UserJob" in summary


def test_parse_yarn_diagnostics_handles_empty():
    assert parse_yarn_diagnostics("") == ""


def test_parse_maven_error_handles_no_error_markers():
    assert parse_maven_error("BUILD SUCCESS") == ""
