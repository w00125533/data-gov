"""schema_validate - 写库前一致性校验 (spec §4.1)。"""
from __future__ import annotations
from backend.agent.tools import validate_change


def schema_validate(state: dict) -> dict:
    result = validate_change(state.get("schema_diff", []))
    return {"validation_result": result}
