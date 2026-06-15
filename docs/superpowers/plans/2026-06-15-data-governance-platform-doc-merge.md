# Data Governance Platform Document Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new unified data governance platform specification set that merges the May wireless RNO semantic data service design with the June Spring Boot/GaussDB governance design without moving or deleting historical documents.

**Architecture:** Add a new document set under `docs/superpowers/specs/data-governance-platform/`. Preserve May's RNO domain, Agent, sandbox, UI, and acceptance details while adopting June's target architecture: Spring Boot governance service, GaussDB metadata store, `/rest/oss/inner/modelengineservice/v1` APIs, shared infrastructure, and AntV X6 target canvases.

**Tech Stack:** Markdown documentation, existing May and June design documents, repository AGENTS.md infrastructure constraints.

---

### Task 1: Create Unified Document Skeleton

**Files:**
- Create: `docs/superpowers/specs/data-governance-platform/index.md`
- Create: `docs/superpowers/specs/data-governance-platform/merge-principles-and-conflicts.md`
- Create: `docs/superpowers/specs/data-governance-platform/product-scope-and-capabilities.md`
- Create: `docs/superpowers/specs/data-governance-platform/rno-domain-model.md`
- Create: `docs/superpowers/specs/data-governance-platform/metadata-and-lineage-model.md`
- Create: `docs/superpowers/specs/data-governance-platform/governance-data-model.md`
- Create: `docs/superpowers/specs/data-governance-platform/api-contracts.md`
- Create: `docs/superpowers/specs/data-governance-platform/runtime-and-infra.md`
- Create: `docs/superpowers/specs/data-governance-platform/agent-search-and-sandbox.md`
- Create: `docs/superpowers/specs/data-governance-platform/ui-and-x6-target-design.md`
- Create: `docs/superpowers/specs/data-governance-platform/implementation-roadmap.md`
- Create: `docs/superpowers/specs/data-governance-platform/acceptance-suite.md`
- Create: `docs/superpowers/specs/data-governance-platform/source-coverage-map.md`

- [ ] **Step 1: Create the document set with the approved structure**

Use the paths above. Keep the two historical source documents and `docs/superpowers/specs/data-governance/` unchanged.

- [ ] **Step 2: Write the index and conflict policy first**

`index.md` must explain the target-state document set and link every child document. `merge-principles-and-conflicts.md` must explicitly resolve FastAPI vs Spring Boot, Neo4j vs GaussDB, G6 vs X6, local infrastructure vs `../shared-data-infra`, and `/api/...` vs `/rest/oss/inner/modelengineservice/v1`.

- [ ] **Step 3: Verify no historical file moved**

Run:

```powershell
Test-Path docs\superpowers\specs\2026-05-13-wireless-rno-data-service-design.md
Test-Path docs\superpowers\specs\2026-06-10-data-product-governance-design.md
Test-Path docs\superpowers\specs\data-governance
```

Expected: all three checks return `True`.

### Task 2: Preserve May Document Detail in Target Form

**Files:**
- Modify: `docs/superpowers/specs/data-governance-platform/product-scope-and-capabilities.md`
- Modify: `docs/superpowers/specs/data-governance-platform/rno-domain-model.md`
- Modify: `docs/superpowers/specs/data-governance-platform/metadata-and-lineage-model.md`
- Modify: `docs/superpowers/specs/data-governance-platform/agent-search-and-sandbox.md`
- Modify: `docs/superpowers/specs/data-governance-platform/ui-and-x6-target-design.md`
- Modify: `docs/superpowers/specs/data-governance-platform/acceptance-suite.md`

- [ ] **Step 1: Port the May function tree**

Preserve the complete user-facing capability tree: infrastructure, `/metadata`, `/metadata/lineage`, `/chat`, `/pipeline`, `/schema-evolution`, sandbox, and `/health`.

- [ ] **Step 2: Port RNO metadata and lineage detail**

Preserve the L1-ODS through L5-EVAL layer model, the 10 sample tables, core fields, upstream dependencies, YAML metadata replica format, metadata evolution strategy, and field-level lineage examples. Rewrite target persistence from Neo4j to GaussDB.

- [ ] **Step 3: Port Agent, search, benchmark, and sandbox detail**

Preserve LangGraph nodes, Agent State, Agent tools, DeepSeek integration, retry model, BM25 plus dense plus RRF semantic search, benchmark dataset and targets, sandbox templates, YARN submission, dry-run result, and resource limits.

- [ ] **Step 4: Port UI detail with X6 target semantics**

Preserve page layouts, forms, drawers, Monaco editors, context menus, drag-to-create lineage, chat context injection, dry-run previews, gap completion cards, pipeline forward/reverse views, and schema-evolution diff views. Replace target canvas implementation with AntV X6 and label G6 only as a migration source.

### Task 3: Preserve June Governance Detail in Target Form

**Files:**
- Modify: `docs/superpowers/specs/data-governance-platform/governance-data-model.md`
- Modify: `docs/superpowers/specs/data-governance-platform/api-contracts.md`
- Modify: `docs/superpowers/specs/data-governance-platform/runtime-and-infra.md`
- Modify: `docs/superpowers/specs/data-governance-platform/implementation-roadmap.md`
- Modify: `docs/superpowers/specs/data-governance-platform/acceptance-suite.md`

- [ ] **Step 1: Port GaussDB table model**

Preserve table-level fields for metadata, metadata_field, metadata_binding, lineage_edge, consumer, subscription, query_record, consumer_job, metadata_event, subscription_notification, and drift_record.

- [ ] **Step 2: Port formal API contracts**

Preserve the `/rest/oss/inner/modelengineservice/v1` prefix, metadata register/PATCH/DELETE, metadata list/detail/lineage, apiquery, sqlquery, and subscriptions APIs, including parameter names, request examples, response structure, validation rules, and runtime semantics.

- [ ] **Step 3: Port runtime and infrastructure behavior**

Preserve startup snapshot semantics, runtime mutation semantics, query audit, subscription notification, Kafka listener behavior, drift rules, StarRocks/Iceberg physical checks, and shared infrastructure constraints.

### Task 4: Add Coverage Map and Self-Review

**Files:**
- Modify: `docs/superpowers/specs/data-governance-platform/source-coverage-map.md`
- Read: `docs/superpowers/specs/TEMP-2026-06-14-doc-rewrite-requirements.md`

- [ ] **Step 1: Map every major May and June source section**

Add a table with source section, new document, preservation notes, and target-state rewrite notes.

- [ ] **Step 2: Run content checks**

Run:

```powershell
rg -n "modelingine(service)?" docs\superpowers\specs\data-governance-platform
rg -n "旧主库误写|旧画布误写|旧基础设施启动命令" docs\superpowers\specs\data-governance-platform
rg -n "/rest/oss/inner/modelengineservice/v1|AntV X6|GaussDB|shared-data-infra" docs\superpowers\specs\data-governance-platform
```

Expected: first command has no target-state violations; second command returns target-state references.

- [ ] **Step 3: Run file size and source preservation checks**

Run:

```powershell
Get-ChildItem docs\superpowers\specs\data-governance-platform -File | Select-Object Name,Length
git status --short
```

Expected: unified document set is materially larger than a summary-only rewrite, and git status shows only new document files plus the pre-existing untracked temporary requirements file.

### Task 5: Reorganize by First-Level Feature and Restore Graph-Default Persistence

**Files:**
- Delete superseded unnumbered files under `docs/superpowers/specs/data-governance-platform/`.
- Create numbered files:
  - `00-merge-principles-and-architecture-decisions.md`
  - `01-infrastructure-and-application-runtime.md`
  - `02-metadata-management.md`
  - `03-lineage-graph.md`
  - `04-natural-language-chat.md`
  - `05-pipeline-visualization.md`
  - `06-schema-evolution-history.md`
  - `07-sandbox-and-dry-run.md`
  - `08-subscription-query-notification.md`
  - `09-domain-model-and-samples.md`
  - `10-data-model-and-persistence.md`
  - `11-api-contracts.md`
  - `12-implementation-roadmap.md`
  - `13-acceptance-suite.md`
  - `14-source-coverage-map.md`
- Modify: `docs/superpowers/specs/data-governance-platform/index.md`

- [ ] **Step 1: Make graph database the default persistence**

Replace target-state wording that says GaussDB is the primary metadata store. The new target is graph database by default, with GaussDB supported through a persistence adapter. Preserve the original graph persistence model and keep GaussDB as a compatible relational implementation.

- [ ] **Step 2: Split first-level features into numbered documents**

Create one numbered document for each first-level feature from the approved capability tree. Each second-level feature must contain these subheadings, even when the content is not applicable:

```markdown
### 功能描述
### 用例
### 主要流程（PlantUML）
### 逻辑图（PlantUML）
### 对外接口
### UI 操作流程
### 数据模型
```

- [ ] **Step 3: Define internal Agent and sandbox APIs in the SPEC**

Add platform-internal Agent APIs in `04-natural-language-chat.md` and platform-internal sandbox APIs in `07-sandbox-and-dry-run.md`. Keep formal governance APIs in `11-api-contracts.md`.

- [ ] **Step 4: Verify reorganization**

Run:

```powershell
Get-ChildItem docs\superpowers\specs\data-governance-platform -File | Sort-Object Name | Select-Object Name,Length
rg -n "旧主库误写|旧图数据库误写|旧画布误写|modelingineservice|TODO|TBD|待定" docs\superpowers\specs\data-governance-platform
rg -n "图数据库默认|GaussDB 兼容|/api/agent|/api/sandbox|## 8.9 drift 分析|### 主要流程（PlantUML）" docs\superpowers\specs\data-governance-platform
```

Expected: numbered files exist, old target-state conflicts are absent, and graph-default/internal API/template markers are present.
