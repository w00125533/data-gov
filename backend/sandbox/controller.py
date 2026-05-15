"""SandboxController.execute -- 7 步编排（spec §5.4）。

1. /tmp/sandbox/{uuid}/  目录
2. copy template + inject code
3. maven_compile()
4. upload JAR to HDFS
5. submit_and_wait()
6. read_result() -> 1 row
7. cleanup
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Literal

from backend.config import get_settings
from backend.sandbox.compile import maven_compile
from backend.sandbox.error_parser import parse_yarn_diagnostics
from backend.sandbox.hdfs import HdfsError, hdfs_cat, hdfs_ls, hdfs_mkdir, hdfs_put, hdfs_rm
from backend.sandbox.models import DryRunResult
from backend.sandbox.submit import SubmitError, flink_run, spark_submit
from backend.sandbox.templates import inject
from backend.sandbox.yarn import YarnError, fetch_app_diagnostics, wait_for_app


CodeType = Literal["spark_sql", "flink_sql", "java_flink"]


class SandboxController:
    """spec §5.4 控制器封装。每次 execute 用 uuid 隔离临时目录。"""

    def execute(self, code: str, code_type: CodeType) -> DryRunResult:
        if code_type not in ("spark_sql", "flink_sql", "java_flink"):
            raise ValueError(f"Unknown code_type: {code_type!r}")
        settings = get_settings()
        sandbox_uuid = uuid.uuid4().hex[:12]
        sandbox_dir = Path(settings.sandbox_base_dir) / sandbox_uuid
        hdfs_jar = f"{settings.sandbox_hdfs_base}/jars/{sandbox_uuid}.jar"
        hdfs_out = f"/tmp/sandbox/out/{sandbox_uuid}"

        try:
            sandbox_dir.parent.mkdir(parents=True, exist_ok=True)

            # 2) inject
            inject(
                code_type=code_type,
                dest_dir=sandbox_dir,
                user_code=code,
                sandbox_uuid=sandbox_uuid,
            )

            # 3) maven compile
            compile_result = maven_compile(sandbox_dir)
            if not compile_result.success:
                return DryRunResult(
                    success=False, error_log=compile_result.error_log,
                    application_id=None,
                )

            # 4) upload jar
            try:
                hdfs_mkdir(f"{settings.sandbox_hdfs_base}/jars")
                hdfs_put(compile_result.jar_path, hdfs_jar)
            except HdfsError as e:
                return DryRunResult(success=False, error_log=f"HDFS upload failed: {e}")

            # 5) submit + wait
            submit_fn = spark_submit if code_type == "spark_sql" else flink_run
            timeout = (settings.sandbox_spark_timeout if code_type == "spark_sql"
                       else settings.sandbox_flink_timeout)
            try:
                app_id = submit_fn(hdfs_jar)
            except SubmitError as e:
                return DryRunResult(success=False, error_log=str(e))
            try:
                wait_for_app(app_id, rm_url=settings.yarn_rm_url, timeout=timeout)
            except YarnError as e:
                diag = ""
                try:
                    diag = fetch_app_diagnostics(app_id, rm_url=settings.yarn_rm_url)
                except YarnError:
                    pass
                err = parse_yarn_diagnostics(diag) or str(e)
                return DryRunResult(success=False, error_log=err, application_id=app_id)

            # 6) read 1 row
            try:
                parts = hdfs_ls(hdfs_out)
                json_parts = [p for p in parts if p.endswith(".json") or "part-" in p]
                if not json_parts:
                    return DryRunResult(success=False,
                                         error_log="No output produced under " + hdfs_out,
                                         application_id=app_id)
                raw = hdfs_cat(json_parts[0])
                preview = self._parse_first_row(raw)
            except HdfsError as e:
                return DryRunResult(success=False, error_log=f"HDFS read failed: {e}",
                                     application_id=app_id)

            return DryRunResult(success=True, preview_row=preview, application_id=app_id)

        finally:
            # 7) cleanup
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            try:
                hdfs_rm(hdfs_jar, recursive=False)
            except HdfsError:
                pass
            try:
                hdfs_rm(hdfs_out, recursive=True)
            except HdfsError:
                pass

    @staticmethod
    def _parse_first_row(raw: str) -> dict | None:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return None


_singleton = SandboxController()


def execute(code: str, code_type: CodeType) -> DryRunResult:
    """模块级入口 -- slice 2b 的 sandbox_stub.execute 委托到这里。"""
    return _singleton.execute(code, code_type)
