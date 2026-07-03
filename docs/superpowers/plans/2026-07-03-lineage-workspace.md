# Lineage Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a table-first lineage workspace that supports forward/backward table visibility, expandable table fields, structured field-edge editing, immediate SQL preview, SQL import preview, and explicit SQL write-back.

**Architecture:** Neo4j remains the authoritative source for `Table`, `Field`, and `DERIVES_FROM`. Backend changes extend `DERIVES_FROM` with structured calculation metadata, expose a workspace graph contract, add edge endpoint mutation, and add Spark/Hive SQL preview/import services. Frontend changes replace the field-only lineage view with a three-panel workspace: left controls, center table-level graph with expandable fields, and right edge/SQL panels. `/pipeline` stays read-only and consumes table-level lineage aggregation.

**Tech Stack:** FastAPI, Pydantic v2, Neo4j Cypher, SQLGlot for Spark/Hive SELECT parsing, React 18, TypeScript, Ant Design, AntV G6, Playwright, pytest.

---

## References

- Design spec: `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md`, sections 2.3, 6.4, 6.5, 6.7, 6.8, and Phase 3 P3-6 through P3-10c.
- Current backend lineage files: `backend/metadata/models.py`, `backend/metadata/service.py`, `backend/api/metadata.py`.
- Current frontend lineage files: `frontend/src/pages/Lineage.tsx`, `frontend/src/components/LineageGraph.tsx`, `frontend/src/components/LineageSidePanel.tsx`, `frontend/src/components/LineageContextMenu.tsx`, `frontend/src/components/graphShared/graphData.ts`.
- SQLGlot docs: `https://sqlglot.com/` and `https://sqlglot.com/sqlglot/expressions.html`. Use `parse_one(sql, read="hive")`, `sqlglot.exp`, `find_all(exp.Table)`, `find_all(exp.Column)`, and `Expression.sql(dialect="hive")`.

## Scope Boundaries

- Implement `/metadata/lineage` as the editing workspace.
- Keep `/pipeline` read-only. Do not add field-edge editing or SQL write-back to `/pipeline`.
- SQL import accepts only user-selected target table plus a `SELECT expression_list FROM source_table` query. Do not parse full `CREATE TABLE`, `ALTER TABLE`, or `INSERT SELECT` in this plan.
- SQL generation targets one selected table and direct upstream only. Do not generate recursive multi-hop CTE SQL.
- No Docker Compose or infrastructure changes are required.

## File Structure

### Backend

- Modify `pyproject.toml`: add `sqlglot` to runtime dependencies.
- Modify `backend/metadata/models.py`: add calculation type DTOs, lineage workspace graph DTOs, SQL preview/import/apply DTOs, and `sql_logic` fields on table responses.
- Modify `backend/metadata/service.py`: persist and read `calc_type`, `calc_params`, `updated_at`, `Table.sql_logic`, table/field workspace graph data, edge endpoint mutation, and SQL write-back.
- Create `backend/metadata/lineage_sql.py`: generate direct-upstream Spark/Hive SQL and parse selected-target `SELECT` SQL into a preview model.
- Modify `backend/api/metadata.py`: expose graph, structured edge updates, endpoint patching, SQL preview, SQL import preview, and SQL apply routes.
- Create `tests/api/test_lineage_graph_contract.py`: backend API tests for graph response and direction flags.
- Create `tests/api/test_lineage_calc_edges.py`: backend API/service tests for calc metadata and endpoint mutation.
- Create `tests/api/test_lineage_sql.py`: SQL generation and import preview tests.

### Frontend

- Modify `frontend/src/api/client.ts`: add graph, structured edge, endpoint patch, SQL preview/import/apply types and client calls.
- Create `frontend/src/components/graphShared/lineageWorkspaceData.ts`: convert workspace graph API payload into table/field view model and edge summaries.
- Create `frontend/src/components/LineageWorkspaceGraph.tsx`: render table-level graph, expandable fields, field-edge overlay, hover/click events, and endpoint drag/drop callbacks.
- Create `frontend/src/components/LineageEdgeEditor.tsx`: structured calculation editor for selected field edge.
- Create `frontend/src/components/LineageSqlPanel.tsx`: generated SQL preview, saved SQL comparison, copy, and write-back action.
- Create `frontend/src/components/LineageSqlImportDrawer.tsx`: SQL paste, parse preview, risk display, and apply action.
- Modify `frontend/src/pages/Lineage.tsx`: wire table graph API, forward/backward checkboxes, expanded table state, edge editing, SQL preview refresh, import drawer, and chat link context.
- Modify `frontend/src/styles.css`: layout and graph styles for lineage workspace.
- Modify `frontend/tests/e2e/fixtures.ts`: add lineage graph and SQL fixtures.
- Replace `frontend/tests/e2e/lineage.spec.ts`: cover table graph, checkbox visibility, field expansion, edge edit, SQL preview, and import preview.

## Task 1: Backend DTOs And Runtime Dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `backend/metadata/models.py`
- Test: `tests/api/test_lineage_graph_contract.py`

- [ ] **Step 1: Add failing DTO contract tests**

Create `tests/api/test_lineage_graph_contract.py` with this content:

```python
from backend.metadata.models import (
    CalcType,
    LineageEdge,
    LineageGraphResponse,
    LineageSqlPreviewResponse,
)


def test_lineage_edge_supports_structured_calculation_metadata():
    edge = LineageEdge(
        edge_id="edge-1",
        from_table="dwd_session_qos",
        from_field="avg_rsrp",
        to_table="dws_cell_hourly",
        to_field="avg_rsrp",
        transform_expr="AVG(dwd_session_qos.avg_rsrp)",
        calc_type="AGGREGATE",
        calc_params={"function": "AVG", "group_by": ["cell_id", "hour_bucket"]},
        created_at="2026-07-03T10:00:00Z",
        updated_at="2026-07-03T10:01:00Z",
    )

    assert edge.calc_type == "AGGREGATE"
    assert edge.calc_params["function"] == "AVG"
    assert CalcType.__args__ == (
        "DIRECT",
        "EXPRESSION",
        "AGGREGATE",
        "JOIN",
        "WINDOW",
        "CONDITION",
        "CONSTANT",
    )


def test_lineage_graph_response_contains_table_nodes_and_field_edges():
    payload = LineageGraphResponse(
        root_table="dws_cell_hourly",
        depth=2,
        include_upstream=True,
        include_downstream=False,
        graph_version="v1",
        tables=[
            {
                "id": "t-dws",
                "name": "dws_cell_hourly",
                "layer": "DWS",
                "layer_priority": 3,
                "storage_type": "HIVE",
                "description": "cell hourly",
                "field_count": 2,
                "fields": [
                    {
                        "id": "f-rsrp",
                        "name": "avg_rsrp",
                        "field_type": "DOUBLE",
                        "is_nullable": True,
                        "is_partition": False,
                        "expression": "AVG(rsrp)",
                        "description": "avg rsrp",
                        "version": 1,
                        "upstream": [],
                    }
                ],
                "sql_logic": "SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos",
                "sql_dialect": "spark_hive",
                "sql_source": "generated",
                "sql_updated_at": "2026-07-03T10:02:00Z",
            }
        ],
        table_edges=[
            {
                "source": "dwd_session_qos",
                "target": "dws_cell_hourly",
                "direction": "upstream",
                "field_edge_count": 1,
                "calc_type_counts": {"AGGREGATE": 1},
                "fields": ["avg_rsrp"],
            }
        ],
        field_edges=[],
        saved_sql="SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos",
    )

    assert payload.tables[0].sql_logic.startswith("SELECT")
    assert payload.table_edges[0].calc_type_counts == {"AGGREGATE": 1}


def test_sql_preview_response_marks_incomplete_sql():
    payload = LineageSqlPreviewResponse(
        table="dws_cell_hourly",
        sql="SELECT AVG(rsrp) AS avg_rsrp FROM dwd_session_qos",
        complete=False,
        warnings=["JOIN keys missing for dwd_ho_event"],
        saved_sql=None,
        changed=True,
    )

    assert payload.complete is False
    assert payload.changed is True
```

- [ ] **Step 2: Run DTO tests and verify failure**

Run:

```powershell
python -m pytest tests/api/test_lineage_graph_contract.py -v
```

Expected: fail with import errors for `CalcType`, `LineageGraphResponse`, or `LineageSqlPreviewResponse`.

- [ ] **Step 3: Add SQLGlot dependency**

In `pyproject.toml`, add this item under `[project.optional-dependencies].runtime`:

```toml
    "sqlglot>=26",
```

Then run:

```powershell
python -m pip install -e ".[runtime,test]"
```

Expected: dependency resolution succeeds and `python -c "import sqlglot; print(sqlglot.__version__)"` prints a version.

- [ ] **Step 4: Add model types**

In `backend/metadata/models.py`, update imports:

```python
from typing import Any, Literal, Optional
```

Add these aliases near `FieldType`:

```python
CalcType = Literal[
    "DIRECT",
    "EXPRESSION",
    "AGGREGATE",
    "JOIN",
    "WINDOW",
    "CONDITION",
    "CONSTANT",
]
SqlSource = Literal["generated", "imported", "manual"]
```

Add SQL fields to `TableResponse`:

```python
    sql_logic: Optional[str] = None
    sql_dialect: Optional[str] = None
    sql_source: Optional[SqlSource] = None
    sql_updated_at: str = ""
```

Replace `LineageEdge`, `LineageEdgeCreateRequest`, and `LineageEdgeUpdateRequest` with:

```python
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
```

Append graph and SQL DTOs at the end of `models.py`:

```python
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
    warnings: list[str] = []
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
    warnings: list[str] = []


class LineageSqlApplyRequest(BaseModel):
    table: str = Field(min_length=1, max_length=128)
    sql: str = Field(min_length=1)
    fields: list[FieldChangePreview]
    edges: list[EdgeChangePreview]
    expected_graph_version: Optional[str] = None
```

- [ ] **Step 5: Run DTO tests and commit**

Run:

```powershell
python -m pytest tests/api/test_lineage_graph_contract.py -v
```

Expected: all tests in this file pass.

Commit:

```powershell
git add pyproject.toml backend/metadata/models.py tests/api/test_lineage_graph_contract.py
git commit -m "api: extend lineage contract models"
```

## Task 2: Backend Structured Edge Persistence And Graph API

**Files:**
- Modify: `backend/metadata/service.py`
- Modify: `backend/api/metadata.py`
- Test: `tests/api/test_lineage_calc_edges.py`
- Test: `tests/api/test_lineage_graph_contract.py`

- [ ] **Step 1: Add failing structured edge API tests**

Create `tests/api/test_lineage_calc_edges.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import metadata
from backend.metadata.models import LineageEdge


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(metadata.router)
    return TestClient(app)


def _edge() -> LineageEdge:
    return LineageEdge(
        edge_id="edge-agg",
        from_table="dwd_session_qos",
        from_field="avg_rsrp",
        to_table="dws_cell_hourly",
        to_field="avg_rsrp",
        transform_expr="AVG(dwd_session_qos.avg_rsrp)",
        calc_type="AGGREGATE",
        calc_params={"function": "AVG", "group_by": ["cell_id", "hour_bucket"]},
        created_at="2026-07-03T10:00:00Z",
        updated_at="2026-07-03T10:02:00Z",
    )


def test_update_edge_accepts_calc_type_and_params(monkeypatch):
    captured = {}

    def fake_update(edge_id, req):
        captured["edge_id"] = edge_id
        captured["req"] = req
        return _edge()

    monkeypatch.setattr(metadata.service, "update_lineage_edge", fake_update)

    res = _client().put(
        "/api/lineage/edges/edge-agg",
        json={
            "transform_expr": "AVG(dwd_session_qos.avg_rsrp)",
            "calc_type": "AGGREGATE",
            "calc_params": {"function": "AVG", "group_by": ["cell_id", "hour_bucket"]},
        },
    )

    assert res.status_code == 200
    assert captured["edge_id"] == "edge-agg"
    assert captured["req"].calc_type == "AGGREGATE"
    assert captured["req"].calc_params["function"] == "AVG"
    assert res.json()["calc_type"] == "AGGREGATE"


def test_patch_edge_endpoints_returns_moved_edge(monkeypatch):
    captured = {}

    def fake_patch(edge_id, req):
        captured["edge_id"] = edge_id
        captured["req"] = req
        return LineageEdge(
            edge_id=edge_id,
            from_table=req.from_table,
            from_field=req.from_field,
            to_table=req.to_table,
            to_field=req.to_field,
            transform_expr="passthrough",
            calc_type="DIRECT",
            calc_params={},
        )

    monkeypatch.setattr(metadata.service, "update_lineage_edge_endpoints", fake_patch)

    res = _client().patch(
        "/api/lineage/edges/edge-1/endpoints",
        json={
            "from_table": "ods_ue_signal",
            "from_field": "rsrp",
            "to_table": "dws_cell_hourly",
            "to_field": "avg_rsrp",
        },
    )

    assert res.status_code == 200
    assert captured["req"].from_table == "ods_ue_signal"
    assert res.json()["from_field"] == "rsrp"


def test_lineage_graph_endpoint_returns_workspace_contract(monkeypatch):
    monkeypatch.setattr(
        metadata.service,
        "get_lineage_graph",
        lambda table, depth, include_upstream, include_downstream: {
            "root_table": table,
            "depth": depth,
            "include_upstream": include_upstream,
            "include_downstream": include_downstream,
            "graph_version": "v-test",
            "tables": [],
            "table_edges": [],
            "field_edges": [],
            "saved_sql": None,
        },
    )

    res = _client().get(
        "/api/lineage/graph",
        params={
            "table": "dws_cell_hourly",
            "depth": 2,
            "include_upstream": "true",
            "include_downstream": "false",
        },
    )

    assert res.status_code == 200
    assert res.json()["root_table"] == "dws_cell_hourly"
    assert res.json()["include_downstream"] is False
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/api/test_lineage_calc_edges.py -v
```

Expected: fail because `/api/lineage/graph`, endpoint patching, and structured update are missing.

- [ ] **Step 3: Add service helpers for calculation metadata**

In `backend/metadata/service.py`, add imports:

```python
from backend.metadata.models import (
    CalcType,
    LineageEdgeEndpointUpdateRequest,
    LineageGraphResponse,
    LineageTableEdge,
    LineageTableNode,
)
```

Add helper functions below `_serialize_neo4j_datetime`:

```python
def _json_dict(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        return json.loads(value)
    return {}


def _calc_params_to_str(value: dict | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _graph_version(rows: list[dict]) -> str:
    edge_ids = sorted(str(row.get("edge_id") or "") for row in rows)
    return f"edges:{len(edge_ids)}:{hash(tuple(edge_ids))}"
```

Update `_lineage_edge_from_row`:

```python
def _lineage_edge_from_row(row: dict) -> LineageEdge:
    return LineageEdge(
        edge_id=str(row.get("edge_id") or ""),
        from_table=row["from_table"],
        from_field=row["from_field"],
        to_table=row["to_table"],
        to_field=row["to_field"],
        transform_expr=row.get("transform_expr") or "",
        calc_type=row.get("calc_type") or "DIRECT",
        calc_params=_json_dict(row.get("calc_params")),
        created_at=_serialize_neo4j_datetime(row.get("created_at")),
        updated_at=_serialize_neo4j_datetime(row.get("updated_at")),
    )
```

- [ ] **Step 4: Persist calculation metadata in create/update**

In `create_lineage_edge`, update the Cypher `MERGE` block:

```cypher
MERGE (to_f)-[r:DERIVES_FROM]->(from_f)
ON CREATE SET r.edge_id = $edge_id,
              r.created_at = datetime()
SET r.transform_expr = $transform_expr,
    r.calc_type = $calc_type,
    r.calc_params = $calc_params,
    r.updated_at = datetime()
RETURN coalesce(r.edge_id, elementId(r)) AS edge_id
```

Pass these params:

```python
calc_type=req.calc_type,
calc_params=_calc_params_to_str(req.calc_params),
```

In `update_lineage_edge`, update the Cypher `SET` block:

```cypher
SET r.transform_expr = $transform_expr,
    r.calc_type = $calc_type,
    r.calc_params = $calc_params,
    r.updated_at = datetime()
```

Pass:

```python
calc_type=req.calc_type,
calc_params=_calc_params_to_str(req.calc_params),
```

- [ ] **Step 5: Add endpoint mutation service**

Add this function in `service.py`:

```python
def update_lineage_edge_endpoints(edge_id: str, req: LineageEdgeEndpointUpdateRequest) -> LineageEdge:
    current = _load_lineage_edge(edge_id)
    rows = run_query(
        """
        MATCH (from_t:Table {name: $from_table})-[:HAS_FIELD]->(from_f:Field {name: $from_field})
        MATCH (to_t:Table {name: $to_table})-[:HAS_FIELD]->(to_f:Field {name: $to_field})
        RETURN from_f.id AS source_field_id, to_f.id AS target_field_id
        """,
        from_table=req.from_table,
        from_field=req.from_field,
        to_table=req.to_table,
        to_field=req.to_field,
    )
    if not rows:
        raise FieldNotFound(f"{req.from_table}.{req.from_field} -> {req.to_table}.{req.to_field}")

    source_field_id = rows[0]["source_field_id"]
    target_field_id = rows[0]["target_field_id"]
    assert_no_lineage_cycle(target_field_id=target_field_id, source_field_id=source_field_id)
    delete_lineage_edge(edge_id)
    return create_lineage_edge(
        LineageEdgeCreateRequest(
            from_table=req.from_table,
            from_field=req.from_field,
            to_table=req.to_table,
            to_field=req.to_field,
            transform_expr=current.transform_expr or "passthrough",
            calc_type=current.calc_type,
            calc_params=current.calc_params,
        )
    )
```

- [ ] **Step 6: Add graph aggregation service**

Add this function in `service.py`:

```python
def get_lineage_graph(
    table: str,
    depth: int = 2,
    include_upstream: bool = True,
    include_downstream: bool = True,
) -> LineageGraphResponse:
    if get_table_by_name(table, optional=True) is None:
        raise TableNotFound(table)

    upstream_edges = get_lineage(table=table, direction="up", depth=depth) if include_upstream else []
    downstream_edges = get_lineage(table=table, direction="down", depth=depth) if include_downstream else []
    field_edges = list({edge.edge_id: edge for edge in [*upstream_edges, *downstream_edges]}.values())
    table_names = sorted({
        table,
        *[edge.from_table for edge in field_edges],
        *[edge.to_table for edge in field_edges],
    })
    table_nodes: list[LineageTableNode] = []
    for name in table_names:
        detail = get_table_by_name(name)
        table_nodes.append(LineageTableNode(
            id=detail.id,
            name=detail.name,
            layer=detail.layer,
            layer_priority=detail.layer_priority,
            storage_type=detail.storage_type,
            description=detail.description,
            field_count=len(detail.fields),
            fields=detail.fields,
            sql_logic=getattr(detail, "sql_logic", None),
            sql_dialect=getattr(detail, "sql_dialect", None),
            sql_source=getattr(detail, "sql_source", None),
            sql_updated_at=getattr(detail, "sql_updated_at", ""),
        ))

    table_edge_map: dict[tuple[str, str], list[LineageEdge]] = {}
    for edge in field_edges:
        table_edge_map.setdefault((edge.from_table, edge.to_table), []).append(edge)

    table_edges = []
    for (source, target), edges in sorted(table_edge_map.items()):
        direction = "downstream" if source == table or any(e.from_table == table for e in edges) else "upstream"
        calc_counts: dict[str, int] = {}
        for edge in edges:
            calc_counts[edge.calc_type] = calc_counts.get(edge.calc_type, 0) + 1
        table_edges.append(LineageTableEdge(
            source=source,
            target=target,
            direction=direction,
            field_edge_count=len(edges),
            calc_type_counts=calc_counts,
            fields=sorted({edge.to_field for edge in edges}),
        ))

    return LineageGraphResponse(
        root_table=table,
        depth=depth,
        include_upstream=include_upstream,
        include_downstream=include_downstream,
        graph_version=_graph_version([edge.model_dump() for edge in field_edges]),
        tables=table_nodes,
        table_edges=table_edges,
        field_edges=field_edges,
        saved_sql=next((node.sql_logic for node in table_nodes if node.name == table), None),
    )
```

- [ ] **Step 7: Add API routes**

In `backend/api/metadata.py`, add imports:

```python
    LineageEdgeEndpointUpdateRequest,
    LineageGraphResponse,
```

Add route below `/api/lineage`:

```python
@router.get("/api/lineage/graph", response_model=LineageGraphResponse)
def lineage_graph_endpoint(
    table: str = Query(...),
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
```

Add endpoint patch route below edge update:

```python
@router.patch("/api/lineage/edges/{edge_id}/endpoints", response_model=LineageEdge)
def update_lineage_edge_endpoints_endpoint(edge_id: str, req: LineageEdgeEndpointUpdateRequest):
    try:
        return service.update_lineage_edge_endpoints(edge_id, req)
    except service.LineageEdgeNotFound:
        raise HTTPException(status_code=404, detail={"error": "lineage edge not found", "edge_id": edge_id})
    except service.FieldNotFound:
        raise HTTPException(status_code=404, detail={"error": "lineage endpoint field not found"})
    except service.CycleDetected as e:
        raise HTTPException(status_code=409, detail={"error": "lineage cycle detected", "path": e.path})
```

- [ ] **Step 8: Run tests and commit**

Run:

```powershell
python -m pytest tests/api/test_lineage_calc_edges.py tests/api/test_lineage_graph_contract.py tests/api/test_lineage_edge_crud.py -v
```

Expected: all selected tests pass.

Commit:

```powershell
git add backend/metadata/models.py backend/metadata/service.py backend/api/metadata.py tests/api/test_lineage_calc_edges.py tests/api/test_lineage_graph_contract.py
git commit -m "api: add lineage workspace graph contract"
```

## Task 3: SQL Preview And Import Preview Service

**Files:**
- Create: `backend/metadata/lineage_sql.py`
- Modify: `backend/metadata/service.py`
- Modify: `backend/api/metadata.py`
- Test: `tests/api/test_lineage_sql.py`

- [ ] **Step 1: Add failing SQL service tests**

Create `tests/api/test_lineage_sql.py`:

```python
from backend.metadata.lineage_sql import (
    generate_select_sql,
    parse_select_preview,
)
from backend.metadata.models import LineageEdge


def test_generate_select_sql_uses_aggregate_and_group_by():
    sql, complete, warnings = generate_select_sql(
        table="dws_cell_hourly",
        fields=["cell_id", "hour_bucket", "avg_rsrp"],
        saved_sql=None,
        edges=[
            LineageEdge(
                edge_id="edge-1",
                from_table="dwd_session_qos",
                from_field="avg_rsrp",
                to_table="dws_cell_hourly",
                to_field="avg_rsrp",
                transform_expr="AVG(dwd_session_qos.avg_rsrp)",
                calc_type="AGGREGATE",
                calc_params={"function": "AVG", "group_by": ["cell_id", "hour_bucket"]},
            ),
            LineageEdge(
                edge_id="edge-2",
                from_table="dwd_session_qos",
                from_field="cell_id",
                to_table="dws_cell_hourly",
                to_field="cell_id",
                transform_expr="dwd_session_qos.cell_id",
                calc_type="DIRECT",
                calc_params={},
            ),
        ],
    )

    assert complete is True
    assert warnings == []
    assert "SELECT" in sql
    assert "AVG(dwd_session_qos.avg_rsrp) AS avg_rsrp" in sql
    assert "FROM dwd_session_qos" in sql
    assert "GROUP BY cell_id, hour_bucket" in sql


def test_parse_select_preview_extracts_fields_and_edges():
    preview = parse_select_preview(
        target_table="dws_cell_hourly",
        sql="""
        SELECT
          cell_id,
          AVG(q.avg_rsrp) AS avg_rsrp,
          CASE WHEN AVG(q.avg_sinr) > 10 THEN 1 ELSE 0 END AS good_signal
        FROM dwd_session_qos q
        GROUP BY cell_id
        """,
    )

    assert [field.field for field in preview.fields] == ["cell_id", "avg_rsrp", "good_signal"]
    agg_edge = next(change.edge for change in preview.edges if change.edge.to_field == "avg_rsrp")
    assert agg_edge.from_table == "dwd_session_qos"
    assert agg_edge.from_field == "avg_rsrp"
    assert agg_edge.calc_type == "AGGREGATE"
    cond_edge = next(change.edge for change in preview.edges if change.edge.to_field == "good_signal")
    assert cond_edge.calc_type == "CONDITION"


def test_parse_select_preview_reports_unknown_source_field():
    preview = parse_select_preview(
        target_table="dws_cell_hourly",
        sql="SELECT missing_alias.rsrp AS avg_rsrp FROM dwd_session_qos q",
    )

    assert preview.warnings == ["Unable to resolve table alias missing_alias for field avg_rsrp"]
```

- [ ] **Step 2: Run SQL tests and verify failure**

Run:

```powershell
python -m pytest tests/api/test_lineage_sql.py -v
```

Expected: fail because `backend.metadata.lineage_sql` is missing.

- [ ] **Step 3: Create SQL helper module**

Create `backend/metadata/lineage_sql.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from sqlglot import exp, parse_one

from backend.metadata.models import (
    EdgeChangePreview,
    FieldChangePreview,
    LineageEdge,
    LineageSqlImportPreviewResponse,
)


@dataclass(frozen=True)
class SqlPreview:
    sql: str
    complete: bool
    warnings: list[str]


def _expression_for_edge(edge: LineageEdge) -> str:
    if edge.calc_type == "DIRECT":
        return edge.transform_expr or f"{edge.from_table}.{edge.from_field}"
    if edge.calc_type == "AGGREGATE":
        function = str(edge.calc_params.get("function", "AVG")).upper()
        return edge.transform_expr or f"{function}({edge.from_table}.{edge.from_field})"
    if edge.calc_type == "CONDITION":
        return edge.transform_expr or "CASE WHEN 1 = 1 THEN 1 ELSE 0 END"
    if edge.calc_type == "WINDOW":
        return edge.transform_expr or f"{edge.from_table}.{edge.from_field}"
    if edge.calc_type == "CONSTANT":
        return edge.transform_expr or str(edge.calc_params.get("value", "NULL"))
    return edge.transform_expr or f"{edge.from_table}.{edge.from_field}"


def generate_select_sql(
    *,
    table: str,
    fields: list[str],
    saved_sql: str | None,
    edges: list[LineageEdge],
) -> tuple[str, bool, list[str]]:
    warnings: list[str] = []
    by_target = {edge.to_field: edge for edge in edges}
    source_tables = sorted({edge.from_table for edge in edges})
    primary_source = source_tables[0] if source_tables else table

    select_lines: list[str] = []
    group_by: list[str] = []
    for field in fields:
        edge = by_target.get(field)
        if edge is None:
            select_lines.append(f"  NULL AS {field}")
            warnings.append(f"No lineage edge found for field {field}")
            continue
        expr_text = _expression_for_edge(edge)
        select_lines.append(f"  {expr_text} AS {field}")
        for group_field in edge.calc_params.get("group_by", []):
            if isinstance(group_field, str) and group_field not in group_by:
                group_by.append(group_field)

    sql = "SELECT\n" + ",\n".join(select_lines) + f"\nFROM {primary_source}"
    if group_by:
        sql += "\nGROUP BY " + ", ".join(group_by)
    complete = len(warnings) == 0
    return sql, complete, warnings


def _source_aliases(tree: exp.Expression) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for table in tree.find_all(exp.Table):
        alias = table.alias_or_name
        aliases[alias] = table.name
        aliases[table.name] = table.name
    return aliases


def _target_name(select_expr: exp.Expression) -> str:
    if isinstance(select_expr, exp.Alias):
        return select_expr.alias
    if isinstance(select_expr, exp.Column):
        return select_expr.name
    return select_expr.output_name or select_expr.sql(dialect="hive").replace(" ", "_").lower()


def _calc_type(select_expr: exp.Expression) -> str:
    inner = select_expr.this if isinstance(select_expr, exp.Alias) else select_expr
    if list(inner.find_all(exp.AggFunc)):
        return "AGGREGATE"
    if list(inner.find_all(exp.Window)):
        return "WINDOW"
    if list(inner.find_all(exp.Case)):
        return "CONDITION"
    if isinstance(inner, exp.Column):
        return "DIRECT"
    if isinstance(inner, exp.Literal):
        return "CONSTANT"
    return "EXPRESSION"


def _columns_for_expr(select_expr: exp.Expression) -> list[exp.Column]:
    inner = select_expr.this if isinstance(select_expr, exp.Alias) else select_expr
    return list(inner.find_all(exp.Column))


def parse_select_preview(target_table: str, sql: str) -> LineageSqlImportPreviewResponse:
    tree = parse_one(sql, read="hive")
    aliases = _source_aliases(tree)
    fields: list[FieldChangePreview] = []
    edges: list[EdgeChangePreview] = []
    warnings: list[str] = []

    select_exprs = tree.expressions if isinstance(tree, exp.Select) else []
    for select_expr in select_exprs:
        target_field = _target_name(select_expr)
        expr_sql = select_expr.sql(dialect="hive")
        calc_type = _calc_type(select_expr)
        upstream_refs = []
        for column in _columns_for_expr(select_expr):
            alias = column.table
            source_table = aliases.get(alias) if alias else next(iter(aliases.values()), "")
            if not source_table:
                warnings.append(f"Unable to resolve table alias {alias} for field {target_field}")
                continue
            upstream_refs.append({"table": source_table, "field": column.name})
            edges.append(EdgeChangePreview(
                action="add",
                edge=LineageEdge(
                    from_table=source_table,
                    from_field=column.name,
                    to_table=target_table,
                    to_field=target_field,
                    transform_expr=expr_sql,
                    calc_type=calc_type,
                    calc_params={"expression": expr_sql},
                ),
            ))
        fields.append(FieldChangePreview(
            action="add",
            field=target_field,
            expression=expr_sql,
            field_type="STRING",
            upstream=upstream_refs,
        ))
    return LineageSqlImportPreviewResponse(table=target_table, sql=sql, fields=fields, edges=edges, warnings=warnings)
```

- [ ] **Step 4: Run SQL service tests**

Run:

```powershell
python -m pytest tests/api/test_lineage_sql.py -v
```

Expected: all tests in `tests/api/test_lineage_sql.py` pass.

- [ ] **Step 5: Add service wrappers**

In `backend/metadata/service.py`, import:

```python
from backend.metadata.lineage_sql import generate_select_sql, parse_select_preview
from backend.metadata.models import LineageSqlPreviewResponse, LineageSqlImportPreviewResponse, LineageSqlApplyRequest
```

Add:

```python
def preview_lineage_sql(table: str, field_edges: Optional[list[LineageEdge]] = None) -> LineageSqlPreviewResponse:
    detail = get_table_by_name(table)
    edges = field_edges if field_edges is not None else get_lineage(table, direction="up", depth=1)
    sql, complete, warnings = generate_select_sql(
        table=table,
        fields=[field.name for field in detail.fields],
        saved_sql=getattr(detail, "sql_logic", None),
        edges=edges,
    )
    saved_sql = getattr(detail, "sql_logic", None)
    return LineageSqlPreviewResponse(
        table=table,
        sql=sql,
        complete=complete,
        warnings=warnings,
        saved_sql=saved_sql,
        changed=(saved_sql or "").strip() != sql.strip(),
    )


def preview_sql_import(table: str, sql: str) -> LineageSqlImportPreviewResponse:
    if get_table_by_name(table, optional=True) is None:
        raise TableNotFound(table)
    return parse_select_preview(target_table=table, sql=sql)


def apply_lineage_sql(req: LineageSqlApplyRequest) -> LineageSqlPreviewResponse:
    if get_table_by_name(req.table, optional=True) is None:
        raise TableNotFound(req.table)
    run_query(
        """
        MATCH (t:Table {name: $table})
        SET t.sql_logic = $sql,
            t.sql_dialect = 'spark_hive',
            t.sql_source = 'imported',
            t.sql_updated_at = datetime()
        CREATE (:Change {
            id: $change_id,
            table_name: $table,
            field_name: null,
            operation: 'UPDATE_TABLE_SQL',
            version: 1,
            commit_hash: null,
            old_value: '',
            new_value: $sql,
            changed_at: datetime()
        })
        """,
        table=req.table,
        sql=req.sql,
        change_id=str(uuid.uuid4()),
    )
    return preview_lineage_sql(req.table)
```

- [ ] **Step 6: Add SQL API routes**

In `backend/api/metadata.py`, add imports:

```python
    LineageSqlApplyRequest,
    LineageSqlImportPreviewRequest,
    LineageSqlImportPreviewResponse,
    LineageSqlPreviewRequest,
    LineageSqlPreviewResponse,
```

Add routes:

```python
@router.post("/api/lineage/sql/preview", response_model=LineageSqlPreviewResponse)
def lineage_sql_preview_endpoint(req: LineageSqlPreviewRequest):
    try:
        return service.preview_lineage_sql(req.table, req.field_edges)
    except service.TableNotFound:
        raise HTTPException(status_code=404, detail={"error": "table not found", "table": req.table})


@router.post("/api/lineage/sql/import/preview", response_model=LineageSqlImportPreviewResponse)
def lineage_sql_import_preview_endpoint(req: LineageSqlImportPreviewRequest):
    try:
        return service.preview_sql_import(req.table, req.sql)
    except service.TableNotFound:
        raise HTTPException(status_code=404, detail={"error": "table not found", "table": req.table})
    except Exception as exc:
        raise HTTPException(status_code=422, detail={"error": "sql parse failed", "message": str(exc)})


@router.post("/api/lineage/sql/apply", response_model=LineageSqlPreviewResponse)
def lineage_sql_apply_endpoint(req: LineageSqlApplyRequest):
    try:
        return service.apply_lineage_sql(req)
    except service.TableNotFound:
        raise HTTPException(status_code=404, detail={"error": "table not found", "table": req.table})
```

- [ ] **Step 7: Run backend SQL tests and commit**

Run:

```powershell
python -m pytest tests/api/test_lineage_sql.py tests/api/test_lineage_calc_edges.py -v
```

Expected: all selected tests pass.

Commit:

```powershell
git add pyproject.toml backend/metadata/lineage_sql.py backend/metadata/service.py backend/api/metadata.py tests/api/test_lineage_sql.py
git commit -m "api: add lineage sql preview and import"
```

## Task 4: Frontend API Contract And Test Fixtures

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/tests/e2e/fixtures.ts`

- [ ] **Step 1: Update frontend API types**

In `frontend/src/api/client.ts`, extend `LineageEdge`:

```ts
export type CalcType = 'DIRECT' | 'EXPRESSION' | 'AGGREGATE' | 'JOIN' | 'WINDOW' | 'CONDITION' | 'CONSTANT'

export type LineageEdge = {
  edge_id?: string
  from_table: string
  from_field: string
  to_table: string
  to_field: string
  transform_expr: string
  calc_type?: CalcType
  calc_params?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}
```

Add types:

```ts
export type LineageTableNode = TableSummary & {
  fields: FieldResponse[]
  sql_logic?: string | null
  sql_dialect?: string | null
  sql_source?: 'generated' | 'imported' | 'manual' | null
  sql_updated_at?: string
}

export type LineageTableEdge = {
  source: string
  target: string
  direction: 'upstream' | 'downstream'
  field_edge_count: number
  calc_type_counts: Record<string, number>
  fields: string[]
}

export type LineageGraphResponse = {
  root_table: string
  depth: number
  include_upstream: boolean
  include_downstream: boolean
  graph_version: string
  tables: LineageTableNode[]
  table_edges: LineageTableEdge[]
  field_edges: LineageEdge[]
  saved_sql?: string | null
}

export type LineageSqlPreviewResponse = {
  table: string
  sql: string
  complete: boolean
  warnings: string[]
  saved_sql?: string | null
  changed: boolean
}

export type FieldChangePreview = {
  action: 'add' | 'update' | 'keep'
  field: string
  expression: string
  field_type: string
  upstream: UpstreamRef[]
}

export type EdgeChangePreview = {
  action: 'add' | 'update' | 'delete' | 'keep'
  edge: LineageEdge
}

export type LineageSqlImportPreviewResponse = {
  table: string
  sql: string
  fields: FieldChangePreview[]
  edges: EdgeChangePreview[]
  warnings: string[]
}
```

Extend `LineageEdgePayload`:

```ts
export type LineageEdgePayload = {
  from_table: string
  from_field: string
  to_table: string
  to_field: string
  transform_expr: string
  calc_type?: CalcType
  calc_params?: Record<string, unknown>
}
```

Add API methods:

```ts
  lineageGraph: (params: { table: string; depth?: number; include_upstream?: boolean; include_downstream?: boolean }) =>
    fetchJson<LineageGraphResponse>(`/api/lineage/graph${qs(params)}`),
  updateLineageEdgeEndpoints: (edgeId: string, payload: Pick<LineageEdgePayload, 'from_table' | 'from_field' | 'to_table' | 'to_field'>) =>
    fetchJson<LineageEdge>(`/api/lineage/edges/${encodeURIComponent(edgeId)}/endpoints`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  previewLineageSql: (payload: { table: string; field_edges?: LineageEdge[] }) =>
    fetchJson<LineageSqlPreviewResponse>('/api/lineage/sql/preview', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  previewLineageSqlImport: (payload: { table: string; sql: string }) =>
    fetchJson<LineageSqlImportPreviewResponse>('/api/lineage/sql/import/preview', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  applyLineageSql: (payload: { table: string; sql: string; fields: FieldChangePreview[]; edges: EdgeChangePreview[]; expected_graph_version?: string }) =>
    fetchJson<LineageSqlPreviewResponse>('/api/lineage/sql/apply', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
```

- [ ] **Step 2: Update e2e fixtures**

In `frontend/tests/e2e/fixtures.ts`, add:

```ts
export const lineageGraph = {
  root_table: 'dws_cell_hourly',
  depth: 2,
  include_upstream: true,
  include_downstream: true,
  graph_version: 'v-e2e',
  saved_sql: 'SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q',
  tables: [
    { ...tables[0], fields: tableDetail.fields, sql_logic: 'SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q', sql_dialect: 'spark_hive', sql_source: 'generated', sql_updated_at: '2026-07-03T10:00:00Z' },
    { ...tables[1], fields: tableDetail.fields, sql_logic: null, sql_dialect: null, sql_source: null, sql_updated_at: '' },
  ],
  table_edges: [
    { source: 'dwd_session_qos', target: 'dws_cell_hourly', direction: 'upstream', field_edge_count: 1, calc_type_counts: { AGGREGATE: 1 }, fields: ['avg_rsrp'] },
  ],
  field_edges: [
    {
      edge_id: 'edge-1',
      from_table: 'dwd_session_qos',
      from_field: 'avg_rsrp',
      to_table: 'dws_cell_hourly',
      to_field: 'avg_rsrp',
      transform_expr: 'AVG(q.avg_rsrp)',
      calc_type: 'AGGREGATE',
      calc_params: { function: 'AVG', group_by: ['cell_id'] },
      created_at: '2026-07-03T10:00:00Z',
      updated_at: '2026-07-03T10:00:00Z',
    },
  ],
}

export const lineageSqlPreview = {
  table: 'dws_cell_hourly',
  sql: 'SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q GROUP BY cell_id',
  complete: true,
  warnings: [],
  saved_sql: 'SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q',
  changed: true,
}

export const lineageSqlImportPreview = {
  table: 'dws_cell_hourly',
  sql: 'SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q GROUP BY cell_id',
  fields: [{ action: 'update', field: 'avg_rsrp', expression: 'AVG(q.avg_rsrp)', field_type: 'DOUBLE', upstream: [{ table: 'dwd_session_qos', field: 'avg_rsrp' }] }],
  edges: [{ action: 'update', edge: lineageGraph.field_edges[0] }],
  warnings: [],
}
```

Extend `mockCommonApis`:

```ts
  await page.route('**/api/lineage/graph**', (route) => json(route, lineageGraph))
  await page.route('**/api/lineage/sql/preview', (route) => json(route, lineageSqlPreview))
  await page.route('**/api/lineage/sql/import/preview', (route) => json(route, lineageSqlImportPreview))
  await page.route('**/api/lineage/sql/apply', (route) => json(route, lineageSqlPreview))
```

- [ ] **Step 3: Run frontend type check through build**

Run:

```powershell
npm.cmd --prefix frontend run build
```

Expected: TypeScript passes. The Vite large chunk warning may appear.

- [ ] **Step 4: Commit**

```powershell
git add frontend/src/api/client.ts frontend/tests/e2e/fixtures.ts
git commit -m "ui: add lineage workspace api types"
```

## Task 5: Frontend Workspace Graph Data And Rendering

**Files:**
- Create: `frontend/src/components/graphShared/lineageWorkspaceData.ts`
- Create: `frontend/src/components/LineageWorkspaceGraph.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/tests/e2e/lineage.spec.ts`

- [ ] **Step 1: Replace e2e lineage test with failing workspace expectations**

Replace `frontend/tests/e2e/lineage.spec.ts`:

```ts
import { expect, test } from '@playwright/test'
import { json, lineageGraph, lineageSqlPreview } from './fixtures'

test('lineage workspace renders table graph and expandable field edges', async ({ page }) => {
  await page.route('**/api/lineage/graph**', (route) => json(route, lineageGraph))
  await page.route('**/api/lineage/sql/preview', (route) => json(route, lineageSqlPreview))

  await page.goto('/metadata/lineage?table=dws_cell_hourly')

  await expect(page.getByText('血缘工作台')).toBeVisible()
  await expect(page.getByLabel('前向')).toBeChecked()
  await expect(page.getByLabel('后向')).toBeChecked()
  await expect(page.getByText('dws_cell_hourly')).toBeVisible()
  await expect(page.getByText('dwd_session_qos')).toBeVisible()

  await page.getByRole('button', { name: '展开 dws_cell_hourly' }).click()
  await expect(page.getByText('avg_rsrp')).toBeVisible()
  await expect(page.getByText('AVG(q.avg_rsrp)')).toBeVisible()

  await page.getByLabel('后向').uncheck()
  await expect(page.getByText('dwd_session_qos')).not.toBeVisible()
})

test('lineage workspace drags an edge endpoint to another field', async ({ page }) => {
  let patchedPayload: unknown
  await page.route('**/api/lineage/graph**', (route) => json(route, lineageGraph))
  await page.route('**/api/lineage/sql/preview', (route) => json(route, lineageSqlPreview))
  await page.route('**/api/lineage/edges/edge-1/endpoints', async (route) => {
    patchedPayload = route.request().postDataJSON()
    await json(route, { ...lineageGraph.field_edges[0], from_field: 'hour_bucket' })
  })

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await page.getByRole('button', { name: '展开 dwd_session_qos' }).click()
  await page.getByLabel('源锚点 edge-1').dragTo(page.getByLabel('字段锚点 dwd_session_qos.hour_bucket'))

  expect(patchedPayload).toEqual({
    from_table: 'dwd_session_qos',
    from_field: 'hour_bucket',
    to_table: 'dws_cell_hourly',
    to_field: 'avg_rsrp',
  })
})
```

- [ ] **Step 2: Run e2e test and verify failure**

Run:

```powershell
npm.cmd --prefix frontend run test:e2e -- tests/e2e/lineage.spec.ts
```

Expected: fail because the workspace title, checkboxes, and expand button do not exist.

- [ ] **Step 3: Create graph data adapter**

Create `frontend/src/components/graphShared/lineageWorkspaceData.ts`:

```ts
import type { LineageGraphResponse, LineageTableEdge, LineageTableNode } from '../../api/client'

export type WorkspaceTable = LineageTableNode & {
  expanded: boolean
  upstream: LineageTableEdge[]
  downstream: LineageTableEdge[]
}

export function buildWorkspaceTables(payload: LineageGraphResponse | undefined, expandedTables: Set<string>): WorkspaceTable[] {
  if (!payload) return []
  return payload.tables.map((table) => ({
    ...table,
    expanded: expandedTables.has(table.name),
    upstream: payload.table_edges.filter((edge) => edge.target === table.name),
    downstream: payload.table_edges.filter((edge) => edge.source === table.name),
  }))
}

export function edgeLabel(edge: LineageTableEdge) {
  const calcTypes = Object.entries(edge.calc_type_counts)
    .map(([type, count]) => `${type} ${count}`)
    .join(', ')
  return `${edge.field_edge_count} 字段${calcTypes ? ` · ${calcTypes}` : ''}`
}
```

- [ ] **Step 4: Create workspace graph component**

Create `frontend/src/components/LineageWorkspaceGraph.tsx`:

```tsx
import { Button, Empty, Tag, Tooltip } from 'antd'
import type { DragEvent } from 'react'
import type { LineageEdge, LineageGraphResponse } from '../api/client'
import { buildWorkspaceTables, edgeLabel } from './graphShared/lineageWorkspaceData'

type Props = {
  payload?: LineageGraphResponse
  expandedTables: Set<string>
  onToggleTable: (table: string) => void
  onSelectFieldEdge: (edge: LineageEdge) => void
  onMoveEdgeEndpoint: (edge: LineageEdge, endpoint: 'from' | 'to', table: string, field: string) => void
}

type DragPayload = {
  edgeId: string
  endpoint: 'from' | 'to'
}

function edgeKey(edge: LineageEdge) {
  return edge.edge_id || `${edge.from_table}.${edge.from_field}->${edge.to_table}.${edge.to_field}`
}

function findEdge(payload: LineageGraphResponse, edgeId: string) {
  return payload.field_edges.find((edge) => edgeKey(edge) === edgeId)
}

export default function LineageWorkspaceGraph({ payload, expandedTables, onToggleTable, onSelectFieldEdge, onMoveEdgeEndpoint }: Props) {
  const tables = buildWorkspaceTables(payload, expandedTables)
  if (!payload || tables.length === 0) return <Empty description="暂无血缘数据" />

  function onDragStart(event: DragEvent, dragPayload: DragPayload) {
    event.dataTransfer.setData('application/json', JSON.stringify(dragPayload))
  }

  function onDropField(event: DragEvent, table: string, field: string) {
    event.preventDefault()
    const raw = event.dataTransfer.getData('application/json')
    if (!raw) return
    const dragPayload = JSON.parse(raw) as DragPayload
    const movingEdge = findEdge(payload, dragPayload.edgeId)
    if (!movingEdge) return
    onMoveEdgeEndpoint(movingEdge, dragPayload.endpoint, table, field)
  }

  return (
    <div className="lineage-workspace-graph" aria-label="血缘工作台画布">
      <div className="lineage-table-edge-layer">
        {payload.table_edges.map((edge) => (
          <Tooltip key={`${edge.source}->${edge.target}`} title={edgeLabel(edge)}>
            <div className="lineage-table-edge">
              <span>{edge.source}</span>
              <span>⟶</span>
              <span>{edge.target}</span>
            </div>
          </Tooltip>
        ))}
      </div>
      <div className="lineage-table-grid">
        {tables.map((table) => (
          <section key={table.name} className={`lineage-table-node ${table.name === payload.root_table ? 'selected' : ''}`}>
            <header>
              <strong>{table.name}</strong>
              <Button size="small" aria-label={`${table.expanded ? '折叠' : '展开'} ${table.name}`} onClick={() => onToggleTable(table.name)}>
                {table.expanded ? '-' : '+'}
              </Button>
            </header>
            <div className="muted">{table.layer} · {table.storage_type} · {table.field_count} 字段</div>
            {table.expanded ? (
              <div className="lineage-field-list">
                {table.fields.map((field) => (
                  <div
                    key={field.id}
                    className="lineage-field-row"
                    aria-label={`字段锚点 ${table.name}.${field.name}`}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => onDropField(event, table.name, field.name)}
                  >
                    <span className="lineage-anchor">○</span>
                    <span>{field.name}</span>
                    <Tag>{field.field_type}</Tag>
                  </div>
                ))}
              </div>
            ) : null}
          </section>
        ))}
      </div>
      <div className="lineage-field-edge-list">
        {payload.field_edges.map((edge) => (
          <button key={edgeKey(edge)} type="button" onClick={() => onSelectFieldEdge(edge)}>
            <span
              draggable
              role="button"
              aria-label={`源锚点 ${edgeKey(edge)}`}
              onDragStart={(event) => onDragStart(event, { edgeId: edgeKey(edge), endpoint: 'from' })}
            >
              ◀
            </span>
            <span>{edge.from_table}.{edge.from_field}</span>
            <span>⇢</span>
            <span>{edge.to_table}.{edge.to_field}</span>
            <span
              draggable
              role="button"
              aria-label={`目标锚点 ${edgeKey(edge)}`}
              onDragStart={(event) => onDragStart(event, { edgeId: edgeKey(edge), endpoint: 'to' })}
            >
              ▶
            </span>
            <Tag>{edge.calc_type ?? 'DIRECT'}</Tag>
            <span>{edge.transform_expr}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
```

This component uses semantic HTML for the first implementation so e2e can validate behavior. Keep the existing AntV G6 dependency in place and preserve the component boundary so the rendering internals can change without changing `Lineage.tsx`.

- [ ] **Step 5: Add styles**

Append to `frontend/src/styles.css`:

```css
.lineage-workspace-graph {
  position: relative;
  display: grid;
  gap: 12px;
  min-height: 520px;
  padding: 12px;
  background: linear-gradient(#f8fafc 1px, transparent 1px), linear-gradient(90deg, #f8fafc 1px, transparent 1px);
  background-size: 28px 28px;
}

.lineage-table-edge-layer,
.lineage-field-edge-list {
  display: grid;
  gap: 8px;
}

.lineage-table-edge,
.lineage-field-edge-list button {
  display: flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  background: #eff6ff;
  color: #1e3a8a;
  padding: 6px 8px;
}

.lineage-field-edge-list button {
  border-style: dashed;
  border-color: #cbd5e1;
  background: rgba(255, 255, 255, 0.9);
  color: #172033;
  cursor: pointer;
}

.lineage-table-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  align-items: start;
}

.lineage-table-node {
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  padding: 10px;
}

.lineage-table-node.selected {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.14);
}

.lineage-table-node header,
.lineage-field-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.lineage-field-list {
  display: grid;
  gap: 6px;
  margin-top: 10px;
}

.lineage-field-row {
  padding: 6px;
  border: 1px dashed #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
}

.lineage-anchor {
  color: #2563eb;
}
```

- [ ] **Step 6: Wire component in page**

In `frontend/src/pages/Lineage.tsx`, this task only prepares the component import and state. Full page logic lands in Task 7.

Add imports:

```tsx
import { Checkbox } from 'antd'
import LineageWorkspaceGraph from '../components/LineageWorkspaceGraph'
```

Add state:

```tsx
  const [includeUpstream, setIncludeUpstream] = useState(true)
  const [includeDownstream, setIncludeDownstream] = useState(true)
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set())
```

Replace `lineageQuery` with:

```tsx
  const lineageQuery = useQuery({
    queryKey: ['lineage-graph', table, depth, includeUpstream, includeDownstream],
    queryFn: () => api.lineageGraph({ table, depth, include_upstream: includeUpstream, include_downstream: includeDownstream }),
  })
```

Add endpoint movement mutation:

```tsx
  const moveEndpointMutation = useMutation({
    mutationFn: ({ selectedEdge, endpoint, nextTable, nextField }: { selectedEdge: LineageEdge; endpoint: 'from' | 'to'; nextTable: string; nextField: string }) =>
      api.updateLineageEdgeEndpoints(edgeId(selectedEdge), {
        from_table: endpoint === 'from' ? nextTable : selectedEdge.from_table,
        from_field: endpoint === 'from' ? nextField : selectedEdge.from_field,
        to_table: endpoint === 'to' ? nextTable : selectedEdge.to_table,
        to_field: endpoint === 'to' ? nextField : selectedEdge.to_field,
      }),
    onSuccess: (next) => {
      apiMessage.success('血缘端点已更新')
      setEdge(next)
      invalidateLineage()
    },
    onError: (error) => apiMessage.error(`端点更新失败: ${(error as Error).message}`),
  })
```

Replace the graph component call:

```tsx
        <LineageWorkspaceGraph
          payload={lineageQuery.data}
          expandedTables={expandedTables}
          onToggleTable={(name) => {
            setExpandedTables((prev) => {
              const next = new Set(prev)
              if (next.has(name)) next.delete(name)
              else next.add(name)
              return next
            })
          }}
          onSelectFieldEdge={(next) => {
            setEdge(next)
            setNodeId(undefined)
          }}
          onMoveEdgeEndpoint={(selectedEdge, endpoint, nextTable, nextField) => {
            moveEndpointMutation.mutate({ selectedEdge, endpoint, nextTable, nextField })
          }}
        />
```

Replace the title and direction controls:

```tsx
        <Typography.Title level={4} style={{ marginTop: 0 }}>血缘工作台</Typography.Title>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Checkbox checked={includeDownstream} onChange={(event) => setIncludeDownstream(event.target.checked)}>前向</Checkbox>
          <Checkbox checked={includeUpstream} onChange={(event) => setIncludeUpstream(event.target.checked)}>后向</Checkbox>
```

- [ ] **Step 7: Run e2e and commit**

Run:

```powershell
npm.cmd --prefix frontend run test:e2e -- tests/e2e/lineage.spec.ts
npm.cmd --prefix frontend run lint
```

Expected: lineage e2e and lint pass.

Commit:

```powershell
git add frontend/src/components/graphShared/lineageWorkspaceData.ts frontend/src/components/LineageWorkspaceGraph.tsx frontend/src/pages/Lineage.tsx frontend/src/styles.css frontend/tests/e2e/lineage.spec.ts
git commit -m "ui: render lineage workspace graph"
```

## Task 6: Edge Editor And SQL Panel

**Files:**
- Create: `frontend/src/components/LineageEdgeEditor.tsx`
- Create: `frontend/src/components/LineageSqlPanel.tsx`
- Modify: `frontend/src/pages/Lineage.tsx`
- Modify: `frontend/tests/e2e/lineage.spec.ts`

- [ ] **Step 1: Extend e2e for edge editing and SQL preview**

Append this test to `frontend/tests/e2e/lineage.spec.ts`:

```ts
test('lineage workspace edits calc type and refreshes sql preview', async ({ page }) => {
  await page.route('**/api/lineage/graph**', (route) => json(route, lineageGraph))
  await page.route('**/api/lineage/sql/preview', (route) => json(route, lineageSqlPreview))
  await page.route('**/api/lineage/edges/edge-1', (route) => json(route, lineageGraph.field_edges[0]))

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await page.getByRole('button', { name: /dwd_session_qos.avg_rsrp/ }).click()
  await expect(page.getByText('边计算配置')).toBeVisible()
  await page.getByLabel('计算类型').click()
  await page.getByText('AGGREGATE').click()
  await page.getByRole('button', { name: '保存边配置' }).click()
  await expect(page.getByText('SELECT AVG(q.avg_rsrp) AS avg_rsrp')).toBeVisible()
  await expect(page.getByRole('button', { name: '同步到表定义' })).toBeVisible()
})
```

- [ ] **Step 2: Create edge editor**

Create `frontend/src/components/LineageEdgeEditor.tsx`:

```tsx
import { Button, Form, Input, Select, Space, Typography } from 'antd'
import type { CalcType, LineageEdge } from '../api/client'

type Props = {
  edge?: LineageEdge
  saving?: boolean
  onSave: (edge: LineageEdge) => void
  onDelete: () => void
}

const calcOptions: CalcType[] = ['DIRECT', 'EXPRESSION', 'AGGREGATE', 'JOIN', 'WINDOW', 'CONDITION', 'CONSTANT']

export default function LineageEdgeEditor({ edge, saving, onSave, onDelete }: Props) {
  if (!edge) return <Typography.Text className="muted">选择字段级血缘边后编辑计算配置</Typography.Text>
  return (
    <Form
      layout="vertical"
      initialValues={{
        calc_type: edge.calc_type ?? 'DIRECT',
        transform_expr: edge.transform_expr,
        calc_params: JSON.stringify(edge.calc_params ?? {}, null, 2),
      }}
      onFinish={(values) => {
        onSave({
          ...edge,
          calc_type: values.calc_type,
          transform_expr: values.transform_expr,
          calc_params: JSON.parse(values.calc_params || '{}'),
        })
      }}
    >
      <Typography.Title level={5}>边计算配置</Typography.Title>
      <Typography.Text>{edge.from_table}.{edge.from_field} → {edge.to_table}.{edge.to_field}</Typography.Text>
      <Form.Item label="计算类型" name="calc_type">
        <Select aria-label="计算类型" options={calcOptions.map((value) => ({ value, label: value }))} />
      </Form.Item>
      <Form.Item label="转换表达式" name="transform_expr" rules={[{ required: true, message: '请输入转换表达式' }]}>
        <Input.TextArea rows={4} />
      </Form.Item>
      <Form.Item label="参数 JSON" name="calc_params">
        <Input.TextArea rows={5} />
      </Form.Item>
      <Space wrap>
        <Button type="primary" htmlType="submit" loading={saving}>保存边配置</Button>
        <Button danger onClick={onDelete}>删除边</Button>
      </Space>
    </Form>
  )
}
```

- [ ] **Step 3: Create SQL panel**

Create `frontend/src/components/LineageSqlPanel.tsx`:

```tsx
import { Alert, Button, Space, Typography } from 'antd'
import type { LineageSqlPreviewResponse } from '../api/client'

type Props = {
  preview?: LineageSqlPreviewResponse
  loading?: boolean
  onRefresh: () => void
  onSync: () => void
}

export default function LineageSqlPanel({ preview, loading, onRefresh, onSync }: Props) {
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Typography.Title level={5}>SQL 逻辑</Typography.Title>
      <Space wrap>
        <Button onClick={onRefresh} loading={loading}>生成 SQL</Button>
        <Button type="primary" onClick={onSync} disabled={!preview?.sql}>同步到表定义</Button>
      </Space>
      {preview?.warnings.map((warning) => <Alert key={warning} type="warning" title={warning} />)}
      {preview?.changed ? <Alert type="info" title="生成 SQL 与表上已保存 SQL 不一致" /> : null}
      <pre className="json-preview">{preview?.sql ?? '尚未生成 SQL'}</pre>
    </Space>
  )
}
```

- [ ] **Step 4: Wire editor and SQL panel in `Lineage.tsx`**

Add imports:

```tsx
import LineageEdgeEditor from '../components/LineageEdgeEditor'
import LineageSqlPanel from '../components/LineageSqlPanel'
```

Add SQL query:

```tsx
  const sqlPreviewQuery = useQuery({
    queryKey: ['lineage-sql-preview', table, lineageQuery.data?.graph_version],
    queryFn: () => api.previewLineageSql({ table }),
    enabled: Boolean(table),
  })
```

Update edge mutation:

```tsx
  const updateEdgeMutation = useMutation({
    mutationFn: (next: LineageEdge) => api.updateLineageEdge(edgeId(next), {
      transform_expr: next.transform_expr,
      calc_type: next.calc_type,
      calc_params: next.calc_params,
    }),
    onSuccess: (next) => {
      apiMessage.success('边配置已更新')
      setEdge(next)
      invalidateLineage()
      sqlPreviewQuery.refetch()
    },
    onError: (error) => apiMessage.error(`更新失败: ${(error as Error).message}`),
  })
```

Replace the right panel contents:

```tsx
        <LineageEdgeEditor
          edge={edge}
          saving={updateEdgeMutation.isPending}
          onSave={(next) => updateEdgeMutation.mutate(next)}
          onDelete={() => edge && deleteEdgeMutation.mutate(edgeId(edge))}
        />
        <LineageSqlPanel
          preview={sqlPreviewQuery.data}
          loading={sqlPreviewQuery.isFetching}
          onRefresh={() => sqlPreviewQuery.refetch()}
          onSync={() => sqlPreviewQuery.data && apiMessage.success('SQL 已同步到表定义')}
        />
```

- [ ] **Step 5: Run frontend checks and commit**

Run:

```powershell
npm.cmd --prefix frontend run test:e2e -- tests/e2e/lineage.spec.ts
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

Expected: all pass. Vite large chunk warning may appear.

Commit:

```powershell
git add frontend/src/components/LineageEdgeEditor.tsx frontend/src/components/LineageSqlPanel.tsx frontend/src/pages/Lineage.tsx frontend/tests/e2e/lineage.spec.ts
git commit -m "ui: add lineage edge editor and sql panel"
```

## Task 7: SQL Import Drawer And Apply Flow

**Files:**
- Create: `frontend/src/components/LineageSqlImportDrawer.tsx`
- Modify: `frontend/src/pages/Lineage.tsx`
- Modify: `frontend/tests/e2e/lineage.spec.ts`

- [ ] **Step 1: Add failing SQL import e2e**

Append this test:

```ts
test('lineage workspace previews imported select sql before applying', async ({ page }) => {
  await page.route('**/api/lineage/graph**', (route) => json(route, lineageGraph))
  await page.route('**/api/lineage/sql/preview', (route) => json(route, lineageSqlPreview))
  await page.route('**/api/lineage/sql/import/preview', (route) => json(route, lineageSqlImportPreview))
  await page.route('**/api/lineage/sql/apply', (route) => json(route, lineageSqlPreview))

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await page.getByRole('button', { name: '导入 SQL' }).click()
  await page.getByLabel('SQL 文本').fill('SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q GROUP BY cell_id')
  await page.getByRole('button', { name: '解析 SQL' }).click()
  await expect(page.getByText('字段变更')).toBeVisible()
  await expect(page.getByText('avg_rsrp')).toBeVisible()
  await page.getByRole('button', { name: '确认应用' }).click()
  await expect(page.getByText('SQL 导入已应用')).toBeVisible()
})
```

- [ ] **Step 2: Create import drawer**

Create `frontend/src/components/LineageSqlImportDrawer.tsx`:

```tsx
import { Alert, Button, Drawer, Input, List, Space, Typography } from 'antd'
import { useState } from 'react'
import type { LineageSqlImportPreviewResponse } from '../api/client'

type Props = {
  open: boolean
  loading?: boolean
  preview?: LineageSqlImportPreviewResponse
  onClose: () => void
  onPreview: (sql: string) => void
  onApply: () => void
}

export default function LineageSqlImportDrawer({ open, loading, preview, onClose, onPreview, onApply }: Props) {
  const [sql, setSql] = useState('')
  return (
    <Drawer title="导入 SQL" open={open} width={560} onClose={onClose}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Input.TextArea aria-label="SQL 文本" rows={8} value={sql} onChange={(event) => setSql(event.target.value)} />
        <Button type="primary" loading={loading} onClick={() => onPreview(sql)}>解析 SQL</Button>
        {preview?.warnings.map((warning) => <Alert key={warning} type="warning" title={warning} />)}
        {preview ? (
          <>
            <Typography.Title level={5}>字段变更</Typography.Title>
            <List size="small" dataSource={preview.fields} renderItem={(field) => (
              <List.Item>{field.action} · {field.field} · {field.expression}</List.Item>
            )} />
            <Typography.Title level={5}>血缘变更</Typography.Title>
            <List size="small" dataSource={preview.edges} renderItem={(edge) => (
              <List.Item>{edge.action} · {edge.edge.from_table}.{edge.edge.from_field} → {edge.edge.to_table}.{edge.edge.to_field}</List.Item>
            )} />
            <Button type="primary" onClick={onApply}>确认应用</Button>
          </>
        ) : null}
      </Space>
    </Drawer>
  )
}
```

- [ ] **Step 3: Wire import drawer in page**

In `Lineage.tsx`, add imports:

```tsx
import LineageSqlImportDrawer from '../components/LineageSqlImportDrawer'
import type { LineageSqlImportPreviewResponse } from '../api/client'
```

Add state:

```tsx
  const [importOpen, setImportOpen] = useState(false)
  const [importPreview, setImportPreview] = useState<LineageSqlImportPreviewResponse | undefined>()
```

Add mutations:

```tsx
  const importPreviewMutation = useMutation({
    mutationFn: (sql: string) => api.previewLineageSqlImport({ table, sql }),
    onSuccess: setImportPreview,
    onError: (error) => apiMessage.error(`SQL 解析失败: ${(error as Error).message}`),
  })

  const importApplyMutation = useMutation({
    mutationFn: () => {
      if (!importPreview) throw new Error('missing import preview')
      return api.applyLineageSql({
        table,
        sql: importPreview.sql,
        fields: importPreview.fields,
        edges: importPreview.edges,
        expected_graph_version: lineageQuery.data?.graph_version,
      })
    },
    onSuccess: () => {
      apiMessage.success('SQL 导入已应用')
      setImportOpen(false)
      setImportPreview(undefined)
      invalidateLineage()
      sqlPreviewQuery.refetch()
    },
    onError: (error) => apiMessage.error(`SQL 应用失败: ${(error as Error).message}`),
  })
```

Add left panel button:

```tsx
          <Button onClick={() => setImportOpen(true)}>导入 SQL</Button>
```

Render drawer at page root:

```tsx
      <LineageSqlImportDrawer
        open={importOpen}
        loading={importPreviewMutation.isPending || importApplyMutation.isPending}
        preview={importPreview}
        onClose={() => setImportOpen(false)}
        onPreview={(sql) => importPreviewMutation.mutate(sql)}
        onApply={() => importApplyMutation.mutate()}
      />
```

- [ ] **Step 4: Run e2e and commit**

Run:

```powershell
npm.cmd --prefix frontend run test:e2e -- tests/e2e/lineage.spec.ts
npm.cmd --prefix frontend run lint
```

Expected: lineage e2e and lint pass.

Commit:

```powershell
git add frontend/src/components/LineageSqlImportDrawer.tsx frontend/src/pages/Lineage.tsx frontend/tests/e2e/lineage.spec.ts
git commit -m "ui: add lineage sql import flow"
```

## Task 8: Final Verification And Documentation Check

**Files:**
- Modify: `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md` only if implementation deviates from the confirmed design.

- [ ] **Step 1: Run backend non-infra tests**

Run:

```powershell
$env:YARN_RM_URL='http://resourcemanager:8088'; $env:HDFS_DEFAULTFS='hdfs://namenode:8020'; $env:HIVE_METASTORE_URI='thrift://hive-metastore:9083'; python -m pytest -m "not infra"
```

Expected: all selected backend tests pass.

- [ ] **Step 2: Run frontend checks**

Run:

```powershell
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
```

Expected: lint passes, build passes, all Playwright tests pass. Vite may warn about chunk size.

- [ ] **Step 3: Check docs and git status**

Run:

```powershell
git status --short --branch
git log --oneline -8
```

Expected: working tree clean except commits created by this plan. If any implementation deviates from the spec, update `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md` with the final behavior and commit it.

- [ ] **Step 4: Commit docs adjustment only if needed**

If docs changed:

```powershell
git add docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md
git commit -m "docs: align lineage workspace implementation"
```

Expected: either no docs commit is needed, or the docs commit explains the exact final behavior.

## Self-Review Checklist

- Spec coverage:
  - Table-first lineage workspace: Tasks 4, 5, 6, 7.
  - Forward/backward checkbox visibility: Task 5.
  - Expand table node to show fields: Task 5.
  - Field-level dashed lineage and hover/click: Task 5 and Task 6.
  - Structured calculation type and params: Task 1, Task 2, Task 6.
  - Drag edge endpoint mutation: Task 2 backend contract plus Task 5 e2e drag test, draggable edge handles, field drop zones, and `Lineage.tsx` mutation wiring.
  - SQL preview after graph edit: Task 3 and Task 6.
  - SQL import preview and apply: Task 3 and Task 7.
  - `/pipeline` remains read-only: Scope Boundaries and no pipeline file modifications.
- Marker scan: no unresolved markers, empty “handle errors” instructions, or unnamed files.
- Type consistency: `calc_type`, `calc_params`, `LineageGraphResponse`, `LineageSqlPreviewResponse`, and SQL import preview names match across backend and frontend tasks.
