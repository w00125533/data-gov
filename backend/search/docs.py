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


def build_field_text(table_name: str, field_obj: dict, *, table_desc: str = "") -> str:
    """构造字段级索引文本。

    把表限定名、字段名、类型、描述、表达式、所属表描述全部串联，
    让 BM25 和 Dense 都能在字段级匹配中捕获语义上下文。
    """
    parts = [
        f"{table_name}.{field_obj['name']}",  # 表限定名: ods_ue_signal.rsrp
        field_obj["name"],                     # 裸字段名
        field_obj.get("type", ""),
        field_obj.get("description", ""),
        f"所属表 {table_name}",
    ]
    if table_desc:
        parts.append(table_desc)
    expr = field_obj.get("expression")
    if expr:
        parts.append(f"计算表达式 {expr}")
        parts.append(f"来源于 {table_name}")
    return " ".join(p for p in parts if p)


def _docs_from_seed(tables: list[dict]) -> list[SearchDoc]:
    docs: list[SearchDoc] = []
    for t in tables:
        table_text = build_table_text(t)
        docs.append(SearchDoc(
            id=f"table:{t['name']}",
            type="table",
            text=table_text,
            metadata={
                "table_name": t["name"],
                "layer": t["layer"],
                "storage_type": t["storage_type"],
                "version": 1,
            },
        ))
        for f in t.get("fields", []):
            # 字段 doc 文本 = 表名上下文 + 字段详情 + 所属表描述 (增强 BM25 匹配)
            field_text = (
                f"{t['name']}.{f['name']} {f['name']} "
                f"{f.get('type', '')} {f.get('description', '')}"
                f" 所属表 {t['name']} {t.get('description', '')}"
            )
            expr = f.get("expression")
            if expr:
                field_text += f" 计算表达式 {expr} 来源于 {t['name']}"
            docs.append(SearchDoc(
                id=f"field:{t['name']}.{f['name']}",
                type="field",
                text=field_text,
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
                 name: f.name, type: f.field_type, description: f.description,
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
                text=build_field_text(r["name"], f, table_desc=r.get("description", "")),
                metadata={
                    "table_name": r["name"],
                    "field_name": f["name"],
                    "data_type": f.get("type", ""),
                    "version": f.get("version") or 1,
                },
            ))
    return docs
