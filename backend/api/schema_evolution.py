"""/api/schema/* - apply + evolution timeline (spec §6.7)。"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from backend.agent.nodes.schema_apply import schema_apply
from backend.agent.tools import validate_change
from backend.config import get_settings
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


def _yaml_path_for_table(table_name: str) -> Path:
    if not table_name.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="invalid table name")
    root = Path(get_settings().metadata_yaml_dir).resolve()
    matches = sorted(root.glob(f"L*-*/{table_name}.yaml"))
    if not matches:
        raise HTTPException(status_code=404, detail="yaml not found")
    path = matches[0].resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status_code=400, detail="invalid yaml path")
    return path


def _parse_json_value(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        if not value.strip():
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _parse_downstream(value) -> list:
    parsed = _parse_json_value(value)
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return parsed
    return [parsed]


def _version_from_row(row: dict) -> int | None:
    version = row.get("version")
    if version is None:
        version = row.get("field_version")
    return int(version) if version is not None else None


def _change_from_row(row: dict) -> dict:
    version = _version_from_row(row)
    return {
        "change_id": row["id"],
        "operation": row["operation"],
        "table_name": row.get("table_name"),
        "field_name": row.get("field_name"),
        "version": version,
        "previous_version": version - 1 if version and version > 1 else None,
        "old_value": _parse_json_value(row.get("old_value")),
        "new_value": _parse_json_value(row.get("new_value")),
        "downstream": _parse_downstream(row.get("downstream")),
        "changed_at": str(row["changed_at"]),
        "commit_hash": row.get("commit_hash"),
    }


@router.get("/api/schema/evolution/yaml-diff")
def yaml_diff(
    table_name: str = Query(...),
    version: int = Query(..., ge=1),
) -> dict:
    yaml_path = _yaml_path_for_table(table_name)
    current = yaml_path.read_text(encoding="utf-8")
    rows = run_query(
        """
        MATCH (c:Change {table_name: $table})
        WHERE c.version = $version OR c.field_version = $version
        RETURN c.commit_hash AS commit_hash
        ORDER BY c.changed_at DESC
        LIMIT 1
        """,
        table=table_name,
        version=version,
    )
    commit = next((r.get("commit_hash") for r in rows if r.get("commit_hash")), None)
    historical = "(initial version)"
    if commit:
        rel_path = yaml_path.relative_to(Path.cwd()).as_posix()
        try:
            historical = subprocess.check_output(
                ["git", "show", f"{commit}:{rel_path}"],
                text=True,
                encoding="utf-8",
            )
        except subprocess.CalledProcessError:
            historical = "(historical yaml unavailable)"
    return {
        "table": table_name,
        "version": version,
        "yaml_path": str(yaml_path),
        "current": current,
        "historical": historical,
        "commit_hash": commit,
    }


@router.get("/api/schema/evolution")
def schema_evolution_list(
    table: str | None = None,
    operation: str | None = None,
    q: str | None = None,
) -> dict:
    filters = []
    params: dict = {}
    if table:
        filters.append("c.table_name = $table")
        params["table"] = table
    if operation:
        filters.append("c.operation = $operation")
        params["operation"] = operation
    if q:
        filters.append("(toLower(c.table_name) CONTAINS toLower($q) OR toLower(coalesce(c.field_name, '')) CONTAINS toLower($q))")
        params["q"] = q
    where = "WHERE " + " AND ".join(filters) if filters else ""
    rows = run_query(
        f"""
        MATCH (c:Change)
        {where}
        RETURN c.id AS id, c.operation AS operation, c.table_name AS table_name, c.field_name AS field_name,
               c.version AS version, c.field_version AS field_version,
               c.old_value AS old_value, c.new_value AS new_value, c.downstream AS downstream,
               c.changed_at AS changed_at, c.commit_hash AS commit_hash
        ORDER BY c.changed_at DESC
        LIMIT 200
        """,
        **params,
    )
    return {
        "table": table,
        "changes": [_change_from_row(r) for r in rows],
    }


@router.get("/api/schema/evolution/{table}")
def schema_evolution(table: str) -> dict:
    rows = run_query(
        """
        MATCH (c:Change {table_name: $table})
        RETURN c.id AS id, c.operation AS operation, c.table_name AS table_name, c.field_name AS field_name,
               c.version AS version, c.field_version AS field_version,
               c.old_value AS old_value, c.new_value AS new_value, c.downstream AS downstream,
               c.changed_at AS changed_at, c.commit_hash AS commit_hash
        ORDER BY c.changed_at DESC
        """,
        table=table,
    )
    return {"table": table, "changes": [_change_from_row(r) for r in rows]}
