"""/api/schema/* - apply + evolution timeline (spec §6.7)。"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from backend.agent.nodes.schema_apply import schema_apply
from backend.agent.tools import validate_change
from backend.metadata.graph import run_query

router = APIRouter()


class SchemaApplyRequest(BaseModel):
    diff: list[dict]


@router.post("/api/schema/apply")
def apply_schema(req: SchemaApplyRequest) -> dict:
    v = validate_change(req.diff)
    if not v["passed"]:
        return {"passed": False, "errors": v["errors"], "warnings": v["warnings"], "applied": []}
    out = schema_apply({"schema_diff": req.diff})
    return {"passed": True, "errors": [], "warnings": v.get("warnings", []), "applied": out["applied_changes"]}


@router.get("/api/schema/evolution/{table}")
def schema_evolution(table: str) -> dict:
    rows = run_query("""MATCH (c:Change {table_name: $table}) RETURN c.id AS id, c.operation AS operation, c.table_name AS table_name, c.field_name AS field_name, c.changed_at AS changed_at, c.commit_hash AS commit_hash ORDER BY c.changed_at DESC""", table=table)
    return {"table": table, "changes": [{"change_id": r["id"], "operation": r["operation"], "field_name": r["field_name"], "changed_at": str(r["changed_at"]), "commit_hash": r["commit_hash"]} for r in rows]}
