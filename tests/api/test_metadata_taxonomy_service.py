import pytest

from backend.metadata.models import TableClassificationUpdateRequest
from backend.metadata.service import (
    CategoryNotFound,
    TableNotFound,
    TagNotFound,
    get_table_by_name,
    list_categories_tree,
    list_tables,
    list_tags,
    update_table_classification,
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
    assert {"dws_cell_hourly", "eval_net_health"}.issubset({table.name for table in quality_tables})

    quality_coverage_tables = list_tables(
        tag_ids=["tag:network.quality", "tag:network.coverage"],
        tag_match="all",
    )
    assert "eval_net_health" in {table.name for table in quality_coverage_tables}


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
