"""schema_evolve - 主流程 LLM 生成 diff; 子流程复用 gap_proposal 草案 (spec §4.1)。"""
from __future__ import annotations
import json
from typing import Any
from backend.agent._msg import last_msg_content
from backend.agent.prompts import SCHEMA_EVOLVE_PROMPT
from backend.agent.tools import lookup_table_schema


def schema_evolve(state: dict, *, llm_client: Any) -> dict:
    if state.get("sub_flow_active"):
        return {"schema_diff": state.get("schema_diff", [])}
    msg = last_msg_content(state)
    current = lookup_table_schema(state.get("target_tables", []))
    prompt = SCHEMA_EVOLVE_PROMPT.format(
        user_request=msg, current_schema=json.dumps(current, ensure_ascii=False)
    )
    for _ in range(2):
        try:
            resp = llm_client.invoke(prompt)
            parsed = json.loads(getattr(resp, "content", str(resp)))
            if isinstance(parsed, list):
                return {"schema_diff": parsed}
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
            continue
    return {"schema_diff": []}
