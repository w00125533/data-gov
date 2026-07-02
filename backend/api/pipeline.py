"""GET /api/pipeline - table-level DAG for the Phase 3 UI."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.metadata import service
from backend.metadata.graph import run_query


router = APIRouter()


class PipelineNode(BaseModel):
    id: str
    name: str
    layer: str
    layer_priority: int
    storage_type: str
    description: str
    field_count: int
    selected: bool = False
    upstream_tables: list[str] = Field(default_factory=list)
    downstream_tables: list[str] = Field(default_factory=list)


class PipelineEdge(BaseModel):
    source: str
    target: str
    weight: int
    fields: list[str] = Field(default_factory=list)
    constraint_summary: str = ""


class PipelineConstraint(BaseModel):
    field: str
    range: list[int]
    rows: int
    bucket: str


class PipelineResponse(BaseModel):
    mode: Literal["forward", "reverse"]
    table: str | None
    depth: int
    nodes: list[PipelineNode]
    edges: list[PipelineEdge]
    selected_path: list[str] = Field(default_factory=list)
    constraints: list[PipelineConstraint] = Field(default_factory=list)


def _table_edges() -> list[PipelineEdge]:
    rows = run_query(
        """
        MATCH (target_t:Table)-[:HAS_FIELD]->(target_f:Field)-[:DERIVES_FROM]->(source_f:Field)<-[:HAS_FIELD]-(source_t:Table)
        RETURN source_t.name AS source, target_t.name AS target, count(*) AS weight,
               collect(DISTINCT target_f.name) AS fields
        ORDER BY source_t.layer_priority, source_t.name, target_t.layer_priority, target_t.name
        """
    )
    return [
        PipelineEdge(
            source=r["source"],
            target=r["target"],
            weight=int(r["weight"]),
            fields=[str(field) for field in (r.get("fields") or []) if field],
        )
        for r in rows
    ]


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted(dict.fromkeys(values))


def _unique_preserve_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _direct_table_summaries(edges: list[PipelineEdge]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    upstream: dict[str, list[str]] = {}
    downstream: dict[str, list[str]] = {}
    for edge in edges:
        upstream.setdefault(edge.target, []).append(edge.source)
        downstream.setdefault(edge.source, []).append(edge.target)
    return (
        {table: _unique_sorted(values) for table, values in upstream.items()},
        {table: _unique_sorted(values) for table, values in downstream.items()},
    )


def _reachable(table: str, edges: list[PipelineEdge], depth: int, *, upstream: bool) -> set[str]:
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        key, value = (edge.target, edge.source) if upstream else (edge.source, edge.target)
        adjacency.setdefault(key, []).append(value)

    seen = {table}
    frontier = {table}
    for _ in range(depth):
        next_frontier: set[str] = set()
        for current in frontier:
            for neighbor in adjacency.get(current, []):
                if neighbor not in seen:
                    seen.add(neighbor)
                    next_frontier.add(neighbor)
        if not next_frontier:
            break
        frontier = next_frontier
    return seen


def _neighborhood(table: str | None, edges: list[PipelineEdge], depth: int) -> set[str] | None:
    if not table:
        return None
    return _reachable(table, edges, depth, upstream=True) | _reachable(table, edges, depth, upstream=False)


def _selected_path(table: str | None, edges: list[PipelineEdge]) -> list[str]:
    if not table:
        return []
    upstream: dict[str, list[str]] = {}
    for edge in edges:
        upstream.setdefault(edge.target, []).append(edge.source)

    def walk(node: str, seen: set[str]) -> list[str]:
        sources = sorted(source for source in upstream.get(node, []) if source not in seen)
        if not sources:
            return [node]
        candidates = [walk(source, seen | {source}) + [node] for source in sources]
        return max(candidates, key=lambda path: (len(path), tuple(path)))

    return walk(table, {table})


def _constraint_summary(fields: list[str]) -> str:
    return "; ".join(f"{field} in [0,100]" for field in fields)


def _reverse_constraints(table: str | None, edges: list[PipelineEdge]) -> list[PipelineConstraint]:
    if not table:
        return []
    fields: list[str] = []
    for edge in edges:
        if edge.target == table:
            fields.extend(edge.fields)
    if not fields:
        for edge in edges:
            fields.extend(edge.fields)
    buckets = [
        ("excellent", [80, 100], 3),
        ("normal", [50, 80], 4),
        ("low", [0, 50], 3),
    ]
    return [
        PipelineConstraint(field=field, range=value_range, rows=rows, bucket=bucket)
        for field, (bucket, value_range, rows) in zip(_unique_preserve_order(fields), buckets)
    ]


@router.get("/api/pipeline", response_model=PipelineResponse)
def pipeline_endpoint(
    mode: Literal["forward", "reverse"] = Query("forward"),
    table: str | None = None,
    depth: int = Query(5, ge=1, le=5),
):
    tables = service.list_tables()
    logical_edges = _table_edges()
    included = _neighborhood(table, logical_edges, depth)
    scoped_edges = [
        edge for edge in logical_edges
        if included is None or (edge.source in included and edge.target in included)
    ]
    direct_upstream, direct_downstream = _direct_table_summaries(logical_edges)
    nodes = [
        PipelineNode(
            id=t.id,
            name=t.name,
            layer=t.layer,
            layer_priority=t.layer_priority,
            storage_type=t.storage_type,
            description=t.description,
            field_count=t.field_count,
            selected=bool(table and t.name == table),
            upstream_tables=direct_upstream.get(t.name, []),
            downstream_tables=direct_downstream.get(t.name, []),
        )
        for t in tables
        if included is None or t.name in included
    ]
    if mode == "reverse":
        display_edges = [
            PipelineEdge(
                source=edge.target,
                target=edge.source,
                weight=edge.weight,
                fields=edge.fields,
                constraint_summary=_constraint_summary(edge.fields),
            )
            for edge in scoped_edges
        ]
    else:
        display_edges = scoped_edges
    return PipelineResponse(
        mode=mode,
        table=table,
        depth=depth,
        nodes=nodes,
        edges=display_edges,
        selected_path=_selected_path(table, logical_edges),
        constraints=_reverse_constraints(table, scoped_edges) if mode == "reverse" else [],
    )
