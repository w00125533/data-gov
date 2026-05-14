"""06_neo4j_seed.py — write 10 tables + ~65 fields + ~45 lineage edges to Neo4j.

Idempotent: MERGE used everywhere; safe to re-run. Re-running with edited
backend.seed.tables will add new nodes/edges but won't remove stale ones —
for a clean re-seed, wipe Neo4j first (MATCH (n) DETACH DELETE n).
"""
from __future__ import annotations

import sys
import uuid

from backend.metadata.graph import run_query
from backend.seed.tables import LAYER_PRIORITY, SEED_TABLES, SEED_LINEAGE


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


def main() -> int:
    t, f = seed_tables_and_fields()
    e = seed_lineage()
    print(f"Seeded {t} tables, {f} fields, {e} lineage edges.")
    return 0 if (t == 10 and 60 <= f <= 80) else 1


if __name__ == "__main__":
    sys.exit(main())
