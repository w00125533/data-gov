"""spark-submit / flink run 子进程包装。"""
from __future__ import annotations

import os
import re
import subprocess
from typing import Optional

from backend.config import get_settings


class SubmitError(RuntimeError):
    pass


_APP_ID_RE = re.compile(r"(application_\d+_\d+)")


def parse_app_id_from_spark(stderr: str) -> str:
    m = _APP_ID_RE.search(stderr)
    return m.group(1) if m else ""


def parse_app_id_from_flink(stdout: str) -> str:
    m = _APP_ID_RE.search(stdout)
    return m.group(1) if m else ""


def _spark_bin() -> str:
    return os.path.join(os.environ.get("SPARK_HOME", "/opt/spark"), "bin", "spark-submit")


def _flink_bin() -> str:
    return os.path.join(os.environ.get("FLINK_HOME", "/opt/flink"), "bin", "flink")


def spark_submit(jar_hdfs_path: str, *, main_class: Optional[str] = None) -> str:
    settings = get_settings()
    cmd = [
        _spark_bin(),
        "--master", "yarn",
        "--deploy-mode", "cluster",
        "--name", "data-gov-sandbox-spark",
        "--conf", "spark.yarn.submit.waitAppCompletion=false",
    ]
    if main_class:
        cmd += ["--class", main_class]
    cmd.append(jar_hdfs_path)

    r = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=settings.sandbox_spark_timeout, check=False,
    )
    if r.returncode != 0:
        raise SubmitError(f"spark-submit failed: {(r.stderr or r.stdout)[:1000]}")
    app_id = parse_app_id_from_spark(r.stderr) or parse_app_id_from_spark(r.stdout)
    if not app_id:
        raise SubmitError(f"Could not parse application_id from spark-submit output: {r.stderr[:500]}")
    return app_id


def flink_run(jar_hdfs_path: str, *, main_class: Optional[str] = None) -> str:
    settings = get_settings()
    cmd = [
        _flink_bin(), "run",
        "-d",  # detached
        "-m", "yarn-cluster",
        "-yqu", "default",
    ]
    if main_class:
        cmd += ["-c", main_class]
    cmd.append(jar_hdfs_path)

    r = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=settings.sandbox_flink_timeout, check=False,
    )
    if r.returncode != 0:
        raise SubmitError(f"flink run failed: {(r.stderr or r.stdout)[:1000]}")
    app_id = parse_app_id_from_flink(r.stdout) or parse_app_id_from_flink(r.stderr)
    if not app_id:
        raise SubmitError(f"Could not parse application_id from flink output: {r.stdout[:500]}")
    return app_id
