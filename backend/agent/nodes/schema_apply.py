"""schema_apply - 把 schema_diff 落 Neo4j + YAML 同步 + git commit + Change.commit_hash 回填。"""
from __future__ import annotations
import json
import uuid
from typing import Optional
from backend.agent import tools, yaml_sync
from backend.metadata.graph import run_query


def _json_value(value: Optional[dict]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _target_type(op: dict) -> str:
    return "field" if op.get("field") else "table"


def _target_id(op: dict) -> str:
    if op.get("field"):
        return f"{op.get('table', '')}.{op['field']}"
    return op.get("table", "")


def _old_new_values(op: dict) -> tuple[Optional[dict], Optional[dict]]:
    kind = op["operation"]
    payload = {k: v for k, v in op.items() if k != "operation"}
    if kind.startswith("ADD_"):
        return None, payload
    if kind.startswith("DELETE_"):
        return payload, None
    return {"target": _target_id(op)}, payload


def _record_change(op: dict, *, commit_hash: Optional[str] = None) -> dict:
    change_id = f"chg_{uuid.uuid4().hex[:12]}"
    old_value, new_value = _old_new_values(op)
    run_query(
        """
        CREATE (c:Change {
            id: $id,
            operation: $operation,
            table_name: $table,
            field_name: $field,
            target_type: $target_type,
            target_id: $target_id,
            old_value: $old_value,
            new_value: $new_value,
            changed_at: datetime(),
            commit_hash: $commit
        })
        """,
        id=change_id,
        operation=op["operation"],
        table=op.get("table", ""),
        field=op.get("field"),
        target_type=_target_type(op),
        target_id=_target_id(op),
        old_value=_json_value(old_value),
        new_value=_json_value(new_value),
        commit=commit_hash,
    )
    return {
        "change_id": change_id,
        "operation": op["operation"],
        "table": op.get("table"),
        "field": op.get("field"),
        "target_type": _target_type(op),
        "target_id": _target_id(op),
        "commit_hash": commit_hash,
    }


def _update_change_commit(change_id: str, sha: str) -> None:
    run_query(
        "MATCH (c:Change {id: $id}) SET c.commit_hash = $sha",
        id=change_id,
        sha=sha,
    )


def _affected_tables(diff: list[dict]) -> list[str]:
    return sorted({op["table"] for op in diff if op.get("table")})


def _summarize(diff: list[dict]) -> str:
    parts = []
    for op in diff:
        if "field" in op and op["field"]:
            parts.append(f"{op['operation']} {op['table']}.{op['field']}")
        else:
            parts.append(f"{op['operation']} {op['table']}")
    return "; ".join(parts) or "(empty)"


def schema_apply(state: dict) -> dict:
    diff = state.get("schema_diff", [])
    if not diff:
        return {"applied_changes": []}

    applied: list[dict] = []
    for op in diff:
        kind = op["operation"]
        if kind == "ADD_TABLE":
            tools.add_table(op)
        elif kind == "ADD_FIELD":
            tools.add_field(op)
        elif kind == "UPDATE_FIELD":
            tools.update_field(op)
        elif kind == "DELETE_FIELD":
            tools.remove_field(op)
        change = _record_change(op, commit_hash=None)
        applied.append(change)

    yaml_sync.sync_yaml(_affected_tables(diff))
    sha = yaml_sync.git_commit(f"schema_evolve: {_summarize(diff)}")
    if sha:
        for a in applied:
            _update_change_commit(a["change_id"], sha)
            a["commit_hash"] = sha

    return {"applied_changes": applied}
