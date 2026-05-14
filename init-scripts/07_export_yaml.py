"""07_export_yaml.py — render Neo4j graph state as YAML under metadata-yaml/.

Output structure:
    metadata-yaml/L1-ODS/ods_ue_signal.yaml
    metadata-yaml/L2-DWD/dwd_session_qos.yaml
    ...

This script reads from Neo4j (authoritative store), not from backend.seed.tables —
so it works after schema_evolve operations too.
"""
from __future__ import annotations

import pathlib
import sys

import yaml

from backend.config import get_settings
from backend.metadata.graph import run_query


LAYER_DIR = {"ODS": "L1-ODS", "DWD": "L2-DWD", "DWS": "L3-DWS", "ADS": "L4-ADS", "EVAL": "L5-EVAL"}


def fetch_tables() -> list[dict]:
    return run_query("""
        MATCH (t:Table)
        RETURN t.name AS name, t.layer AS layer, t.layer_priority AS layer_priority,
               t.storage_type AS storage_type, t.description AS description
        ORDER BY t.layer_priority, t.name
    """)


def fetch_fields(table_name: str) -> list[dict]:
    rows = run_query("""
        MATCH (t:Table {name: $name})-[:HAS_FIELD]->(f:Field)
        OPTIONAL MATCH (f)-[r:DERIVES_FROM]->(up:Field)<-[:HAS_FIELD]-(up_t:Table)
        WITH f, collect(DISTINCT {table: up_t.name, field: up.name}) AS upstream
        RETURN f.name AS name, f.field_type AS type, f.is_nullable AS nullable,
               f.is_partition AS partition, f.expression AS expression,
               f.description AS description, upstream
        ORDER BY f.name
    """, name=table_name)
    # Normalize: drop empty `[{table: null, field: null}]` artifacts when no upstream
    for row in rows:
        row["upstream"] = [u for u in row["upstream"] if u["table"] and u["field"]]
    return rows


def write_yaml(out_dir: pathlib.Path, table: dict) -> pathlib.Path:
    layer_dir = out_dir / LAYER_DIR[table["layer"]]
    layer_dir.mkdir(parents=True, exist_ok=True)
    path = layer_dir / f"{table['name']}.yaml"
    fields = fetch_fields(table["name"])
    payload = {
        "table_name": table["name"],
        "layer": table["layer"],
        "layer_priority": table["layer_priority"],
        "description": table["description"],
        "storage_type": table["storage_type"],
        "fields": [
            {
                "name": f["name"],
                "type": f["type"],
                "nullable": f["nullable"],
                "partition": f["partition"],
                **({"expression": f["expression"]} if f["expression"] else {}),
                "description": f["description"],
                **({"upstream": f["upstream"]} if f["upstream"] else {}),
            }
            for f in fields
        ],
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def main() -> int:
    out = pathlib.Path(get_settings().metadata_yaml_dir)
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    for table in fetch_tables():
        write_yaml(out, table)
        count += 1
    print(f"Wrote {count} YAML files under {out}/")
    return 0 if count == 10 else 1


if __name__ == "__main__":
    sys.exit(main())
