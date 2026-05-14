"""Service-level tests -- exercise the Cypher implementations directly.
P1-6 and P1-7 add HTTP-level acceptance tests in later tasks."""
import pytest

from backend.metadata.models import CreateTableRequest, CreateFieldRequest, UpstreamRef
from backend.metadata.service import (
    FieldHasDownstream,
    TableNotFound,
    create_field,
    create_table,
    delete_field,
    delete_table,
    get_lineage,
    get_table_by_name,
    list_tables,
    update_field_expression,
)


@pytest.mark.infra
def test_list_tables_returns_ten_after_seed():
    tables = list_tables()
    assert len(tables) == 10


@pytest.mark.infra
def test_list_tables_filter_by_layer():
    ods = list_tables(layer="ODS")
    assert {t.name for t in ods} == {"ods_ue_signal", "ods_gnb_alarm"}


@pytest.mark.infra
def test_get_table_by_name_returns_full_payload():
    t = get_table_by_name("dwd_session_qos")
    field_names = {f.name for f in t.fields}
    assert {"avg_rsrp", "avg_sinr", "drop_flag"}.issubset(field_names)


@pytest.mark.infra
def test_lineage_downstream_from_dwd_session_qos():
    edges = get_lineage(table="dwd_session_qos", direction="down", depth=1)
    tables_downstream = {e.to_table for e in edges}
    assert {"dws_cell_hourly", "dws_area_traffic"}.issubset(tables_downstream)


@pytest.mark.infra
def test_create_and_delete_table_roundtrip():
    req = CreateTableRequest(name="tmp_test_table", layer="DWS", storage_type="HIVE", description="t")
    created = create_table(req)
    assert created.name == "tmp_test_table"
    delete_table("tmp_test_table")
    assert get_table_by_name("tmp_test_table", optional=True) is None


@pytest.mark.infra
def test_delete_field_with_downstream_raises():
    field = next(f for f in get_table_by_name("ods_ue_signal").fields if f.name == "rsrp")
    with pytest.raises(FieldHasDownstream):
        delete_field(field.id)


@pytest.mark.infra
def test_update_field_expression_bumps_version():
    field = next(f for f in get_table_by_name("dws_cell_hourly").fields if f.name == "drop_rate")
    original_version = field.version
    updated = update_field_expression(field.id, new_expression="SUM(drop_flag)/COUNT(*)")
    assert updated.version == original_version + 1


@pytest.mark.infra
def test_table_not_found():
    with pytest.raises(TableNotFound):
        get_table_by_name("nonexistent_table")
