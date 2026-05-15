"""tests/sandbox/test_templates.py"""
from pathlib import Path

import pytest

from backend.sandbox.templates import load_template, inject


def test_load_template_returns_dir(tmp_path):
    src = load_template("spark_sql")
    assert (src / "pom.xml").exists()
    assert (src / "src/main/java/SandboxSparkJob.java").exists()


def test_load_template_unknown_raises():
    with pytest.raises(ValueError, match="code_type"):
        load_template("python")


def test_inject_replaces_placeholders(tmp_path):
    dest = tmp_path / "project"
    inject(
        code_type="spark_sql",
        dest_dir=dest,
        user_code="SELECT 1 AS x",
        sandbox_uuid="abc123",
    )
    java = (dest / "src/main/java/SandboxSparkJob.java").read_text(encoding="utf-8")
    assert "abc123" in java
    assert "SELECT 1 AS x" in java
    assert "${user_sql}" not in java
    assert "${sandbox_uuid}" not in java


def test_inject_flink_java_replaces_user_code_block(tmp_path):
    dest = tmp_path / "p"
    body = (
        "public static void main(String[] args) throws Exception { "
        "System.out.println(SANDBOX_UUID); }"
    )
    inject(code_type="java_flink", dest_dir=dest, user_code=body, sandbox_uuid="u1")
    src = (dest / "src/main/java/io/datagov/sandbox/SandboxFlinkJob.java").read_text(encoding="utf-8")
    assert body in src
    assert "${user_code_block}" not in src
