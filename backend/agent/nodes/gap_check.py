"""gap_check - 检测用户需求实体与现有元数据的缺口 (spec §4.1)。"""
from __future__ import annotations
import json
from typing import Any

EXTRACT_ENTITIES_PROMPT = """从用户消息抽取业务实体关键词。
用户消息: {msg}
返回严格 JSON 数组:
[{{"keyword": "...", "field_specified": false, "field": null}}, ...]
"""


def _extract_required_entities(msg: str, llm_client: Any) -> list[dict]:
    try:
        resp = llm_client.invoke(EXTRACT_ENTITIES_PROMPT.format(msg=msg))
        return json.loads(getattr(resp, "content", str(resp)))
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return []


def gap_check(
    state: dict, *, llm_client: Any, searcher: Any, threshold: float = 0.6
) -> dict:
    msg = state.get("messages", [{}])[-1].get("content", "")
    required = _extract_required_entities(msg, llm_client)
    gaps: list[dict] = []
    for ent in required:
        kw = ent.get("keyword")
        if not kw:
            continue
        raw = searcher.search(kw, k=3, use_rerank=False)
        top_score = raw[0]["score"] if raw else 0.0
        if top_score < threshold:
            gaps.append(
                {
                    "type": "missing_table",
                    "keyword": kw,
                    "suggestion": f"建议新建表覆盖 '{kw}'",
                }
            )
    return {"gaps": gaps, "has_gaps": len(gaps) > 0}
