"""gap_proposal - 根据 gaps 生成补齐草案 (spec §4.1)。"""
from __future__ import annotations
import json
from typing import Any
from backend.agent._msg import last_msg_content
from backend.agent.prompts import PROPOSE_PROMPT


def gap_proposal(state: dict, *, llm_client: Any) -> dict:
    gaps = state.get("gaps", [])
    msg = last_msg_content(state)
    prompt = PROPOSE_PROMPT.format(
        gaps=json.dumps(gaps, ensure_ascii=False), user_request=msg
    )
    try:
        resp = llm_client.invoke(prompt)
        draft = json.loads(getattr(resp, "content", str(resp)))
        if not isinstance(draft, list):
            draft = []
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        draft = []
    return {
        "schema_diff": draft,
        "sub_flow_active": True,
        "sub_flow_return_point": "code_generate",
        "presenter_payload": {
            "type": "gap_proposal_card",
            "draft": draft,
            "gaps": gaps,
        },
    }
