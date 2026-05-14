"""LangGraph 装配 + 条件边 + Agent 层迭代上限 (spec §4.1 + §4.5)。"""
from __future__ import annotations
from typing import Any
from langgraph.graph import END, START, StateGraph
from backend.agent.state import AgentState
from backend.agent.nodes.classifier import classifier
from backend.agent.nodes.forward_etl import forward_etl
from backend.agent.nodes.reverse_synth import reverse_synth
from backend.agent.nodes.pipeline_parse import pipeline_parse
from backend.agent.nodes.schema_lookup import schema_lookup
from backend.agent.nodes.gap_check import gap_check
from backend.agent.nodes.gap_proposal import gap_proposal
from backend.agent.nodes.code_generate import code_generate
from backend.agent.nodes.dry_run import dry_run
from backend.agent.nodes.presenter import presenter
from backend.agent.nodes.schema_evolve import schema_evolve
from backend.agent.nodes.schema_validate import schema_validate
from backend.agent.nodes.schema_apply import schema_apply
from backend.config import get_settings


def after_classifier(state: dict) -> str:
    if state.get("needs_clarification"):
        return "presenter"
    return state.get("intent", "forward_etl")


def after_gap_check(state: dict) -> str:
    return "gap_proposal" if state.get("has_gaps") else "code_generate"


def after_gap_proposal(state: dict) -> str:
    return "presenter"


def after_schema_validate(state: dict) -> str:
    return "schema_apply" if (state.get("validation_result") or {}).get("passed") else "presenter"


def after_schema_apply(state: dict) -> str:
    return "schema_lookup" if state.get("sub_flow_active") else "presenter"


def after_dry_run(state: dict) -> str:
    settings = get_settings()
    dr = state.get("dry_run_result") or {}
    if dr.get("success"):
        return "presenter"
    if state.get("iteration_count", 0) >= settings.agent_max_iterations:
        return "presenter"
    return "code_generate"


def build_graph(*, llm_client: Any, searcher: Any):
    g = StateGraph(AgentState)

    g.add_node("classifier", lambda s: classifier(s, llm_client=llm_client))
    g.add_node("forward_etl", lambda s: forward_etl(s, llm_client=llm_client, searcher=searcher))
    g.add_node("reverse_synth", lambda s: reverse_synth(s, llm_client=llm_client, searcher=searcher))
    g.add_node("pipeline_parse", pipeline_parse)
    g.add_node("schema_lookup", schema_lookup)
    g.add_node("gap_check", lambda s: gap_check(s, llm_client=llm_client, searcher=searcher))
    g.add_node("gap_proposal", lambda s: gap_proposal(s, llm_client=llm_client))
    g.add_node("code_generate", lambda s: code_generate(s, llm_client=llm_client))
    g.add_node("dry_run", dry_run)
    g.add_node("schema_evolve", lambda s: schema_evolve(s, llm_client=llm_client))
    g.add_node("schema_validate", schema_validate)
    g.add_node("schema_apply", schema_apply)
    g.add_node("presenter", presenter)

    g.add_edge(START, "classifier")

    g.add_conditional_edges(
        "classifier",
        after_classifier,
        {
            "forward_etl": "forward_etl",
            "reverse_synth": "reverse_synth",
            "schema_evolve": "schema_evolve",
            "presenter": "presenter",
        },
    )

    g.add_edge("forward_etl", "schema_lookup")
    g.add_edge("reverse_synth", "pipeline_parse")
    g.add_edge("pipeline_parse", "gap_check")
    g.add_edge("schema_lookup", "gap_check")

    g.add_conditional_edges(
        "gap_check",
        after_gap_check,
        {"code_generate": "code_generate", "gap_proposal": "gap_proposal"},
    )

    g.add_conditional_edges(
        "gap_proposal", after_gap_proposal, {"presenter": "presenter"}
    )

    g.add_edge("schema_evolve", "schema_validate")

    g.add_conditional_edges(
        "schema_validate",
        after_schema_validate,
        {"schema_apply": "schema_apply", "presenter": "presenter"},
    )

    g.add_conditional_edges(
        "schema_apply",
        after_schema_apply,
        {"schema_lookup": "schema_lookup", "presenter": "presenter"},
    )

    g.add_edge("code_generate", "dry_run")

    g.add_conditional_edges(
        "dry_run",
        after_dry_run,
        {"code_generate": "code_generate", "presenter": "presenter"},
    )

    g.add_edge("presenter", END)

    return g.compile()
