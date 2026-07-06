from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import metadata
from backend.metadata.models import (
    CategoryNodeResponse,
    CategoryRef,
    TableClassificationUpdateRequest,
    TableResponse,
    TagGroupResponse,
    TagResponse,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(metadata.router)
    return TestClient(app)


def _table_response() -> TableResponse:
    return TableResponse(
        id="t1",
        name="dwd_network_quality",
        layer="DWD",
        layer_priority=2,
        storage_type="HIVE",
        description="",
        fields=[],
        category=CategoryRef(
            id="category:quality.coverage",
            code="quality.coverage",
            name="覆盖",
            path=["质量", "覆盖"],
        ),
        tags=[],
    )


def test_categories_tree_returns_mocked_children(monkeypatch):
    def fake_list_categories_tree():
        return [
            CategoryNodeResponse(
                id="category:quality",
                code="quality",
                name="质量",
                level=1,
                children=[
                    CategoryNodeResponse(
                        id="category:quality.coverage",
                        code="quality.coverage",
                        name="覆盖",
                        level=2,
                    )
                ],
            )
        ]

    monkeypatch.setattr(metadata.service, "list_categories_tree", fake_list_categories_tree)

    response = _client().get("/api/metadata/categories/tree")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["children"][0]["name"] == "覆盖"


def test_tags_returns_mocked_tag_group(monkeypatch):
    def fake_list_tags():
        return [
            TagGroupResponse(
                id="tag-group:network",
                code="network",
                name="网络",
                tags=[
                    TagResponse(
                        id="tag:network.coverage",
                        code="network.coverage",
                        name="覆盖",
                    )
                ],
            )
        ]

    monkeypatch.setattr(metadata.service, "list_tags", fake_list_tags)

    response = _client().get("/api/metadata/tags")

    assert response.status_code == 200
    tag = response.json()[0]["tags"][0]
    assert tag["id"] == "tag:network.coverage"
    assert tag["code"] == "network.coverage"
    assert tag["name"] == "覆盖"


def test_update_table_classification_passes_request_and_returns_category_path(monkeypatch):
    captured = {}

    def fake_update_table_classification(table_id, req):
        captured["table_id"] = table_id
        captured["req"] = req
        return _table_response()

    monkeypatch.setattr(
        metadata.service,
        "update_table_classification",
        fake_update_table_classification,
    )

    response = _client().put(
        "/api/tables/t1/classification",
        json={
            "category_id": "category:quality.coverage",
            "tag_ids": ["tag:network.coverage"],
        },
    )

    assert response.status_code == 200
    assert captured["table_id"] == "t1"
    assert isinstance(captured["req"], TableClassificationUpdateRequest)
    assert captured["req"].category_id == "category:quality.coverage"
    assert captured["req"].tag_ids == ["tag:network.coverage"]
    assert response.json()["category"]["path"] == ["质量", "覆盖"]


def test_list_tables_passes_taxonomy_filters(monkeypatch):
    captured = {}

    def fake_list_tables(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(metadata.service, "list_tables", fake_list_tables)

    response = _client().get(
        "/api/tables",
        params=[
            ("layer", "DWD"),
            ("search", "network"),
            ("category_id", "category:quality.coverage"),
            ("include_children", "false"),
            ("tag_ids", "tag:network.coverage"),
            ("tag_ids", "tag:network.quality"),
            ("tag_match", "all"),
            ("uncategorized", "true"),
        ],
    )

    assert response.status_code == 200
    assert captured == {
        "layer": "DWD",
        "search": "network",
        "category_id": "category:quality.coverage",
        "include_children": False,
        "tag_ids": ["tag:network.coverage", "tag:network.quality"],
        "tag_match": "all",
        "uncategorized": True,
    }


def test_update_table_classification_category_not_found_returns_404(monkeypatch):
    def fake_update_table_classification(_table_id, _req):
        raise metadata.service.CategoryNotFound("category:missing")

    monkeypatch.setattr(
        metadata.service,
        "update_table_classification",
        fake_update_table_classification,
    )

    response = _client().put(
        "/api/tables/t1/classification",
        json={"category_id": "category:missing", "tag_ids": []},
    )

    assert response.status_code == 404


def test_update_table_classification_tag_not_found_returns_404(monkeypatch):
    def fake_update_table_classification(_table_id, _req):
        raise metadata.service.TagNotFound("tag:missing")

    monkeypatch.setattr(
        metadata.service,
        "update_table_classification",
        fake_update_table_classification,
    )

    response = _client().put(
        "/api/tables/t1/classification",
        json={"category_id": "category:quality.coverage", "tag_ids": ["tag:missing"]},
    )

    assert response.status_code == 404


def test_create_duplicate_category_returns_409(monkeypatch):
    def fake_create_category(_req):
        raise metadata.service.CategoryAlreadyExists("quality.coverage")

    monkeypatch.setattr(metadata.service, "create_category", fake_create_category)

    response = _client().post(
        "/api/metadata/categories",
        json={"code": "quality.coverage", "name": "覆盖"},
    )

    assert response.status_code == 409


def test_invalid_category_move_returns_409(monkeypatch):
    def fake_move_category(_category_id, _req):
        raise metadata.service.InvalidCategoryMove("invalid move")

    monkeypatch.setattr(metadata.service, "move_category", fake_move_category)

    response = _client().patch(
        "/api/metadata/categories/category:quality/move",
        json={"parent_id": "category:other"},
    )

    assert response.status_code == 409
