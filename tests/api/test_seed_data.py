"""Sanity-check the SEED_TABLES + SEED_LINEAGE constants — they're the single source
of truth used by 06_neo4j_seed.py, 07_export_yaml.py, and several acceptance tests."""
import pytest

from backend.seed.tables import SEED_TABLES, SEED_LINEAGE, LAYER_PRIORITY
from backend.seed.tables import (
    DEFAULT_CATEGORY_TREE,
    DEFAULT_TAG_GROUPS,
    TABLE_CLASSIFICATION,
)


def test_ten_tables():
    assert len(SEED_TABLES) == 10
    names = {t["name"] for t in SEED_TABLES}
    assert names == {
        "ods_ue_signal", "ods_gnb_alarm",
        "dwd_session_qos", "dwd_ho_event",
        "dws_cell_hourly", "dws_area_traffic",
        "ads_cell_profile", "ads_neighbor_pair",
        "eval_user_score", "eval_net_health",
    }


def test_field_counts_around_seventy():
    total = sum(len(t["fields"]) for t in SEED_TABLES)
    assert 60 <= total <= 80, f"expected ~70 fields total, got {total}"


def test_every_lineage_edge_references_real_fields():
    field_keys = {
        (t["name"], f["name"]) for t in SEED_TABLES for f in t["fields"]
    }
    for edge in SEED_LINEAGE:
        src = (edge["from_table"], edge["from_field"])
        dst = (edge["to_table"], edge["to_field"])
        assert src in field_keys, f"lineage from {src} references unknown field"
        assert dst in field_keys, f"lineage to {dst} references unknown field"


def test_layer_priority_complete():
    assert LAYER_PRIORITY == {"ODS": 1, "DWD": 2, "DWS": 3, "ADS": 4, "EVAL": 5}


def test_default_category_tree_matches_approved_design():
    tree = {root["name"]: [child["name"] for child in root["children"]] for root in DEFAULT_CATEGORY_TREE}
    assert tree == {
        "环境": ["地理", "场景", "天气", "机房"],
        "设备": ["前传", "时钟", "回传", "天馈", "电源", "射频", "BBU"],
        "网络": ["覆盖", "干扰", "话务", "容量", "速率", "时延", "质量", "接入", "保持", "移动", "丢包", "能耗"],
        "用户": ["标识信息", "终端信息", "套餐信息", "位置信息", "业务信息", "活动信息"],
        "业务": ["直播", "视频", "游戏", "网页", "扫码", "上传下载", "即时通信", "生产", "Mobile AI"],
        "源数据": ["话统", "CHR", "配置", "工参", "电子地图"],
    }


def test_table_classification_covers_all_seed_tables():
    table_names = {table["name"] for table in SEED_TABLES}
    tag_codes_by_name = {
        tag["name"]: tag["code"]
        for group in DEFAULT_TAG_GROUPS
        for tag in group["tags"]
    }
    assert set(TABLE_CLASSIFICATION) == table_names
    for table_name, classification in TABLE_CLASSIFICATION.items():
        assert classification["category_path"]
        assert len(classification["category_path"]) == 2, table_name
        assert classification["tags"], table_name
        assert classification["category_code"], table_name
        assert classification["tag_codes"], table_name
        assert len(classification["tags"]) == len(classification["tag_codes"]), table_name
        assert classification["tag_codes"] == [
            tag_codes_by_name[tag_name]
            for tag_name in classification["tags"]
        ], table_name


def test_table_classification_references_known_categories_and_tags():
    category_paths = {
        (root["name"], child["name"])
        for root in DEFAULT_CATEGORY_TREE
        for child in root["children"]
    }
    category_codes = {
        child["code"]
        for root in DEFAULT_CATEGORY_TREE
        for child in root["children"]
    }
    tag_names = {tag["name"] for group in DEFAULT_TAG_GROUPS for tag in group["tags"]}
    explicit_tag_codes = {
        tag["code"]
        for group in DEFAULT_TAG_GROUPS
        for tag in group["tags"]
    }
    for classification in TABLE_CLASSIFICATION.values():
        assert tuple(classification["category_path"]) in category_paths
        assert set(classification["tags"]).issubset(tag_names)
        assert classification["category_code"] in category_codes
        assert set(classification["tag_codes"]).issubset(explicit_tag_codes)
