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
]

INDEXES = [
    "CREATE INDEX field_name_idx IF NOT EXISTS FOR (f:Field) ON (f.name)",
    "CREATE INDEX change_changed_at_idx IF NOT EXISTS FOR (c:Change) ON (c.changed_at)",
    "CREATE INDEX change_table_name_idx IF NOT EXISTS FOR (c:Change) ON (c.table_name)",
]


def main() -> int:
    for stmt in CONSTRAINTS + INDEXES:
        print(f"executing: {stmt}")
        run_query(stmt)
    print("Neo4j schema initialized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
