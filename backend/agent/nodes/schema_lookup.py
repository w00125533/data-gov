"""schema_lookup - 把 target+source 表的 schema 取到 State (spec §4.1)。"""
from __future__ import annotations
from backend.agent.tools import lookup_table_schema


def schema_lookup(state: dict) -> dict:
    tables = list({*state.get("target_tables", []), *state.get("source_tables", [])})
    schemas = lookup_table_schema(tables)
    out: dict = {"schemas_resolved": schemas}
    if state.get("sub_flow_active"):
        out["sub_flow_active"] = False
    return out
