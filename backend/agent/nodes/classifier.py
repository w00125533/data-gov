"""classifier 节点 - spec §4.1。LLM 失败时降级到关键词规则。"""
from __future__ import annotations
import json
from typing import Any
from backend.agent._msg import msg_content, msg_role
from backend.agent.prompts import CLASSIFIER_PROMPT

VALID_INTENTS = {"forward_etl", "reverse_synth", "schema_evolve"}


def _keyword_fallback(text: str) -> str:
    if any(k in text for k in ("造数据", "造点", "合成数据", "生成测试数据")):
        return "reverse_synth"
    if any(k in text for k in ("加字段", "加个字段", "加一个", "新增字段", "删除字段", "改字段", "新建表", "演进")):
        return "schema_evolve"
    return "forward_etl"


def classifier(state: dict, *, llm_client: Any) -> dict:
    recent = state.get("messages", [])[-3:]
    history_text = "\n".join(
        f"{msg_role(m)}: {msg_content(m)}" for m in recent
    )
    prompt = CLASSIFIER_PROMPT.format(
        history=history_text,
        prev_intent=state.get("intent"),
        context_source=state.get("context_source"),
    )
    last_msg = msg_content(recent[-1]) if recent else ""

    for _ in range(2):
        try:
            resp = llm_client.invoke(prompt)
            parsed = json.loads(getattr(resp, "content", str(resp)))
            intent = parsed.get("intent")
            confidence = float(parsed.get("confidence", 0.0))
            if intent in VALID_INTENTS:
                if confidence < 0.7:
                    return {
                        "intent": state.get("intent") or "forward_etl",
                        "needs_clarification": True,
                    }
                return {"intent": intent, "needs_clarification": False}
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
            continue

    return {"intent": _keyword_fallback(last_msg), "needs_clarification": False}
