"""dry_run 节点 — slice 2c 起走 sandbox 层 execute_with_retry。"""
from __future__ import annotations

from dataclasses import asdict

from backend.clients.deepseek import build_chat_client
from backend.config import get_settings
from backend.sandbox.retry import execute_with_retry


VALID_CODE_TYPES = {"spark_sql", "flink_sql", "java_flink"}


def dry_run(state: dict) -> dict:
    code_type = state.get("code_type", "")
    if code_type not in VALID_CODE_TYPES:
        return {
            "dry_run_result": {"success": False, "preview_row": None,
                                "error_log": f"unknown code_type: {code_type!r}",
                                "application_id": None},
            "error_feedback": f"unknown code_type: {code_type!r}",
        }
    settings = get_settings()
    try:
        client = build_chat_client(temperature=0.0)
    except RuntimeError:
        # DeepSeek 没配 key — 跑无重试模式 (Agent 层会接管)
        from backend.sandbox.controller import execute as raw_execute
        result = raw_execute(state.get("generated_code", ""), code_type)
    else:
        result = execute_with_retry(
            state.get("generated_code", ""), code_type,
            llm_client=client,
            max_retries=settings.sandbox_max_retries,
        )
    payload = asdict(result)
    if result.success:
        return {"dry_run_result": payload, "error_feedback": None}
    err = (result.error_log or "")[:2000]
    return {"dry_run_result": payload, "error_feedback": err}
