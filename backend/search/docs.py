"""把 Neo4j 元数据序列化为 search docs (spec §4.6.1)。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.metadata.graph import run_query
from backend.seed.tables import SEED_TABLES


@dataclass
class SearchDoc:
    id: str
    type: str  # "table" | "field"
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def build_table_text(table: dict) -> str:
    parts = [table["name"], table.get("description", "")]
    for f in table.get("fields", []):
        parts.append(f["name"])
        parts.append(f.get("description", ""))
    return " ".join(p for p in parts if p)


def build_field_text(table_name: str, field_obj: dict) -> str:
    parts = [
        field_obj["name"],
        field_obj.get("type", ""),
        field_obj.get("description", ""),
    ]
    expr = field_obj.get("expression")
    if expr:
        parts.append(f"表达式 {expr}")
    return " ".join(p for p in parts if p)


def _docs_from_seed(tables: list[dict]) -> list[SearchDoc]:
    docs: list[SearchDoc] = []
    for t in tables:
        docs.append(SearchDoc(
            id=f"table:{t['name']}",
            type="table",
            text=build_table_text(t),
            metadata={
                "table_name": t["name"],
                "layer": t["layer"],
                "storage_type": t["storage_type"],
                "version": 1,
            },
        ))
        for f in t.get("fields", []):
            docs.append(SearchDoc(
                id=f"field:{t['name']}.{f['name']}",
                type="field",
                text=build_field_text(t["name"], f),
                metadata={
                    "table_name": t["name"],
                    "field_name": f["name"],
                    "data_type": f.get("type", ""),
                    "version": 1,
                },
            ))
    return docs


def build_docs_from_neo4j(seed_only: bool = False) -> list[SearchDoc]:
    if seed_only:
        return _docs_from_seed(SEED_TABLES)

    rows = run_query(
        """
        MATCH (t:Table)
        OPTIONAL MATCH (t)-[:HAS_FIELD]->(f:Field)
        WITH t,
             collect(CASE WHEN f IS NULL THEN null ELSE {
                 name: f.name, type: f.data_type, description: f.description,
                 expression: f.expression, version: f.version
             } END) AS fields
        RETURN t.name AS name, t.layer AS layer, t.storage_type AS storage_type,
               t.description AS description, t.version AS version, fields
        """
    )
    docs: list[SearchDoc] = []
    for r in rows:
        clean_fields = [f for f in r["fields"] if f is not None]
        docs.append(SearchDoc(
            id=f"table:{r['name']}",
            type="table",
            text=build_table_text({
                "name": r["name"],
                "description": r["description"],
                "fields": clean_fields,
            }),
            metadata={
                "table_name": r["name"],
                "layer": r["layer"],
                "storage_type": r["storage_type"],
                "version": r.get("version") or 1,
            },
        ))
        for f in clean_fields:
            docs.append(SearchDoc(
                id=f"field:{r['name']}.{f['name']}",
                type="field",
                text=build_field_text(r["name"], f),
                metadata={
                    "table_name": r["name"],
                    "field_name": f["name"],
                    "data_type": f.get("type", ""),
                    "version": f.get("version") or 1,
                },
            ))
    return docs
