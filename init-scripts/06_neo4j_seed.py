"""06_neo4j_seed.py — write 10 tables + ~65 fields + ~45 lineage edges to Neo4j.

Idempotent: MERGE used everywhere; safe to re-run. Re-running with edited
backend.seed.tables will add new nodes/edges but won't remove stale ones —
for a clean re-seed, wipe Neo4j first (MATCH (n) DETACH DELETE n).
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.metadata.graph import run_query
from backend.seed.tables import (
    DEFAULT_CATEGORY_TREE,
    DEFAULT_TAG_GROUPS,
    LAYER_PRIORITY,
    SEED_LINEAGE,
    SEED_TABLES,
    TABLE_CLASSIFICATION,
)


def _category_id(code: str) -> str:
    return f"category:{code}"


def _tag_group_id(code: str) -> str:
    return f"tag-group:{code}"


def _tag_code(code: str) -> str:
    return code


def _tag_id(code: str) -> str:
    return f"tag:{_tag_code(code)}"


def seed_taxonomy() -> tuple[int, int, int]:
    category_count = 0
    group_count = 0
    tag_count = 0

    for root_index, root in enumerate(DEFAULT_CATEGORY_TREE, start=1):
        root_id = _category_id(root["code"])
        run_query(
            """
            MERGE (root:MetaCategory {code: $code})
            ON CREATE SET root.id = $id,
                          root.created_at = datetime()
            SET root.name = $name,
                root.level = 1,
                root.sort_order = $sort_order,
                root.protected = true,
                root.active = true,
                root.updated_at = datetime()
            """,
            id=root_id,
            code=root["code"],
            name=root["name"],
            sort_order=root_index,
        )
        category_count += 1

        for child_index, child in enumerate(root["children"], start=1):
            child_id = _category_id(child["code"])
            run_query(
                """
                MATCH (root:MetaCategory {code: $root_code})
                MERGE (child:MetaCategory {code: $code})
                ON CREATE SET child.id = $id,
                              child.created_at = datetime()
                SET child.name = $name,
                    child.level = 2,
                    child.sort_order = $sort_order,
                    child.protected = false,
                    child.active = true,
                    child.updated_at = datetime()
                MERGE (root)-[:HAS_CHILD]->(child)
                """,
                root_code=root["code"],
                id=child_id,
                code=child["code"],
                name=child["name"],
                sort_order=child_index,
            )
            category_count += 1

    for group_index, group in enumerate(DEFAULT_TAG_GROUPS, start=1):
        group_id = _tag_group_id(group["code"])
        run_query(
            """
            MERGE (g:MetaTagGroup {code: $code})
            ON CREATE SET g.id = $id,
                          g.created_at = datetime()
            SET g.name = $name,
                g.sort_order = $sort_order,
                g.active = true,
                g.updated_at = datetime()
            """,
            id=group_id,
            code=group["code"],
            name=group["name"],
            sort_order=group_index,
        )
        group_count += 1

        for tag_index, tag in enumerate(group["tags"], start=1):
            tag_code = _tag_code(tag["code"])
            run_query(
                """
                MATCH (g:MetaTagGroup {code: $group_code})
                MERGE (tag:MetaTag {code: $code})
                ON CREATE SET tag.id = $id,
                              tag.created_at = datetime()
                SET tag.name = $name,
                    tag.sort_order = $sort_order,
                    tag.active = true,
                    tag.updated_at = datetime()
                MERGE (g)-[:HAS_TAG]->(tag)
                """,
                group_code=group["code"],
                id=_tag_id(tag["code"]),
                code=tag_code,
                name=tag["name"],
                sort_order=tag_index,
            )
            tag_count += 1

    return category_count, group_count, tag_count


def seed_tables_and_fields() -> tuple[int, int]:
    table_count = 0
    field_count = 0
    for tbl in SEED_TABLES:
        run_query(
            """
            MERGE (t:Table {name: $name})
            ON CREATE SET t.id = $id,
                          t.layer = $layer,
                          t.layer_priority = $layer_priority,
                          t.storage_type = $storage_type,
                          t.description = $description
            """,
            id=str(uuid.uuid4()),
            name=tbl["name"],
            layer=tbl["layer"],
            layer_priority=LAYER_PRIORITY[tbl["layer"]],
            storage_type=tbl["storage_type"],
            description=tbl["description"],
        )
        table_count += 1
        for field in tbl["fields"]:
            run_query(
                """
                MATCH (t:Table {name: $table})
                MERGE (t)-[:HAS_FIELD]->(f:Field {name: $name})
                ON CREATE SET f.id = $id,
                              f.field_type = $field_type,
                              f.is_nullable = $is_nullable,
                              f.is_partition = $is_partition,
                              f.expression = $expression,
                              f.description = $description,
                              f.version = 1,
                              f.previous_expr = '[]'
                """,
                table=tbl["name"],
                id=str(uuid.uuid4()),
                name=field["name"],
                field_type=field["type"],
                is_nullable=field["nullable"],
                is_partition=field["partition"],
                expression=field.get("expression", ""),
                description=field["description"],
            )
            field_count += 1
    return table_count, field_count


def seed_lineage() -> int:
    edge_count = 0
    for edge in SEED_LINEAGE:
        run_query(
            """
            MATCH (t_src:Table {name: $src_t})-[:HAS_FIELD]->(f_src:Field {name: $src_f})
            MATCH (t_dst:Table {name: $dst_t})-[:HAS_FIELD]->(f_dst:Field {name: $dst_f})
            MERGE (f_dst)-[r:DERIVES_FROM]->(f_src)
            ON CREATE SET r.transform_expr = $transform_expr,
                          r.created_at = datetime()
            """,
            src_t=edge["from_table"],
            src_f=edge["from_field"],
            dst_t=edge["to_table"],
            dst_f=edge["to_field"],
            transform_expr=edge["transform_expr"],
        )
        edge_count += 1
    return edge_count


def seed_table_classification() -> int:
    classified_count = 0
    for table_name, classification in TABLE_CLASSIFICATION.items():
        root_name, child_name = classification["category_path"]
        run_query(
            """
            MATCH (t:Table {name: $table})
            MATCH (:MetaCategory {name: $root_name})-[:HAS_CHILD]->(category:MetaCategory {name: $child_name})
            OPTIONAL MATCH (t)-[old:IN_CATEGORY]->(:MetaCategory)
            DELETE old
            MERGE (t)-[:IN_CATEGORY]->(category)
            """,
            table=table_name,
            root_name=root_name,
            child_name=child_name,
        )
        for tag_name in classification["tags"]:
            run_query(
                """
                MATCH (t:Table {name: $table})
                MATCH (tag:MetaTag {name: $tag_name})
                MERGE (t)-[:TAGGED_WITH]->(tag)
                """,
                table=table_name,
                tag_name=tag_name,
            )
        classified_count += 1
    return classified_count


def main() -> int:
    category_count, group_count, tag_count = seed_taxonomy()
    t, f = seed_tables_and_fields()
    classified = seed_table_classification()
    e = seed_lineage()
    print(
        f"Seeded {category_count} categories, {group_count} tag groups, "
        f"{tag_count} tags, {t} tables, {f} fields, {classified} classifications, {e} lineage edges."
    )
    return 0 if (t == 10 and classified == 10 and 60 <= f <= 80) else 1


if __name__ == "__main__":
    sys.exit(main())
