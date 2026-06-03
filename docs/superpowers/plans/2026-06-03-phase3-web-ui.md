# Phase 3 Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 3 React UI and the backend endpoints the UI needs for metadata browsing, lineage, chat, pipeline visualization, YAML preview/export, health, and schema evolution.

**Architecture:** Keep Neo4j/FastAPI as the runtime source of truth and add thin API endpoints for table-level pipeline and YAML read/export concerns. Add a new Vite React app under `frontend/` with route-level pages, shared API client, graph components, and focused UI modules.

**Tech Stack:** React 18, TypeScript, Vite, Ant Design, AntV G6, React Query, Zustand, Monaco Editor, FastAPI, pytest.

---

## Plan/Spec Review

The repository did not contain a Phase 3 plan before this file. Existing plans only cover Phase 1 and Phase 2.

Spec-aligned Phase 3 requirements found in `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md`:

- Frontend stack: React 18 + TypeScript + Vite, Ant Design, AntV G6, Monaco, React Query + Zustand.
- Routes: `/metadata`, `/metadata/lineage`, `/chat`, `/pipeline`, `/schema-evolution`, `/health`.
- API endpoints: existing `/api/tables`, `/api/fields`, `/api/lineage`, `/api/chat/*`, `/api/schema/*`, `/api/search`, `/api/health`; missing `/api/pipeline`, `/api/yaml/export`, `/api/yaml/preview/:table`, and YAML diff endpoint.
- Acceptance cases P3-1 through P3-22 cover metadata browsing/maintenance, lineage graph interactions, chat streaming, pipeline visualization, schema evolution timeline, and cross-page context injection.

Current implementation gaps:

- No `frontend/` app exists.
- No `app-compose.yml` wiring for a React dev server exists.
- No `/api/pipeline` route exists for table-level DAG aggregation.
- No `/api/yaml/export` or `/api/yaml/preview/{table}` route exists.
- No `/api/schema/evolution/yaml-diff` route exists.
- Chat start/message APIs do not persist URL context into session state.
- `/api/chat/{session_id}/result` returns `last_result`, but the streaming runner does not currently update it.
- Direct lineage-edge CRUD is not exposed as a backend API; field updates can carry upstream refs, so graph editing should initially route through field edit APIs.

## File Structure

- Create `backend/api/pipeline.py`: table-level DAG response for `/api/pipeline`.
- Create `backend/api/yaml_metadata.py`: YAML preview/export response helpers.
- Modify `backend/api/schema_evolution.py`: add YAML diff route.
- Modify `backend/api/chat.py`: accept and persist context metadata, update last result during stream completion.
- Modify `backend/main.py`: include new routers.
- Create `tests/api/test_pipeline.py`: API-level tests for pipeline aggregation.
- Create `tests/api/test_yaml_metadata.py`: API-level tests for preview/export path handling.
- Create `tests/api/test_chat_context.py`: verifies context persistence.
- Create `frontend/`: Vite React app with route pages and shared modules.

## Tasks

### Task 1: Backend Phase 3 Support APIs

**Files:**
- Create: `backend/api/pipeline.py`
- Create: `backend/api/yaml_metadata.py`
- Modify: `backend/api/schema_evolution.py`
- Modify: `backend/api/chat.py`
- Modify: `backend/main.py`
- Test: `tests/api/test_pipeline.py`
- Test: `tests/api/test_yaml_metadata.py`
- Test: `tests/api/test_chat_context.py`

- [x] Add failing tests for pipeline, YAML preview/export, schema YAML diff, and chat context.
- [x] Implement `/api/pipeline?mode=forward|reverse&table=...` by aggregating field lineage into table nodes and weighted edges.
- [x] Implement `/api/yaml/preview/{table}` and `/api/yaml/export?table=...`.
- [x] Implement `/api/schema/evolution/yaml-diff?table_name=...&version=...`.
- [x] Persist chat context from `POST /api/chat/start` and include it in the initial agent state.
- [x] Run `python -m pytest tests/api/test_pipeline.py tests/api/test_yaml_metadata.py tests/api/test_chat_context.py -v`.

### Task 2: Frontend Scaffold and App Shell

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/store/ui.ts`

- [x] Scaffold React 18 + TypeScript + Vite.
- [x] Add Ant Design theme and route shell.
- [x] Add routes for `/metadata`, `/metadata/lineage`, `/chat`, `/pipeline`, `/schema-evolution`, `/health`.
- [x] Run `npm.cmd --prefix frontend run build`.

### Task 3: Metadata, Health, and Schema Evolution Pages

**Files:**
- Create: `frontend/src/pages/Metadata.tsx`
- Create: `frontend/src/pages/Health.tsx`
- Create: `frontend/src/pages/SchemaEvolution.tsx`
- Create: `frontend/src/components/DiffPanel.tsx`
- Create: `frontend/src/components/EvolutionTimeline.tsx`
- Create: `frontend/src/components/HealthPanel.tsx`

- [x] Implement table list filtering by layer and search.
- [x] Implement table detail with fields, upstream tooltip, YAML preview, lineage link, and schema evolution link.
- [x] Implement health cards with 30s refresh.
- [x] Implement schema evolution timeline and YAML diff modal.
- [ ] Verify P3-1, P3-2, P3-22 manually against running app.

### Task 4: Lineage and Pipeline Graph Pages

**Files:**
- Create: `frontend/src/pages/Lineage.tsx`
- Create: `frontend/src/pages/Pipeline.tsx`
- Create: `frontend/src/components/LineageGraph.tsx`
- Create: `frontend/src/components/PipelineDAG.tsx`
- Create: `frontend/src/components/graphShared/graphData.ts`
- Create: `frontend/src/components/graphShared/palette.ts`

- [x] Render field-level lineage using `/api/lineage`.
- [x] Render table-level pipeline using `/api/pipeline`.
- [x] Add graph direction toggle, depth slider, selected node/edge detail, zoom/drag/minimap behaviors where supported.
- [x] Add graph-to-chat links with URL context parameters.
- [ ] Verify P3-6, P3-7, P3-10, P3-18, P3-20 manually.

### Task 5: Chat Page and Agent Result Cards

**Files:**
- Create: `frontend/src/pages/Chat.tsx`
- Create: `frontend/src/components/ChatStream.tsx`
- Create: `frontend/src/components/CodeCard.tsx`
- Create: `frontend/src/components/DryRunPreview.tsx`
- Create: `frontend/src/components/ConstraintSlider.tsx`

- [x] Start a chat session with URL context payload.
- [x] Stream `/api/chat/message` with fetch + ReadableStream.
- [x] Render intent badges, presenter messages, code cards, dry-run previews, gap proposal cards, schema diff panels, and reverse-synthesis constraints when present.
- [ ] Verify P3-11 through P3-17 against backend events.

### Task 6: Verification

**Files:**
- Modify: frontend and backend files touched above.

- [x] Run backend targeted tests.
- [x] Run `python -m pytest -m "not infra"`.
- [x] Run `npm.cmd --prefix frontend run build`.
- [ ] Start backend and frontend dev server.
- [ ] Open the UI in the in-app browser and verify desktop/mobile layouts for `/metadata`, `/metadata/lineage`, `/chat`, `/pipeline`, `/schema-evolution`, and `/health`.
