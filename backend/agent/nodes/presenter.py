"""presenter 节点 - 终止节点, 构造 UI 载荷 (spec §4.1)。"""
from __future__ import annotations
from typing import Any, Callable, Optional

def build_payload(state: dict) -> dict:
    if state.get("presenter_payload"):
        return state["presenter_payload"]
    if state.get("needs_clarification"):
        return {"type": "clarification", "summary": "需要澄清，请补充更多信息。"}
    intent = state.get("intent")
    vr = state.get("validation_result") or {}
    if intent == "schema_evolve":
        if vr.get("passed") is False:
            err_codes = [e[0] for e in vr.get("errors", [])]
            return {"type": "error", "summary": "校验未通过: " + ", ".join(err_codes), "errors": vr.get("errors", [])}
        if state.get("applied_changes"):
            return {"type": "schema_diff_card", "applied": state["applied_changes"], "warnings": vr.get("warnings", [])}
    dr = state.get("dry_run_result") or {}
    if dr:
        return {"type": "code_card", "code": state.get("generated_code", ""), "code_type": state.get("code_type"), "preview_row": dr.get("preview_row"), "success": bool(dr.get("success")), "error_log": dr.get("error_log"), "summary": "执行成功" if dr.get("success") else "执行失败，请查看错误日志"}
    return {"type": "error", "summary": "未知状态"}

def presenter(state: dict, *, sse_emit: Optional[Callable[[dict], None]] = None) -> dict:
    payload = build_payload(state)
    if sse_emit is not None:
        sse_emit(payload)
    summary = payload.get("summary") or "已完成"
    return {"final_message": summary, "presenter_payload": payload}
