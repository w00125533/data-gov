import pytest
from pydantic import ValidationError

from backend.metadata.models import (
    CreateTableRequest,
    UpdateTableRequest,
    CreateFieldRequest,
    UpdateFieldRequest,
    TableResponse,
    FieldResponse,
    LineageEdge,
)


def test_create_table_request_rejects_unknown_layer():
    with pytest.raises(ValidationError):
        CreateTableRequest(name="x", layer="L0", storage_type="HIVE", description="")


def test_create_table_request_accepts_valid_layer():
    req = CreateTableRequest(name="my_table", layer="DWS", storage_type="HIVE", description="d")
    assert req.layer == "DWS"


def test_create_field_request_requires_table_id():
    with pytest.raises(ValidationError):
        CreateFieldRequest(name="x", field_type="STRING")


def test_field_response_round_trip():
    f = FieldResponse(
        id="abc", name="rsrp", field_type="DOUBLE", is_nullable=True, is_partition=False,
        expression=None, description="", version=1, upstream=[],
    )
    dumped = f.model_dump()
    assert dumped["field_type"] == "DOUBLE"


def test_lineage_edge_structure():
    edge = LineageEdge(
        from_table="ods_ue_signal", from_field="rsrp",
        to_table="dwd_session_qos", to_field="avg_rsrp",
        transform_expr="AVG(rsrp)",
    )
    assert edge.from_table == "ods_ue_signal"
