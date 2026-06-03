"""Tests for presenter node (spec §4.1)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.agent.nodes.presenter import build_payload, presenter


class TestBuildPayload:
    def test_build_payload_for_dry_run_success(self):
        state = {
            "dry_run_result": {"success": True, "preview_row": {"id": 1, "name": "foo"}},
            "generated_code": "SELECT 1",
            "code_type": "sql",
        }
        payload = build_payload(state)
        assert payload["type"] == "code_card"
        assert payload["code"] == "SELECT 1"
        assert payload["code_type"] == "sql"
        assert payload["preview_row"] == {"id": 1, "name": "foo"}
        assert payload["success"] is True
        assert payload["summary"] == "执行成功"

    def test_build_payload_for_clarification(self):
        state = {"needs_clarification": True}
        payload = build_payload(state)
        assert payload["type"] == "clarification"
        assert "summary" in payload

    def test_build_payload_for_gap_proposal(self):
        state = {"presenter_payload": {"type": "gap_proposal", "summary": "推荐新增指标"}}
        payload = build_payload(state)
        assert payload["type"] == "gap_proposal"
        assert payload["summary"] == "推荐新增指标"

    def test_build_payload_for_schema_apply(self):
        state = {
            "intent": "schema_evolve",
            "applied_changes": ["ALTER TABLE t ADD COLUMN x"],
            "validation_result": {"warnings": ["backup recommended"]},
        }
        payload = build_payload(state)
        assert payload["type"] == "schema_diff_card"
        assert payload["applied"] == ["ALTER TABLE t ADD COLUMN x"]
        assert payload["warnings"] == ["backup recommended"]

    def test_build_payload_for_validation_failure(self):
        state = {
            "intent": "schema_evolve",
            "validation_result": {"passed": False, "errors": [["ERR01", "missing FK"], ["ERR02", "type mismatch"]]},
        }
        payload = build_payload(state)
        assert payload["type"] == "error"
        assert "ERR01" in payload["summary"]
        assert "ERR02" in payload["summary"]


class TestPresenter:
    def test_presenter_emits_sse(self):
        sse_emit = MagicMock()
        state = {"dry_run_result": {"success": True}, "generated_code": "OK", "code_type": "text"}
        result = presenter(state, sse_emit=sse_emit)
        sse_emit.assert_called_once()
        called_payload = sse_emit.call_args[0][0]
        assert called_payload["type"] == "code_card"
        assert called_payload["summary"] == "执行成功"
        assert result["final_message"] == "执行成功"
        assert result["presenter_payload"]["type"] == "code_card"
        assert result["presenter_payload"]["code"] == "OK"
