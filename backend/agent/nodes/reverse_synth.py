"""reverse_synth 节点 - spec §4.1。"""
from __future__ import annotations
import json
from typing import Any
from backend.agent.prompts import EXTRACT_PROMPT
from backend.agent.tools import search_tables_by_keyword


def reverse_synth(state: dict, *, llm_client: Any, searcher: Any) -> dict:
    msg = state.get("messages", [{}])[-1].get("content", "")
    prompt = EXTRACT_PROMPT.format(msg=msg, intent="reverse_synth")
    try:
        resp = llm_client.invoke(prompt)
        parsed = json.loads(getattr(resp, "content", str(resp)))
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        parsed = {}
    eval_target = parsed.get("eval_target", "")
    target = (
        search_tables_by_keyword(eval_target, searcher=searcher).top_table
        if eval_target
        else None
    )
    return {
        "target_tables": [target] if target else [],
        "source_tables": [],
        "row_count_hint": int(parsed.get("row_count_hint", 10)),
        "buckets_hint": parsed.get("buckets_hint", []) or [],
    }
