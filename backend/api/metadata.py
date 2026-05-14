"""HTTP routes for /api/tables, /api/fields, /api/lineage."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.metadata import service
from backend.metadata.models import (
    CreateFieldRequest,
    CreateTableRequest,
    FieldResponse,
    LineageResponse,
    TableResponse,
    TableSummary,
    UpdateFieldRequest,
    UpdateTableRequest,
)


router = APIRouter()


# ---- tables ----

@router.get("/api/tables", response_model=list[TableSummary])
def list_tables_endpoint(layer: Optional[str] = None, search: Optional[str] = None):
    return service.list_tables(layer=layer, search=search)


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

@router.get("/api/lineage", response_model=LineageResponse)
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
