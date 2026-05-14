"""sync_yaml(tables) -- per-table YAML rewrite; git_commit -- commit metadata-yaml/."""
from __future__ import annotations

import pathlib
from typing import Optional

import yaml
from git import Actor, InvalidGitRepositoryError, Repo

from backend.config import get_settings
from backend.metadata.graph import run_query


LAYER_DIR = {"ODS": "L1-ODS", "DWD": "L2-DWD", "DWS": "L3-DWS", "ADS": "L4-ADS", "EVAL": "L5-EVAL"}


def sync_yaml(table_names: list[str]) -> list[str]:
    """Rewrite YAML files for the given table names.

    For each table name in *table_names* a Cypher query reads the table node and
    its field nodes (with optional upstream lineage) from Neo4j, then writes a
    single YAML file under ``<metadata_yaml_dir>/<LAYER_DIR>/<name>.yaml``.

    Returns the list of absolute paths that were written (tables not found in
    the graph are silently skipped).
    """
    settings = get_settings()
    root = pathlib.Path(settings.metadata_yaml_dir).resolve()
    paths: list[str] = []
    for name in table_names:
        rows = run_query(
            """MATCH (t:Table {name: $name})
            RETURN t.name AS name, t.layer AS layer, t.layer_priority AS layer_priority,
                   t.storage_type AS storage_type, t.description AS description""",
            name=name,
        )
        if not rows:
            continue
        t = rows[0]
        field_rows = run_query(
            """MATCH (t:Table {name: $name})-[:HAS_FIELD]->(f:Field)
            OPTIONAL MATCH (f)-[:DERIVES_FROM]->(up:Field)<-[:HAS_FIELD]-(up_t:Table)
            WITH f, collect(DISTINCT {table: up_t.name, field: up.name}) AS upstream
            RETURN f.name AS name, f.field_type AS type, f.is_nullable AS nullable,
                   f.is_partition AS partition, f.expression AS expression,
                   f.description AS description, upstream
            ORDER BY f.name""",
            name=name,
        )
        doc = {
            "name": t["name"],
            "layer": t["layer"],
            "storage_type": t["storage_type"],
            "description": t["description"],
            "fields": [
                {
                    "name": f["name"],
                    "type": f["type"],
                    "nullable": f["nullable"],
                    "partition": f["partition"],
                    "expression": f["expression"],
                    "description": f["description"],
                    "upstream": [u for u in f["upstream"] if u.get("table")],
                }
                for f in field_rows
            ],
        }
        layer_dir = root / LAYER_DIR[t["layer"]]
        layer_dir.mkdir(parents=True, exist_ok=True)
        out = layer_dir / f"{name}.yaml"
        out.write_text(
            yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        paths.append(str(out))
    return paths


def git_commit(message: str, *, repo_root: Optional[str] = None) -> str:
    """Stage all changes under *repo_root* and create a commit.

    Returns the commit hex SHA on success, or an empty string when there is
    nothing to commit or the directory is not a Git repository.
    """
    settings = get_settings()
    actor = Actor(settings.git_author_name, settings.git_author_email)
    try:
        repo = Repo(repo_root or ".", search_parent_directories=True)
    except InvalidGitRepositoryError:
        return ""

    # Fast-path: nothing dirty and nothing staged -> skip
    if not repo.is_dirty(untracked_files=True) and not repo.untracked_files:
        return ""

    repo.git.add(A=True)

    # After staging, check whether there is a diff against HEAD.
    # For an empty/orphan repository ``index.diff("HEAD")`` returns nothing.
    if not repo.index.diff("HEAD") and not repo.untracked_files:
        return ""

    commit = repo.index.commit(message, author=actor, committer=actor)
    return commit.hexsha
