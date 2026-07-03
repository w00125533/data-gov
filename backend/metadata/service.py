"""Cypher implementations for table/field CRUD + lineage queries.

This module is the single source of truth for graph mutations and reads.
Both HTTP routes (backend/api/metadata.py) and future Agent tools depend on it.
"""
from __future__ import annotations

import hashlib
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
    LineageEdgeEndpointUpdateRequest,
    LineageGraphResponse,
    LineageTableEdge,
    LineageTableNode,
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


class LineageEndpointConflict(Exception):
    def __init__(self, edge_id: str):
        self.edge_id = edge_id
        super().__init__("lineage endpoint already exists")


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
               t.storage_type AS storage_type, t.description AS description, fields,
               t.sql_logic AS sql_logic, t.sql_dialect AS sql_dialect,
               t.sql_source AS sql_source, t.sql_updated_at AS sql_updated_at
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
        sql_logic=row.get("sql_logic") or None,
        sql_dialect=row.get("sql_dialect") or None,
        sql_source=row.get("sql_source") or None,
        sql_updated_at=_serialize_neo4j_datetime(row.get("sql_updated_at")),
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


def _json_dict(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        if not value.strip():
            return {}
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _calc_params_to_str(value) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _graph_version(rows: list[LineageEdge]) -> str:
    payload = [
        {
            "edge_id": edge.edge_id,
            "from_table": edge.from_table,
            "from_field": edge.from_field,
            "to_table": edge.to_table,
            "to_field": edge.to_field,
            "transform_expr": edge.transform_expr,
            "calc_type": edge.calc_type,
            "calc_params": edge.calc_params,
            "updated_at": edge.updated_at,
        }
        for edge in sorted(
            rows,
            key=lambda e: (e.edge_id, e.from_table, e.from_field, e.to_table, e.to_field),
        )
    ]
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"edges:{len(rows)}:{digest}"


def _lineage_edge_from_row(row: dict) -> LineageEdge:
    return LineageEdge(
        edge_id=str(row.get("edge_id") or ""),
        from_table=row["from_table"],
        from_field=row["from_field"],
        to_table=row["to_table"],
        to_field=row["to_field"],
        transform_expr=row.get("transform_expr") or "",
        calc_type=row.get("calc_type") or "DIRECT",
        calc_params=_json_dict(row.get("calc_params")),
        created_at=_serialize_neo4j_datetime(row.get("created_at")),
        updated_at=_serialize_neo4j_datetime(row.get("updated_at")),
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
               r.transform_expr AS transform_expr,
               coalesce(r.calc_type, 'DIRECT') AS calc_type,
               coalesce(r.calc_params, '{}') AS calc_params,
               r.created_at AS created_at, r.updated_at AS updated_at
        """,
        edge_id=edge_id,
    )
    if not rows:
        raise LineageEdgeNotFound(edge_id)
    return _lineage_edge_from_row(rows[0])


def assert_no_lineage_cycle(
    target_field_id: str,
    source_field_id: str,
    ignore_edge_id: str | None = None,
) -> None:
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
        WHERE $ignore_edge_id IS NULL OR none(
            rel IN relationships(p)
            WHERE coalesce(rel.edge_id, elementId(rel)) = $ignore_edge_id
        )
        WITH nodes(p) AS path_nodes
        UNWIND path_nodes AS f
        MATCH (t:Table)-[:HAS_FIELD]->(f)
        RETURN collect({table: t.name, field: f.name, field_id: f.id}) AS path
        LIMIT 1
        """,
        source_field_id=source_field_id,
        target_field_id=target_field_id,
        ignore_edge_id=ignore_edge_id,
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
                      r.created_at = datetime()
        ON MATCH SET r.transform_expr = $transform_expr,
                     r.calc_type = $calc_type,
                     r.calc_params = $calc_params,
                     r.updated_at = datetime()
        SET r.transform_expr = $transform_expr,
            r.calc_type = $calc_type,
            r.calc_params = $calc_params,
            r.updated_at = datetime()
        RETURN coalesce(r.edge_id, elementId(r)) AS edge_id
        """,
        source_field_id=source_field_id,
        target_field_id=target_field_id,
        edge_id=str(uuid.uuid4()),
        transform_expr=req.transform_expr,
        calc_type=req.calc_type,
        calc_params=_calc_params_to_str(req.calc_params),
    )
    if not rows:
        raise LineageEdgeNotFound(f"{req.from_table}.{req.from_field} -> {req.to_table}.{req.to_field}")
    return _load_lineage_edge(rows[0]["edge_id"])


def update_lineage_edge(edge_id: str, req: LineageEdgeUpdateRequest) -> LineageEdge:
    rows = run_query(
        """
        MATCH ()-[r:DERIVES_FROM]->()
        WHERE r.edge_id = $edge_id OR elementId(r) = $edge_id
        SET r.transform_expr = $transform_expr,
            r.calc_type = $calc_type,
            r.calc_params = $calc_params,
            r.updated_at = datetime()
        RETURN coalesce(r.edge_id, elementId(r)) AS edge_id
        """,
        edge_id=edge_id,
        transform_expr=req.transform_expr,
        calc_type=req.calc_type,
        calc_params=_calc_params_to_str(req.calc_params),
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


def update_lineage_edge_endpoints(edge_id: str, req: LineageEdgeEndpointUpdateRequest) -> LineageEdge:
    current = _load_lineage_edge(edge_id)
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
    assert_no_lineage_cycle(
        target_field_id=target_field_id,
        source_field_id=source_field_id,
        ignore_edge_id=edge_id,
    )

    rows = run_query(
        """
        MATCH ()-[old_r:DERIVES_FROM]->()
        WHERE old_r.edge_id = $edge_id OR elementId(old_r) = $edge_id
        MATCH (from_f:Field {id: $source_field_id})
        MATCH (to_f:Field {id: $target_field_id})
        OPTIONAL MATCH (to_f)-[existing:DERIVES_FROM]->(from_f)
        WITH old_r, from_f, to_f, existing, properties(old_r) AS old_props,
             coalesce(existing.edge_id, elementId(existing)) AS existing_edge_id
        WITH old_r, from_f, to_f, old_props,
             CASE
                 WHEN existing IS NOT NULL AND existing <> old_r THEN existing_edge_id
                 ELSE null
             END AS conflict_edge_id
        FOREACH (_ IN CASE WHEN conflict_edge_id IS NULL THEN [1] ELSE [] END |
            DELETE old_r
        )
        FOREACH (_ IN CASE WHEN conflict_edge_id IS NULL THEN [1] ELSE [] END |
            CREATE (to_f)-[new_r:DERIVES_FROM]->(from_f)
            SET new_r = old_props,
                new_r.edge_id = $edge_id,
                new_r.updated_at = datetime()
        )
        RETURN CASE WHEN conflict_edge_id IS NULL THEN $edge_id ELSE null END AS edge_id,
               conflict_edge_id
        """,
        source_field_id=source_field_id,
        target_field_id=target_field_id,
        edge_id=edge_id,
    )
    if not rows:
        raise LineageEdgeNotFound(edge_id)
    if rows[0].get("conflict_edge_id"):
        raise LineageEndpointConflict(rows[0]["conflict_edge_id"])
    return _load_lineage_edge(rows[0]["edge_id"])


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
               r.transform_expr AS transform_expr,
               coalesce(r.calc_type, 'DIRECT') AS calc_type,
               coalesce(r.calc_params, '{}') AS calc_params,
               r.created_at AS created_at, r.updated_at AS updated_at
        ORDER BY from_table, from_field, to_table, to_field
        """,
        name=table,
    )
    return [_lineage_edge_from_row(r) for r in rows]


def get_lineage_graph(
    table: str,
    depth: int = 2,
    include_upstream: bool = True,
    include_downstream: bool = True,
) -> LineageGraphResponse:
    root_table = get_table_by_name(table, optional=True)
    if root_table is None:
        raise TableNotFound(table)

    upstream_edges = get_lineage(table, direction="up", depth=depth) if include_upstream else []
    downstream_edges = get_lineage(table, direction="down", depth=depth) if include_downstream else []

    field_edge_by_id: dict[str, LineageEdge] = {}
    for edge in [*upstream_edges, *downstream_edges]:
        field_edge_by_id[edge.edge_id] = edge
    field_edges = sorted(
        field_edge_by_id.values(),
        key=lambda e: (e.from_table, e.to_table, e.from_field, e.to_field, e.edge_id),
    )

    table_names = {table}
    for edge in field_edges:
        table_names.add(edge.from_table)
        table_names.add(edge.to_table)

    tables: list[LineageTableNode] = []
    detail_by_name: dict[str, TableResponse] = {}
    for table_name in sorted(table_names):
        detail = get_table_by_name(table_name)
        detail_by_name[table_name] = detail
        tables.append(LineageTableNode(
            id=detail.id,
            name=detail.name,
            layer=detail.layer,
            layer_priority=detail.layer_priority,
            storage_type=detail.storage_type,
            description=detail.description,
            field_count=len(detail.fields),
            fields=detail.fields,
            sql_logic=detail.sql_logic,
            sql_dialect=detail.sql_dialect,
            sql_source=detail.sql_source,
            sql_updated_at=detail.sql_updated_at,
        ))

    grouped: dict[tuple[str, str, str], list[LineageEdge]] = {}
    for edge in upstream_edges:
        grouped.setdefault((edge.from_table, edge.to_table, "upstream"), []).append(edge)
    for edge in downstream_edges:
        grouped.setdefault((edge.from_table, edge.to_table, "downstream"), []).append(edge)

    table_edges: list[LineageTableEdge] = []
    for (from_table, to_table, direction), edges in sorted(grouped.items()):
        calc_type_counts: dict[str, int] = {}
        for edge in edges:
            calc_type_counts[edge.calc_type] = calc_type_counts.get(edge.calc_type, 0) + 1
        table_edges.append(LineageTableEdge(
            source=from_table,
            target=to_table,
            direction=direction,
            field_edge_count=len(edges),
            calc_type_counts=dict(sorted(calc_type_counts.items())),
            fields=sorted({edge.to_field for edge in edges}),
        ))

    return LineageGraphResponse(
        root_table=table,
        depth=depth,
        include_upstream=include_upstream,
        include_downstream=include_downstream,
        graph_version=_graph_version(field_edges),
        tables=tables,
        table_edges=table_edges,
        field_edges=field_edges,
        saved_sql=detail_by_name[table].sql_logic,
    )


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
               r.transform_expr AS transform_expr,
               coalesce(r.calc_type, 'DIRECT') AS calc_type,
               coalesce(r.calc_params, '{{}}') AS calc_params,
               r.created_at AS created_at, r.updated_at AS updated_at
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
