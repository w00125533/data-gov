"""Agent tools - thin service wrappers. spec §4.3: HTTP routes and Agent tools share service."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from backend.metadata import service as metadata_service
from backend.metadata.models import (
    CreateFieldRequest, CreateTableRequest, UpdateFieldRequest, UpstreamRef,
)
from backend.seed import fake_data
from backend.agent import sandbox_stub as sandbox


# ---------------- search ----------------

@dataclass
class SearchHit:
    table: str
    field: Optional[str]
    score: float


@dataclass
class SearchResult:
    top_table: Optional[str]
    top_score: float
    top_field: Optional[str]
    candidates: list[SearchHit] = field(default_factory=list)


def search_tables_by_keyword(keyword: str, *, searcher) -> SearchResult:
    raw = searcher.search(keyword, k=10, use_rerank=False)
    if not raw:
        return SearchResult(top_table=None, top_score=0.0, top_field=None)
    top = raw[0]
    return SearchResult(
        top_table=top["table"],
        top_score=top["score"],
        top_field=top["doc"].metadata.get("field_name"),
        candidates=[
            SearchHit(table=r["table"], field=r["doc"].metadata.get("field_name"), score=r["score"])
            for r in raw
        ],
    )


# ---------------- lookup ----------------

def lookup_table_schema(tables: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name in tables:
        if not name:
            continue
        try:
            t = metadata_service.get_table_by_name(name)
        except metadata_service.TableNotFound:
            continue
        out[name] = {
            "name": t.name, "layer": t.layer, "storage_type": t.storage_type,
            "fields": [{"name": f.name, "type": f.field_type, "description": f.description, "expression": f.expression} for f in t.fields],
        }
    return out


def lookup_lineage(table: str, *, direction: str = "down", depth: int = 5) -> list:
    return metadata_service.get_lineage(table, direction=direction, depth=depth)


# ---------------- gap check ----------------

def check_gaps(keywords: list[str], *, searcher, threshold: float = 0.6) -> list[dict]:
    gaps: list[dict] = []
    for kw in keywords:
        raw = searcher.search(kw, k=3, use_rerank=False)
        top_score = raw[0]["score"] if raw else 0.0
        if top_score < threshold:
            gaps.append({"type": "missing_table", "keyword": kw, "suggestion": f"建议新建表覆盖业务概念 '{kw}'"})
    return gaps


def propose_gap_fix(gaps: list[dict], *, llm_client) -> list[dict]:
    return gaps


# ---------------- schema validation ----------------

def validate_change(diff: list[dict]) -> dict:
    errors, warnings = [], []
    for op in diff:
        kind = op["operation"]
        if kind == "ADD_FIELD":
            try:
                t = metadata_service.get_table_by_name(op["table"])
                if any(f.name == op["field"] for f in t.fields):
                    errors.append(("DUPLICATE", op))
            except metadata_service.TableNotFound:
                errors.append(("TABLE_NOT_FOUND", op))
        elif kind == "DELETE_FIELD":
            ds = metadata_service.get_lineage(op["table"], direction="down", depth=5)
            ds_relevant = [
                e for e in ds
                if getattr(e, "from_table", None) == op["table"]
                and getattr(e, "from_field", None) == op["field"]
            ]
            if ds_relevant:
                errors.append(("BREAK_DOWNSTREAM", op, [
                    (getattr(e, "to_table", None), getattr(e, "to_field", None)) for e in ds_relevant
                ]))
        elif kind == "UPDATE_FIELD":
            try:
                t = metadata_service.get_table_by_name(op["table"])
                if not any(f.name == op["field"] for f in t.fields):
                    errors.append(("FIELD_NOT_FOUND", op))
            except metadata_service.TableNotFound:
                errors.append(("TABLE_NOT_FOUND", op))
        elif kind == "ADD_TABLE":
            if not op.get("category_id"):
                errors.append(("MISSING_CATEGORY", op))
            try:
                metadata_service.get_table_by_name(op["table"])
                errors.append(("DUPLICATE_TABLE", op))
            except metadata_service.TableNotFound:
                pass
    return {"errors": errors, "warnings": warnings, "passed": len(errors) == 0}


# ---------------- schema mutations ----------------

def add_table(op: dict) -> dict:
    req = CreateTableRequest(
        name=op["table"],
        layer=op["layer"],
        storage_type=op["storage_type"],
        description=op.get("description", ""),
        category_id=op["category_id"],
        tag_ids=op.get("tag_ids", []),
    )
    t = metadata_service.create_table(req)
    field_ids = []
    for f in op.get("fields", []):
        fr = CreateFieldRequest(table_id=t.id, name=f["name"], field_type=f["data_type"], is_nullable=f.get("nullable", True), is_partition=f.get("partition", False), expression=f.get("expression"), description=f.get("description", ""), upstream=[UpstreamRef(**u) for u in f.get("upstream", [])])
        created = metadata_service.create_field(fr)
        field_ids.append(created.id)
    return {"table_id": t.id, "field_ids": field_ids}


def add_field(op: dict) -> dict:
    t = metadata_service.get_table_by_name(op["table"])
    fr = CreateFieldRequest(table_id=t.id, name=op["field"], field_type=op["data_type"], is_nullable=op.get("nullable", True), is_partition=op.get("partition", False), expression=op.get("expression"), description=op.get("description", ""), upstream=[UpstreamRef(**u) for u in op.get("upstream", [])])
    created = metadata_service.create_field(fr)
    return {"field_id": created.id, "name": created.name}


def update_field(op: dict) -> dict:
    t = metadata_service.get_table_by_name(op["table"])
    fld = next(f for f in t.fields if f.name == op["field"])
    req = UpdateFieldRequest(field_type=op.get("data_type"), expression=op.get("expression"), description=op.get("description"), upstream=[UpstreamRef(**u) for u in op["upstream"]] if "upstream" in op else None)
    updated = metadata_service.update_field(fld.id, req)
    return {"field_id": updated.id, "version": updated.version}


def remove_field(op: dict) -> dict:
    t = metadata_service.get_table_by_name(op["table"])
    fld = next(f for f in t.fields if f.name == op["field"])
    metadata_service.delete_field(fld.id)
    return {"field_id": fld.id, "removed": True}


# ---------------- data + dry-run dispatchers ----------------

def generate_fake_data(table: str, rows: int) -> dict:
    return fake_data.generate_fake_data(table, rows)


def dry_run_spark_sql(code: str):
    return sandbox.execute(code, "spark_sql")


def dry_run_flink_sql(code: str):
    return sandbox.execute(code, "flink_sql")


def dry_run_java_flink(code: str):
    return sandbox.execute(code, "java_flink")
