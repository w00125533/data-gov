"""pipeline_parse - 反向合成专用，从根表回溯到所有上游 (spec §4.1)。"""
from __future__ import annotations
from backend.agent.tools import lookup_lineage


def pipeline_parse(state: dict) -> dict:
    roots = state.get("target_tables", [])
    if not roots:
        return {"source_tables": [], "pipeline_chain": []}
    root = roots[0]
    chain: list[dict] = []
    visited: set[str] = set()
    stack: list[str] = [root]
    while stack:
        t = stack.pop()
        if t in visited:
            continue
        visited.add(t)
        edges = lookup_lineage(t, direction="up", depth=1)
        upstream_tables = sorted({e.from_table for e in edges if getattr(e, "from_table", None)})
        chain.append({
            "table": t,
            "fields": sorted({
                e.from_field for e in edges if getattr(e, "from_field", None)
            }),
            "upstream": upstream_tables,
        })
        stack.extend(upstream_tables)
    return {
        "source_tables": sorted(visited - {root}),
        "pipeline_chain": list(reversed(chain)),
    }
