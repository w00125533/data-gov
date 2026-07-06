"""05_neo4j_init.py — create constraints and indexes on the metadata graph.

Idempotent: all statements use `IF NOT EXISTS`. Safe to re-run.

Run from repo root:
    python init-scripts/05_neo4j_init.py
"""
from __future__ import annotations

import sys

from backend.metadata.graph import run_query


CONSTRAINTS = [
    "CREATE CONSTRAINT table_id_unique IF NOT EXISTS FOR (t:Table) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT table_name_unique IF NOT EXISTS FOR (t:Table) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT field_id_unique IF NOT EXISTS FOR (f:Field) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT change_id_unique IF NOT EXISTS FOR (c:Change) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT category_id_unique IF NOT EXISTS FOR (c:MetaCategory) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT category_code_unique IF NOT EXISTS FOR (c:MetaCategory) REQUIRE c.code IS UNIQUE",
    "CREATE CONSTRAINT tag_group_id_unique IF NOT EXISTS FOR (g:MetaTagGroup) REQUIRE g.id IS UNIQUE",
    "CREATE CONSTRAINT tag_group_code_unique IF NOT EXISTS FOR (g:MetaTagGroup) REQUIRE g.code IS UNIQUE",
    "CREATE CONSTRAINT tag_id_unique IF NOT EXISTS FOR (tag:MetaTag) REQUIRE tag.id IS UNIQUE",
    "CREATE CONSTRAINT tag_code_unique IF NOT EXISTS FOR (tag:MetaTag) REQUIRE tag.code IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX field_name_idx IF NOT EXISTS FOR (f:Field) ON (f.name)",
    "CREATE INDEX change_changed_at_idx IF NOT EXISTS FOR (c:Change) ON (c.changed_at)",
    "CREATE INDEX change_table_name_idx IF NOT EXISTS FOR (c:Change) ON (c.table_name)",
    "CREATE INDEX category_name_idx IF NOT EXISTS FOR (c:MetaCategory) ON (c.name)",
    "CREATE INDEX category_level_idx IF NOT EXISTS FOR (c:MetaCategory) ON (c.level)",
    "CREATE INDEX category_sort_idx IF NOT EXISTS FOR (c:MetaCategory) ON (c.sort_order)",
    "CREATE INDEX tag_name_idx IF NOT EXISTS FOR (tag:MetaTag) ON (tag.name)",
    "CREATE INDEX tag_sort_idx IF NOT EXISTS FOR (tag:MetaTag) ON (tag.sort_order)",
    "CREATE INDEX change_target_type_idx IF NOT EXISTS FOR (c:Change) ON (c.target_type)",
    "CREATE INDEX change_target_id_idx IF NOT EXISTS FOR (c:Change) ON (c.target_id)",
]


def main() -> int:
    for stmt in CONSTRAINTS + INDEXES:
        print(f"executing: {stmt}")
        run_query(stmt)
    print("Neo4j schema initialized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
