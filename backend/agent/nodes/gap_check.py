"""gap_check - 检测用户需求实体与现有元数据的缺口 (spec §4.1)。"""
from __future__ import annotations
import json
from typing import Any

from backend.agent._msg import last_msg_content


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
    msg = last_msg_content(state)
    required = _extract_required_entities(msg, llm_client)
    gaps: list[dict] = []
    for ent in required:
        kw = ent.get("keyword")
        if not kw:
            continue
        raw = searcher.search(kw, k=3, use_rerank=False)
        top_score = raw[0]["score"] if raw else 0.0
        if ent.get("field_specified") and ent.get("field"):
            field = ent["field"]
            table = ent.get("table")
            field_found = False
            table_found = False
            for hit in raw:
                hit_table = hit.get("table")
                doc = hit.get("doc")
                metadata = getattr(doc, "metadata", {}) or {}
                hit_field = metadata.get("field_name")
                if table is None or hit_table == table or metadata.get("table_name") == table:
                    table_found = table_found or top_score >= threshold
                    if hit_field == field:
                        field_found = True
                        break
            if table_found and not field_found:
                gaps.append(
                    {
                        "type": "missing_field",
                        "keyword": kw,
                        "table": table or (raw[0].get("table") if raw else None),
                        "field": field,
                        "suggestion": f"建议在表 {table or (raw[0].get('table') if raw else '')} 补回字段 {field}",
                    }
                )
                continue
        if top_score < threshold:
            gaps.append(
                {
                    "type": "missing_table",
                    "keyword": kw,
                    "suggestion": f"建议新建表覆盖 '{kw}'",
                }
            )
    return {"gaps": gaps, "has_gaps": len(gaps) > 0}
