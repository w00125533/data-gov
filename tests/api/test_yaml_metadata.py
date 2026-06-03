from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import schema_evolution, yaml_metadata
from backend.config import get_settings


def _prepare_yaml_root(tmp_path: Path, monkeypatch):
    root = tmp_path / "metadata-yaml"
    layer = root / "L3-DWS"
    layer.mkdir(parents=True)
    (layer / "dws_cell_hourly.yaml").write_text("table_name: dws_cell_hourly\n", encoding="utf-8")
    monkeypatch.setenv("METADATA_YAML_DIR", str(root))
    get_settings.cache_clear()
    return root


def test_yaml_preview_reads_table_yaml(tmp_path, monkeypatch):
    _prepare_yaml_root(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(yaml_metadata.router)

    res = TestClient(app).get("/api/yaml/preview/dws_cell_hourly")

    assert res.status_code == 200
    assert res.json()["table"] == "dws_cell_hourly"
    assert "table_name: dws_cell_hourly" in res.json()["content"]


def test_yaml_export_can_return_all_yaml_files(tmp_path, monkeypatch):
    _prepare_yaml_root(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(yaml_metadata.router)

    res = TestClient(app).get("/api/yaml/export")

    assert res.status_code == 200
    payload = res.json()
    assert payload["table"] is None
    assert [f["table"] for f in payload["files"]] == ["dws_cell_hourly"]


def test_schema_yaml_diff_route_is_not_shadowed_by_table_route(tmp_path, monkeypatch):
    _prepare_yaml_root(tmp_path, monkeypatch)
    monkeypatch.setattr(schema_evolution, "run_query", lambda *_args, **_kwargs: [])
    app = FastAPI()
    app.include_router(schema_evolution.router)

    res = TestClient(app).get("/api/schema/evolution/yaml-diff?table_name=dws_cell_hourly&version=1")

    assert res.status_code == 200
    assert res.json()["table"] == "dws_cell_hourly"
    assert res.json()["historical"] == "(initial version)"
