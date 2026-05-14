"""P1-5 (YAML part): metadata-yaml/L*-*/ contains 10 yaml files matching seed."""
import pathlib

import pytest
import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
METADATA_YAML = REPO_ROOT / "metadata-yaml"

EXPECTED = {
    "L1-ODS": ["ods_ue_signal", "ods_gnb_alarm"],
    "L2-DWD": ["dwd_session_qos", "dwd_ho_event"],
    "L3-DWS": ["dws_cell_hourly", "dws_area_traffic"],
    "L4-ADS": ["ads_cell_profile", "ads_neighbor_pair"],
    "L5-EVAL": ["eval_user_score", "eval_net_health"],
}


@pytest.mark.infra
def test_p1_5_yaml_files_exist_per_layer():
    for layer_dir, table_names in EXPECTED.items():
        for name in table_names:
            path = METADATA_YAML / layer_dir / f"{name}.yaml"
            assert path.exists(), f"missing {path}"


@pytest.mark.infra
def test_yaml_dws_cell_hourly_has_expected_fields():
    path = METADATA_YAML / "L3-DWS" / "dws_cell_hourly.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert payload["table_name"] == "dws_cell_hourly"
    assert payload["layer"] == "DWS"
    assert payload["storage_type"] == "HIVE"
    field_names = {f["name"] for f in payload["fields"]}
    assert {"cell_id", "hour_bucket", "avg_rsrp", "avg_sinr", "drop_rate", "ho_success_rate"}.issubset(field_names)
    avg_rsrp = next(f for f in payload["fields"] if f["name"] == "avg_rsrp")
    assert avg_rsrp.get("expression") == "AVG(rsrp)"
    assert {"table": "dwd_session_qos", "field": "avg_rsrp"} in avg_rsrp["upstream"]
