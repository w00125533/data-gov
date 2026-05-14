"""forward_etl 节点 - spec §4.1。"""
from __future__ import annotations
import json
from typing import Any
from backend.agent.prompts import EXTRACT_PROMPT
from backend.agent.tools import search_tables_by_keyword


def forward_etl(state: dict, *, llm_client: Any, searcher: Any) -> dict:
    msg = state.get("messages", [{}])[-1].get("content", "")
    prompt = EXTRACT_PROMPT.format(msg=msg, intent="forward_etl")
    try:
        resp = llm_client.invoke(prompt)
        parsed = json.loads(getattr(resp, "content", str(resp)))
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return {"target_tables": [], "source_tables": [], "code_type": None}
    targets = [
        search_tables_by_keyword(k, searcher=searcher).top_table
        for k in parsed.get("target_entities", [])
    ]
    sources = [
        search_tables_by_keyword(k, searcher=searcher).top_table
        for k in parsed.get("source_hints", [])
    ]
    hint = parsed.get("code_type_hint")
    return {
        "target_tables": [t for t in targets if t],
        "source_tables": [s for s in sources if s],
        "code_type": hint if hint and hint != "auto" else None,
    }
