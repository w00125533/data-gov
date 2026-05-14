"""LLM rerank — RRF Top-1 低置信度时调用 (spec §4.6.7)."""
from __future__ import annotations

import json
import logging
from typing import Any

from backend.search.docs import SearchDoc

logger = logging.getLogger(__name__)

RERANK_PROMPT = """你是无线网络数据专家。用户用自然语言描述了业务需求，
请从以下候选元数据对象中选出最匹配的表和字段。

用户需求: {user_query}

候选对象 (JSON):
{candidates_json}

返回严格的 JSON 格式 (不要 Markdown 包裹):
{{
  "top_table": {{"name": "...", "score": 0.95, "reason": "..."}},
  "top_fields": [{{"name": "...", "table": "...", "score": 0.88, "reason": "..."}}],
  "alternative_tables": [{{"name": "...", "score": 0.72, "reason": "..."}}]
}}
"""


def llm_rerank(
    query: str,
    candidates: list[tuple[SearchDoc, float]],
    client: Any,
) -> list[tuple[SearchDoc, float]]:
    """用 DeepSeek 重排候选。client 必须暴露 .invoke(prompt: str) -> obj.content。

    解析失败 / 返回缺字段时退化为输入顺序。
    """
    cand_json = json.dumps(
        [
            {
                "name": d.metadata.get("table_name") or d.id,
                "type": d.type,
                "description": d.text[:200],
            }
            for d, _ in candidates[:10]
        ],
        ensure_ascii=False,
    )
    prompt = RERANK_PROMPT.format(user_query=query, candidates_json=cand_json)
    try:
        resp = client.invoke(prompt)
        content = getattr(resp, "content", str(resp))
        parsed = json.loads(content)
        top = parsed.get("top_table") or {}
        top_name = top.get("name")
        top_score = float(top.get("score", 0.0))
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as e:
        logger.warning("LLM rerank parse failed: %s — falling back to input order", e)
        return candidates

    by_table = {d.metadata.get("table_name"): (d, top_score) for d, _ in candidates}
    if top_name in by_table:
        d, s = by_table[top_name]
        rest = [(dd, ss) for dd, ss in candidates if dd.metadata.get("table_name") != top_name]
        return [(d, s)] + rest
    return candidates
