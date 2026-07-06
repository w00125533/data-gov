"""Cypher implementations for table/field CRUD + lineage queries.

This module is the single source of truth for graph mutations and reads.
Both HTTP routes (backend/api/metadata.py) and future Agent tools depend on it.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Optional

from backend.metadata.graph import run_query, run_write_transaction
from backend.metadata.lineage_sql import generate_select_sql, parse_select_preview
from backend.metadata.models import (
    CategoryNodeResponse,
    CategoryRef,
    CreateCategoryRequest,
    CreateFieldRequest,
    CreateTagGroupRequest,
    CreateTagRequest,
    CreateTableRequest,
    FieldResponse,
    ImpactResponse,
    LineageEdge,
    LineageEdgeCreateRequest,
    LineageEdgeEndpointUpdateRequest,
    LineageGraphResponse,
    LineageSqlApplyRequest,
    LineageSqlImportPreviewResponse,
    LineageSqlPreviewResponse,
    LineageTableEdge,
    LineageTableNode,
    LineageEdgeUpdateRequest,
    MoveCategoryRequest,
    StatusUpdateRequest,
    TableClassificationUpdateRequest,
    TableResponse,
    TableSummary,
    TagGroupResponse,
    TagRef,
    TagResponse,
    UpdateCategoryRequest,
    UpdateFieldRequest,
    UpdateTagGroupRequest,
    UpdateTagRequest,
    UpstreamRef,
)


LAYER_PRIORITY = {"ODS": 1, "DWD": 2, "DWS": 3, "ADS": 4, "EVAL": 5}


class TableNotFound(Exception):
    pass


class CategoryNotFound(Exception):
    pass


class CategoryAlreadyExists(Exception):
    pass


class InvalidCategoryMove(Exception):
    pass


class TagNotFound(Exception):
    pass


class TagAlreadyExists(Exception):
    pass


class TagGroupNotFound(Exception):
    pass


class TagGroupAlreadyExists(Exception):
    pass


class ProtectedCategoryOperation(Exception):
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

def _category_id(code: str) -> str:
    return f"category:{code}"


def _tag_group_id(code: str) -> str:
    return f"tag-group:{code}"


def _tag_id(code: str) -> str:
    return f"tag:{code}"


def _json_change_value(value: Optional[dict | list]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _record_change(
    operation: str,
    target_type: str,
    target_id: str,
    *,
    tx=None,
    table_name: Optional[str] = None,
    field_name: Optional[str] = None,
    old_value: Optional[dict | list] = None,
    new_value: Optional[dict | list] = None,
) -> None:
    cypher = (
        """
        CREATE (:Change {
            id: $change_id,
            operation: $operation,
            table_name: $table_name,
            field_name: $field_name,
            target_type: $target_type,
            target_id: $target_id,
            old_value: $old_value,
            new_value: $new_value,
            changed_at: datetime(),
            commit_hash: $commit_hash
        })
        """
    )
    params = dict(
        change_id=str(uuid.uuid4()),
        operation=operation,
        table_name=table_name,
        field_name=field_name,
        target_type=target_type,
        target_id=target_id,
        old_value=_json_change_value(old_value),
        new_value=_json_change_value(new_value),
        commit_hash="",
    )
    if tx is not None:
        tx.run(cypher, params)
        return
    run_query(cypher, **params)


def _clean_optional_map(value: Optional[dict]) -> Optional[dict]:
    if not value or value.get("id") is None:
        return None
    return value


def _load_table_taxonomy(table_id: str) -> tuple[Optional[CategoryRef], list[TagRef]]:
    rows = run_query(
        """
        MATCH (t:Table {id: $table_id})
        OPTIONAL MATCH (t)-[:IN_CATEGORY]->(category:MetaCategory)
        OPTIONAL MATCH (parent:MetaCategory)-[:HAS_CHILD]->(category)
        WITH t, category, parent
        OPTIONAL MATCH (t)-[:TAGGED_WITH]->(tag:MetaTag)
        WHERE tag IS NULL OR NOT tag.code STARTS WITH 'tag:'
        WITH category, parent, tag
        ORDER BY tag.sort_order, tag.name
        WITH category, parent,
             collect(CASE WHEN tag IS NULL THEN null ELSE {
                 id: tag.id,
                 code: tag.code,
                 name: tag.name
             } END) AS raw_tags
        RETURN CASE WHEN category IS NULL THEN null ELSE {
                   id: category.id,
                   code: category.code,
                   name: category.name,
                   path: CASE
                       WHEN parent IS NULL THEN [category.name]
                       ELSE [parent.name, category.name]
                   END
               } END AS category,
               [tag IN raw_tags WHERE tag IS NOT NULL AND tag.id IS NOT NULL] AS tags
        """,
        table_id=table_id,
    )
    if not rows:
        return None, []
    category = _clean_optional_map(rows[0].get("category"))
    tags = [tag for tag in rows[0].get("tags", []) if tag.get("id") is not None]
    return (
        CategoryRef(**category) if category is not None else None,
        [TagRef(**tag) for tag in tags],
    )


def list_tables(
    layer: Optional[str] = None,
    search: Optional[str] = None,
    category_id: Optional[str] = None,
    include_children: bool = True,
    tag_ids: Optional[list[str]] = None,
    tag_match: str = "all",
    uncategorized: bool = False,
) -> list[TableSummary]:
    if tag_match not in ("any", "all"):
        raise ValueError(f"tag_match must be 'any' or 'all', got {tag_match!r}")

    cypher_filters = []
    params: dict = {}
    if layer:
        cypher_filters.append("t.layer = $layer")
        params["layer"] = layer
    if search:
        cypher_filters.append("(toLower(t.name) CONTAINS toLower($search) OR toLower(t.description) CONTAINS toLower($search))")
        params["search"] = search
    if category_id:
        cypher_filters.append(
            """
            EXISTS {
                MATCH (selected:MetaCategory {id: $category_id})
                MATCH (t)-[:IN_CATEGORY]->(category:MetaCategory)
                WHERE category.id = selected.id
                   OR ($include_children = true AND EXISTS {
                       MATCH (selected)-[:HAS_CHILD]->(category)
                   })
            }
            """
        )
        params["category_id"] = category_id
        params["include_children"] = include_children
    if uncategorized:
        cypher_filters.append("NOT EXISTS { MATCH (t)-[:IN_CATEGORY]->(:MetaCategory) }")
    normalized_tag_ids = tag_ids or []
    if normalized_tag_ids:
        params["tag_ids"] = normalized_tag_ids
        if tag_match == "any":
            cypher_filters.append(
                """
                EXISTS {
                    MATCH (t)-[:TAGGED_WITH]->(tag:MetaTag)
                    WHERE tag.id IN $tag_ids
                }
                """
            )
        else:
            cypher_filters.append(
                """
                all(tag_id IN $tag_ids WHERE EXISTS {
                    MATCH (t)-[:TAGGED_WITH]->(tag:MetaTag)
                    WHERE tag.id = tag_id
                })
                """
            )
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
    summaries: list[TableSummary] = []
    for row in rows:
        category, tags = _load_table_taxonomy(row["id"])
        summaries.append(TableSummary(**row, category=category, tags=tags))
    return summaries


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
    category, tags = _load_table_taxonomy(row["id"])
    return TableResponse(
        id=row["id"], name=row["name"], layer=row["layer"], layer_priority=row["layer_priority"],
        storage_type=row["storage_type"], description=row["description"], fields=fields,
        sql_logic=row.get("sql_logic") or None,
        sql_dialect=row.get("sql_dialect") or None,
        sql_source=row.get("sql_source") or None,
        sql_updated_at=_serialize_neo4j_datetime(row.get("sql_updated_at")),
        category=category,
        tags=tags,
    )


def get_table_by_id(table_id: str) -> TableResponse:
    rows = run_query("MATCH (t:Table {id: $id}) RETURN t.name AS name", id=table_id)
    if not rows:
        raise TableNotFound(table_id)
    return get_table_by_name(rows[0]["name"])


def create_table(req: CreateTableRequest) -> TableResponse:
    table_id = str(uuid.uuid4())
    _validate_active_level2_category(req.category_id)
    unique_tag_ids = list(dict.fromkeys(req.tag_ids))
    _validate_active_tags(unique_tag_ids)

    def _create(tx):
        tx.run(
            """
            CREATE (t:Table {
                id: $id, name: $name, layer: $layer, layer_priority: $layer_priority,
                storage_type: $storage_type, description: $description
            })
            """,
            {
                "id": table_id,
                "name": req.name,
                "layer": req.layer,
                "layer_priority": LAYER_PRIORITY[req.layer],
                "storage_type": req.storage_type,
                "description": req.description,
            },
        )
        tx.run(
            """
            MATCH (t:Table {id: $table_id})
            MATCH (category:MetaCategory {id: $category_id})
            MERGE (t)-[:IN_CATEGORY]->(category)
            """,
            {
                "table_id": table_id,
                "category_id": req.category_id,
            },
        )
        if unique_tag_ids:
            tx.run(
                """
                MATCH (t:Table {id: $table_id})
                WITH t
            MATCH (tag:MetaTag)
            WHERE tag.id IN $tag_ids
            MERGE (t)-[:TAGGED_WITH]->(tag)
            """,
                {
                    "table_id": table_id,
                    "tag_ids": unique_tag_ids,
                },
            )
        _record_change(
            "table_create",
            "table",
            table_id,
            tx=tx,
            table_name=req.name,
            new_value={
                "name": req.name,
                "layer": req.layer,
                "storage_type": req.storage_type,
                "description": req.description,
                "category_id": req.category_id,
                "tag_ids": unique_tag_ids,
            },
        )

    run_write_transaction(_create)
    return get_table_by_name(req.name)


def delete_table(name: str) -> None:
    run_query("MATCH (t:Table {name: $name}) DETACH DELETE t", name=name)


# ----------------------- Taxonomy -----------------------

def _category_node_from_row(row: dict, children: Optional[list[CategoryNodeResponse]] = None) -> CategoryNodeResponse:
    return CategoryNodeResponse(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        level=row["level"],
        sort_order=row.get("sort_order") or 0,
        active=row.get("active", True),
        protected=row.get("protected", False),
        table_count=row.get("table_count") or 0,
        children=children or [],
    )


def _load_category_node(category_id: str) -> CategoryNodeResponse:
    rows = run_query(
        """
        MATCH (category:MetaCategory {id: $category_id})
        OPTIONAL MATCH (category)<-[:IN_CATEGORY]-(table:Table)
        RETURN category.id AS id,
               category.code AS code,
               category.name AS name,
               category.level AS level,
               coalesce(category.sort_order, 0) AS sort_order,
               coalesce(category.active, true) AS active,
               coalesce(category.protected, false) AS protected,
               count(DISTINCT table) AS table_count
        """,
        category_id=category_id,
    )
    if not rows:
        raise CategoryNotFound(category_id)
    return _category_node_from_row(rows[0])


def _load_tag_group(group_id: str) -> TagGroupResponse:
    rows = run_query(
        """
        MATCH (group:MetaTagGroup {id: $group_id})
        OPTIONAL MATCH (group)-[:HAS_TAG]->(tag:MetaTag)
        WITH group, tag
        ORDER BY tag.sort_order, tag.name
        WITH group,
             collect(CASE WHEN tag IS NULL THEN null ELSE {
                 id: tag.id,
                 code: tag.code,
                 name: tag.name,
                 sort_order: coalesce(tag.sort_order, 0),
                 active: coalesce(tag.active, true)
             } END) AS raw_tags
        RETURN group.id AS id,
               group.code AS code,
               group.name AS name,
               coalesce(group.sort_order, 0) AS sort_order,
               coalesce(group.active, true) AS active,
               [tag IN raw_tags WHERE tag IS NOT NULL AND tag.id IS NOT NULL] AS tags
        """,
        group_id=group_id,
    )
    if not rows:
        raise TagGroupNotFound(group_id)
    row = rows[0]
    return TagGroupResponse(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        sort_order=row["sort_order"],
        active=row["active"],
        tags=[TagResponse(**tag) for tag in row["tags"]],
    )


def _load_tag(tag_id: str) -> TagResponse:
    rows = run_query(
        """
        MATCH (tag:MetaTag {id: $tag_id})
        RETURN tag.id AS id,
               tag.code AS code,
               tag.name AS name,
               coalesce(tag.sort_order, 0) AS sort_order,
               coalesce(tag.active, true) AS active
        """,
        tag_id=tag_id,
    )
    if not rows:
        raise TagNotFound(tag_id)
    return TagResponse(**rows[0])


def list_categories_tree() -> list[CategoryNodeResponse]:
    rows = run_query(
        """
        MATCH (root:MetaCategory)
        WHERE coalesce(root.level, 1) = 1
        CALL {
            WITH root
            OPTIONAL MATCH (root)<-[:IN_CATEGORY]-(root_table:Table)
            RETURN count(DISTINCT root_table) AS direct_table_count
        }
        CALL {
            WITH root
            OPTIONAL MATCH (root)-[:HAS_CHILD]->(:MetaCategory)<-[:IN_CATEGORY]-(child_table:Table)
            RETURN count(DISTINCT child_table) AS child_table_count_total
        }
        CALL {
            WITH root
            OPTIONAL MATCH (root)-[:HAS_CHILD]->(child:MetaCategory)
            OPTIONAL MATCH (child)<-[:IN_CATEGORY]-(child_table:Table)
            WITH child, count(DISTINCT child_table) AS child_table_count
            ORDER BY child.sort_order, child.name
            RETURN collect(CASE WHEN child IS NULL THEN null ELSE {
                id: child.id,
                code: child.code,
                name: child.name,
                level: child.level,
                sort_order: coalesce(child.sort_order, 0),
                active: coalesce(child.active, true),
                protected: coalesce(child.protected, false),
                table_count: child_table_count
            } END) AS raw_children
        }
        RETURN root.id AS id,
               root.code AS code,
               root.name AS name,
               root.level AS level,
               coalesce(root.sort_order, 0) AS sort_order,
               coalesce(root.active, true) AS active,
               coalesce(root.protected, false) AS protected,
               direct_table_count + child_table_count_total AS table_count,
               [child IN raw_children WHERE child IS NOT NULL AND child.id IS NOT NULL] AS children
        ORDER BY sort_order, name
        """
    )
    roots: list[CategoryNodeResponse] = []
    for row in rows:
        children = [_category_node_from_row(child) for child in row["children"]]
        roots.append(_category_node_from_row(row, children=children))
    return roots


def list_tags() -> list[TagGroupResponse]:
    rows = run_query(
        """
        MATCH (group:MetaTagGroup)
        OPTIONAL MATCH (group)-[:HAS_TAG]->(tag:MetaTag)
        WHERE tag IS NULL OR NOT tag.code STARTS WITH 'tag:'
        WITH group, tag
        ORDER BY group.sort_order, group.name, tag.sort_order, tag.name
        WITH group,
             collect(CASE WHEN tag IS NULL THEN null ELSE {
                 id: tag.id,
                 code: tag.code,
                 name: tag.name,
                 sort_order: coalesce(tag.sort_order, 0),
                 active: coalesce(tag.active, true)
             } END) AS raw_tags
        RETURN group.id AS id,
               group.code AS code,
               group.name AS name,
               coalesce(group.sort_order, 0) AS sort_order,
               coalesce(group.active, true) AS active,
               [tag IN raw_tags WHERE tag IS NOT NULL AND tag.id IS NOT NULL] AS tags
        ORDER BY sort_order, name
        """
    )
    return [
        TagGroupResponse(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            sort_order=row["sort_order"],
            active=row["active"],
            tags=[TagResponse(**tag) for tag in row["tags"]],
        )
        for row in rows
    ]


def _validate_active_level2_category(category_id: str) -> None:
    rows = run_query(
        """
        MATCH (category:MetaCategory {id: $category_id})
        WHERE coalesce(category.active, true) = true
          AND category.level = 2
        RETURN category.id AS id
        """,
        category_id=category_id,
    )
    if not rows:
        raise CategoryNotFound(category_id)


def _validate_active_tags(tag_ids: list[str]) -> None:
    if not tag_ids:
        return
    unique_tag_ids = list(dict.fromkeys(tag_ids))
    rows = run_query(
        """
        MATCH (tag:MetaTag)
        WHERE tag.id IN $tag_ids
          AND coalesce(tag.active, true) = true
        RETURN collect(tag.id) AS found_ids
        """,
        tag_ids=unique_tag_ids,
    )
    found_ids = set(rows[0]["found_ids"] if rows else [])
    missing = [tag_id for tag_id in unique_tag_ids if tag_id not in found_ids]
    if missing:
        raise TagNotFound(missing[0])


def update_table_classification(table_id: str, req: TableClassificationUpdateRequest) -> TableResponse:
    table_rows = run_query("MATCH (t:Table {id: $table_id}) RETURN t.name AS name", table_id=table_id)
    if not table_rows:
        raise TableNotFound(table_id)

    _validate_active_level2_category(req.category_id)
    _validate_active_tags(req.tag_ids)

    unique_tag_ids = list(dict.fromkeys(req.tag_ids))

    def _update(tx):
        old_rows = list(tx.run(
            """
            MATCH (t:Table {id: $table_id})
            OPTIONAL MATCH (t)-[:IN_CATEGORY]->(old_category:MetaCategory)
            OPTIONAL MATCH (t)-[:TAGGED_WITH]->(old_tag:MetaTag)
            WITH old_category, old_tag
            ORDER BY old_tag.id
            RETURN CASE WHEN old_category IS NULL THEN null ELSE old_category.id END AS old_category,
                   [tag_id IN collect(old_tag.id) WHERE tag_id IS NOT NULL] AS old_tags
            """,
            {"table_id": table_id},
        ))
        old_category = old_rows[0]["old_category"] if old_rows else None
        old_tags = old_rows[0]["old_tags"] if old_rows else []
        tx.run(
            """
            MATCH (t:Table {id: $table_id})
            MATCH (category:MetaCategory {id: $category_id})
            OPTIONAL MATCH (t)-[old_category_rel:IN_CATEGORY]->(:MetaCategory)
            DELETE old_category_rel
            MERGE (t)-[:IN_CATEGORY]->(category)
            WITH t
            OPTIONAL MATCH (t)-[old_tag_rel:TAGGED_WITH]->(:MetaTag)
            DELETE old_tag_rel
            """,
            {
                "table_id": table_id,
                "category_id": req.category_id,
            },
        )
        if unique_tag_ids:
            tx.run(
                """
                MATCH (t:Table {id: $table_id})
                WITH t
            MATCH (tag:MetaTag)
            WHERE tag.id IN $tag_ids
            MERGE (t)-[:TAGGED_WITH]->(tag)
            """,
                {
                    "table_id": table_id,
                    "tag_ids": unique_tag_ids,
                },
            )
        _record_change(
            "table_classification_update",
            "table",
            table_id,
            tx=tx,
            table_name=table_rows[0]["name"],
            old_value={
                "category_id": old_category,
                "tag_ids": old_tags,
            },
            new_value={
                "category_id": req.category_id,
                "tag_ids": unique_tag_ids,
            },
        )

    run_write_transaction(_update)
    return get_table_by_name(table_rows[0]["name"])


def create_category(req: CreateCategoryRequest) -> CategoryNodeResponse:
    category_id = _category_id(req.code)
    existing = run_query(
        "MATCH (category:MetaCategory {code: $code}) RETURN category.id AS id",
        code=req.code,
    )
    if existing:
        raise CategoryAlreadyExists(req.code)

    if req.parent_id is None:
        level = 1
        def _create_root(tx):
            tx.run(
                """
                CREATE (category:MetaCategory {
                    id: $id,
                    code: $code,
                    name: $name,
                    level: $level,
                    sort_order: $sort_order,
                    active: $active,
                    protected: false,
                    created_at: datetime(),
                    updated_at: datetime()
                })
                """,
                {
                    "id": category_id,
                    "code": req.code,
                    "name": req.name,
                    "level": level,
                    "sort_order": req.sort_order,
                    "active": req.active,
                },
            )
            _record_change(
                "category_create",
                "MetaCategory",
                category_id,
                tx=tx,
                new_value=req.model_dump(),
            )

        run_write_transaction(_create_root)
        return _load_category_node(category_id)

    parent_rows = run_query(
        "MATCH (parent:MetaCategory {id: $parent_id}) RETURN parent.level AS level",
        parent_id=req.parent_id,
    )
    if not parent_rows:
        raise CategoryNotFound(req.parent_id)
    if int(parent_rows[0]["level"]) != 1:
        raise InvalidCategoryMove(req.parent_id)
    level = int(parent_rows[0]["level"]) + 1
    def _create_child(tx):
        tx.run(
            """
            MATCH (parent:MetaCategory {id: $parent_id})
            CREATE (category:MetaCategory {
                id: $id,
                code: $code,
                name: $name,
                level: $level,
                sort_order: $sort_order,
                active: $active,
                protected: false,
                created_at: datetime(),
                updated_at: datetime()
            })
            MERGE (parent)-[:HAS_CHILD]->(category)
            """,
            {
                "parent_id": req.parent_id,
                "id": category_id,
                "code": req.code,
                "name": req.name,
                "level": level,
                "sort_order": req.sort_order,
                "active": req.active,
            },
        )
        _record_change(
            "category_create",
            "MetaCategory",
            category_id,
            tx=tx,
            new_value=req.model_dump(),
        )

    run_write_transaction(_create_child)
    return _load_category_node(category_id)


def update_category(category_id: str, req: UpdateCategoryRequest) -> CategoryNodeResponse:
    if not run_query("MATCH (:MetaCategory {id: $category_id}) RETURN 1 AS found", category_id=category_id):
        raise CategoryNotFound(category_id)
    sets: list[str] = []
    params: dict = {"category_id": category_id}
    if req.name is not None:
        sets.append("category.name = $name")
        params["name"] = req.name
    if req.sort_order is not None:
        sets.append("category.sort_order = $sort_order")
        params["sort_order"] = req.sort_order
    if sets:
        sets.append("category.updated_at = datetime()")
        def _update(tx):
            old_rows = list(tx.run(
                """
                MATCH (category:MetaCategory {id: $category_id})
                RETURN category.name AS name,
                       coalesce(category.sort_order, 0) AS sort_order
                """,
                {"category_id": category_id},
            ))
            old = dict(old_rows[0]) if old_rows else {}
            tx.run(
                f"MATCH (category:MetaCategory {{id: $category_id}}) SET {', '.join(sets)}",
                params,
            )
            _record_change(
                "category_update",
                "MetaCategory",
                category_id,
                tx=tx,
                old_value=old,
                new_value={
                    "name": req.name if req.name is not None else old.get("name"),
                    "sort_order": req.sort_order if req.sort_order is not None else old.get("sort_order"),
                },
            )

        run_write_transaction(_update)
    return _load_category_node(category_id)


def move_category(category_id: str, req: MoveCategoryRequest) -> CategoryNodeResponse:
    category_rows = run_query(
        """
        MATCH (category:MetaCategory {id: $category_id})
        RETURN category.level AS level,
               coalesce(category.protected, false) AS protected
        """,
        category_id=category_id,
    )
    if not category_rows:
        raise CategoryNotFound(category_id)
    if category_rows[0]["protected"]:
        raise ProtectedCategoryOperation(category_id)
    if category_id == req.parent_id:
        raise InvalidCategoryMove(category_id)
    if int(category_rows[0]["level"]) != 2:
        raise InvalidCategoryMove(category_id)
    parent_rows = run_query(
        "MATCH (parent:MetaCategory {id: $parent_id}) RETURN parent.level AS level",
        parent_id=req.parent_id,
    )
    if not parent_rows:
        raise CategoryNotFound(req.parent_id)
    if int(parent_rows[0]["level"]) != 1:
        raise InvalidCategoryMove(req.parent_id)
    def _move(tx):
        old_rows = list(tx.run(
            """
            MATCH (category:MetaCategory {id: $category_id})
            OPTIONAL MATCH (old_parent:MetaCategory)-[:HAS_CHILD]->(category)
            RETURN old_parent.id AS parent_id
            """,
            {"category_id": category_id},
        ))
        old_parent_id = old_rows[0]["parent_id"] if old_rows else None
        tx.run(
            """
            MATCH (category:MetaCategory {id: $category_id})
            MATCH (parent:MetaCategory {id: $parent_id})
            OPTIONAL MATCH (:MetaCategory)-[old_parent:HAS_CHILD]->(category)
            DELETE old_parent
            MERGE (parent)-[:HAS_CHILD]->(category)
            SET category.level = parent.level + 1,
                category.updated_at = datetime()
            """,
            {"category_id": category_id, "parent_id": req.parent_id},
        )
        _record_change(
            "category_move",
            "MetaCategory",
            category_id,
            tx=tx,
            old_value={"parent_id": old_parent_id},
            new_value={"parent_id": req.parent_id},
        )

    run_write_transaction(_move)
    return _load_category_node(category_id)


def update_category_status(category_id: str, req: StatusUpdateRequest) -> CategoryNodeResponse:
    rows = run_query(
        """
        MATCH (category:MetaCategory {id: $category_id})
        RETURN coalesce(category.protected, false) AS protected,
               coalesce(category.active, true) AS active
        """,
        category_id=category_id,
    )
    if not rows:
        raise CategoryNotFound(category_id)
    if rows[0]["protected"] and req.active is False:
        raise ProtectedCategoryOperation(category_id)
    def _update_status(tx):
        old_rows = list(tx.run(
            """
            MATCH (category:MetaCategory {id: $category_id})
            RETURN coalesce(category.active, true) AS active
            """,
            {"category_id": category_id},
        ))
        old_active = old_rows[0]["active"] if old_rows else None
        tx.run(
            """
            MATCH (category:MetaCategory {id: $category_id})
            SET category.active = $active,
                category.updated_at = datetime()
            """,
            {"category_id": category_id, "active": req.active},
        )
        _record_change(
            "category_status_update",
            "MetaCategory",
            category_id,
            tx=tx,
            old_value={"active": old_active},
            new_value={"active": req.active},
        )

    run_write_transaction(_update_status)
    return _load_category_node(category_id)


def create_tag_group(req: CreateTagGroupRequest) -> TagGroupResponse:
    group_id = _tag_group_id(req.code)
    existing = run_query(
        "MATCH (group:MetaTagGroup {code: $code}) RETURN group.id AS id",
        code=req.code,
    )
    if existing:
        raise TagGroupAlreadyExists(req.code)

    def _create_group(tx):
        tx.run(
            """
            CREATE (group:MetaTagGroup {
                id: $id,
                code: $code,
                name: $name,
                sort_order: $sort_order,
                active: $active,
                created_at: datetime(),
                updated_at: datetime()
            })
            """,
            {
                "id": group_id,
                "code": req.code,
                "name": req.name,
                "sort_order": req.sort_order,
                "active": req.active,
            },
        )
        _record_change(
            "tag_group_create",
            "MetaTagGroup",
            group_id,
            tx=tx,
            new_value=req.model_dump(),
        )

    run_write_transaction(_create_group)
    return _load_tag_group(group_id)


def update_tag_group(group_id: str, req: UpdateTagGroupRequest) -> TagGroupResponse:
    if not run_query("MATCH (:MetaTagGroup {id: $group_id}) RETURN 1 AS found", group_id=group_id):
        raise TagGroupNotFound(group_id)
    sets: list[str] = []
    params: dict = {"group_id": group_id}
    if req.name is not None:
        sets.append("group.name = $name")
        params["name"] = req.name
    if req.sort_order is not None:
        sets.append("group.sort_order = $sort_order")
        params["sort_order"] = req.sort_order
    if req.active is not None:
        sets.append("group.active = $active")
        params["active"] = req.active
    if sets:
        sets.append("group.updated_at = datetime()")
        def _update_group(tx):
            old_rows = list(tx.run(
                """
                MATCH (group:MetaTagGroup {id: $group_id})
                RETURN group.name AS name,
                       coalesce(group.sort_order, 0) AS sort_order,
                       coalesce(group.active, true) AS active
                """,
                {"group_id": group_id},
            ))
            old = dict(old_rows[0]) if old_rows else {}
            tx.run(
                f"MATCH (group:MetaTagGroup {{id: $group_id}}) SET {', '.join(sets)}",
                params,
            )
            _record_change(
                "tag_group_update",
                "MetaTagGroup",
                group_id,
                tx=tx,
                old_value=old,
                new_value={
                    "name": req.name if req.name is not None else old.get("name"),
                    "sort_order": req.sort_order if req.sort_order is not None else old.get("sort_order"),
                    "active": req.active if req.active is not None else old.get("active"),
                },
            )

        run_write_transaction(_update_group)
    return _load_tag_group(group_id)


def create_tag(req: CreateTagRequest) -> TagResponse:
    if not run_query("MATCH (:MetaTagGroup {id: $group_id}) RETURN 1 AS found", group_id=req.group_id):
        raise TagGroupNotFound(req.group_id)
    tag_id = _tag_id(req.code)
    existing = run_query(
        "MATCH (tag:MetaTag {code: $code}) RETURN tag.id AS id",
        code=req.code,
    )
    if existing:
        raise TagAlreadyExists(req.code)

    def _create_tag(tx):
        tx.run(
            """
            MATCH (group:MetaTagGroup {id: $group_id})
            CREATE (group)-[:HAS_TAG]->(tag:MetaTag {
                id: $id,
                code: $code,
                name: $name,
                sort_order: $sort_order,
                active: $active,
                created_at: datetime(),
                updated_at: datetime()
            })
            """,
            {
                "group_id": req.group_id,
                "id": tag_id,
                "code": req.code,
                "name": req.name,
                "sort_order": req.sort_order,
                "active": req.active,
            },
        )
        _record_change(
            "tag_create",
            "MetaTag",
            tag_id,
            tx=tx,
            new_value=req.model_dump(),
        )

    run_write_transaction(_create_tag)
    return _load_tag(tag_id)


def update_tag(tag_id: str, req: UpdateTagRequest) -> TagResponse:
    if not run_query("MATCH (:MetaTag {id: $tag_id}) RETURN 1 AS found", tag_id=tag_id):
        raise TagNotFound(tag_id)
    if req.group_id is not None:
        if not run_query("MATCH (:MetaTagGroup {id: $group_id}) RETURN 1 AS found", group_id=req.group_id):
            raise TagGroupNotFound(req.group_id)
    sets: list[str] = []
    params: dict = {"tag_id": tag_id}
    if req.name is not None:
        sets.append("tag.name = $name")
        params["name"] = req.name
    if req.sort_order is not None:
        sets.append("tag.sort_order = $sort_order")
        params["sort_order"] = req.sort_order
    if sets or req.group_id is not None:
        sets.append("tag.updated_at = datetime()")

        def _update(tx):
            rows = list(tx.run(
                """
                MATCH (tag:MetaTag {id: $tag_id})
                OPTIONAL MATCH (group:MetaTagGroup)-[:HAS_TAG]->(tag)
                RETURN tag.name AS name,
                       coalesce(tag.sort_order, 0) AS sort_order,
                       group.id AS group_id
                """,
                {"tag_id": tag_id},
            ))
            old = dict(rows[0]) if rows else {}
            if sets:
                tx.run(
                    f"MATCH (tag:MetaTag {{id: $tag_id}}) SET {', '.join(sets)}",
                    params,
                )
            if req.group_id is not None:
                tx.run(
                    """
                    MATCH (tag:MetaTag {id: $tag_id})
                    MATCH (group:MetaTagGroup {id: $group_id})
                    OPTIONAL MATCH (:MetaTagGroup)-[old_group_edge:HAS_TAG]->(tag)
                    DELETE old_group_edge
                    MERGE (group)-[:HAS_TAG]->(tag)
                    SET tag.updated_at = datetime()
                    """,
                    {"tag_id": tag_id, "group_id": req.group_id},
                )
            _record_change(
                "tag_update",
                "MetaTag",
                tag_id,
                tx=tx,
                old_value={
                    "name": old.get("name"),
                    "sort_order": old.get("sort_order"),
                    "group_id": old.get("group_id"),
                },
                new_value={
                    "name": req.name if req.name is not None else old.get("name"),
                    "sort_order": req.sort_order if req.sort_order is not None else old.get("sort_order"),
                    "group_id": req.group_id if req.group_id is not None else old.get("group_id"),
                },
            )

        run_write_transaction(_update)
    return _load_tag(tag_id)


def update_tag_status(tag_id: str, req: StatusUpdateRequest) -> TagResponse:
    if not run_query("MATCH (:MetaTag {id: $tag_id}) RETURN 1 AS found", tag_id=tag_id):
        raise TagNotFound(tag_id)
    def _update_status(tx):
        old_rows = list(tx.run(
            """
            MATCH (tag:MetaTag {id: $tag_id})
            RETURN coalesce(tag.active, true) AS active
            """,
            {"tag_id": tag_id},
        ))
        old_active = old_rows[0]["active"] if old_rows else None
        tx.run(
            """
            MATCH (tag:MetaTag {id: $tag_id})
            SET tag.active = $active,
                tag.updated_at = datetime()
            """,
            {"tag_id": tag_id, "active": req.active},
        )
        _record_change(
            "tag_status_update",
            "MetaTag",
            tag_id,
            tx=tx,
            old_value={"active": old_active},
            new_value={"active": req.active},
        )

    run_write_transaction(_update_status)
    return _load_tag(tag_id)


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
        WITH path_nodes, collect({table: t.name, field: f.name, field_id: f.id}) AS path
        RETURN path
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


# ----------------------- Lineage SQL -----------------------

def preview_lineage_sql(
    table: str,
    field_edges: Optional[list[LineageEdge]] = None,
) -> LineageSqlPreviewResponse:
    detail = get_table_by_name(table)
    edges = field_edges if field_edges is not None else get_lineage(table=table, direction="up", depth=1)
    sql, complete, warnings = generate_select_sql(
        table=table,
        fields=[field.name for field in detail.fields],
        saved_sql=detail.sql_logic,
        edges=edges,
    )
    return LineageSqlPreviewResponse(
        table=table,
        sql=sql,
        complete=complete,
        warnings=warnings,
        saved_sql=detail.sql_logic,
        changed=(detail.sql_logic or "").strip() != sql.strip(),
    )


def preview_sql_import(table: str, sql: str) -> LineageSqlImportPreviewResponse:
    get_table_by_name(table)
    return parse_select_preview(table, sql)


def apply_lineage_sql(req: LineageSqlApplyRequest) -> LineageSqlPreviewResponse:
    detail = get_table_by_name(req.table)
    run_query(
        """
        MATCH (t:Table {name: $table})
        SET t.sql_logic = $sql,
            t.sql_dialect = $sql_dialect,
            t.sql_source = $sql_source,
            t.sql_updated_at = datetime()
        CREATE (:Change {
            id: $change_id,
            operation: $operation,
            table_name: $table,
            field_name: $field_name,
            target_type: $target_type,
            target_id: t.id,
            old_value: $old_value,
            new_value: $new_value,
            changed_at: datetime(),
            commit_hash: $commit_hash
        })
        """,
        table=req.table,
        sql=req.sql,
        sql_dialect="hive",
        sql_source="imported",
        change_id=str(uuid.uuid4()),
        operation="lineage_sql_apply",
        field_name="",
        target_type="table",
        old_value=_json_change_value({
            "sql_logic": detail.sql_logic,
            "sql_dialect": detail.sql_dialect,
            "sql_source": detail.sql_source,
        }),
        new_value=_json_change_value({
            "sql_logic": req.sql,
            "sql_dialect": "hive",
            "sql_source": "imported",
        }),
        commit_hash="",
    )
    return preview_lineage_sql(req.table)
