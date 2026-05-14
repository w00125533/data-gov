"""tests/search/test_rerank.py — mock DeepSeek; 验证 rerank prompt 构造与解析。"""
import json
from unittest.mock import MagicMock

from backend.search.docs import SearchDoc
from backend.search.rerank import llm_rerank, RERANK_PROMPT


def _doc(id_: str, table_name: str, text: str) -> SearchDoc:
    return SearchDoc(
        id=id_, type="table", text=text,
        metadata={"table_name": table_name, "version": 1},
    )


def test_rerank_calls_client_with_prompt_containing_query():
    candidates = [(_doc("table:a", "a", "table a desc"), 0.05)]
    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.content = json.dumps({
        "top_table": {"name": "a", "score": 0.95, "reason": "match"},
        "top_fields": [],
        "alternative_tables": [],
    })
    fake_client.invoke = MagicMock(return_value=fake_resp)

    result = llm_rerank("查覆盖强度", candidates, fake_client)
    assert result[0][0].metadata["table_name"] == "a"
    assert result[0][1] == 0.95
    # prompt 内含用户 query
    prompt_used = fake_client.invoke.call_args[0][0]
    assert "查覆盖强度" in prompt_used


def test_rerank_falls_back_to_input_order_when_llm_returns_invalid_json():
    candidates = [
        (_doc("table:a", "a", ""), 0.05),
        (_doc("table:b", "b", ""), 0.04),
    ]
    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.content = "not a json"
    fake_client.invoke = MagicMock(return_value=fake_resp)
    result = llm_rerank("...", candidates, fake_client)
    # 解析失败 → 原顺序返回，分数不变
    assert [d.metadata["table_name"] for d, _ in result] == ["a", "b"]


def test_rerank_prompt_template_has_required_placeholders():
    assert "{user_query}" in RERANK_PROMPT
    assert "{candidates_json}" in RERANK_PROMPT
