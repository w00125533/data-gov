"""GET /api/pipeline - table-level DAG for the Phase 3 UI."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

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


class PipelineEdge(BaseModel):
    source: str
    target: str
    weight: int


class PipelineResponse(BaseModel):
    mode: Literal["forward", "reverse"]
    table: str | None
    nodes: list[PipelineNode]
    edges: list[PipelineEdge]


def _table_edges() -> list[PipelineEdge]:
    rows = run_query(
        """
        MATCH (target_t:Table)-[:HAS_FIELD]->(target_f:Field)-[:DERIVES_FROM]->(source_f:Field)<-[:HAS_FIELD]-(source_t:Table)
        RETURN source_t.name AS source, target_t.name AS target, count(*) AS weight
        ORDER BY source_t.layer_priority, source_t.name, target_t.layer_priority, target_t.name
        """
    )
    return [PipelineEdge(source=r["source"], target=r["target"], weight=int(r["weight"])) for r in rows]


@router.get("/api/pipeline", response_model=PipelineResponse)
def pipeline_endpoint(
    mode: Literal["forward", "reverse"] = Query("forward"),
    table: str | None = None,
):
    tables = service.list_tables()
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
        )
        for t in tables
    ]
    edges = _table_edges()
    if mode == "reverse":
        edges = [PipelineEdge(source=e.target, target=e.source, weight=e.weight) for e in edges]
    return PipelineResponse(mode=mode, table=table, nodes=nodes, edges=edges)
