"""Cypher implementations for table/field CRUD + lineage queries.

This module is the single source of truth for graph mutations and reads.
Both HTTP routes (backend/api/metadata.py) and future Agent tools depend on it.
"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from backend.metadata.graph import run_query
from backend.metadata.models import (
    CreateFieldRequest,
    CreateTableRequest,
    FieldResponse,
    ImpactResponse,
    LineageEdge,
    LineageEdgeCreateRequest,
    LineageEdgeUpdateRequest,
    TableResponse,
    TableSummary,
    UpdateFieldRequest,
    UpstreamRef,
)


LAYER_PRIORITY = {"ODS": 1, "DWD": 2, "DWS": 3, "ADS": 4, "EVAL": 5}


class TableNotFound(Exception):
    pass


class FieldNotFound(Exception):
    pass


class FieldHasDownstream(Exception):
    def __init__(self, downstream: list[tuple[str, str]]):
        self.downstream = downstream
        super().__init__(f"field has {len(downstream)} downstream dependents")


class LineageEdgeNotFound(Exception):
    pass


class CycleDetected(Exception):
    def __init__(self, path: list[dict]):
        self.path = path
        super().__init__("lineage cycle detected")


# ----------------------- Tables -----------------------

def list_tables(layer: Optional[str] = None, search: Optional[str] = None) -> list[TableSummary]:
    cypher_filters = []
    params: dict = {}
    if layer:
        cypher_filters.append("t.layer = $layer")
        params["layer"] = layer
    if search:
        cypher_filters.append("toLower(t.name) CONTAINS toLower($search) OR toLower(t.description) CONTAINS toLower($search)")
        params["search"] = search
    where = ("WHERE " + " AND ".join(cypher_filters)) if cypher_filters else ""
    rows = run_query(
        f"""
        MATCH (t:Table)
        {where}
        OPTIONAL MATCH (t)-[:HAS_FIELD]->(f:Field)
        RETURN t.id AS id, t.name AS name, t.layer AS layer, t.layer_priority AS layer_priority,
               t.storage_type AS storage_type, t.description AS description, count(f) AS field_count
        ORDER BY t.layer_priority, t.name
        """,
        **params,
    )
    return [TableSummary(**r) for r in rows]


def get_table_by_name(name: str, optional: bool = False) -> Optional[TableResponse]:
    rows = run_query(
        """
        MATCH (t:Table {name: $name})
        OPTIONAL MATCH (t)-[:HAS_FIELD]->(f:Field)
        OPTIONAL MATCH (f)-[:DERIVES_FROM]->(up:Field)<-[:HAS_FIELD]-(up_t:Table)
        WITH t, f, collect(DISTINCT {table: up_t.name, field: up.name}) AS upstream
        WITH t, collect({
            id: f.id, name: f.name, field_type: f.field_type,
            is_nullable: f.is_nullable, is_partition: f.is_partition,
            expression: f.expression, description: f.description,
            version: f.version, upstream: upstream
        }) AS fields
        RETURN t.id AS id, t.name AS name, t.layer AS layer, t.layer_priority AS layer_priority,
               t.storage_type AS storage_type, t.description AS description, fields
        """,
        name=name,
    )
    if not rows:
        if optional:
            return None
        raise TableNotFound(name)
    row = rows[0]
    raw_fields = [f for f in row["fields"] if f.get("name") is not None]
    fields = []
    for f in raw_fields:
        upstream = [UpstreamRef(**u) for u in f["upstream"] if u["table"] is not None]
        fields.append(FieldResponse(
            id=f["id"], name=f["name"], field_type=f["field_type"],
            is_nullable=f["is_nullable"], is_partition=f["is_partition"],
            expression=f["expression"] or None, description=f["description"] or "",
            version=f["version"], upstream=upstream,
        ))
    return TableResponse(
        id=row["id"], name=row["name"], layer=row["layer"], layer_priority=row["layer_priority"],
        storage_type=row["storage_type"], description=row["description"], fields=fields,
    )


def get_table_by_id(table_id: str) -> TableResponse:
    rows = run_query("MATCH (t:Table {id: $id}) RETURN t.name AS name", id=table_id)
    if not rows:
        raise TableNotFound(table_id)
    return get_table_by_name(rows[0]["name"])


def create_table(req: CreateTableRequest) -> TableResponse:
    table_id = str(uuid.uuid4())
    run_query(
        """
        CREATE (t:Table {
            id: $id, name: $name, layer: $layer, layer_priority: $layer_priority,
            storage_type: $storage_type, description: $description
        })
        """,
        id=table_id, name=req.name, layer=req.layer,
        layer_priority=LAYER_PRIORITY[req.layer],
        storage_type=req.storage_type, description=req.description,
    )
    return get_table_by_name(req.name)


def delete_table(name: str) -> None:
    run_query("MATCH (t:Table {name: $name}) DETACH DELETE t", name=name)


# ----------------------- Fields -----------------------

def create_field(req: CreateFieldRequest) -> FieldResponse:
    field_id = str(uuid.uuid4())
    run_query(
        """
        MATCH (t:Table {id: $table_id})
        CREATE (t)-[:HAS_FIELD]->(f:Field {
            id: $id, name: $name, field_type: $field_type,
            is_nullable: $is_nullable, is_partition: $is_partition,
            expression: $expression, description: $description,
            version: 1, previous_expr: '[]'
        })
        """,
        table_id=req.table_id, id=field_id, name=req.name, field_type=req.field_type,
        is_nullable=req.is_nullable, is_partition=req.is_partition,
        expression=req.expression or "", description=req.description,
    )
    for up in req.upstream:
        run_query(
            """
            MATCH (f:Field {id: $field_id})
            MATCH (t_up:Table {name: $up_t})-[:HAS_FIELD]->(f_up:Field {name: $up_f})
            MERGE (f)-[r:DERIVES_FROM]->(f_up)
            ON CREATE SET r.transform_expr = $transform_expr, r.created_at = datetime()
            """,
            field_id=field_id, up_t=up.table, up_f=up.field,
            transform_expr=req.expression or "passthrough",
        )
    return _load_field(field_id)


def _load_field(field_id: str) -> FieldResponse:
    rows = run_query(
        """
        MATCH (f:Field {id: $id})
        OPTIONAL MATCH (f)-[:DERIVES_FROM]->(up:Field)<-[:HAS_FIELD]-(up_t:Table)
        WITH f, collect(DISTINCT {table: up_t.name, field: up.name}) AS upstream
        RETURN f.id AS id, f.name AS name, f.field_type AS field_type,
               f.is_nullable AS is_nullable, f.is_partition AS is_partition,
               f.expression AS expression, f.description AS description,
               f.version AS version, upstream
        """,
        id=field_id,
    )
    if not rows:
        raise FieldNotFound(field_id)
    r = rows[0]
    upstream = [UpstreamRef(**u) for u in r["upstream"] if u["table"] is not None]
    return FieldResponse(
        id=r["id"], name=r["name"], field_type=r["field_type"],
        is_nullable=r["is_nullable"], is_partition=r["is_partition"],
        expression=r["expression"] or None, description=r["description"] or "",
        version=r["version"], upstream=upstream,
    )


def update_field_expression(field_id: str, new_expression: str) -> FieldResponse:
    rows = run_query("MATCH (f:Field {id: $id}) RETURN f.expression AS expr, f.version AS v, f.previous_expr AS prev", id=field_id)
    if not rows:
        raise FieldNotFound(field_id)
    old_expr = rows[0]["expr"]
    old_version = rows[0]["v"]
    history = json.loads(rows[0]["prev"] or "[]")
    history.append({"v": old_version, "expr": old_expr})
    run_query(
        """
        MATCH (f:Field {id: $id})
        SET f.expression = $expr, f.version = f.version + 1, f.previous_expr = $history
        """,
        id=field_id, expr=new_expression, history=json.dumps(history),
    )
    return _load_field(field_id)


def update_field(field_id: str, req: UpdateFieldRequest) -> FieldResponse:
    sets: list[str] = []
    params: dict = {"id": field_id}
    for attr, prop in [
        ("field_type", "field_type"), ("is_nullable", "is_nullable"),
        ("is_partition", "is_partition"), ("description", "description"),
    ]:
        value = getattr(req, attr)
        if value is not None:
            sets.append(f"f.{prop} = ${attr}")
            params[attr] = value
    if sets:
        run_query(f"MATCH (f:Field {{id: $id}}) SET {', '.join(sets)}", **params)
    if req.expression is not None:
        update_field_expression(field_id, req.expression)
    if req.upstream is not None:
        run_query("MATCH (f:Field {id: $id})-[r:DERIVES_FROM]->() DELETE r", id=field_id)
        for up in req.upstream:
            run_query(
                """
                MATCH (f:Field {id: $id})
                MATCH (t_up:Table {name: $up_t})-[:HAS_FIELD]->(f_up:Field {name: $up_f})
                MERGE (f)-[r:DERIVES_FROM]->(f_up)
                ON CREATE SET r.transform_expr = $expr, r.created_at = datetime()
                """,
                id=field_id, up_t=up.table, up_f=up.field,
                expr=req.expression or "passthrough",
            )
    return _load_field(field_id)


def delete_field(field_id: str) -> None:
    rows = run_query(
        """
        MATCH (f:Field {id: $id})
        OPTIONAL MATCH (downstream:Field)-[:DERIVES_FROM]->(f)
        OPTIONAL MATCH (down_t:Table)-[:HAS_FIELD]->(downstream)
        RETURN collect(DISTINCT [down_t.name, downstream.name]) AS downstream
        """,
        id=field_id,
    )
    if not rows:
        raise FieldNotFound(field_id)
    downstream = [(p[0], p[1]) for p in rows[0]["downstream"] if p and p[0] is not None]
    if downstream:
        raise FieldHasDownstream(downstream)
    run_query("MATCH (f:Field {id: $id}) DETACH DELETE f", id=field_id)


# ----------------------- Lineage -----------------------

def _serialize_neo4j_datetime(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _lineage_edge_from_row(row: dict) -> LineageEdge:
    return LineageEdge(
        edge_id=str(row.get("edge_id") or ""),
        from_table=row["from_table"],
        from_field=row["from_field"],
        to_table=row["to_table"],
        to_field=row["to_field"],
        transform_expr=row.get("transform_expr") or "",
        created_at=_serialize_neo4j_datetime(row.get("created_at")),
    )


def _load_lineage_edge(edge_id: str) -> LineageEdge:
    rows = run_query(
        """
        MATCH (to_f:Field)-[r:DERIVES_FROM]->(from_f:Field)
        WHERE r.edge_id = $edge_id OR elementId(r) = $edge_id
        MATCH (from_t:Table)-[:HAS_FIELD]->(from_f)
        MATCH (to_t:Table)-[:HAS_FIELD]->(to_f)
        RETURN coalesce(r.edge_id, elementId(r)) AS edge_id,
               from_t.name AS from_table, from_f.name AS from_field,
               to_t.name AS to_table, to_f.name AS to_field,
               r.transform_expr AS transform_expr, r.created_at AS created_at
        """,
        edge_id=edge_id,
    )
    if not rows:
        raise LineageEdgeNotFound(edge_id)
    return _lineage_edge_from_row(rows[0])


def assert_no_lineage_cycle(target_field_id: str, source_field_id: str) -> None:
    if target_field_id == source_field_id:
        rows = run_query(
            """
            MATCH (f:Field {id: $id})<-[:HAS_FIELD]-(t:Table)
            RETURN [{table: t.name, field: f.name, field_id: f.id}] AS path
            """,
            id=target_field_id,
        )
        raise CycleDetected(rows[0]["path"] if rows else [])
    rows = run_query(
        """
        MATCH p = (source:Field {id: $source_field_id})-[:DERIVES_FROM*1..20]->(target:Field {id: $target_field_id})
        WITH nodes(p) AS path_nodes
        UNWIND path_nodes AS f
        MATCH (t:Table)-[:HAS_FIELD]->(f)
        RETURN collect({table: t.name, field: f.name, field_id: f.id}) AS path
        LIMIT 1
        """,
        source_field_id=source_field_id,
        target_field_id=target_field_id,
    )
    if rows:
        raise CycleDetected(rows[0]["path"])


def create_lineage_edge(req: LineageEdgeCreateRequest) -> LineageEdge:
    rows = run_query(
        """
        MATCH (from_t:Table {name: $from_table})-[:HAS_FIELD]->(from_f:Field {name: $from_field})
        MATCH (to_t:Table {name: $to_table})-[:HAS_FIELD]->(to_f:Field {name: $to_field})
        RETURN from_f.id AS source_field_id, to_f.id AS target_field_id
        """,
        from_table=req.from_table,
        from_field=req.from_field,
        to_table=req.to_table,
        to_field=req.to_field,
    )
    if not rows:
        raise FieldNotFound(f"{req.from_table}.{req.from_field} -> {req.to_table}.{req.to_field}")

    source_field_id = rows[0]["source_field_id"]
    target_field_id = rows[0]["target_field_id"]
    assert_no_lineage_cycle(target_field_id=target_field_id, source_field_id=source_field_id)

    rows = run_query(
        """
        MATCH (from_f:Field {id: $source_field_id})
        MATCH (to_f:Field {id: $target_field_id})
        MERGE (to_f)-[r:DERIVES_FROM]->(from_f)
        ON CREATE SET r.edge_id = $edge_id,
                      r.created_at = datetime(),
                      r.transform_expr = $transform_expr
        ON MATCH SET r.transform_expr = $transform_expr
        RETURN coalesce(r.edge_id, elementId(r)) AS edge_id
        """,
        source_field_id=source_field_id,
        target_field_id=target_field_id,
        edge_id=str(uuid.uuid4()),
        transform_expr=req.transform_expr,
    )
    if not rows:
        raise LineageEdgeNotFound(f"{req.from_table}.{req.from_field} -> {req.to_table}.{req.to_field}")
    return _load_lineage_edge(rows[0]["edge_id"])


def update_lineage_edge(edge_id: str, req: LineageEdgeUpdateRequest) -> LineageEdge:
    rows = run_query(
        """
        MATCH ()-[r:DERIVES_FROM]->()
        WHERE r.edge_id = $edge_id OR elementId(r) = $edge_id
        SET r.transform_expr = $transform_expr
        RETURN coalesce(r.edge_id, elementId(r)) AS edge_id
        """,
        edge_id=edge_id,
        transform_expr=req.transform_expr,
    )
    if not rows:
        raise LineageEdgeNotFound(edge_id)
    return _load_lineage_edge(rows[0]["edge_id"])


def delete_lineage_edge(edge_id: str) -> None:
    rows = run_query(
        """
        MATCH ()-[r:DERIVES_FROM]->()
        WHERE r.edge_id = $edge_id OR elementId(r) = $edge_id
        WITH collect(r) AS rels
        FOREACH (r IN rels | DELETE r)
        RETURN size(rels) AS deleted
        """,
        edge_id=edge_id,
    )
    if not rows or rows[0]["deleted"] == 0:
        raise LineageEdgeNotFound(edge_id)

def get_lineage(table: str, direction: str = "down", depth: int = 5) -> list[LineageEdge]:
    if direction not in ("up", "down"):
        raise ValueError(f"direction must be 'up' or 'down', got {direction!r}")
    if not 1 <= depth <= 5:
        raise ValueError(f"depth must be in [1,5], got {depth}")
    if get_table_by_name(table, optional=True) is None:
        raise TableNotFound(table)
    path_match = (
        f"MATCH p = (:Table {{name: $name}})-[:HAS_FIELD]->(:Field)<-[:DERIVES_FROM*1..{depth}]-(:Field)"
        if direction == "down"
        else f"MATCH p = (:Table {{name: $name}})-[:HAS_FIELD]->(:Field)-[:DERIVES_FROM*1..{depth}]->(:Field)"
    )
    rows = run_query(
        path_match + """
        UNWIND relationships(p) AS r
        WITH DISTINCT r, startNode(r) AS to_f, endNode(r) AS from_f
        MATCH (from_t:Table)-[:HAS_FIELD]->(from_f)
        MATCH (to_t:Table)-[:HAS_FIELD]->(to_f)
        RETURN coalesce(r.edge_id, elementId(r)) AS edge_id,
               from_t.name AS from_table, from_f.name AS from_field,
               to_t.name AS to_table, to_f.name AS to_field,
               r.transform_expr AS transform_expr, r.created_at AS created_at
        ORDER BY from_table, from_field, to_table, to_field
        """,
        name=table,
    )
    return [_lineage_edge_from_row(r) for r in rows]


def get_downstream_impact(table: str, field: Optional[str] = None) -> ImpactResponse:
    if get_table_by_name(table, optional=True) is None:
        raise TableNotFound(table)
    field_filter = "AND root_f.name = $field" if field is not None else ""
    rows = run_query(
        f"""
        MATCH (:Table {{name: $table}})-[:HAS_FIELD]->(root_f:Field)
        {field_filter}
        MATCH p = (root_f)<-[:DERIVES_FROM*1..5]-(:Field)
        UNWIND relationships(p) AS r
        WITH DISTINCT r, startNode(r) AS to_f, endNode(r) AS from_f
        MATCH (from_t:Table)-[:HAS_FIELD]->(from_f)
        MATCH (to_t:Table)-[:HAS_FIELD]->(to_f)
        RETURN coalesce(r.edge_id, elementId(r)) AS edge_id,
               from_t.name AS from_table, from_f.name AS from_field,
               to_t.name AS to_table, to_f.name AS to_field,
               r.transform_expr AS transform_expr, r.created_at AS created_at
        ORDER BY to_t.name, to_f.name
        """,
        table=table,
        field=field,
    )
    if field is not None and not rows:
        exists = run_query(
            """
            MATCH (:Table {name: $table})-[:HAS_FIELD]->(:Field {name: $field})
            RETURN 1 AS found
            """,
            table=table,
            field=field,
        )
        if not exists:
            raise FieldNotFound(f"{table}.{field}")
    downstream = [_lineage_edge_from_row(r) for r in rows]
    affected_tables = sorted({edge.to_table for edge in downstream})
    return ImpactResponse(
        table=table,
        field=field,
        has_downstream=bool(downstream),
        affected_tables=affected_tables,
        downstream=downstream,
    )


def run_query_update_table(table_id: str, req) -> None:
    sets: list[str] = []
    params: dict = {"id": table_id}
    if req.layer is not None:
        sets.append("t.layer = $layer")
        sets.append("t.layer_priority = $layer_priority")
        params["layer"] = req.layer
        params["layer_priority"] = LAYER_PRIORITY[req.layer]
    if req.storage_type is not None:
        sets.append("t.storage_type = $storage_type")
        params["storage_type"] = req.storage_type
    if req.description is not None:
        sets.append("t.description = $description")
        params["description"] = req.description
    if not sets:
        return
    run_query(f"MATCH (t:Table {{id: $id}}) SET {', '.join(sets)}", **params)
