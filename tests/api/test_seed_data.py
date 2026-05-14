"""Sanity-check the SEED_TABLES + SEED_LINEAGE constants — they're the single source
of truth used by 06_neo4j_seed.py, 07_export_yaml.py, and several acceptance tests."""
import pytest

from backend.seed.tables import SEED_TABLES, SEED_LINEAGE, LAYER_PRIORITY


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
