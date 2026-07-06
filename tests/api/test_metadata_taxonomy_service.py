import pytest

from backend.metadata import service
from backend.metadata.models import (
    CreateCategoryRequest,
    CreateTagGroupRequest,
    CreateTagRequest,
    MoveCategoryRequest,
    StatusUpdateRequest,
    TableClassificationUpdateRequest,
)
from backend.metadata.service import (
    CategoryAlreadyExists,
    InvalidCategoryMove,
    CategoryNotFound,
    TableNotFound,
    TagAlreadyExists,
    TagGroupAlreadyExists,
    TagNotFound,
    create_category,
    create_tag,
    create_tag_group,
    get_table_by_name,
    list_categories_tree,
    list_tables,
    list_tags,
    move_category,
    update_table_classification,
    update_tag_status,
)


@pytest.mark.infra
def test_list_categories_tree_returns_network_children():
    roots = list_categories_tree()

    network = next(root for root in roots if root.name == "网络")

    assert network.protected is True
    assert [child.name for child in network.children] == [
        "覆盖",
        "干扰",
        "话务",
        "容量",
        "速率",
        "时延",
        "质量",
        "接入",
        "保持",
        "移动",
        "丢包",
        "能耗",
    ]
    coverage = next(child for child in network.children if child.name == "覆盖")
    child_table_total = sum(child.table_count for child in network.children)
    assert network.table_count >= child_table_total
    assert network.table_count >= 7
    assert coverage.table_count >= 2


@pytest.mark.infra
def test_list_tags_returns_grouped_tags():
    groups = list_tags()

    network_group = next(group for group in groups if group.code == "network-domain")
    tags_by_name = {tag.name: tag for tag in network_group.tags}

    assert {"覆盖", "质量", "移动"}.issubset(tags_by_name)
    assert tags_by_name["覆盖"].id == "tag:network.coverage"
    assert tags_by_name["质量"].id == "tag:network.quality"
    assert tags_by_name["移动"].id == "tag:network.mobility"


@pytest.mark.infra
def test_seed_table_has_category_and_tags():
    table = get_table_by_name("dws_cell_hourly")

    assert table.category is not None
    assert table.category.path == ["网络", "覆盖"]
    assert {"话务", "速率", "保持", "质量"}.issubset({tag.name for tag in table.tags})


@pytest.mark.infra
def test_list_tables_filters_by_category_and_tag():
    coverage_tables = list_tables(category_id="category:network.coverage", include_children=True)
    assert {"dws_cell_hourly", "ads_cell_profile"}.issubset({table.name for table in coverage_tables})

    quality_tables = list_tables(tag_ids=["tag:network.quality"], tag_match="any")
    quality_names = {table.name for table in quality_tables}
    assert {"dws_cell_hourly", "ads_neighbor_pair"}.issubset(quality_names)
    assert "eval_net_health" not in quality_names

    quality_coverage_tables = list_tables(
        tag_ids=["tag:network.quality", "tag:network.coverage"],
        tag_match="all",
    )
    quality_coverage_names = {table.name for table in quality_coverage_tables}
    assert "ods_ue_signal" in quality_coverage_names
    assert "eval_net_health" not in quality_coverage_names


def test_create_category_rejects_duplicate_code_without_writing(monkeypatch):
    calls = []

    def fake_run_query(cypher, **params):
        calls.append((cypher, params))
        if "RETURN category.id AS id" in cypher:
            return [{"id": "category:network.coverage"}]
        if "MERGE" in cypher or "CREATE" in cypher or "SET" in cypher:
            raise AssertionError("duplicate category attempted to write")
        return []

    monkeypatch.setattr(service, "run_query", fake_run_query)

    with pytest.raises(CategoryAlreadyExists):
        create_category(
            CreateCategoryRequest(
                code="network.coverage",
                name="coverage duplicate",
                parent_id="category:network",
            )
        )

    assert not any("MERGE" in cypher or "CREATE" in cypher or "SET" in cypher for cypher, _ in calls[1:])


def test_create_tag_group_rejects_duplicate_code_without_writing(monkeypatch):
    calls = []

    def fake_run_query(cypher, **params):
        calls.append((cypher, params))
        if "RETURN group.id AS id" in cypher:
            return [{"id": "tag-group:network-domain"}]
        if "MERGE" in cypher or "CREATE" in cypher or "SET" in cypher:
            raise AssertionError("duplicate tag group attempted to write")
        return []

    monkeypatch.setattr(service, "run_query", fake_run_query)

    with pytest.raises(TagGroupAlreadyExists):
        create_tag_group(
            CreateTagGroupRequest(
                code="network-domain",
                name="duplicate",
            )
        )

    assert not any("MERGE" in cypher or "CREATE" in cypher or "SET" in cypher for cypher, _ in calls[1:])


def test_create_tag_rejects_duplicate_code_without_attaching_to_group(monkeypatch):
    calls = []

    def fake_run_query(cypher, **params):
        calls.append((cypher, params))
        if "MATCH (:MetaTagGroup {id: $group_id}) RETURN 1 AS found" in cypher:
            return [{"found": 1}]
        if "RETURN tag.id AS id" in cypher:
            return [{"id": "tag:network.coverage"}]
        if "MERGE" in cypher or "CREATE" in cypher or "SET" in cypher:
            raise AssertionError("duplicate tag attempted to write")
        return []

    monkeypatch.setattr(service, "run_query", fake_run_query)

    with pytest.raises(TagAlreadyExists):
        create_tag(
            CreateTagRequest(
                group_id="tag-group:network-domain",
                code="network.coverage",
                name="duplicate",
            )
        )

    assert not any("MERGE" in cypher or "CREATE" in cypher or "SET" in cypher for cypher, _ in calls[2:])


def test_move_category_rejects_invalid_level_without_writing(monkeypatch):
    calls = []

    def fake_run_query(cypher, **params):
        calls.append((cypher, params))
        if "category:MetaCategory {id: $category_id}" in cypher:
            return [{"level": 2, "protected": False}]
        if "parent:MetaCategory {id: $parent_id}" in cypher:
            return [{"level": 2}]
        if "MERGE" in cypher or "DELETE" in cypher or "SET" in cypher:
            raise AssertionError("invalid category move attempted to write")
        return []

    monkeypatch.setattr(service, "run_query", fake_run_query)

    with pytest.raises(InvalidCategoryMove):
        move_category(
            "category:network.coverage",
            MoveCategoryRequest(parent_id="category:network.quality"),
        )

    assert not any("MERGE" in cypher or "DELETE" in cypher or "SET" in cypher for cypher, _ in calls[2:])


@pytest.mark.infra
def test_taxonomy_mutation_records_change_node():
    tag_id = "tag:network.coverage"
    before_rows = service.run_query(
        """
        MATCH (tag:MetaTag {id: $tag_id})
        OPTIONAL MATCH (change:Change {
            operation: $operation,
            target_type: $target_type,
            target_id: $tag_id
        })
        RETURN coalesce(tag.active, true) AS active,
               collect(change.id) AS change_ids
        """,
        tag_id=tag_id,
        operation="tag_status_update",
        target_type="MetaTag",
    )
    original_active = before_rows[0]["active"]
    before_change_ids = set(before_rows[0]["change_ids"])
    new_change_ids: set[str] = set()

    try:
        update_tag_status(tag_id, StatusUpdateRequest(active=not original_active))
        update_tag_status(tag_id, StatusUpdateRequest(active=original_active))

        after_rows = service.run_query(
            """
            MATCH (change:Change {
                operation: $operation,
                target_type: $target_type,
                target_id: $tag_id
            })
            RETURN collect(change.id) AS change_ids
            """,
            tag_id=tag_id,
            operation="tag_status_update",
            target_type="MetaTag",
        )
        new_change_ids = set(after_rows[0]["change_ids"]) - before_change_ids

        assert new_change_ids
    finally:
        service.run_query(
            """
            MATCH (tag:MetaTag {id: $tag_id})
            SET tag.active = $active,
                tag.updated_at = datetime()
            """,
            tag_id=tag_id,
            active=original_active,
        )
        if new_change_ids:
            service.run_query(
                """
                MATCH (change:Change)
                WHERE change.id IN $change_ids
                DETACH DELETE change
                """,
                change_ids=list(new_change_ids),
            )


@pytest.mark.infra
def test_update_table_classification_replaces_category_and_tags():
    table = get_table_by_name("ads_neighbor_pair")

    updated = update_table_classification(
        table.id,
        TableClassificationUpdateRequest(
            category_id="category:source-data.engineering",
            tag_ids=["tag:source.engineering", "tag:network.retain"],
        ),
    )

    assert updated.category is not None
    assert updated.category.path == ["源数据", "工参"]
    assert {tag.name for tag in updated.tags} == {"工参", "保持"}

    restored = update_table_classification(
        table.id,
        TableClassificationUpdateRequest(
            category_id="category:network.mobility",
            tag_ids=["tag:network.retain", "tag:network.quality", "tag:source.engineering"],
        ),
    )
    assert restored.category is not None
    assert restored.category.path == ["网络", "移动"]
    assert {"保持", "质量", "工参"}.issubset({tag.name for tag in restored.tags})


@pytest.mark.infra
def test_update_table_classification_validates_ids():
    table = get_table_by_name("ads_neighbor_pair")

    with pytest.raises(CategoryNotFound):
        update_table_classification(
            table.id,
            TableClassificationUpdateRequest(
                category_id="category:missing",
                tag_ids=["tag:network.quality"],
            ),
        )

    with pytest.raises(TagNotFound):
        update_table_classification(
            table.id,
            TableClassificationUpdateRequest(
                category_id="category:network.mobility",
                tag_ids=["tag:missing"],
            ),
        )

    with pytest.raises(TableNotFound):
        update_table_classification(
            "table:missing",
            TableClassificationUpdateRequest(
                category_id="category:network.mobility",
                tag_ids=["tag:network.quality"],
            ),
        )
