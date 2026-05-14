"""code_generate 节点 - spec §4.1。"""
from __future__ import annotations

import json
import re
from typing import Any

from backend.agent._msg import last_msg_content
from backend.agent.prompts import CODE_GEN_PROMPT

_STORAGE_TO_CODE_TYPE = {"HIVE": "spark_sql", "KAFKA": "flink_sql", "STARROCKS": "spark_sql"}


def _code_type_to_lang(code_type: str) -> str:
    return {"spark_sql": "spark-sql", "flink_sql": "flink-sql", "java_flink": "java"}.get(code_type, "")


def extract_code_block(text: str, *, lang: str) -> str:
    pat = re.compile(r"```" + re.escape(lang) + r"\s*\n(.*?)```", re.DOTALL)
    m = pat.search(text)
    if m:
        return m.group(1).strip()
    pat2 = re.compile(r"```\s*\n(.*?)```", re.DOTALL)
    m2 = pat2.search(text)
    return m2.group(1).strip() if m2 else ""


def infer_code_type(state: dict) -> str:
    targets = state.get("target_tables", [])
    schemas = state.get("schemas_resolved", {})
    for t in targets:
        st = (schemas.get(t) or {}).get("storage_type")
        if st in _STORAGE_TO_CODE_TYPE:
            return _STORAGE_TO_CODE_TYPE[st]
    return "spark_sql"


def code_generate(state: dict, *, llm_client: Any) -> dict:
    code_type = state.get("code_type") or infer_code_type(state)
    schemas = state.get("schemas_resolved", {})
    msg = last_msg_content(state)
    prompt = CODE_GEN_PROMPT.format(
        schema=json.dumps(schemas, ensure_ascii=False),
        intent=state.get("intent", "forward_etl"),
        user_request=msg,
        code_type=code_type,
        error_feedback=state.get("error_feedback") or "(无)",
    )
    resp = llm_client.invoke(prompt)
    content = getattr(resp, "content", str(resp))
    code = extract_code_block(content, lang=_code_type_to_lang(code_type))
    return {"generated_code": code, "code_type": code_type, "iteration_count": state.get("iteration_count", 0) + 1}
