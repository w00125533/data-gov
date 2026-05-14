"""tests/agent/test_state.py"""
from typing import get_type_hints

from backend.agent.state import AgentState


def test_agent_state_has_all_spec_fields():
    hints = get_type_hints(AgentState)
    required = {
        "messages", "intent", "context_source", "needs_clarification",
        "target_tables", "source_tables", "schemas_resolved",
        "row_count_hint", "buckets_hint", "pipeline_chain",
        "generated_code", "code_type", "dry_run_result", "error_feedback",
        "iteration_count",
        "schema_diff", "validation_result", "applied_changes",
        "gaps", "has_gaps", "resolved_gaps", "sub_flow_active", "sub_flow_return_point",
        "presenter_payload", "final_message",
    }
    missing = required - set(hints)
    assert not missing, f"AgentState missing fields: {missing}"


def test_agent_state_total_false_allows_partial():
    s: AgentState = {}
    assert isinstance(s, dict)
    s["intent"] = "forward_etl"
    assert s["intent"] == "forward_etl"
