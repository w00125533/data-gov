"""dry_run 节点 - spec §4.1。沙箱真实实现在 slice 2c。"""
from __future__ import annotations

from dataclasses import asdict

from backend.agent import sandbox_stub as sandbox

VALID_CODE_TYPES = {"spark_sql", "flink_sql", "java_flink"}


def dry_run(state: dict) -> dict:
    code_type = state.get("code_type", "")
    if code_type not in VALID_CODE_TYPES:
        return {
            "dry_run_result": {
                "success": False,
                "preview_row": None,
                "error_log": f"unknown code_type: {code_type!r}",
                "application_id": None,
            },
            "error_feedback": f"unknown code_type: {code_type!r}",
        }
    result = sandbox.execute(state.get("generated_code", ""), code_type)
    payload = asdict(result)
    if result.success:
        return {"dry_run_result": payload, "error_feedback": None}
    err = (result.error_log or "")[:2000]
    return {"dry_run_result": payload, "error_feedback": err}
