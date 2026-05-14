"""Tests for StateGraph assembly and conditional-edge routing functions."""
from unittest.mock import MagicMock

from backend.agent.graph import (
    after_classifier,
    after_dry_run,
    after_gap_check,
    after_gap_proposal,
    after_schema_apply,
    after_schema_validate,
    build_graph,
)


# ---------------------------------------------------------------------------
# after_classifier
# ---------------------------------------------------------------------------

class TestAfterClassifier:
    def test_needs_clarification_routes_to_presenter(self):
        assert after_classifier({"needs_clarification": True}) == "presenter"

    def test_intent_forward_etl(self):
        assert after_classifier({"intent": "forward_etl"}) == "forward_etl"

    def test_intent_reverse_synth(self):
        assert after_classifier({"intent": "reverse_synth"}) == "reverse_synth"

    def test_intent_schema_evolve(self):
        assert after_classifier({"intent": "schema_evolve"}) == "schema_evolve"

    def test_no_intent_defaults_to_forward_etl(self):
        assert after_classifier({}) == "forward_etl"


# ---------------------------------------------------------------------------
# after_gap_check
# ---------------------------------------------------------------------------

class TestAfterGapCheck:
    def test_no_gaps_routes_to_code_generate(self):
        assert after_gap_check({"has_gaps": False}) == "code_generate"
        assert after_gap_check({}) == "code_generate"

    def test_has_gaps_routes_to_gap_proposal(self):
        assert after_gap_check({"has_gaps": True}) == "gap_proposal"


# ---------------------------------------------------------------------------
# after_gap_proposal
# ---------------------------------------------------------------------------

class TestAfterGapProposal:
    def test_always_returns_presenter(self):
        assert after_gap_proposal({}) == "presenter"
        assert after_gap_proposal({"anything": 42}) == "presenter"


# ---------------------------------------------------------------------------
# after_schema_validate
# ---------------------------------------------------------------------------

class TestAfterSchemaValidate:
    def test_passed_routes_to_schema_apply(self):
        state = {"validation_result": {"passed": True}}
        assert after_schema_validate(state) == "schema_apply"

    def test_not_passed_routes_to_presenter(self):
        state = {"validation_result": {"passed": False}}
        assert after_schema_validate(state) == "presenter"

    def test_missing_validation_result_routes_to_presenter(self):
        assert after_schema_validate({}) == "presenter"


# ---------------------------------------------------------------------------
# after_schema_apply
# ---------------------------------------------------------------------------

class TestAfterSchemaApply:
    def test_sub_flow_active_routes_to_schema_lookup(self):
        state = {"sub_flow_active": True}
        assert after_schema_apply(state) == "schema_lookup"

    def test_no_sub_flow_routes_to_presenter(self):
        state = {"sub_flow_active": False}
        assert after_schema_apply(state) == "presenter"
        assert after_schema_apply({}) == "presenter"


# ---------------------------------------------------------------------------
# after_dry_run
# ---------------------------------------------------------------------------

class TestAfterDryRun:
    def test_success_routes_to_presenter(self):
        state = {"dry_run_result": {"success": True, "error_log": None}}
        assert after_dry_run(state) == "presenter"

    def test_failure_within_iteration_limit_loops_to_code_generate(self):
        state = {
            "dry_run_result": {"success": False, "error_log": "fail"},
            "iteration_count": 1,
        }
        assert after_dry_run(state) == "code_generate"

    def test_failure_at_max_iterations_routes_to_presenter(self):
        state = {
            "dry_run_result": {"success": False, "error_log": "fail"},
            "iteration_count": 3,
        }
        assert after_dry_run(state) == "presenter"

    def test_failure_below_max_iterations_still_loops(self):
        state = {
            "dry_run_result": {"success": False, "error_log": "err"},
            "iteration_count": 2,
        }
        # agent_max_iterations defaults to 3; 2 < 3 => loop back
        assert after_dry_run(state) == "code_generate"


# ---------------------------------------------------------------------------
# build_graph integration
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_returns_compiled_graph_with_invoke(self):
        graph = build_graph(llm_client=MagicMock(), searcher=MagicMock())
        assert hasattr(graph, "invoke")
        assert callable(graph.invoke)
