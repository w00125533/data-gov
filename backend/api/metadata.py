"""HTTP routes for /api/tables, /api/fields, /api/lineage."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlglot.errors import ParseError

from backend.metadata import service
from backend.metadata.lineage_sql import UnsupportedSqlError
from backend.metadata.models import (
    CategoryNodeResponse,
    CreateCategoryRequest,
    CreateFieldRequest,
    CreateTagGroupRequest,
    CreateTagRequest,
    CreateTableRequest,
    FieldResponse,
    ImpactResponse,
    LineageEdge,
    LineageEdgeCreateRequest,
    LineageEdgeEndpointUpdateRequest,
    LineageGraphResponse,
    LineageSqlApplyRequest,
    LineageSqlImportPreviewRequest,
    LineageSqlImportPreviewResponse,
    LineageSqlPreviewRequest,
    LineageSqlPreviewResponse,
    LineageEdgeUpdateRequest,
    LineageResponse,
    MoveCategoryRequest,
    StatusUpdateRequest,
    TableClassificationUpdateRequest,
    TableResponse,
    TableSummary,
    TagGroupResponse,
    TagResponse,
    UpdateCategoryRequest,
    UpdateFieldRequest,
    UpdateTagGroupRequest,
    UpdateTagRequest,
    UpdateTableRequest,
)


router = APIRouter()


def _raise_not_found(detail: str) -> None:
    raise HTTPException(status_code=404, detail=detail)


def _raise_conflict(detail: str) -> None:
    raise HTTPException(status_code=409, detail=detail)


# ---- tables ----

@router.get("/api/tables", response_model=list[TableSummary])
def list_tables_endpoint(
    layer: Optional[str] = None,
    search: Optional[str] = None,
    category_id: Optional[str] = None,
    include_children: bool = True,
    tag_ids: list[str] = Query(default=[]),
    tag_match: str = Query("any", pattern="^(any|all)$"),
    uncategorized: bool = False,
):
    return service.list_tables(
        layer=layer,
        search=search,
        category_id=category_id,
        include_children=include_children,
        tag_ids=tag_ids,
        tag_match=tag_match,
        uncategorized=uncategorized,
    )


@router.get("/api/tables/{table_id}", response_model=TableResponse)
def get_table(table_id: str):
    try:
        return service.get_table_by_id(table_id)
    except service.TableNotFound:
        raise HTTPException(status_code=404, detail="table not found")


@router.post("/api/tables", response_model=TableResponse, status_code=201)
def create_table_endpoint(req: CreateTableRequest):
    return service.create_table(req)


@router.put("/api/tables/{table_id}", response_model=TableResponse)
def update_table_endpoint(table_id: str, req: UpdateTableRequest):
    table = service.get_table_by_id(table_id)
    if req.layer is not None or req.storage_type is not None or req.description is not None:
        service.run_query_update_table(table_id, req)
    return service.get_table_by_id(table_id)


@router.put("/api/tables/{table_id}/classification", response_model=TableResponse)
def update_table_classification_endpoint(table_id: str, req: TableClassificationUpdateRequest):
    try:
        return service.update_table_classification(table_id, req)
    except service.TableNotFound:
        _raise_not_found("table not found")
    except service.CategoryNotFound:
        _raise_not_found("category not found")
    except service.TagNotFound:
        _raise_not_found("tag not found")


@router.delete("/api/tables/{table_id}", status_code=204)
def delete_table_endpoint(table_id: str):
    table = service.get_table_by_id(table_id)
    for field in table.fields:
        try:
            service.delete_field(field.id)
        except service.FieldHasDownstream as e:
            raise HTTPException(status_code=409, detail={
                "error": "table has fields with downstream dependents",
                "downstream": [{"table": t, "field": f} for t, f in e.downstream],
            })
    service.delete_table(table.name)


# ---- taxonomy ----

@router.get("/api/metadata/categories/tree", response_model=list[CategoryNodeResponse])
def list_categories_tree_endpoint():
    return service.list_categories_tree()


@router.post("/api/metadata/categories", response_model=CategoryNodeResponse, status_code=201)
def create_category_endpoint(req: CreateCategoryRequest):
    try:
        return service.create_category(req)
    except service.CategoryAlreadyExists:
        _raise_conflict("category already exists")
    except service.CategoryNotFound:
        _raise_not_found("category not found")
    except service.InvalidCategoryMove:
        _raise_conflict("invalid category move")


@router.put("/api/metadata/categories/{category_id}", response_model=CategoryNodeResponse)
def update_category_endpoint(category_id: str, req: UpdateCategoryRequest):
    try:
        return service.update_category(category_id, req)
    except service.CategoryNotFound:
        _raise_not_found("category not found")
    except service.ProtectedCategoryOperation:
        _raise_conflict("protected category operation")


@router.patch("/api/metadata/categories/{category_id}/move", response_model=CategoryNodeResponse)
def move_category_endpoint(category_id: str, req: MoveCategoryRequest):
    try:
        return service.move_category(category_id, req)
    except service.CategoryNotFound:
        _raise_not_found("category not found")
    except service.InvalidCategoryMove:
        _raise_conflict("invalid category move")
    except service.ProtectedCategoryOperation:
        _raise_conflict("protected category operation")


@router.patch("/api/metadata/categories/{category_id}/status", response_model=CategoryNodeResponse)
def update_category_status_endpoint(category_id: str, req: StatusUpdateRequest):
    try:
        return service.update_category_status(category_id, req)
    except service.CategoryNotFound:
        _raise_not_found("category not found")
    except service.ProtectedCategoryOperation:
        _raise_conflict("protected category operation")


@router.get("/api/metadata/tags", response_model=list[TagGroupResponse])
def list_tags_endpoint():
    return service.list_tags()


@router.post("/api/metadata/tag-groups", response_model=TagGroupResponse, status_code=201)
def create_tag_group_endpoint(req: CreateTagGroupRequest):
    return service.create_tag_group(req)


@router.put("/api/metadata/tag-groups/{group_id}", response_model=TagGroupResponse)
def update_tag_group_endpoint(group_id: str, req: UpdateTagGroupRequest):
    try:
        return service.update_tag_group(group_id, req)
    except service.TagGroupNotFound:
        _raise_not_found("tag group not found")


@router.post("/api/metadata/tags", response_model=TagResponse, status_code=201)
def create_tag_endpoint(req: CreateTagRequest):
    try:
        return service.create_tag(req)
    except service.TagGroupNotFound:
        _raise_not_found("tag group not found")


@router.put("/api/metadata/tags/{tag_id}", response_model=TagResponse)
def update_tag_endpoint(tag_id: str, req: UpdateTagRequest):
    try:
        return service.update_tag(tag_id, req)
    except service.TagNotFound:
        _raise_not_found("tag not found")


@router.patch("/api/metadata/tags/{tag_id}/status", response_model=TagResponse)
def update_tag_status_endpoint(tag_id: str, req: StatusUpdateRequest):
    try:
        return service.update_tag_status(tag_id, req)
    except service.TagNotFound:
        _raise_not_found("tag not found")


# ---- fields ----

@router.get("/api/fields/{field_id}", response_model=FieldResponse)
def get_field(field_id: str):
    try:
        return service._load_field(field_id)
    except service.FieldNotFound:
        raise HTTPException(status_code=404, detail="field not found")


@router.post("/api/fields", response_model=FieldResponse, status_code=201)
def create_field_endpoint(req: CreateFieldRequest):
    return service.create_field(req)


@router.put("/api/fields/{field_id}", response_model=FieldResponse)
def update_field_endpoint(field_id: str, req: UpdateFieldRequest):
    try:
        return service.update_field(field_id, req)
    except service.FieldNotFound:
        raise HTTPException(status_code=404, detail="field not found")


@router.delete("/api/fields/{field_id}", status_code=204)
def delete_field_endpoint(field_id: str):
    try:
        service.delete_field(field_id)
    except service.FieldNotFound:
        raise HTTPException(status_code=404, detail="field not found")
    except service.FieldHasDownstream as e:
        raise HTTPException(status_code=409, detail={
            "error": "field has downstream dependents",
            "downstream": [{"table": t, "field": f} for t, f in e.downstream],
        })


# ---- lineage ----

@router.get(
    "/api/lineage",
    response_model=LineageResponse,
    response_model_exclude={"edges": {"__all__": {"calc_type", "calc_params", "updated_at"}}},
)
def lineage_endpoint(
    table: str = Query(..., description="root table name"),
    direction: str = Query("down", pattern="^(up|down)$"),
    depth: int = Query(5, ge=1, le=5),
):
    try:
        edges = service.get_lineage(table=table, direction=direction, depth=depth)
    except service.TableNotFound:
        raise HTTPException(status_code=404, detail="table not found")
    return LineageResponse(root_table=table, direction=direction, depth=depth, edges=edges)


@router.get("/api/lineage/graph", response_model=LineageGraphResponse)
def lineage_graph_endpoint(
    table: str = Query(..., description="root table name"),
    depth: int = Query(2, ge=1, le=5),
    include_upstream: bool = True,
    include_downstream: bool = True,
):
    try:
        return service.get_lineage_graph(
            table=table,
            depth=depth,
            include_upstream=include_upstream,
            include_downstream=include_downstream,
        )
    except service.TableNotFound:
        raise HTTPException(status_code=404, detail="table not found")


@router.post("/api/lineage/sql/preview", response_model=LineageSqlPreviewResponse)
def lineage_sql_preview_endpoint(req: LineageSqlPreviewRequest):
    try:
        return service.preview_lineage_sql(req.table, field_edges=req.field_edges)
    except service.TableNotFound:
        raise HTTPException(status_code=404, detail="table not found")


@router.post("/api/lineage/sql/import/preview", response_model=LineageSqlImportPreviewResponse)
def lineage_sql_import_preview_endpoint(req: LineageSqlImportPreviewRequest):
    try:
        return service.preview_sql_import(req.table, req.sql)
    except service.TableNotFound:
        raise HTTPException(status_code=404, detail="table not found")
    except (ParseError, UnsupportedSqlError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "sql parse failed", "message": str(exc)},
        )


@router.post("/api/lineage/sql/apply", response_model=LineageSqlPreviewResponse)
def lineage_sql_apply_endpoint(req: LineageSqlApplyRequest):
    try:
        return service.apply_lineage_sql(req)
    except service.TableNotFound:
        raise HTTPException(status_code=404, detail="table not found")


@router.post(
    "/api/lineage/edges",
    response_model=LineageEdge,
    response_model_exclude={"calc_type", "calc_params", "updated_at"},
    status_code=201,
)
def create_lineage_edge_endpoint(req: LineageEdgeCreateRequest):
    try:
        return service.create_lineage_edge(req)
    except service.FieldNotFound:
        raise HTTPException(status_code=404, detail={
            "error": "lineage endpoint field not found",
            "from": {"table": req.from_table, "field": req.from_field},
            "to": {"table": req.to_table, "field": req.to_field},
        })
    except service.CycleDetected as e:
        raise HTTPException(status_code=409, detail={
            "error": "lineage cycle detected",
            "path": e.path,
        })


@router.put(
    "/api/lineage/edges/{edge_id}",
    response_model=LineageEdge,
)
def update_lineage_edge_endpoint(edge_id: str, req: LineageEdgeUpdateRequest):
    try:
        return service.update_lineage_edge(edge_id, req)
    except service.LineageEdgeNotFound:
        raise HTTPException(status_code=404, detail={
            "error": "lineage edge not found",
            "edge_id": edge_id,
        })


@router.patch("/api/lineage/edges/{edge_id}/endpoints", response_model=LineageEdge)
def update_lineage_edge_endpoints_endpoint(edge_id: str, req: LineageEdgeEndpointUpdateRequest):
    try:
        return service.update_lineage_edge_endpoints(edge_id, req)
    except service.LineageEdgeNotFound:
        raise HTTPException(status_code=404, detail={
            "error": "lineage edge not found",
            "edge_id": edge_id,
        })
    except service.FieldNotFound:
        raise HTTPException(status_code=404, detail={
            "error": "lineage endpoint field not found",
        })
    except service.CycleDetected as e:
        raise HTTPException(status_code=409, detail={
            "error": "lineage cycle detected",
            "path": e.path,
        })
    except service.LineageEndpointConflict as e:
        raise HTTPException(status_code=409, detail={
            "error": "lineage endpoint already exists",
            "edge_id": e.edge_id,
        })


@router.delete("/api/lineage/edges/{edge_id}", status_code=204)
def delete_lineage_edge_endpoint(edge_id: str):
    try:
        service.delete_lineage_edge(edge_id)
    except service.LineageEdgeNotFound:
        raise HTTPException(status_code=404, detail={
            "error": "lineage edge not found",
            "edge_id": edge_id,
        })


@router.get(
    "/api/metadata/impact",
    response_model=ImpactResponse,
    response_model_exclude={"downstream": {"__all__": {"calc_type", "calc_params", "updated_at"}}},
)
def downstream_impact_endpoint(
    table: str = Query(..., description="source table name"),
    field: Optional[str] = Query(None, description="optional source field name"),
):
    try:
        return service.get_downstream_impact(table=table, field=field)
    except service.TableNotFound:
        raise HTTPException(status_code=404, detail={
            "error": "table not found",
            "table": table,
        })
    except service.FieldNotFound:
        raise HTTPException(status_code=404, detail={
            "error": "field not found",
            "table": table,
            "field": field,
        })
