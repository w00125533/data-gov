"""Pydantic v2 wire DTOs for the metadata API."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


Layer = Literal["ODS", "DWD", "DWS", "ADS", "EVAL"]
StorageType = Literal["KAFKA", "HIVE", "STARROCKS"]
FieldType = Literal["STRING", "INT", "BIGINT", "DOUBLE", "TIMESTAMP", "DATE"]
CalcType = Literal[
    "DIRECT", "EXPRESSION", "AGGREGATE", "JOIN", "WINDOW", "CONDITION", "CONSTANT",
]
SqlSource = Literal["generated", "imported", "manual"]


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


class CategoryRef(BaseModel):
    id: str
    code: str
    name: str
    path: list[str] = Field(default_factory=list)


class TagRef(BaseModel):
    id: str
    code: str
    name: str


class CategoryNodeResponse(BaseModel):
    id: str
    code: str
    name: str
    level: int
    sort_order: int = 0
    active: bool = True
    protected: bool = False
    table_count: int = 0
    children: list["CategoryNodeResponse"] = Field(default_factory=list)


class TagResponse(BaseModel):
    id: str
    code: str
    name: str
    sort_order: int = 0
    active: bool = True


class TagGroupResponse(BaseModel):
    id: str
    code: str
    name: str
    sort_order: int = 0
    active: bool = True
    tags: list[TagResponse] = Field(default_factory=list)


class CreateCategoryRequest(BaseModel):
    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    parent_id: Optional[str] = None
    sort_order: int = 0
    active: bool = True


class UpdateCategoryRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    sort_order: Optional[int] = None


class MoveCategoryRequest(BaseModel):
    parent_id: str


class StatusUpdateRequest(BaseModel):
    active: bool


class CreateTagGroupRequest(BaseModel):
    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    sort_order: int = 0
    active: bool = True


class UpdateTagGroupRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    sort_order: Optional[int] = None
    active: Optional[bool] = None


class CreateTagRequest(BaseModel):
    group_id: str
    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    sort_order: int = 0
    active: bool = True


class UpdateTagRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    sort_order: Optional[int] = None


class TableClassificationUpdateRequest(BaseModel):
    category_id: str
    tag_ids: list[str] = Field(default_factory=list)


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
    sql_logic: Optional[str] = None
    sql_dialect: Optional[str] = None
    sql_source: Optional[SqlSource] = None
    sql_updated_at: str = ""
    category: Optional[CategoryRef] = None
    tags: list[TagRef] = Field(default_factory=list)


class TableSummary(BaseModel):
    id: str
    name: str
    layer: Layer
    layer_priority: int
    storage_type: StorageType
    description: str
    field_count: int
    category: Optional[CategoryRef] = None
    tags: list[TagRef] = Field(default_factory=list)


class LineageEdge(BaseModel):
    edge_id: str = ""
    from_table: str
    from_field: str
    to_table: str
    to_field: str
    transform_expr: str
    calc_type: CalcType = "DIRECT"
    calc_params: dict[str, Any] = {}
    created_at: str = ""
    updated_at: str = ""


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
    calc_type: CalcType = "DIRECT"
    calc_params: dict[str, Any] = {}


class LineageEdgeUpdateRequest(BaseModel):
    transform_expr: str = Field(min_length=1)
    calc_type: CalcType = "DIRECT"
    calc_params: dict[str, Any] = {}


class LineageEdgeEndpointUpdateRequest(BaseModel):
    from_table: str = Field(min_length=1, max_length=128)
    from_field: str = Field(min_length=1, max_length=128)
    to_table: str = Field(min_length=1, max_length=128)
    to_field: str = Field(min_length=1, max_length=128)


class ImpactResponse(BaseModel):
    table: str
    field: Optional[str] = None
    has_downstream: bool
    affected_tables: list[str]
    downstream: list[LineageEdge]


class LineageTableNode(TableSummary):
    fields: list[FieldResponse] = []
    sql_logic: Optional[str] = None
    sql_dialect: Optional[str] = None
    sql_source: Optional[SqlSource] = None
    sql_updated_at: str = ""


class LineageTableEdge(BaseModel):
    source: str
    target: str
    direction: Literal["upstream", "downstream"]
    field_edge_count: int
    calc_type_counts: dict[str, int] = {}
    fields: list[str] = []


class LineageGraphResponse(BaseModel):
    root_table: str
    depth: int
    include_upstream: bool
    include_downstream: bool
    graph_version: str
    tables: list[LineageTableNode]
    table_edges: list[LineageTableEdge]
    field_edges: list[LineageEdge]
    saved_sql: Optional[str] = None


class LineageSqlPreviewRequest(BaseModel):
    table: str = Field(min_length=1, max_length=128)
    field_edges: Optional[list[LineageEdge]] = None


class LineageSqlPreviewResponse(BaseModel):
    table: str
    sql: str
    complete: bool
    warnings: list[str] = Field(default_factory=list)
    saved_sql: Optional[str] = None
    changed: bool


class LineageSqlImportPreviewRequest(BaseModel):
    table: str = Field(min_length=1, max_length=128)
    sql: str = Field(min_length=1)


class FieldChangePreview(BaseModel):
    action: Literal["add", "update", "keep"]
    field: str
    expression: str
    field_type: FieldType = "STRING"
    upstream: list[UpstreamRef] = []


class EdgeChangePreview(BaseModel):
    action: Literal["add", "update", "delete", "keep"]
    edge: LineageEdge


class LineageSqlImportPreviewResponse(BaseModel):
    table: str
    sql: str
    fields: list[FieldChangePreview]
    edges: list[EdgeChangePreview]
    warnings: list[str] = Field(default_factory=list)


class LineageSqlApplyRequest(BaseModel):
    table: str = Field(min_length=1, max_length=128)
    sql: str = Field(min_length=1)
    fields: list[FieldChangePreview]
    edges: list[EdgeChangePreview]
    expected_graph_version: Optional[str] = None
