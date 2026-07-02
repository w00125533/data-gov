"""Pydantic v2 wire DTOs for the metadata API."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


Layer = Literal["ODS", "DWD", "DWS", "ADS", "EVAL"]
StorageType = Literal["KAFKA", "HIVE", "STARROCKS"]
FieldType = Literal["STRING", "INT", "BIGINT", "DOUBLE", "TIMESTAMP", "DATE"]


class UpstreamRef(BaseModel):
    table: str
    field: str


class CreateTableRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    layer: Layer
    storage_type: StorageType
    description: str = ""


class UpdateTableRequest(BaseModel):
    layer: Optional[Layer] = None
    storage_type: Optional[StorageType] = None
    description: Optional[str] = None


class CreateFieldRequest(BaseModel):
    table_id: str
    name: str = Field(min_length=1, max_length=128)
    field_type: FieldType
    is_nullable: bool = True
    is_partition: bool = False
    expression: Optional[str] = None
    description: str = ""
    upstream: list[UpstreamRef] = []


class UpdateFieldRequest(BaseModel):
    field_type: Optional[FieldType] = None
    is_nullable: Optional[bool] = None
    is_partition: Optional[bool] = None
    expression: Optional[str] = None
    description: Optional[str] = None
    upstream: Optional[list[UpstreamRef]] = None


class FieldResponse(BaseModel):
    id: str
    name: str
    field_type: FieldType
    is_nullable: bool
    is_partition: bool
    expression: Optional[str]
    description: str
    version: int
    upstream: list[UpstreamRef]


class TableResponse(BaseModel):
    id: str
    name: str
    layer: Layer
    layer_priority: int
    storage_type: StorageType
    description: str
    fields: list[FieldResponse]


class TableSummary(BaseModel):
    id: str
    name: str
    layer: Layer
    layer_priority: int
    storage_type: StorageType
    description: str
    field_count: int


class LineageEdge(BaseModel):
    edge_id: str = ""
    from_table: str
    from_field: str
    to_table: str
    to_field: str
    transform_expr: str
    created_at: str = ""


class LineageResponse(BaseModel):
    root_table: str
    direction: Literal["up", "down"]
    depth: int
    edges: list[LineageEdge]


class LineageEdgeCreateRequest(BaseModel):
    from_table: str = Field(min_length=1, max_length=128)
    from_field: str = Field(min_length=1, max_length=128)
    to_table: str = Field(min_length=1, max_length=128)
    to_field: str = Field(min_length=1, max_length=128)
    transform_expr: str = Field(min_length=1)


class LineageEdgeUpdateRequest(BaseModel):
    transform_expr: str = Field(min_length=1)


class ImpactResponse(BaseModel):
    table: str
    field: Optional[str] = None
    has_downstream: bool
    affected_tables: list[str]
    downstream: list[LineageEdge]
