# Metadata Category Tag Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add editable source-table category and tag management to `/metadata`, initialize the confirmed taxonomy into Neo4j, and classify all existing seed tables into that taxonomy.

**Architecture:** Keep Neo4j as the single persistence boundary for metadata, adding `MetaCategory`, `MetaTagGroup`, and `MetaTag` nodes plus `IN_CATEGORY` and `TAGGED_WITH` relationships from `Table`. Backend seed constants define the default taxonomy and table mappings; service/API methods expose tree, tag, filter, and edit operations. The frontend keeps the existing Ant Design metadata page but replaces the left flat layer filter with a category tree plus tag filters and management drawer.

**Tech Stack:** FastAPI, Pydantic v2, Neo4j Cypher, pytest, React 18, TypeScript, Ant Design, React Query, Playwright.

---

## References

- Design spec: `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md`
  - Section `2.2.1 示例表默认分类与标签纳管`
  - Neo4j schema additions around `MetaCategory`, `MetaTagGroup`, `MetaTag`, `IN_CATEGORY`, `TAGGED_WITH`
  - `/metadata` section `分类与标签导航管理`
  - API table entries for `/api/metadata/categories/*`, `/api/metadata/tags/*`, and `/api/tables/:id/classification`
- Backend seed source: `backend/seed/tables.py`
- Neo4j schema init: `init-scripts/05_neo4j_init.py`
- Neo4j seed script: `init-scripts/06_neo4j_seed.py`
- Backend service/API: `backend/metadata/models.py`, `backend/metadata/service.py`, `backend/api/metadata.py`
- Frontend metadata page/API: `frontend/src/pages/Metadata.tsx`, `frontend/src/api/client.ts`
- Existing metadata e2e mocks: `frontend/tests/e2e/fixtures.ts`, `frontend/tests/e2e/metadata.spec.ts`

## Scope Boundaries

- Do not add Docker Compose services. This feature reuses the existing Neo4j service from `../shared-data-infra`.
- Do not change lineage graph persistence. Lineage pages may later consume category/tag fields from table summaries, but this plan only changes `/metadata`.
- Do not hard-delete categories or tags from the graph. Status changes use `active=false`.
- First version supports one table main category and multiple tags. The table may temporarily appear under virtual `uncategorized` only when historical data has no `IN_CATEGORY` relationship.
- Large root categories are protected. They can be renamed, sorted, and deactivated only through the same status API, but cannot be deleted or moved.
- Small categories can be created, renamed, moved under another root category, sorted, and deactivated.
- Tags are flat and may belong to a tag group. Tag groups are editable and sortable.

## File Structure

- Modify `backend/seed/tables.py`: add taxonomy constants, tag groups, and table classification mappings next to existing seed table definitions.
- Modify `tests/api/test_seed_data.py`: validate taxonomy constants, seed table classifications, and tag references.
- Modify `init-scripts/05_neo4j_init.py`: add constraints and indexes for categories, tag groups, tags, and change target fields.
- Modify `init-scripts/06_neo4j_seed.py`: seed taxonomy nodes/relationships and connect existing sample tables to their default category/tags.
- Modify `backend/metadata/models.py`: add Pydantic DTOs for categories, tags, table classification, and extend table responses with category/tag metadata.
- Modify `backend/metadata/service.py`: implement category/tag reads, edits, table filters, and table classification update with `Change` audit nodes.
- Modify `backend/api/metadata.py`: expose category/tag management endpoints and extended table filtering/query params.
- Create `tests/api/test_metadata_taxonomy_service.py`: service-level tests for classification reads/writes using Neo4j.
- Create `tests/api/test_metadata_taxonomy_api.py`: HTTP route tests with monkeypatched service methods, no infrastructure needed.
- Modify `frontend/src/api/client.ts`: add category/tag types and API client methods.
- Modify `frontend/tests/e2e/fixtures.ts`: extend mocked tables, categories, tags, and update endpoints.
- Modify `frontend/src/pages/Metadata.tsx`: wire taxonomy queries, filters, chips, table classification edit, and drawer entry points.
- Create `frontend/src/components/MetadataTaxonomyPanel.tsx`: left navigation tree, tag filters, and combined filter controls.
- Create `frontend/src/components/MetadataTaxonomyDrawer.tsx`: category/tag/tag-group management drawer.
- Modify `frontend/src/styles.css`: metadata taxonomy layout, tree list, chips, and drawer compact styles.
- Modify `frontend/tests/e2e/metadata.spec.ts`: cover category tree, tag filtering, management drawer, and table classification save.
- Modify `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md` only if implementation semantics diverge from the approved design.

## Task 1: Seed Taxonomy Constants And Tests

**Files:**
- Modify: `backend/seed/tables.py`
- Modify: `tests/api/test_seed_data.py`

- [ ] **Step 1: Add failing seed taxonomy tests**

Append these tests to `tests/api/test_seed_data.py`:

```python
from backend.seed.tables import (
    DEFAULT_CATEGORY_TREE,
    DEFAULT_TAG_GROUPS,
    TABLE_CLASSIFICATION,
)


def test_default_category_tree_matches_approved_design():
    tree = {root["name"]: [child["name"] for child in root["children"]] for root in DEFAULT_CATEGORY_TREE}
    assert tree == {
        "环境": ["地理", "场景", "天气", "机房"],
        "设备": ["前传", "时钟", "回传", "天馈", "电源", "射频", "BBU"],
        "网络": ["覆盖", "干扰", "话务", "容量", "速率", "时延", "质量", "接入", "保持", "移动", "丢包", "能耗"],
        "用户": ["标识信息", "终端信息", "套餐信息", "位置信息", "业务信息", "活动信息"],
        "业务": ["直播", "视频", "游戏", "网页", "扫码", "上传下载", "即时通信", "生产", "Mobile AI"],
        "源数据": ["话统", "CHR", "配置", "工参", "电子地图"],
    }


def test_table_classification_covers_all_seed_tables():
    table_names = {table["name"] for table in SEED_TABLES}
    assert set(TABLE_CLASSIFICATION) == table_names
    for table_name, classification in TABLE_CLASSIFICATION.items():
        assert classification["category_path"]
        assert len(classification["category_path"]) == 2, table_name
        assert classification["tags"], table_name


def test_table_classification_references_known_categories_and_tags():
    category_paths = {
        (root["name"], child["name"])
        for root in DEFAULT_CATEGORY_TREE
        for child in root["children"]
    }
    tag_names = {tag["name"] for group in DEFAULT_TAG_GROUPS for tag in group["tags"]}
    for classification in TABLE_CLASSIFICATION.values():
        assert tuple(classification["category_path"]) in category_paths
        assert set(classification["tags"]).issubset(tag_names)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/api/test_seed_data.py -q
```

Expected: fail with `ImportError` or `NameError` because `DEFAULT_CATEGORY_TREE`, `DEFAULT_TAG_GROUPS`, and `TABLE_CLASSIFICATION` do not exist.

- [ ] **Step 3: Add taxonomy constants**

In `backend/seed/tables.py`, after `LAYER_PRIORITY`, add:

```python
DEFAULT_CATEGORY_TREE: list[dict] = [
    {
        "code": "environment",
        "name": "环境",
        "children": [
            {"code": "environment.geo", "name": "地理"},
            {"code": "environment.scenario", "name": "场景"},
            {"code": "environment.weather", "name": "天气"},
            {"code": "environment.machine-room", "name": "机房"},
        ],
    },
    {
        "code": "equipment",
        "name": "设备",
        "children": [
            {"code": "equipment.fronthaul", "name": "前传"},
            {"code": "equipment.clock", "name": "时钟"},
            {"code": "equipment.backhaul", "name": "回传"},
            {"code": "equipment.antenna-feeder", "name": "天馈"},
            {"code": "equipment.power", "name": "电源"},
            {"code": "equipment.rf", "name": "射频"},
            {"code": "equipment.bbu", "name": "BBU"},
        ],
    },
    {
        "code": "network",
        "name": "网络",
        "children": [
            {"code": "network.coverage", "name": "覆盖"},
            {"code": "network.interference", "name": "干扰"},
            {"code": "network.traffic", "name": "话务"},
            {"code": "network.capacity", "name": "容量"},
            {"code": "network.rate", "name": "速率"},
            {"code": "network.latency", "name": "时延"},
            {"code": "network.quality", "name": "质量"},
            {"code": "network.access", "name": "接入"},
            {"code": "network.retain", "name": "保持"},
            {"code": "network.mobility", "name": "移动"},
            {"code": "network.packet-loss", "name": "丢包"},
            {"code": "network.energy", "name": "能耗"},
        ],
    },
    {
        "code": "user",
        "name": "用户",
        "children": [
            {"code": "user.identity", "name": "标识信息"},
            {"code": "user.terminal", "name": "终端信息"},
            {"code": "user.plan", "name": "套餐信息"},
            {"code": "user.location", "name": "位置信息"},
            {"code": "user.service", "name": "业务信息"},
            {"code": "user.activity", "name": "活动信息"},
        ],
    },
    {
        "code": "business",
        "name": "业务",
        "children": [
            {"code": "business.live", "name": "直播"},
            {"code": "business.video", "name": "视频"},
            {"code": "business.game", "name": "游戏"},
            {"code": "business.web", "name": "网页"},
            {"code": "business.scan", "name": "扫码"},
            {"code": "business.upload-download", "name": "上传下载"},
            {"code": "business.im", "name": "即时通信"},
            {"code": "business.production", "name": "生产"},
            {"code": "business.mobile-ai", "name": "Mobile AI"},
        ],
    },
    {
        "code": "source-data",
        "name": "源数据",
        "children": [
            {"code": "source-data.counter", "name": "话统"},
            {"code": "source-data.chr", "name": "CHR"},
            {"code": "source-data.config", "name": "配置"},
            {"code": "source-data.engineering", "name": "工参"},
            {"code": "source-data.map", "name": "电子地图"},
        ],
    },
]


DEFAULT_TAG_GROUPS: list[dict] = [
    {
        "code": "source",
        "name": "来源类型",
        "tags": ["话统", "CHR", "配置", "工参", "电子地图"],
    },
    {
        "code": "network-domain",
        "name": "网络域",
        "tags": ["覆盖", "干扰", "话务", "容量", "速率", "时延", "质量", "接入", "保持", "移动", "丢包", "能耗"],
    },
    {
        "code": "equipment-domain",
        "name": "设备域",
        "tags": ["前传", "时钟", "回传", "天馈", "电源", "射频", "BBU", "机房"],
    },
    {
        "code": "user-domain",
        "name": "用户域",
        "tags": ["标识信息", "终端信息", "套餐信息", "位置信息", "业务信息", "活动信息"],
    },
    {
        "code": "business-domain",
        "name": "业务域",
        "tags": ["直播", "视频", "游戏", "网页", "扫码", "上传下载", "即时通信", "生产", "Mobile AI"],
    },
]


TABLE_CLASSIFICATION: dict[str, dict] = {
    "ods_ue_signal": {
        "category_path": ["源数据", "CHR"],
        "tags": ["覆盖", "质量", "射频", "标识信息"],
    },
    "ods_gnb_alarm": {
        "category_path": ["源数据", "配置"],
        "tags": ["BBU", "电源", "机房", "质量"],
    },
    "dwd_session_qos": {
        "category_path": ["网络", "质量"],
        "tags": ["速率", "时延", "丢包", "保持", "标识信息"],
    },
    "dwd_ho_event": {
        "category_path": ["网络", "移动"],
        "tags": ["保持", "接入", "质量", "标识信息"],
    },
    "dws_cell_hourly": {
        "category_path": ["网络", "覆盖"],
        "tags": ["话务", "速率", "保持", "质量"],
    },
    "dws_area_traffic": {
        "category_path": ["网络", "话务"],
        "tags": ["容量", "速率", "时延", "活动信息"],
    },
    "ads_cell_profile": {
        "category_path": ["网络", "覆盖"],
        "tags": ["容量", "质量", "射频"],
    },
    "ads_neighbor_pair": {
        "category_path": ["网络", "移动"],
        "tags": ["保持", "质量", "工参"],
    },
    "eval_user_score": {
        "category_path": ["用户", "业务信息"],
        "tags": ["覆盖", "移动", "业务信息", "活动信息"],
    },
    "eval_net_health": {
        "category_path": ["网络", "质量"],
        "tags": ["覆盖", "话务", "机房", "业务信息"],
    },
}
```

- [ ] **Step 4: Run seed tests and commit**

Run:

```powershell
python -m pytest tests/api/test_seed_data.py -q
```

Expected: all tests in `test_seed_data.py` pass.

Commit:

```powershell
git add backend/seed/tables.py tests/api/test_seed_data.py
git commit -m "feat: define metadata taxonomy seed mappings"
```

## Task 2: Neo4j Schema And Seed Script

**Files:**
- Modify: `init-scripts/05_neo4j_init.py`
- Modify: `init-scripts/06_neo4j_seed.py`
- Create: `tests/api/test_metadata_taxonomy_seed_script.py`

- [ ] **Step 1: Add failing script-level tests**

Create `tests/api/test_metadata_taxonomy_seed_script.py`:

```python
from tests.api.init_scripts_import import load_script_module


def test_neo4j_init_contains_taxonomy_constraints():
    module = load_script_module("05_neo4j_init.py")
    statements = "\n".join(module.CONSTRAINTS + module.INDEXES)
    assert "MetaCategory" in statements
    assert "MetaTagGroup" in statements
    assert "MetaTag" in statements
    assert "category_code_unique" in statements
    assert "tag_code_unique" in statements


def test_seed_script_has_taxonomy_seed_function():
    module = load_script_module("06_neo4j_seed.py")
    assert hasattr(module, "seed_taxonomy")
    assert hasattr(module, "seed_table_classification")
```

Also create the shared loader helper `tests/api/init_scripts_import.py` if it does not exist:

```python
import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INIT_SCRIPT_DIR = REPO_ROOT / "init-scripts"


def load_script_module(filename: str):
    path = INIT_SCRIPT_DIR / filename
    module_name = filename.replace("-", "_").replace(".", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
python -m pytest tests/api/test_metadata_taxonomy_seed_script.py -q
```

Expected: fail because schema statements and seed functions are not present.

- [ ] **Step 3: Extend Neo4j schema init**

In `init-scripts/05_neo4j_init.py`, add these entries to `CONSTRAINTS`:

```python
    "CREATE CONSTRAINT category_id_unique IF NOT EXISTS FOR (c:MetaCategory) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT category_code_unique IF NOT EXISTS FOR (c:MetaCategory) REQUIRE c.code IS UNIQUE",
    "CREATE CONSTRAINT tag_group_id_unique IF NOT EXISTS FOR (g:MetaTagGroup) REQUIRE g.id IS UNIQUE",
    "CREATE CONSTRAINT tag_group_code_unique IF NOT EXISTS FOR (g:MetaTagGroup) REQUIRE g.code IS UNIQUE",
    "CREATE CONSTRAINT tag_id_unique IF NOT EXISTS FOR (tag:MetaTag) REQUIRE tag.id IS UNIQUE",
    "CREATE CONSTRAINT tag_code_unique IF NOT EXISTS FOR (tag:MetaTag) REQUIRE tag.code IS UNIQUE",
```

Add these entries to `INDEXES`:

```python
    "CREATE INDEX category_name_idx IF NOT EXISTS FOR (c:MetaCategory) ON (c.name)",
    "CREATE INDEX category_level_idx IF NOT EXISTS FOR (c:MetaCategory) ON (c.level)",
    "CREATE INDEX category_sort_idx IF NOT EXISTS FOR (c:MetaCategory) ON (c.sort_order)",
    "CREATE INDEX tag_name_idx IF NOT EXISTS FOR (tag:MetaTag) ON (tag.name)",
    "CREATE INDEX tag_sort_idx IF NOT EXISTS FOR (tag:MetaTag) ON (tag.sort_order)",
    "CREATE INDEX change_target_type_idx IF NOT EXISTS FOR (c:Change) ON (c.target_type)",
    "CREATE INDEX change_target_id_idx IF NOT EXISTS FOR (c:Change) ON (c.target_id)",
```

- [ ] **Step 4: Seed taxonomy and table classification**

Modify imports in `init-scripts/06_neo4j_seed.py`:

```python
from backend.seed.tables import (
    DEFAULT_CATEGORY_TREE,
    DEFAULT_TAG_GROUPS,
    LAYER_PRIORITY,
    SEED_LINEAGE,
    SEED_TABLES,
    TABLE_CLASSIFICATION,
)
```

Add these helpers above `seed_tables_and_fields()`:

```python
def _category_id(code: str) -> str:
    return f"category:{code}"


def _tag_group_id(code: str) -> str:
    return f"tag-group:{code}"


def _tag_code(name: str) -> str:
    return "tag:" + name.strip().lower().replace(" ", "-")


def _tag_id(name: str) -> str:
    return _tag_code(name)
```

Add taxonomy seed functions:

```python
def seed_taxonomy() -> tuple[int, int, int]:
    category_count = 0
    group_count = 0
    tag_count = 0

    for root_index, root in enumerate(DEFAULT_CATEGORY_TREE, start=1):
        root_id = _category_id(root["code"])
        run_query(
            """
            MERGE (root:MetaCategory {code: $code})
            ON CREATE SET root.id = $id,
                          root.created_at = datetime()
            SET root.name = $name,
                root.level = 1,
                root.sort_order = $sort_order,
                root.protected = true,
                root.active = true,
                root.updated_at = datetime()
            """,
            id=root_id,
            code=root["code"],
            name=root["name"],
            sort_order=root_index,
        )
        category_count += 1

        for child_index, child in enumerate(root["children"], start=1):
            child_id = _category_id(child["code"])
            run_query(
                """
                MATCH (root:MetaCategory {code: $root_code})
                MERGE (child:MetaCategory {code: $code})
                ON CREATE SET child.id = $id,
                              child.created_at = datetime()
                SET child.name = $name,
                    child.level = 2,
                    child.sort_order = $sort_order,
                    child.protected = false,
                    child.active = true,
                    child.updated_at = datetime()
                MERGE (root)-[:HAS_CHILD]->(child)
                """,
                root_code=root["code"],
                id=child_id,
                code=child["code"],
                name=child["name"],
                sort_order=child_index,
            )
            category_count += 1

    for group_index, group in enumerate(DEFAULT_TAG_GROUPS, start=1):
        group_id = _tag_group_id(group["code"])
        run_query(
            """
            MERGE (g:MetaTagGroup {code: $code})
            ON CREATE SET g.id = $id,
                          g.created_at = datetime()
            SET g.name = $name,
                g.sort_order = $sort_order,
                g.active = true,
                g.updated_at = datetime()
            """,
            id=group_id,
            code=group["code"],
            name=group["name"],
            sort_order=group_index,
        )
        group_count += 1

        for tag_index, tag_name in enumerate(group["tags"], start=1):
            tag_code = _tag_code(tag_name)
            run_query(
                """
                MATCH (g:MetaTagGroup {code: $group_code})
                MERGE (tag:MetaTag {code: $code})
                ON CREATE SET tag.id = $id,
                              tag.created_at = datetime()
                SET tag.name = $name,
                    tag.sort_order = $sort_order,
                    tag.active = true,
                    tag.updated_at = datetime()
                MERGE (g)-[:HAS_TAG]->(tag)
                """,
                group_code=group["code"],
                id=_tag_id(tag_name),
                code=tag_code,
                name=tag_name,
                sort_order=tag_index,
            )
            tag_count += 1

    return category_count, group_count, tag_count


def seed_table_classification() -> int:
    classified_count = 0
    for table_name, classification in TABLE_CLASSIFICATION.items():
        root_name, child_name = classification["category_path"]
        run_query(
            """
            MATCH (t:Table {name: $table})
            MATCH (:MetaCategory {name: $root_name})-[:HAS_CHILD]->(category:MetaCategory {name: $child_name})
            OPTIONAL MATCH (t)-[old:IN_CATEGORY]->(:MetaCategory)
            DELETE old
            MERGE (t)-[:IN_CATEGORY]->(category)
            """,
            table=table_name,
            root_name=root_name,
            child_name=child_name,
        )
        for tag_name in classification["tags"]:
            run_query(
                """
                MATCH (t:Table {name: $table})
                MATCH (tag:MetaTag {name: $tag_name})
                MERGE (t)-[:TAGGED_WITH]->(tag)
                """,
                table=table_name,
                tag_name=tag_name,
            )
        classified_count += 1
    return classified_count
```

Update `main()`:

```python
def main() -> int:
    category_count, group_count, tag_count = seed_taxonomy()
    t, f = seed_tables_and_fields()
    classified = seed_table_classification()
    e = seed_lineage()
    print(
        f"Seeded {category_count} categories, {group_count} tag groups, "
        f"{tag_count} tags, {t} tables, {f} fields, {classified} classifications, {e} lineage edges."
    )
    return 0 if (t == 10 and classified == 10 and 60 <= f <= 80) else 1
```

- [ ] **Step 5: Run non-infra script tests**

Run:

```powershell
python -m pytest tests/api/test_metadata_taxonomy_seed_script.py tests/api/test_seed_data.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Run Neo4j init config path if infra is available**

If shared Neo4j is running, run:

```powershell
python init-scripts/05_neo4j_init.py
python init-scripts/06_neo4j_seed.py
```

Expected: both scripts exit 0. The seed script prints `10 classifications`.

- [ ] **Step 7: Commit schema and seed script**

Commit:

```powershell
git add init-scripts/05_neo4j_init.py init-scripts/06_neo4j_seed.py tests/api/init_scripts_import.py tests/api/test_metadata_taxonomy_seed_script.py
git commit -m "feat: seed metadata taxonomy into neo4j"
```

## Task 3: Backend DTOs And Service Logic

**Files:**
- Modify: `backend/metadata/models.py`
- Modify: `backend/metadata/service.py`
- Create: `tests/api/test_metadata_taxonomy_service.py`

- [ ] **Step 1: Add failing service tests**

Create `tests/api/test_metadata_taxonomy_service.py`:

```python
import pytest

from backend.metadata.models import TableClassificationUpdateRequest
from backend.metadata.service import (
    CategoryNotFound,
    TableNotFound,
    TagNotFound,
    get_table_by_name,
    list_categories_tree,
    list_tables,
    list_tags,
    update_table_classification,
)


@pytest.mark.infra
def test_list_categories_tree_returns_network_children():
    tree = list_categories_tree()
    network = next(node for node in tree if node.name == "网络")
    assert network.protected is True
    assert [child.name for child in network.children] == [
        "覆盖", "干扰", "话务", "容量", "速率", "时延", "质量", "接入", "保持", "移动", "丢包", "能耗",
    ]
    coverage = next(child for child in network.children if child.name == "覆盖")
    assert coverage.table_count >= 2


@pytest.mark.infra
def test_list_tags_returns_grouped_tags():
    groups = list_tags()
    network = next(group for group in groups if group.code == "network-domain")
    assert {"覆盖", "质量", "移动"}.issubset({tag.name for tag in network.tags})


@pytest.mark.infra
def test_seed_table_has_category_and_tags():
    table = get_table_by_name("dws_cell_hourly")
    assert table.category is not None
    assert table.category.path == ["网络", "覆盖"]
    assert {"话务", "速率", "保持", "质量"}.issubset({tag.name for tag in table.tags})


@pytest.mark.infra
def test_list_tables_filters_by_category_and_tag():
    coverage_tables = list_tables(category_id="category:network.coverage", include_children=True)
    assert {"dws_cell_hourly", "ads_cell_profile"}.issubset({table.name for table in coverage_tables})

    quality_tables = list_tables(tag_ids=["tag:质量"], tag_match="any")
    assert {"dws_cell_hourly", "eval_net_health"}.issubset({table.name for table in quality_tables})

    quality_and_coverage = list_tables(tag_ids=["tag:质量", "tag:覆盖"], tag_match="all")
    assert "eval_net_health" in {table.name for table in quality_and_coverage}


@pytest.mark.infra
def test_update_table_classification_replaces_category_and_tags():
    table = get_table_by_name("ads_neighbor_pair")
    updated = update_table_classification(
        table.id,
        TableClassificationUpdateRequest(
            category_id="category:source-data.engineering",
            tag_ids=["tag:工参", "tag:保持"],
        ),
    )
    assert updated.category is not None
    assert updated.category.path == ["源数据", "工参"]
    assert {tag.name for tag in updated.tags} == {"工参", "保持"}

    update_table_classification(
        table.id,
        TableClassificationUpdateRequest(
            category_id="category:network.mobility",
            tag_ids=["tag:保持", "tag:质量", "tag:工参"],
        ),
    )


@pytest.mark.infra
def test_update_table_classification_validates_ids():
    table = get_table_by_name("dws_area_traffic")
    with pytest.raises(CategoryNotFound):
        update_table_classification(
            table.id,
            TableClassificationUpdateRequest(category_id="category:not-found", tag_ids=[]),
        )
    with pytest.raises(TagNotFound):
        update_table_classification(
            table.id,
            TableClassificationUpdateRequest(category_id="category:network.traffic", tag_ids=["tag:not-found"]),
        )
    with pytest.raises(TableNotFound):
        update_table_classification(
            "missing-table-id",
            TableClassificationUpdateRequest(category_id="category:network.traffic", tag_ids=[]),
        )
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/api/test_metadata_taxonomy_service.py -q
```

Expected: fail because DTOs, exceptions, and service functions do not exist.

- [ ] **Step 3: Add DTOs**

In `backend/metadata/models.py`, add these models after `UpdateTableRequest`:

```python
class CategoryRef(BaseModel):
    id: str
    code: str
    name: str
    path: list[str] = Field(default_factory=list)
    active: bool = True


class TagRef(BaseModel):
    id: str
    code: str
    name: str
    group_id: Optional[str] = None
    group_name: Optional[str] = None
    active: bool = True


class CategoryNodeResponse(BaseModel):
    id: str
    code: str
    name: str
    level: int
    sort_order: int
    protected: bool
    active: bool
    table_count: int = 0
    children: list["CategoryNodeResponse"] = Field(default_factory=list)


class TagResponse(BaseModel):
    id: str
    code: str
    name: str
    sort_order: int
    active: bool


class TagGroupResponse(BaseModel):
    id: str
    code: str
    name: str
    sort_order: int
    active: bool
    tags: list[TagResponse] = Field(default_factory=list)


class CreateCategoryRequest(BaseModel):
    parent_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=64)
    code: Optional[str] = Field(default=None, max_length=128)
    sort_order: int = 100


class UpdateCategoryRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    sort_order: Optional[int] = None


class MoveCategoryRequest(BaseModel):
    parent_id: str = Field(min_length=1)
    sort_order: int = 100


class StatusUpdateRequest(BaseModel):
    active: bool


class CreateTagGroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    code: Optional[str] = Field(default=None, max_length=128)
    sort_order: int = 100


class UpdateTagGroupRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    sort_order: Optional[int] = None
    active: Optional[bool] = None


class CreateTagRequest(BaseModel):
    group_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=64)
    code: Optional[str] = Field(default=None, max_length=128)
    sort_order: int = 100


class UpdateTagRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    group_id: Optional[str] = None
    sort_order: Optional[int] = None


class TableClassificationUpdateRequest(BaseModel):
    category_id: str = Field(min_length=1)
    tag_ids: list[str] = Field(default_factory=list)
```

Then extend `TableResponse` with:

```python
    category: Optional[CategoryRef] = None
    tags: list[TagRef] = Field(default_factory=list)
```

Extend `TableSummary` with:

```python
    category: Optional[CategoryRef] = None
    tags: list[TagRef] = Field(default_factory=list)
```

- [ ] **Step 4: Import DTOs in service and add exceptions**

In `backend/metadata/service.py`, extend imports from `backend.metadata.models` with:

```python
    CategoryNodeResponse,
    CategoryRef,
    CreateCategoryRequest,
    CreateTagGroupRequest,
    CreateTagRequest,
    MoveCategoryRequest,
    StatusUpdateRequest,
    TableClassificationUpdateRequest,
    TagGroupResponse,
    TagRef,
    TagResponse,
    UpdateCategoryRequest,
    UpdateTagGroupRequest,
    UpdateTagRequest,
```

Add exceptions near `TableNotFound`:

```python
class CategoryNotFound(Exception):
    pass


class TagNotFound(Exception):
    pass


class TagGroupNotFound(Exception):
    pass


class ProtectedCategoryOperation(Exception):
    pass
```

Add helpers near `_serialize_neo4j_datetime`:

```python
def _slug(value: str) -> str:
    return value.strip().lower().replace(" ", "-").replace("/", "-")


def _category_ref_from_row(row: dict) -> Optional[CategoryRef]:
    if row.get("category_id") is None:
        return None
    path = [item for item in row.get("category_path", []) if item]
    return CategoryRef(
        id=row["category_id"],
        code=row["category_code"],
        name=row["category_name"],
        path=path,
        active=bool(row.get("category_active", True)),
    )


def _tag_refs_from_row(row: dict) -> list[TagRef]:
    refs: list[TagRef] = []
    for tag in row.get("tags", []) or []:
        if not tag.get("id"):
            continue
        refs.append(TagRef(
            id=tag["id"],
            code=tag["code"],
            name=tag["name"],
            group_id=tag.get("group_id"),
            group_name=tag.get("group_name"),
            active=bool(tag.get("active", True)),
        ))
    return sorted(refs, key=lambda tag: (tag.group_name or "", tag.name))


def _record_change(operation: str, target_type: str, target_id: str, table_name: str = "", field_name: str = "") -> None:
    run_query(
        """
        CREATE (:Change {
            id: $id,
            operation: $operation,
            table_name: $table_name,
            field_name: $field_name,
            target_type: $target_type,
            target_id: $target_id,
            changed_at: datetime(),
            commit_hash: $commit_hash
        })
        """,
        id=str(uuid.uuid4()),
        operation=operation,
        table_name=table_name,
        field_name=field_name,
        target_type=target_type,
        target_id=target_id,
        commit_hash="",
    )
```

- [ ] **Step 5: Extend table list and detail queries**

Replace `list_tables` signature:

```python
def list_tables(
    layer: Optional[str] = None,
    search: Optional[str] = None,
    category_id: Optional[str] = None,
    include_children: bool = True,
    tag_ids: Optional[list[str]] = None,
    tag_match: str = "any",
    uncategorized: bool = False,
) -> list[TableSummary]:
```

Build filters with these conditions before query execution:

```python
    tag_ids = tag_ids or []
    cypher_filters = []
    params: dict = {"tag_ids": tag_ids}
    if layer:
        cypher_filters.append("t.layer = $layer")
        params["layer"] = layer
    if search:
        cypher_filters.append("toLower(t.name) CONTAINS toLower($search) OR toLower(t.description) CONTAINS toLower($search)")
        params["search"] = search
    if category_id:
        params["category_id"] = category_id
        if include_children:
            cypher_filters.append(
                "EXISTS { MATCH (selected:MetaCategory {id: $category_id})-[:HAS_CHILD*0..]->(cat) }"
            )
        else:
            cypher_filters.append("cat.id = $category_id")
    if uncategorized:
        cypher_filters.append("cat IS NULL")
    if tag_ids and tag_match == "all":
        cypher_filters.append("all(tag_id IN $tag_ids WHERE tag_id IN tag_ids_for_table)")
    elif tag_ids:
        cypher_filters.append("any(tag_id IN $tag_ids WHERE tag_id IN tag_ids_for_table)")
```

Use this query body:

```python
    where = ("WHERE " + " AND ".join(cypher_filters)) if cypher_filters else ""
    rows = run_query(
        f"""
        MATCH (t:Table)
        OPTIONAL MATCH (t)-[:HAS_FIELD]->(f:Field)
        OPTIONAL MATCH (t)-[:IN_CATEGORY]->(cat:MetaCategory)
        OPTIONAL MATCH (root:MetaCategory)-[:HAS_CHILD]->(cat)
        OPTIONAL MATCH (t)-[:TAGGED_WITH]->(tag:MetaTag)
        OPTIONAL MATCH (group:MetaTagGroup)-[:HAS_TAG]->(tag)
        WITH t, cat, root, count(DISTINCT f) AS field_count,
             collect(DISTINCT tag.id) AS tag_ids_for_table,
             collect(DISTINCT {{
                id: tag.id, code: tag.code, name: tag.name, active: tag.active,
                group_id: group.id, group_name: group.name
             }}) AS tags
        {where}
        RETURN t.id AS id, t.name AS name, t.layer AS layer, t.layer_priority AS layer_priority,
               t.storage_type AS storage_type, t.description AS description, field_count,
               cat.id AS category_id, cat.code AS category_code, cat.name AS category_name,
               cat.active AS category_active,
               CASE WHEN root.name IS NULL AND cat.name IS NULL THEN [] ELSE [root.name, cat.name] END AS category_path,
               tags
        ORDER BY t.layer_priority, t.name
        """,
        **params,
    )
    return [
        TableSummary(
            id=r["id"],
            name=r["name"],
            layer=r["layer"],
            layer_priority=r["layer_priority"],
            storage_type=r["storage_type"],
            description=r["description"],
            field_count=r["field_count"],
            category=_category_ref_from_row(r),
            tags=_tag_refs_from_row(r),
        )
        for r in rows
    ]
```

In `get_table_by_name`, extend the Cypher with category and tags:

```cypher
        OPTIONAL MATCH (t)-[:IN_CATEGORY]->(cat:MetaCategory)
        OPTIONAL MATCH (root:MetaCategory)-[:HAS_CHILD]->(cat)
        OPTIONAL MATCH (t)-[:TAGGED_WITH]->(tag:MetaTag)
        OPTIONAL MATCH (group:MetaTagGroup)-[:HAS_TAG]->(tag)
```

Return these columns:

```cypher
               cat.id AS category_id, cat.code AS category_code, cat.name AS category_name,
               cat.active AS category_active,
               CASE WHEN root.name IS NULL AND cat.name IS NULL THEN [] ELSE [root.name, cat.name] END AS category_path,
               collect(DISTINCT {
                    id: tag.id, code: tag.code, name: tag.name, active: tag.active,
                    group_id: group.id, group_name: group.name
               }) AS tags
```

When constructing `TableResponse`, pass:

```python
        category=_category_ref_from_row(row),
        tags=_tag_refs_from_row(row),
```

- [ ] **Step 6: Add category and tag read methods**

Append before the `# ----------------------- Lineage -----------------------` marker:

```python
# ----------------------- Taxonomy -----------------------

def list_categories_tree() -> list[CategoryNodeResponse]:
    rows = run_query(
        """
        MATCH (root:MetaCategory {level: 1})
        OPTIONAL MATCH (root)-[:HAS_CHILD]->(child:MetaCategory)
        OPTIONAL MATCH (root)<-[:IN_CATEGORY]-(root_t:Table)
        OPTIONAL MATCH (child)<-[:IN_CATEGORY]-(child_t:Table)
        WITH root, child, count(DISTINCT root_t) AS root_direct_count, count(DISTINCT child_t) AS child_count
        ORDER BY root.sort_order, child.sort_order
        WITH root, root_direct_count,
             collect({
                id: child.id,
                code: child.code,
                name: child.name,
                level: child.level,
                sort_order: child.sort_order,
                protected: child.protected,
                active: child.active,
                table_count: child_count
             }) AS children
        RETURN root.id AS id, root.code AS code, root.name AS name, root.level AS level,
               root.sort_order AS sort_order, root.protected AS protected, root.active AS active,
               root_direct_count + reduce(total = 0, c IN children | total + coalesce(c.table_count, 0)) AS table_count,
               children
        ORDER BY sort_order
        """
    )
    tree: list[CategoryNodeResponse] = []
    for row in rows:
        children = [
            CategoryNodeResponse(**child, children=[])
            for child in row["children"]
            if child.get("id") is not None
        ]
        tree.append(CategoryNodeResponse(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            level=row["level"],
            sort_order=row["sort_order"],
            protected=row["protected"],
            active=row["active"],
            table_count=row["table_count"],
            children=children,
        ))
    return tree


def list_tags() -> list[TagGroupResponse]:
    rows = run_query(
        """
        MATCH (g:MetaTagGroup)
        OPTIONAL MATCH (g)-[:HAS_TAG]->(tag:MetaTag)
        WITH g, tag
        ORDER BY g.sort_order, tag.sort_order, tag.name
        WITH g, collect({
            id: tag.id,
            code: tag.code,
            name: tag.name,
            sort_order: tag.sort_order,
            active: tag.active
        }) AS tags
        RETURN g.id AS id, g.code AS code, g.name AS name,
               g.sort_order AS sort_order, g.active AS active, tags
        ORDER BY sort_order, name
        """
    )
    return [
        TagGroupResponse(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            sort_order=row["sort_order"],
            active=row["active"],
            tags=[TagResponse(**tag) for tag in row["tags"] if tag.get("id") is not None],
        )
        for row in rows
    ]
```

- [ ] **Step 7: Add table classification update**

Append after `list_tags()`:

```python
def update_table_classification(table_id: str, req: TableClassificationUpdateRequest) -> TableResponse:
    table_rows = run_query("MATCH (t:Table {id: $id}) RETURN t.name AS name", id=table_id)
    if not table_rows:
        raise TableNotFound(table_id)

    category_rows = run_query(
        """
        MATCH (category:MetaCategory {id: $id})
        WHERE category.active = true AND category.level = 2
        RETURN category.id AS id
        """,
        id=req.category_id,
    )
    if not category_rows:
        raise CategoryNotFound(req.category_id)

    if req.tag_ids:
        tag_rows = run_query(
            """
            MATCH (tag:MetaTag)
            WHERE tag.id IN $ids AND tag.active = true
            RETURN collect(tag.id) AS ids
            """,
            ids=req.tag_ids,
        )
        found_ids = set(tag_rows[0]["ids"] if tag_rows else [])
        missing = set(req.tag_ids) - found_ids
        if missing:
            raise TagNotFound(",".join(sorted(missing)))

    run_query(
        """
        MATCH (t:Table {id: $table_id})
        MATCH (category:MetaCategory {id: $category_id})
        OPTIONAL MATCH (t)-[old_category:IN_CATEGORY]->(:MetaCategory)
        DELETE old_category
        WITH t, category
        MERGE (t)-[:IN_CATEGORY]->(category)
        WITH t
        OPTIONAL MATCH (t)-[old_tag:TAGGED_WITH]->(:MetaTag)
        DELETE old_tag
        WITH t
        UNWIND $tag_ids AS tag_id
        MATCH (tag:MetaTag {id: tag_id})
        MERGE (t)-[:TAGGED_WITH]->(tag)
        """,
        table_id=table_id,
        category_id=req.category_id,
        tag_ids=req.tag_ids,
    )
    table_name = table_rows[0]["name"]
    _record_change(
        operation="table_classification_update",
        target_type="Table",
        target_id=table_id,
        table_name=table_name,
    )
    return get_table_by_name(table_name)
```

- [ ] **Step 8: Add category and tag mutation methods**

Append after `update_table_classification()`:

```python
def create_category(req: CreateCategoryRequest) -> CategoryNodeResponse:
    parent_rows = run_query(
        "MATCH (p:MetaCategory {id: $id}) WHERE p.level = 1 RETURN p.code AS code",
        id=req.parent_id,
    )
    if not parent_rows:
        raise CategoryNotFound(req.parent_id)
    code = req.code or f"{parent_rows[0]['code']}.{_slug(req.name)}"
    category_id = f"category:{code}"
    run_query(
        """
        MATCH (parent:MetaCategory {id: $parent_id})
        MERGE (category:MetaCategory {code: $code})
        ON CREATE SET category.id = $id,
                      category.created_at = datetime()
        SET category.name = $name,
            category.level = 2,
            category.sort_order = $sort_order,
            category.protected = false,
            category.active = true,
            category.updated_at = datetime()
        MERGE (parent)-[:HAS_CHILD]->(category)
        """,
        parent_id=req.parent_id,
        id=category_id,
        code=code,
        name=req.name,
        sort_order=req.sort_order,
    )
    _record_change("category_create", "MetaCategory", category_id)
    return next(child for root in list_categories_tree() for child in root.children if child.id == category_id)


def update_category(category_id: str, req: UpdateCategoryRequest) -> CategoryNodeResponse:
    sets: list[str] = []
    params: dict = {"id": category_id}
    if req.name is not None:
        sets.append("category.name = $name")
        params["name"] = req.name
    if req.sort_order is not None:
        sets.append("category.sort_order = $sort_order")
        params["sort_order"] = req.sort_order
    if not sets:
        rows = run_query("MATCH (category:MetaCategory {id: $id}) RETURN category.id AS id", id=category_id)
        if not rows:
            raise CategoryNotFound(category_id)
    else:
        rows = run_query(
            f"""
            MATCH (category:MetaCategory {{id: $id}})
            SET {', '.join(sets)}, category.updated_at = datetime()
            RETURN category.id AS id
            """,
            **params,
        )
        if not rows:
            raise CategoryNotFound(category_id)
        _record_change("category_update", "MetaCategory", category_id)
    return next(item for root in list_categories_tree() for item in [root, *root.children] if item.id == category_id)


def move_category(category_id: str, req: MoveCategoryRequest) -> CategoryNodeResponse:
    rows = run_query(
        """
        MATCH (category:MetaCategory {id: $category_id})
        MATCH (parent:MetaCategory {id: $parent_id})
        WHERE category.level = 2 AND parent.level = 1 AND coalesce(category.protected, false) = false
        OPTIONAL MATCH (:MetaCategory)-[old:HAS_CHILD]->(category)
        DELETE old
        MERGE (parent)-[:HAS_CHILD]->(category)
        SET category.sort_order = $sort_order,
            category.updated_at = datetime()
        RETURN category.id AS id
        """,
        category_id=category_id,
        parent_id=req.parent_id,
        sort_order=req.sort_order,
    )
    if not rows:
        raise CategoryNotFound(category_id)
    _record_change("category_move", "MetaCategory", category_id)
    return next(child for root in list_categories_tree() for child in root.children if child.id == category_id)


def update_category_status(category_id: str, req: StatusUpdateRequest) -> CategoryNodeResponse:
    rows = run_query(
        """
        MATCH (category:MetaCategory {id: $id})
        SET category.active = $active,
            category.updated_at = datetime()
        RETURN category.id AS id
        """,
        id=category_id,
        active=req.active,
    )
    if not rows:
        raise CategoryNotFound(category_id)
    _record_change("category_status_update", "MetaCategory", category_id)
    return next(item for root in list_categories_tree() for item in [root, *root.children] if item.id == category_id)


def create_tag_group(req: CreateTagGroupRequest) -> TagGroupResponse:
    code = req.code or _slug(req.name)
    group_id = f"tag-group:{code}"
    run_query(
        """
        MERGE (g:MetaTagGroup {code: $code})
        ON CREATE SET g.id = $id,
                      g.created_at = datetime()
        SET g.name = $name,
            g.sort_order = $sort_order,
            g.active = true,
            g.updated_at = datetime()
        """,
        id=group_id,
        code=code,
        name=req.name,
        sort_order=req.sort_order,
    )
    _record_change("tag_group_create", "MetaTagGroup", group_id)
    return next(group for group in list_tags() if group.id == group_id)


def update_tag_group(group_id: str, req: UpdateTagGroupRequest) -> TagGroupResponse:
    sets: list[str] = []
    params: dict = {"id": group_id}
    for attr in ("name", "sort_order", "active"):
        value = getattr(req, attr)
        if value is not None:
            sets.append(f"g.{attr} = ${attr}")
            params[attr] = value
    if not sets:
        rows = run_query("MATCH (g:MetaTagGroup {id: $id}) RETURN g.id AS id", id=group_id)
    else:
        rows = run_query(
            f"MATCH (g:MetaTagGroup {{id: $id}}) SET {', '.join(sets)}, g.updated_at = datetime() RETURN g.id AS id",
            **params,
        )
    if not rows:
        raise TagGroupNotFound(group_id)
    _record_change("tag_group_update", "MetaTagGroup", group_id)
    return next(group for group in list_tags() if group.id == group_id)


def create_tag(req: CreateTagRequest) -> TagResponse:
    group_rows = run_query("MATCH (g:MetaTagGroup {id: $id}) RETURN g.id AS id", id=req.group_id)
    if not group_rows:
        raise TagGroupNotFound(req.group_id)
    code = req.code or f"tag:{_slug(req.name)}"
    tag_id = code
    run_query(
        """
        MATCH (g:MetaTagGroup {id: $group_id})
        MERGE (tag:MetaTag {code: $code})
        ON CREATE SET tag.id = $id,
                      tag.created_at = datetime()
        SET tag.name = $name,
            tag.sort_order = $sort_order,
            tag.active = true,
            tag.updated_at = datetime()
        MERGE (g)-[:HAS_TAG]->(tag)
        """,
        group_id=req.group_id,
        id=tag_id,
        code=code,
        name=req.name,
        sort_order=req.sort_order,
    )
    _record_change("tag_create", "MetaTag", tag_id)
    return next(tag for group in list_tags() for tag in group.tags if tag.id == tag_id)


def update_tag(tag_id: str, req: UpdateTagRequest) -> TagResponse:
    sets: list[str] = []
    params: dict = {"id": tag_id}
    if req.name is not None:
        sets.append("tag.name = $name")
        params["name"] = req.name
    if req.sort_order is not None:
        sets.append("tag.sort_order = $sort_order")
        params["sort_order"] = req.sort_order
    if sets:
        rows = run_query(
            f"MATCH (tag:MetaTag {{id: $id}}) SET {', '.join(sets)}, tag.updated_at = datetime() RETURN tag.id AS id",
            **params,
        )
    else:
        rows = run_query("MATCH (tag:MetaTag {id: $id}) RETURN tag.id AS id", id=tag_id)
    if not rows:
        raise TagNotFound(tag_id)
    if req.group_id is not None:
        group_rows = run_query("MATCH (g:MetaTagGroup {id: $id}) RETURN g.id AS id", id=req.group_id)
        if not group_rows:
            raise TagGroupNotFound(req.group_id)
        run_query(
            """
            MATCH (tag:MetaTag {id: $tag_id})
            OPTIONAL MATCH (:MetaTagGroup)-[old:HAS_TAG]->(tag)
            DELETE old
            WITH tag
            MATCH (g:MetaTagGroup {id: $group_id})
            MERGE (g)-[:HAS_TAG]->(tag)
            """,
            tag_id=tag_id,
            group_id=req.group_id,
        )
    _record_change("tag_update", "MetaTag", tag_id)
    return next(tag for group in list_tags() for tag in group.tags if tag.id == tag_id)


def update_tag_status(tag_id: str, req: StatusUpdateRequest) -> TagResponse:
    rows = run_query(
        "MATCH (tag:MetaTag {id: $id}) SET tag.active = $active, tag.updated_at = datetime() RETURN tag.id AS id",
        id=tag_id,
        active=req.active,
    )
    if not rows:
        raise TagNotFound(tag_id)
    _record_change("tag_status_update", "MetaTag", tag_id)
    return next(tag for group in list_tags() for tag in group.tags if tag.id == tag_id)
```

- [ ] **Step 9: Run service tests**

If Neo4j is available and seeded, run:

```powershell
python init-scripts/05_neo4j_init.py
python init-scripts/06_neo4j_seed.py
python -m pytest tests/api/test_metadata_taxonomy_service.py -q
```

Expected: all service tests pass. If `test_update_table_classification_replaces_category_and_tags` changed `ads_neighbor_pair`, the test restores the original mapping before finishing.

- [ ] **Step 10: Commit service layer**

Commit:

```powershell
git add backend/metadata/models.py backend/metadata/service.py tests/api/test_metadata_taxonomy_service.py
git commit -m "feat: add metadata taxonomy service"
```

## Task 4: Backend HTTP API Routes

**Files:**
- Modify: `backend/api/metadata.py`
- Create: `tests/api/test_metadata_taxonomy_api.py`

- [ ] **Step 1: Add failing route tests**

Create `tests/api/test_metadata_taxonomy_api.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.metadata import router
from backend.metadata import service
from backend.metadata.models import (
    CategoryNodeResponse,
    CategoryRef,
    TableResponse,
    TagGroupResponse,
    TagRef,
    TagResponse,
)


def _client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_categories_tree_endpoint(monkeypatch):
    monkeypatch.setattr(
        service,
        "list_categories_tree",
        lambda: [
            CategoryNodeResponse(
                id="category:network",
                code="network",
                name="网络",
                level=1,
                sort_order=3,
                protected=True,
                active=True,
                table_count=2,
                children=[
                    CategoryNodeResponse(
                        id="category:network.coverage",
                        code="network.coverage",
                        name="覆盖",
                        level=2,
                        sort_order=1,
                        protected=False,
                        active=True,
                        table_count=2,
                        children=[],
                    )
                ],
            )
        ],
    )
    response = _client().get("/api/metadata/categories/tree")
    assert response.status_code == 200
    assert response.json()[0]["children"][0]["name"] == "覆盖"


def test_tags_endpoint(monkeypatch):
    monkeypatch.setattr(
        service,
        "list_tags",
        lambda: [
            TagGroupResponse(
                id="tag-group:network-domain",
                code="network-domain",
                name="网络域",
                sort_order=1,
                active=True,
                tags=[TagResponse(id="tag:覆盖", code="tag:覆盖", name="覆盖", sort_order=1, active=True)],
            )
        ],
    )
    response = _client().get("/api/metadata/tags")
    assert response.status_code == 200
    assert response.json()[0]["tags"][0]["name"] == "覆盖"


def test_table_classification_endpoint(monkeypatch):
    captured = {}

    def fake_update(table_id, req):
        captured["table_id"] = table_id
        captured["category_id"] = req.category_id
        captured["tag_ids"] = req.tag_ids
        return TableResponse(
            id=table_id,
            name="dws_cell_hourly",
            layer="DWS",
            layer_priority=3,
            storage_type="HIVE",
            description="cell hourly",
            field_count=0,
            fields=[],
            category=CategoryRef(
                id="category:network.coverage",
                code="network.coverage",
                name="覆盖",
                path=["网络", "覆盖"],
            ),
            tags=[TagRef(id="tag:质量", code="tag:质量", name="质量")],
        )

    monkeypatch.setattr(service, "update_table_classification", fake_update)
    response = _client().put(
        "/api/tables/t1/classification",
        json={"category_id": "category:network.coverage", "tag_ids": ["tag:质量"]},
    )
    assert response.status_code == 200
    assert captured == {
        "table_id": "t1",
        "category_id": "category:network.coverage",
        "tag_ids": ["tag:质量"],
    }
    assert response.json()["category"]["path"] == ["网络", "覆盖"]
```

- [ ] **Step 2: Run route tests and verify failure**

Run:

```powershell
python -m pytest tests/api/test_metadata_taxonomy_api.py -q
```

Expected: fail because routes are missing.

- [ ] **Step 3: Import DTOs in API router**

In `backend/api/metadata.py`, extend model imports:

```python
    CategoryNodeResponse,
    CreateCategoryRequest,
    CreateTagGroupRequest,
    CreateTagRequest,
    MoveCategoryRequest,
    StatusUpdateRequest,
    TableClassificationUpdateRequest,
    TagGroupResponse,
    TagResponse,
    UpdateCategoryRequest,
    UpdateTagGroupRequest,
    UpdateTagRequest,
```

- [ ] **Step 4: Extend table listing query params**

Replace `list_tables_endpoint` with:

```python
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
```

- [ ] **Step 5: Add taxonomy routes**

Add these routes after `delete_table_endpoint` and before field routes:

```python
@router.put("/api/tables/{table_id}/classification", response_model=TableResponse)
def update_table_classification_endpoint(table_id: str, req: TableClassificationUpdateRequest):
    try:
        return service.update_table_classification(table_id, req)
    except service.TableNotFound:
        raise HTTPException(status_code=404, detail="table not found")
    except service.CategoryNotFound:
        raise HTTPException(status_code=404, detail="category not found")
    except service.TagNotFound:
        raise HTTPException(status_code=404, detail="tag not found")


@router.get("/api/metadata/categories/tree", response_model=list[CategoryNodeResponse])
def categories_tree_endpoint():
    return service.list_categories_tree()


@router.post("/api/metadata/categories", response_model=CategoryNodeResponse, status_code=201)
def create_category_endpoint(req: CreateCategoryRequest):
    try:
        return service.create_category(req)
    except service.CategoryNotFound:
        raise HTTPException(status_code=404, detail="parent category not found")


@router.put("/api/metadata/categories/{category_id}", response_model=CategoryNodeResponse)
def update_category_endpoint(category_id: str, req: UpdateCategoryRequest):
    try:
        return service.update_category(category_id, req)
    except service.CategoryNotFound:
        raise HTTPException(status_code=404, detail="category not found")


@router.patch("/api/metadata/categories/{category_id}/move", response_model=CategoryNodeResponse)
def move_category_endpoint(category_id: str, req: MoveCategoryRequest):
    try:
        return service.move_category(category_id, req)
    except service.CategoryNotFound:
        raise HTTPException(status_code=404, detail="category not found")


@router.patch("/api/metadata/categories/{category_id}/status", response_model=CategoryNodeResponse)
def update_category_status_endpoint(category_id: str, req: StatusUpdateRequest):
    try:
        return service.update_category_status(category_id, req)
    except service.CategoryNotFound:
        raise HTTPException(status_code=404, detail="category not found")


@router.get("/api/metadata/tags", response_model=list[TagGroupResponse])
def tags_endpoint():
    return service.list_tags()


@router.post("/api/metadata/tag-groups", response_model=TagGroupResponse, status_code=201)
def create_tag_group_endpoint(req: CreateTagGroupRequest):
    return service.create_tag_group(req)


@router.put("/api/metadata/tag-groups/{group_id}", response_model=TagGroupResponse)
def update_tag_group_endpoint(group_id: str, req: UpdateTagGroupRequest):
    try:
        return service.update_tag_group(group_id, req)
    except service.TagGroupNotFound:
        raise HTTPException(status_code=404, detail="tag group not found")


@router.post("/api/metadata/tags", response_model=TagResponse, status_code=201)
def create_tag_endpoint(req: CreateTagRequest):
    try:
        return service.create_tag(req)
    except service.TagGroupNotFound:
        raise HTTPException(status_code=404, detail="tag group not found")


@router.put("/api/metadata/tags/{tag_id}", response_model=TagResponse)
def update_tag_endpoint(tag_id: str, req: UpdateTagRequest):
    try:
        return service.update_tag(tag_id, req)
    except service.TagNotFound:
        raise HTTPException(status_code=404, detail="tag not found")
    except service.TagGroupNotFound:
        raise HTTPException(status_code=404, detail="tag group not found")


@router.patch("/api/metadata/tags/{tag_id}/status", response_model=TagResponse)
def update_tag_status_endpoint(tag_id: str, req: StatusUpdateRequest):
    try:
        return service.update_tag_status(tag_id, req)
    except service.TagNotFound:
        raise HTTPException(status_code=404, detail="tag not found")
```

- [ ] **Step 6: Run API tests**

Run:

```powershell
python -m pytest tests/api/test_metadata_taxonomy_api.py tests/api/test_http_smoke.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Run broader non-infra backend tests**

Run:

```powershell
python -m pytest -m "not infra"
```

Expected: non-infra tests pass.

- [ ] **Step 8: Commit API routes**

Commit:

```powershell
git add backend/api/metadata.py tests/api/test_metadata_taxonomy_api.py
git commit -m "feat: expose metadata taxonomy api"
```

## Task 5: Frontend API Client And E2E Fixtures

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/tests/e2e/fixtures.ts`

- [ ] **Step 1: Add API types**

In `frontend/src/api/client.ts`, after `UpdateTablePayload`, add:

```ts
export type CategoryRef = {
  id: string
  code: string
  name: string
  path: string[]
  active: boolean
}

export type TagRef = {
  id: string
  code: string
  name: string
  group_id?: string | null
  group_name?: string | null
  active: boolean
}

export type CategoryNode = {
  id: string
  code: string
  name: string
  level: number
  sort_order: number
  protected: boolean
  active: boolean
  table_count: number
  children: CategoryNode[]
}

export type TagItem = {
  id: string
  code: string
  name: string
  sort_order: number
  active: boolean
}

export type TagGroup = {
  id: string
  code: string
  name: string
  sort_order: number
  active: boolean
  tags: TagItem[]
}

export type TableClassificationPayload = {
  category_id: string
  tag_ids: string[]
}

export type CreateCategoryPayload = {
  parent_id: string
  name: string
  code?: string | null
  sort_order?: number
}

export type UpdateCategoryPayload = {
  name?: string
  sort_order?: number
}

export type MoveCategoryPayload = {
  parent_id: string
  sort_order?: number
}

export type StatusPayload = {
  active: boolean
}

export type CreateTagGroupPayload = {
  name: string
  code?: string | null
  sort_order?: number
}

export type UpdateTagGroupPayload = {
  name?: string
  sort_order?: number
  active?: boolean
}

export type CreateTagPayload = {
  group_id: string
  name: string
  code?: string | null
  sort_order?: number
}

export type UpdateTagPayload = {
  name?: string
  group_id?: string
  sort_order?: number
}
```

Extend `TableSummary` with:

```ts
  category?: CategoryRef | null
  tags?: TagRef[]
```

Extend `TableResponse` inherits this through `TableSummary`.

- [ ] **Step 2: Extend table API params and taxonomy methods**

Change `api.tables` signature:

```ts
  tables: (params: {
    layer?: string
    search?: string
    category_id?: string
    include_children?: boolean
    tag_ids?: string[]
    tag_match?: 'any' | 'all'
    uncategorized?: boolean
  } = {}) => {
    const { tag_ids, ...rest } = params
    const query = qs(rest)
    const search = new URLSearchParams(query.startsWith('?') ? query.slice(1) : query)
    ;(tag_ids ?? []).forEach((tagId) => search.append('tag_ids', tagId))
    const out = search.toString()
    return fetchJson<TableSummary[]>(`/api/tables${out ? `?${out}` : ''}`)
  },
```

Add these API methods near `updateTable`:

```ts
  updateTableClassification: (id: string, payload: TableClassificationPayload) =>
    fetchJson<TableResponse>(`/api/tables/${id}/classification`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  categoriesTree: () => fetchJson<CategoryNode[]>('/api/metadata/categories/tree'),
  createCategory: (payload: CreateCategoryPayload) =>
    fetchJson<CategoryNode>('/api/metadata/categories', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateCategory: (id: string, payload: UpdateCategoryPayload) =>
    fetchJson<CategoryNode>(`/api/metadata/categories/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  moveCategory: (id: string, payload: MoveCategoryPayload) =>
    fetchJson<CategoryNode>(`/api/metadata/categories/${id}/move`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  updateCategoryStatus: (id: string, payload: StatusPayload) =>
    fetchJson<CategoryNode>(`/api/metadata/categories/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  tags: () => fetchJson<TagGroup[]>('/api/metadata/tags'),
  createTagGroup: (payload: CreateTagGroupPayload) =>
    fetchJson<TagGroup>('/api/metadata/tag-groups', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateTagGroup: (id: string, payload: UpdateTagGroupPayload) =>
    fetchJson<TagGroup>(`/api/metadata/tag-groups/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  createTag: (payload: CreateTagPayload) =>
    fetchJson<TagItem>('/api/metadata/tags', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateTag: (id: string, payload: UpdateTagPayload) =>
    fetchJson<TagItem>(`/api/metadata/tags/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  updateTagStatus: (id: string, payload: StatusPayload) =>
    fetchJson<TagItem>(`/api/metadata/tags/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
```

- [ ] **Step 3: Extend e2e fixtures**

In `frontend/tests/e2e/fixtures.ts`, add above `tables`:

```ts
export const categoryTree = [
  {
    id: 'category:network',
    code: 'network',
    name: '网络',
    level: 1,
    sort_order: 3,
    protected: true,
    active: true,
    table_count: 2,
    children: [
      {
        id: 'category:network.coverage',
        code: 'network.coverage',
        name: '覆盖',
        level: 2,
        sort_order: 1,
        protected: false,
        active: true,
        table_count: 1,
        children: [],
      },
      {
        id: 'category:network.quality',
        code: 'network.quality',
        name: '质量',
        level: 2,
        sort_order: 7,
        protected: false,
        active: true,
        table_count: 1,
        children: [],
      },
    ],
  },
  {
    id: 'category:source-data',
    code: 'source-data',
    name: '源数据',
    level: 1,
    sort_order: 6,
    protected: true,
    active: true,
    table_count: 0,
    children: [
      {
        id: 'category:source-data.chr',
        code: 'source-data.chr',
        name: 'CHR',
        level: 2,
        sort_order: 2,
        protected: false,
        active: true,
        table_count: 0,
        children: [],
      },
    ],
  },
]

export const tagGroups = [
  {
    id: 'tag-group:network-domain',
    code: 'network-domain',
    name: '网络域',
    sort_order: 1,
    active: true,
    tags: [
      { id: 'tag:覆盖', code: 'tag:覆盖', name: '覆盖', sort_order: 1, active: true },
      { id: 'tag:质量', code: 'tag:质量', name: '质量', sort_order: 7, active: true },
    ],
  },
]
```

Extend the first `tables` item:

```ts
    category: { id: 'category:network.coverage', code: 'network.coverage', name: '覆盖', path: ['网络', '覆盖'], active: true },
    tags: [
      { id: 'tag:覆盖', code: 'tag:覆盖', name: '覆盖', group_id: 'tag-group:network-domain', group_name: '网络域', active: true },
      { id: 'tag:质量', code: 'tag:质量', name: '质量', group_id: 'tag-group:network-domain', group_name: '网络域', active: true },
    ],
```

Extend the second `tables` item:

```ts
    category: { id: 'category:network.quality', code: 'network.quality', name: '质量', path: ['网络', '质量'], active: true },
    tags: [
      { id: 'tag:质量', code: 'tag:质量', name: '质量', group_id: 'tag-group:network-domain', group_name: '网络域', active: true },
    ],
```

In `mockCommonApis`, add routes before the table routes:

```ts
  await page.route('**/api/metadata/categories/tree', (route) => json(route, categoryTree))
  await page.route('**/api/metadata/tags', (route) => json(route, tagGroups))
  await page.route('**/api/tables/t1/classification', async (route) => {
    const payload = route.request().postDataJSON()
    await json(route, {
      ...tableDetail,
      category: categoryTree[0].children[1],
      tags: tagGroups[0].tags.filter((tag) => payload.tag_ids.includes(tag.id)),
    })
  })
```

- [ ] **Step 4: Run TypeScript build and expected failure**

Run:

```powershell
npm.cmd --prefix frontend run build
```

Expected: fail until UI code consumes the new fields cleanly, or pass if type changes are isolated. Continue either way.

- [ ] **Step 5: Commit client and fixtures**

Commit after TypeScript compiles or the only failures point to the not-yet-updated metadata page:

```powershell
git add frontend/src/api/client.ts frontend/tests/e2e/fixtures.ts
git commit -m "feat: add metadata taxonomy frontend api"
```

## Task 6: Metadata Taxonomy Panel Component

**Files:**
- Create: `frontend/src/components/MetadataTaxonomyPanel.tsx`
- Modify: `frontend/src/pages/Metadata.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/e2e/metadata.spec.ts`

- [ ] **Step 1: Add failing e2e assertions for taxonomy navigation**

Replace the body of `metadata page exposes management interactions` in `frontend/tests/e2e/metadata.spec.ts` with:

```ts
test('metadata page exposes taxonomy navigation and table chips', async ({ page }) => {
  await mockCommonApis(page)
  await page.goto('/metadata')

  await expect(page.getByText('元数据管理')).toBeVisible()
  await expect(page.getByRole('treeitem', { name: /网络/ })).toBeVisible()
  await expect(page.getByRole('treeitem', { name: /覆盖/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /管理分类/ })).toBeVisible()
  await expect(page.getByText('dws_cell_hourly').first()).toBeVisible()
  await expect(page.getByText('网络 / 覆盖').first()).toBeVisible()
  await expect(page.getByText('质量').first()).toBeVisible()

  await page.getByRole('treeitem', { name: /质量/ }).click()
  await expect(page).toHaveURL(/category_id=category%3Anetwork\.quality/)
})
```

If the existing file still has mojibake labels, replace mojibake assertions with the Chinese labels above as part of this task.

- [ ] **Step 2: Run e2e and verify failure**

Run:

```powershell
npm.cmd --prefix frontend run test:e2e -- tests/e2e/metadata.spec.ts
```

Expected: fail because tree items and category chips are not rendered.

- [ ] **Step 3: Create taxonomy panel component**

Create `frontend/src/components/MetadataTaxonomyPanel.tsx`:

```tsx
import { Button, Checkbox, Input, Radio, Select, Space, Tag, Tree, Typography } from 'antd'
import type { DataNode } from 'antd/es/tree'
import { SettingOutlined } from '@ant-design/icons'
import type { CategoryNode, TagGroup } from '../api/client'

type Props = {
  categories?: CategoryNode[]
  tagGroups?: TagGroup[]
  selectedCategoryId?: string
  includeChildren: boolean
  selectedTagIds: string[]
  tagMatch: 'any' | 'all'
  layer: string
  search: string
  layers: string[]
  onSearchChange: (value: string) => void
  onSearchSubmit: (value: string) => void
  onLayerChange: (value: string) => void
  onCategoryChange: (categoryId?: string) => void
  onIncludeChildrenChange: (value: boolean) => void
  onTagsChange: (tagIds: string[]) => void
  onTagMatchChange: (value: 'any' | 'all') => void
  onOpenManager: () => void
}

function toTreeData(categories: CategoryNode[] = []): DataNode[] {
  return categories.map((category) => ({
    key: category.id,
    title: `${category.name} (${category.table_count})`,
    children: category.children.map((child) => ({
      key: child.id,
      title: `${child.name} (${child.table_count})`,
    })),
  }))
}

function tagOptions(tagGroups: TagGroup[] = []) {
  return tagGroups.flatMap((group) =>
    group.tags
      .filter((tag) => tag.active)
      .map((tag) => ({
        label: `${tag.name} · ${group.name}`,
        value: tag.id,
      })),
  )
}

export default function MetadataTaxonomyPanel({
  categories,
  tagGroups,
  selectedCategoryId,
  includeChildren,
  selectedTagIds,
  tagMatch,
  layer,
  search,
  layers,
  onSearchChange,
  onSearchSubmit,
  onLayerChange,
  onCategoryChange,
  onIncludeChildrenChange,
  onTagsChange,
  onTagMatchChange,
  onOpenManager,
}: Props) {
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <div className="metadata-taxonomy-header">
        <Typography.Title level={4} style={{ margin: 0 }}>元数据管理</Typography.Title>
        <Button icon={<SettingOutlined />} onClick={onOpenManager}>管理分类</Button>
      </div>
      <Input.Search
        value={search}
        placeholder="表名/字段/描述"
        allowClear
        onChange={(event) => onSearchChange(event.target.value)}
        onSearch={onSearchSubmit}
      />
      <Select
        value={layer}
        onChange={onLayerChange}
        options={layers.map((value) => ({ value, label: value === 'ALL' ? '全部层级' : value }))}
        style={{ width: '100%' }}
      />
      <div className="metadata-filter-block">
        <Space style={{ justifyContent: 'space-between', width: '100%' }}>
          <Typography.Text strong>主分类</Typography.Text>
          <Button size="small" type="link" onClick={() => onCategoryChange(undefined)}>全部</Button>
        </Space>
        <Checkbox checked={includeChildren} onChange={(event) => onIncludeChildrenChange(event.target.checked)}>
          包含子类
        </Checkbox>
        <Tree
          blockNode
          selectedKeys={selectedCategoryId ? [selectedCategoryId] : []}
          treeData={toTreeData(categories)}
          onSelect={(keys) => onCategoryChange(keys[0] ? String(keys[0]) : undefined)}
        />
      </div>
      <div className="metadata-filter-block">
        <Space style={{ justifyContent: 'space-between', width: '100%' }}>
          <Typography.Text strong>标签</Typography.Text>
          <Radio.Group
            size="small"
            value={tagMatch}
            onChange={(event) => onTagMatchChange(event.target.value)}
            options={[
              { label: '任一', value: 'any' },
              { label: '全部', value: 'all' },
            ]}
          />
        </Space>
        <Select
          mode="multiple"
          allowClear
          maxTagCount="responsive"
          value={selectedTagIds}
          onChange={onTagsChange}
          options={tagOptions(tagGroups)}
          placeholder="选择标签"
          style={{ width: '100%' }}
        />
        {selectedTagIds.length ? (
          <Space size={[4, 4]} wrap>
            {selectedTagIds.map((tagId) => {
              const tag = tagGroups?.flatMap((group) => group.tags).find((item) => item.id === tagId)
              return <Tag key={tagId}>{tag?.name ?? tagId}</Tag>
            })}
          </Space>
        ) : null}
      </div>
    </Space>
  )
}
```

- [ ] **Step 4: Wire taxonomy state in Metadata page**

In `frontend/src/pages/Metadata.tsx`, add import:

```tsx
import MetadataTaxonomyPanel from '../components/MetadataTaxonomyPanel'
```

Add state after `search`:

```tsx
  const [categoryId, setCategoryId] = useState(params.get('category_id') ?? undefined)
  const [includeChildren, setIncludeChildren] = useState((params.get('include_children') ?? 'true') !== 'false')
  const [selectedTagIds, setSelectedTagIds] = useState(params.getAll('tag_ids'))
  const [tagMatch, setTagMatch] = useState<'any' | 'all'>((params.get('tag_match') as 'any' | 'all') ?? 'any')
  const [taxonomyDrawerOpen, setTaxonomyDrawerOpen] = useState(false)
```

Add taxonomy queries before `tableQuery`:

```tsx
  const categoriesQuery = useQuery({
    queryKey: ['metadata-categories'],
    queryFn: api.categoriesTree,
  })

  const tagsQuery = useQuery({
    queryKey: ['metadata-tags'],
    queryFn: api.tags,
  })
```

Change `tableQuery`:

```tsx
  const tableQuery = useQuery({
    queryKey: ['tables', layer, search, categoryId, includeChildren, selectedTagIds, tagMatch],
    queryFn: () => api.tables({
      layer: layer === 'ALL' ? undefined : layer,
      search,
      category_id: categoryId,
      include_children: includeChildren,
      tag_ids: selectedTagIds,
      tag_match: tagMatch,
    }),
  })
```

Add URL helper inside component:

```tsx
  function updateQuery(next: Record<string, string | string[] | boolean | undefined>) {
    const updated = new URLSearchParams(params)
    Object.entries(next).forEach(([key, value]) => {
      updated.delete(key)
      if (Array.isArray(value)) {
        value.forEach((item) => updated.append(key, item))
      } else if (value !== undefined && value !== '') {
        updated.set(key, String(value))
      }
    })
    setParams(updated)
  }
```

Replace the existing title/search/layer block in the left panel with:

```tsx
        <MetadataTaxonomyPanel
          categories={categoriesQuery.data}
          tagGroups={tagsQuery.data}
          selectedCategoryId={categoryId}
          includeChildren={includeChildren}
          selectedTagIds={selectedTagIds}
          tagMatch={tagMatch}
          layer={layer}
          search={search}
          layers={layers}
          onSearchChange={setSearch}
          onSearchSubmit={(value) => updateQuery({ search: value || undefined })}
          onLayerChange={(value) => {
            setLayer(value)
            updateQuery({ layer: value === 'ALL' ? undefined : value })
          }}
          onCategoryChange={(value) => {
            setCategoryId(value)
            updateQuery({ category_id: value })
          }}
          onIncludeChildrenChange={(value) => {
            setIncludeChildren(value)
            updateQuery({ include_children: value })
          }}
          onTagsChange={(values) => {
            setSelectedTagIds(values)
            updateQuery({ tag_ids: values })
          }}
          onTagMatchChange={(value) => {
            setTagMatch(value)
            updateQuery({ tag_match: value })
          }}
          onOpenManager={() => setTaxonomyDrawerOpen(true)}
        />
```

In table rows, after the layer tag, render category and tags:

```tsx
              {table.category ? <Tag color="blue">{table.category.path.join(' / ')}</Tag> : <Tag>未归类</Tag>}
              {(table.tags ?? []).slice(0, 3).map((tag) => <Tag key={tag.id}>{tag.name}</Tag>)}
```

- [ ] **Step 5: Add styles**

Append to `frontend/src/styles.css`:

```css
.metadata-taxonomy-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.metadata-filter-block {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.metadata-filter-block .ant-tree {
  background: transparent;
}
```

- [ ] **Step 6: Run frontend checks**

Run:

```powershell
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e -- tests/e2e/metadata.spec.ts
```

Expected: build and metadata e2e pass after component wiring.

- [ ] **Step 7: Commit taxonomy navigation UI**

Commit:

```powershell
git add frontend/src/components/MetadataTaxonomyPanel.tsx frontend/src/pages/Metadata.tsx frontend/src/styles.css frontend/tests/e2e/metadata.spec.ts
git commit -m "ui: add metadata taxonomy navigation"
```

## Task 7: Taxonomy Management Drawer And Table Classification Editing

**Files:**
- Create: `frontend/src/components/MetadataTaxonomyDrawer.tsx`
- Modify: `frontend/src/pages/Metadata.tsx`
- Modify: `frontend/tests/e2e/metadata.spec.ts`

- [ ] **Step 1: Add failing e2e for drawer and table classification save**

Append to `frontend/tests/e2e/metadata.spec.ts`:

```ts
test('metadata page edits taxonomy and table classification', async ({ page }) => {
  await mockCommonApis(page)
  await page.goto('/metadata')

  await page.getByRole('button', { name: /管理分类/ }).click()
  await expect(page.getByRole('tab', { name: '分类' })).toBeVisible()
  await expect(page.getByRole('tab', { name: '标签' })).toBeVisible()
  await expect(page.getByRole('button', { name: /新增小分类/ })).toBeVisible()
  await page.getByRole('button', { name: /关闭/ }).click()

  await page.getByRole('button', { name: /编辑表/ }).click()
  await page.getByLabel('主分类').click()
  await page.getByTitle('质量').click()
  await page.getByLabel('标签').click()
  await page.getByTitle('质量 · 网络域').click()
  await page.getByRole('button', { name: '保存分类' }).click()

  await expect(page.getByText('网络 / 质量').first()).toBeVisible()
})
```

- [ ] **Step 2: Run e2e and verify failure**

Run:

```powershell
npm.cmd --prefix frontend run test:e2e -- tests/e2e/metadata.spec.ts
```

Expected: fail because management drawer and classification form are missing.

- [ ] **Step 3: Create management drawer component**

Create `frontend/src/components/MetadataTaxonomyDrawer.tsx`:

```tsx
import { Button, Drawer, Form, Input, InputNumber, Select, Space, Switch, Tabs, Tree, Typography, message } from 'antd'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { CategoryNode, TagGroup } from '../api/client'
import { api } from '../api/client'

type Props = {
  open: boolean
  categories?: CategoryNode[]
  tagGroups?: TagGroup[]
  onClose: () => void
}

function rootOptions(categories: CategoryNode[] = []) {
  return categories.map((category) => ({ value: category.id, label: category.name }))
}

function groupOptions(groups: TagGroup[] = []) {
  return groups.map((group) => ({ value: group.id, label: group.name }))
}

export default function MetadataTaxonomyDrawer({ open, categories, tagGroups, onClose }: Props) {
  const queryClient = useQueryClient()
  const [apiMessage, holder] = message.useMessage()
  const [categoryForm] = Form.useForm()
  const [tagGroupForm] = Form.useForm()
  const [tagForm] = Form.useForm()

  function refreshTaxonomy() {
    queryClient.invalidateQueries({ queryKey: ['metadata-categories'] })
    queryClient.invalidateQueries({ queryKey: ['metadata-tags'] })
    queryClient.invalidateQueries({ queryKey: ['tables'] })
  }

  const createCategory = useMutation({
    mutationFn: api.createCategory,
    onSuccess: () => {
      apiMessage.success('分类已创建')
      categoryForm.resetFields()
      refreshTaxonomy()
    },
    onError: (error) => apiMessage.error(`分类创建失败: ${(error as Error).message}`),
  })

  const createTagGroup = useMutation({
    mutationFn: api.createTagGroup,
    onSuccess: () => {
      apiMessage.success('标签分组已创建')
      tagGroupForm.resetFields()
      refreshTaxonomy()
    },
    onError: (error) => apiMessage.error(`标签分组创建失败: ${(error as Error).message}`),
  })

  const createTag = useMutation({
    mutationFn: api.createTag,
    onSuccess: () => {
      apiMessage.success('标签已创建')
      tagForm.resetFields()
      refreshTaxonomy()
    },
    onError: (error) => apiMessage.error(`标签创建失败: ${(error as Error).message}`),
  })

  const updateCategoryStatus = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => api.updateCategoryStatus(id, { active }),
    onSuccess: refreshTaxonomy,
  })

  const updateTagStatus = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => api.updateTagStatus(id, { active }),
    onSuccess: refreshTaxonomy,
  })

  return (
    <Drawer title="分类与标签管理" open={open} onClose={onClose} width={720} extra={<Button onClick={onClose}>关闭</Button>}>
      {holder}
      <Tabs
        items={[
          {
            key: 'categories',
            label: '分类',
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size={16}>
                <Tree
                  blockNode
                  treeData={(categories ?? []).map((category) => ({
                    key: category.id,
                    title: (
                      <Space>
                        <Typography.Text>{category.name}</Typography.Text>
                        <Switch
                          size="small"
                          checked={category.active}
                          onChange={(active) => updateCategoryStatus.mutate({ id: category.id, active })}
                        />
                      </Space>
                    ),
                    children: category.children.map((child) => ({
                      key: child.id,
                      title: (
                        <Space>
                          <Typography.Text>{child.name}</Typography.Text>
                          <Switch
                            size="small"
                            checked={child.active}
                            onChange={(active) => updateCategoryStatus.mutate({ id: child.id, active })}
                          />
                        </Space>
                      ),
                    })),
                  }))}
                />
                <Form
                  layout="inline"
                  form={categoryForm}
                  onFinish={(values) => createCategory.mutate({
                    parent_id: values.parent_id,
                    name: values.name,
                    sort_order: values.sort_order ?? 100,
                  })}
                >
                  <Form.Item name="parent_id" label="大分类" rules={[{ required: true }]}>
                    <Select options={rootOptions(categories)} style={{ width: 140 }} />
                  </Form.Item>
                  <Form.Item name="name" label="小分类" rules={[{ required: true }]}>
                    <Input style={{ width: 140 }} />
                  </Form.Item>
                  <Form.Item name="sort_order" label="排序">
                    <InputNumber min={1} style={{ width: 90 }} />
                  </Form.Item>
                  <Button htmlType="submit" type="primary" loading={createCategory.isPending}>新增小分类</Button>
                </Form>
              </Space>
            ),
          },
          {
            key: 'tags',
            label: '标签',
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size={16}>
                {(tagGroups ?? []).map((group) => (
                  <div className="metadata-filter-block" key={group.id}>
                    <Typography.Text strong>{group.name}</Typography.Text>
                    <Space wrap>
                      {group.tags.map((tag) => (
                        <Space key={tag.id} size={4}>
                          <Typography.Text>{tag.name}</Typography.Text>
                          <Switch
                            size="small"
                            checked={tag.active}
                            onChange={(active) => updateTagStatus.mutate({ id: tag.id, active })}
                          />
                        </Space>
                      ))}
                    </Space>
                  </div>
                ))}
                <Form layout="inline" form={tagGroupForm} onFinish={(values) => createTagGroup.mutate(values)}>
                  <Form.Item name="name" label="分组名" rules={[{ required: true }]}>
                    <Input style={{ width: 140 }} />
                  </Form.Item>
                  <Form.Item name="sort_order" label="排序">
                    <InputNumber min={1} style={{ width: 90 }} />
                  </Form.Item>
                  <Button htmlType="submit">新增分组</Button>
                </Form>
                <Form
                  layout="inline"
                  form={tagForm}
                  onFinish={(values) => createTag.mutate({
                    group_id: values.group_id,
                    name: values.name,
                    sort_order: values.sort_order ?? 100,
                  })}
                >
                  <Form.Item name="group_id" label="分组" rules={[{ required: true }]}>
                    <Select options={groupOptions(tagGroups)} style={{ width: 150 }} />
                  </Form.Item>
                  <Form.Item name="name" label="标签名" rules={[{ required: true }]}>
                    <Input style={{ width: 140 }} />
                  </Form.Item>
                  <Form.Item name="sort_order" label="排序">
                    <InputNumber min={1} style={{ width: 90 }} />
                  </Form.Item>
                  <Button htmlType="submit" type="primary" loading={createTag.isPending}>新增标签</Button>
                </Form>
              </Space>
            ),
          },
        ]}
      />
    </Drawer>
  )
}
```

- [ ] **Step 4: Wire drawer and table classification editing**

In `frontend/src/pages/Metadata.tsx`, import the drawer:

```tsx
import MetadataTaxonomyDrawer from '../components/MetadataTaxonomyDrawer'
```

Extend `TableFormValues`:

```tsx
  category_id?: string
  tag_ids?: string[]
```

Add helper functions in the component:

```tsx
  const categoryOptions = (categoriesQuery.data ?? []).flatMap((root) =>
    root.children.filter((child) => child.active).map((child) => ({
      value: child.id,
      label: `${root.name} / ${child.name}`,
    })),
  )

  const tagOptions = (tagsQuery.data ?? []).flatMap((group) =>
    group.tags.filter((tag) => tag.active).map((tag) => ({
      value: tag.id,
      label: `${tag.name} · ${group.name}`,
    })),
  )
```

Add mutation:

```tsx
  const updateClassificationMutation = useMutation({
    mutationFn: (values: TableFormValues) => api.updateTableClassification(detailQuery.data!.id, {
      category_id: values.category_id!,
      tag_ids: values.tag_ids ?? [],
    }),
    onSuccess: (table) => {
      apiMessage.success('分类与标签已保存')
      refreshMetadata(table)
      queryClient.invalidateQueries({ queryKey: ['metadata-categories'] })
      queryClient.invalidateQueries({ queryKey: ['metadata-tags'] })
    },
    onError: (error) => apiMessage.error(`分类保存失败: ${(error as Error).message}`),
  })
```

In `openEditTable()`, add:

```tsx
      category_id: detailQuery.data.category?.id,
      tag_ids: detailQuery.data.tags?.map((tag) => tag.id) ?? [],
```

In the table detail action toolbar, keep the existing edit button label as `编辑表`, and ensure it opens the modal with classification fields.

Inside the edit table modal form, after description field add:

```tsx
          {tableModal === 'edit' ? (
            <>
              <Form.Item name="category_id" label="主分类" rules={[{ required: true, message: '请选择主分类' }]}>
                <Select options={categoryOptions} showSearch optionFilterProp="label" />
              </Form.Item>
              <Form.Item name="tag_ids" label="标签">
                <Select mode="multiple" options={tagOptions} showSearch optionFilterProp="label" />
              </Form.Item>
            </>
          ) : null}
```

In `submitTable`, when editing, run both table base update and classification update:

```tsx
      if (tableModal === 'edit') {
        updateTableMutation.mutate(values)
        if (values.category_id) updateClassificationMutation.mutate(values)
        return
      }
```

In modal footer, change the edit primary button text:

```tsx
            {tableModal === 'edit' ? '保存分类' : '保存'}
```

At the end of the JSX, before the YAML drawer, add:

```tsx
      <MetadataTaxonomyDrawer
        open={taxonomyDrawerOpen}
        categories={categoriesQuery.data}
        tagGroups={tagsQuery.data}
        onClose={() => setTaxonomyDrawerOpen(false)}
      />
```

- [ ] **Step 5: Run frontend checks**

Run:

```powershell
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e -- tests/e2e/metadata.spec.ts
```

Expected: build and metadata e2e pass.

- [ ] **Step 6: Commit management UI**

Commit:

```powershell
git add frontend/src/components/MetadataTaxonomyDrawer.tsx frontend/src/pages/Metadata.tsx frontend/tests/e2e/metadata.spec.ts
git commit -m "ui: manage metadata categories and tags"
```

## Task 8: Integration Verification And Documentation Check

**Files:**
- Modify: `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md` only if verification finds behavior drift.

- [ ] **Step 1: Verify infrastructure config is unchanged**

Run:

```powershell
docker compose -f ..\shared-data-infra\compose.yaml --profile data-gov config
docker compose -f app-compose.yml config
```

Expected: both config commands exit 0. This confirms no accidental local duplication of shared infra services.

- [ ] **Step 2: Re-seed Neo4j and run backend tests**

Run:

```powershell
python init-scripts/05_neo4j_init.py
python init-scripts/06_neo4j_seed.py
python -m pytest tests/api/test_seed_data.py tests/api/test_metadata_taxonomy_seed_script.py tests/api/test_metadata_taxonomy_api.py tests/api/test_metadata_taxonomy_service.py -q
python -m pytest -m "not infra"
```

Expected: selected taxonomy tests and non-infra backend tests pass.

- [ ] **Step 3: Run frontend checks**

Run:

```powershell
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run test:e2e -- tests/e2e/metadata.spec.ts
```

Expected: build, lint, and metadata e2e pass. Vite large chunk warnings are acceptable if the exit code is 0.

- [ ] **Step 4: Manual browser check**

Start local services if they are not already running:

```powershell
Start-Process -FilePath 'python' -ArgumentList @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory 'D:\agent-code\data-gov' -WindowStyle Hidden
Start-Process -FilePath 'yarn.cmd' -ArgumentList @('--cwd','frontend','dev','--host','127.0.0.1','--port','5174','--strictPort') -WorkingDirectory 'D:\agent-code\data-gov' -WindowStyle Hidden
Start-Process 'http://127.0.0.1:5174/metadata'
```

Check these states:

- Left panel shows `环境`, `设备`, `网络`, `用户`, `业务`, `源数据`.
- `网络 / 覆盖` shows `dws_cell_hourly` and `ads_cell_profile`.
- Selecting tag `质量` filters table cards to tagged tables.
- Table cards show category path and tag chips.
- `管理分类` opens a drawer with `分类` and `标签` tabs.
- Creating a small category under a root category refreshes the tree.
- Creating a tag under a tag group refreshes the tag list.
- Editing a table and saving `主分类` plus `标签` refreshes the card, detail, and category counts.
- No visible text overflows in left panel, table card chips, or drawer forms at desktop width and at `390px` mobile viewport.

- [ ] **Step 5: Documentation drift check**

Run:

```powershell
git diff -- docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md
rg -n "MetaCategory|TAGGED_WITH|分类与标签导航管理|/api/metadata/categories/tree|/api/tables/:id/classification" docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md
```

Expected: spec already matches implementation. If actual behavior differs, update only the affected section and use PlantUML for any new diagram.

- [ ] **Step 6: Final status and commit any doc correction**

Run:

```powershell
git status --short
```

Expected: working tree clean after the feature commits. If a spec correction was required, commit it:

```powershell
git add docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md
git commit -m "docs: align metadata taxonomy implementation"
```

## Self-Review Checklist

- Spec coverage:
  - Hybrid `主分类树 + 标签` model: Tasks 1, 3, 5, 6.
  - Six protected root categories and provided child categories: Tasks 1, 2.
  - Existing sample tables classified into the taxonomy: Tasks 1, 2, 3.
  - Neo4j nodes/relationships and constraints: Tasks 2, 3.
  - `/api/tables` combined filters and `/api/tables/:id/classification`: Tasks 3, 4, 5.
  - Category/tag edit APIs: Tasks 3, 4.
  - `/metadata` left navigation, chips, management drawer, and edit form: Tasks 6, 7.
  - Lightweight audit through `Change`: Task 3.
  - Documentation refresh check: Task 8.
- Placeholder scan:
  - This plan contains concrete file paths, commands, code snippets, and expected outcomes.
  - No open-ended implementation markers remain.
- Type consistency:
  - Backend `CategoryRef`, `TagRef`, `CategoryNodeResponse`, `TagGroupResponse`, and `TableClassificationUpdateRequest` match frontend `CategoryRef`, `TagRef`, `CategoryNode`, `TagGroup`, and `TableClassificationPayload`.
  - Category ids use `category:<code>`, tag ids use `tag:<name-or-slug>`, and table update payload uses `category_id` plus `tag_ids`.
  - Frontend query keys `metadata-categories`, `metadata-tags`, and `tables` are invalidated after taxonomy mutations.
