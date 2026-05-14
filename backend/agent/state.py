"""Agent State - spec §4.2. total=False 让 LangGraph 自动 merge partial dict."""
from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # classifier / 对话基础
    messages: Annotated[list, add_messages]
    intent: str
    context_source: str
    needs_clarification: bool

    # forward_etl / schema_lookup
    target_tables: list[str]
    source_tables: list[str]
    schemas_resolved: dict

    # reverse_synth / pipeline_parse
    row_count_hint: int
    buckets_hint: list[dict]
    pipeline_chain: list[dict]

    # code_generate / dry_run
    generated_code: str
    code_type: str
    dry_run_result: dict
    error_feedback: str
    iteration_count: int

    # schema_evolve / validate / apply
    schema_diff: list[dict]
    validation_result: dict
    applied_changes: list[dict]

    # gap_check / gap_proposal
    gaps: list[dict]
    has_gaps: bool
    resolved_gaps: dict
    sub_flow_active: bool
    sub_flow_return_point: str

    # presenter
    presenter_payload: dict
    final_message: str
