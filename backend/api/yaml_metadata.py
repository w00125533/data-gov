"""YAML metadata preview/export endpoints for the Phase 3 UI."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import get_settings


router = APIRouter()


class YamlFile(BaseModel):
    table: str
    path: str
    content: str


class YamlExportResponse(BaseModel):
    table: str | None
    files: list[YamlFile]


def _metadata_root() -> Path:
    return Path(get_settings().metadata_yaml_dir).resolve()


def _find_yaml_file(table: str) -> Path:
    if not table.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="invalid table name")
    root = _metadata_root()
    matches = sorted(root.glob(f"L*-*/{table}.yaml"))
    if not matches:
        raise HTTPException(status_code=404, detail="yaml not found")
    path = matches[0].resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status_code=400, detail="invalid yaml path")
    return path


def _read_yaml(path: Path) -> YamlFile:
    return YamlFile(table=path.stem, path=str(path), content=path.read_text(encoding="utf-8"))


@router.get("/api/yaml/preview/{table}", response_model=YamlFile)
def yaml_preview(table: str):
    return _read_yaml(_find_yaml_file(table))


@router.get("/api/yaml/export", response_model=YamlExportResponse)
def yaml_export(table: str | None = None):
    if table:
        return YamlExportResponse(table=table, files=[_read_yaml(_find_yaml_file(table))])
    root = _metadata_root()
    files = [_read_yaml(p.resolve()) for p in sorted(root.glob("L*-*/*.yaml"))]
    return YamlExportResponse(table=None, files=files)
