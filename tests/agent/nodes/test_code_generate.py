"""Tests for code_generate node - spec §4.1."""
from __future__ import annotations

from unittest import mock

import pytest

from backend.agent.nodes.code_generate import (
    _code_type_to_lang,
    code_generate,
    extract_code_block,
    infer_code_type,
)


class TestExtractCodeBlock:
    """extract_code_block: 从 LLM 回复中提取 fenced code block。"""

    def test_matching_lang(self) -> None:
        text = '一些解释\n```spark-sql\nSELECT * FROM tbl\n```\n更多文字'
        assert extract_code_block(text, lang="spark-sql") == "SELECT * FROM tbl"

    def test_fallback_no_lang(self) -> None:
        """当指定 lang 不匹配时, 尝试无标注的 ``` 块。"""
        text = '```\nSELECT 1\n```'
        assert extract_code_block(text, lang="spark-sql") == "SELECT 1"

    def test_no_code_block(self) -> None:
        """无任何代码块时返回空字符串。"""
        assert extract_code_block("纯文本解释", lang="spark-sql") == ""

    def test_trailing_newline(self) -> None:
        """代码块内容首尾空白被 strip。"""
        text = '```spark-sql\n  SELECT 1  \n```'
        assert extract_code_block(text, lang="spark-sql") == "SELECT 1"

    def test_mixed_case_no_lang_fallback(self) -> None:
        """有正确 lang 块时优先使用带 lang 标记的块。"""
        text = '```\nSELECT 0\n```\n```spark-sql\nSELECT 1\n```'
        assert extract_code_block(text, lang="spark-sql") == "SELECT 1"

    def test_multiple_code_blocks(self) -> None:
        """多个同 lang 块时返回第一个匹配。"""
        text = '```spark-sql\nFIRST\n```\n```spark-sql\nSECOND\n```'
        assert extract_code_block(text, lang="spark-sql") == "FIRST"


class TestInferCodeType:
    """infer_code_type: 从 target_tables 的 storage_type 推断 code_type。"""

    def test_hive_storage(self) -> None:
        state = {
            "target_tables": ["ods_logs"],
            "schemas_resolved": {"ods_logs": {"storage_type": "HIVE"}},
        }
        assert infer_code_type(state) == "spark_sql"

    def test_kafka_storage(self) -> None:
        state = {
            "target_tables": ["kafka_stream"],
            "schemas_resolved": {"kafka_stream": {"storage_type": "KAFKA"}},
        }
        assert infer_code_type(state) == "flink_sql"

    def test_starrocks_storage(self) -> None:
        state = {
            "target_tables": ["dws_agg"],
            "schemas_resolved": {"dws_agg": {"storage_type": "STARROCKS"}},
        }
        assert infer_code_type(state) == "spark_sql"

    def test_first_match_wins(self) -> None:
        state = {
            "target_tables": ["kafka_stream", "hive_table"],
            "schemas_resolved": {
                "kafka_stream": {"storage_type": "KAFKA"},
                "hive_table": {"storage_type": "HIVE"},
            },
        }
        assert infer_code_type(state) == "flink_sql"

    def test_no_match_defaults_to_spark_sql(self) -> None:
        state = {
            "target_tables": ["unknown_store"],
            "schemas_resolved": {"unknown_store": {"storage_type": "MYSQL"}},
        }
        assert infer_code_type(state) == "spark_sql"

    def test_empty_targets(self) -> None:
        assert infer_code_type({"target_tables": [], "schemas_resolved": {}}) == "spark_sql"

    def test_missing_schema_entry(self) -> None:
        state = {
            "target_tables": ["missing_schema"],
            "schemas_resolved": {},
        }
        assert infer_code_type(state) == "spark_sql"


class TestCodeTypeToLang:
    def test_mapping(self) -> None:
        assert _code_type_to_lang("spark_sql") == "spark-sql"
        assert _code_type_to_lang("flink_sql") == "flink-sql"
        assert _code_type_to_lang("java_flink") == "java"

    def test_unknown(self) -> None:
        assert _code_type_to_lang("unknown") == ""


class TestCodeGenerate:
    """code_generate 节点。"""

    def test_increments_iteration_count(self) -> None:
        """iteration_count 递增。"""
        mock_client = mock.Mock()
        mock_client.invoke.return_value = mock.Mock(content='```spark-sql\nSELECT 1\n```')
        state = {
            "target_tables": ["t"],
            "schemas_resolved": {"t": {"storage_type": "HIVE"}},
            "code_type": "spark_sql",
            "messages": [{"role": "user", "content": "do etl"}],
            "intent": "forward_etl",
            "iteration_count": 0,
            "error_feedback": None,
        }
        result = code_generate(state, llm_client=mock_client)
        assert result["iteration_count"] == 1

        result2 = code_generate({**state, "iteration_count": 5}, llm_client=mock_client)
        assert result2["iteration_count"] == 6

    def test_uses_code_type_from_state(self) -> None:
        """state 中已有 code_type 时不走推理路径。"""
        mock_client = mock.Mock()
        mock_client.invoke.return_value = mock.Mock(content='```flink-sql\nSELECT 1\n```')
        state = {
            "target_tables": [],
            "schemas_resolved": {},
            "code_type": "flink_sql",
            "messages": [{"role": "user", "content": "do etl"}],
            "intent": "forward_etl",
            "iteration_count": 0,
            "error_feedback": None,
        }
        result = code_generate(state, llm_client=mock_client)
        assert result["code_type"] == "flink_sql"

    def test_infers_code_type_when_missing(self) -> None:
        """state 无 code_type 时从 storage_type 推理。"""
        mock_client = mock.Mock()
        mock_client.invoke.return_value = mock.Mock(content='```spark-sql\nSELECT 1\n```')
        state = {
            "target_tables": ["t"],
            "schemas_resolved": {"t": {"storage_type": "HIVE"}},
            "messages": [{"role": "user", "content": "do etl"}],
            "intent": "forward_etl",
            "iteration_count": 0,
        }
        result = code_generate(state, llm_client=mock_client)
        assert result["code_type"] == "spark_sql"
        assert result["generated_code"] == "SELECT 1"

    def test_llm_object_without_content_attr(self) -> None:
        """llm_client.invoke 返回普通字符串时也能处理。"""
        mock_client = mock.Mock()
        mock_client.invoke.return_value = "```spark-sql\nSELECT 2\n```"
        state = {
            "target_tables": ["t"],
            "schemas_resolved": {"t": {"storage_type": "HIVE"}},
            "code_type": "spark_sql",
            "messages": [{"role": "user", "content": "do etl"}],
            "intent": "forward_etl",
            "iteration_count": 0,
            "error_feedback": None,
        }
        result = code_generate(state, llm_client=mock_client)
        assert result["generated_code"] == "SELECT 2"

    def test_error_feedback_in_prompt(self) -> None:
        """error_feedback 出现在 prompt 中。"""
        mock_client = mock.Mock()
        mock_client.invoke.return_value = mock.Mock(content='```spark-sql\nFIXED\n```')
        state = {
            "target_tables": ["t"],
            "schemas_resolved": {"t": {"storage_type": "HIVE"}},
            "code_type": "spark_sql",
            "messages": [{"role": "user", "content": "do etl"}],
            "intent": "forward_etl",
            "iteration_count": 1,
            "error_feedback": "SyntaxError: unexpected token",
        }
        result = code_generate(state, llm_client=mock_client)
        assert result["iteration_count"] == 2
        # 确认 prompt 中包含反馈
        call_args, _ = mock_client.invoke.call_args
        assert "SyntaxError: unexpected token" in call_args[0]

    def test_default_error_feedback(self) -> None:
        """error_feedback 为 None 时使用 '(无)'。"""
        mock_client = mock.Mock()
        mock_client.invoke.return_value = mock.Mock(content='```spark-sql\nSELECT 1\n```')
        state = {
            "target_tables": ["t"],
            "schemas_resolved": {"t": {"storage_type": "HIVE"}},
            "code_type": "spark_sql",
            "messages": [{"role": "user", "content": "do etl"}],
            "intent": "forward_etl",
            "iteration_count": 0,
            "error_feedback": None,
        }
        code_generate(state, llm_client=mock_client)
        call_args, _ = mock_client.invoke.call_args
        assert "(无)" in call_args[0]
