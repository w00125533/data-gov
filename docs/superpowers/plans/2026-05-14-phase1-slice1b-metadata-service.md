# Phase 1 Slice 1b: Neo4j Metadata Graph + FastAPI Metadata Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Phase 1 — bring up the Neo4j metadata graph (10 tables, ~65 fields, full field-level lineage) with YAML export, implement the FastAPI metadata service (`/api/tables`, `/api/fields`, `/api/lineage`, `/api/health`), introduce `app-compose.yml`, and extend the Hive seeder so all of P1-5, P1-5b, P1-6, P1-7, P1-8 pass.

**Architecture:** Neo4j becomes the authoritative metadata store. Three new init scripts seed it (`05_neo4j_init.py` for constraints/indexes, `06_neo4j_seed.py` for 10 tables + ~65 fields + ~45 `DERIVES_FROM` edges, `07_export_yaml.py` to materialize the YAML副本). A FastAPI app (`backend/`) ships behind a new `app-compose.yml`, using the official `neo4j` Python driver and reading directly from the graph — no separate caching layer. The CRUD service module is reused by Agent tools in later slices (per spec §4.3 note: HTTP routes and Agent tools share the same service functions). Hive reverse-synth seeding for P1-8 lands as a standalone `backend.seed.fake_data.generate_fake_data` function that delegates to an ephemeral Spark client.

**Tech Stack:**
- Neo4j Python driver: `neo4j>=5.18`
- FastAPI: `fastapi>=0.110`, `uvicorn[standard]>=0.27`
- Settings: `pydantic-settings>=2.2`
- YAML: `PyYAML>=6.0`
- Tests: `httpx>=0.27` (FastAPI TestClient companion), `pytest` (already from slice 1a)
- Docker: same compose backbone as slice 1a; new `app-compose.yml` overlays a single `backend` service
- Spark client: same `apache/spark:3.5.4` ephemeral container as slice 1a

**Prerequisites (from slice 1a):**
- `base-compose.yml` stack runs healthy (`./scripts/wait-for-healthy.sh 300` exits 0)
- `init-scripts/01_hive_init.sql`, `02_kafka_init.sh`, `03_starrocks_init.sql`, `04_sample_data.py` are present
- `pyproject.toml` exists with `[project.optional-dependencies] test` group
- `docker/hadoop-conf/`, `docker/hive-conf/` config dirs exist

**Out of scope for this slice (deferred):**
- LangGraph Agent (slice 2b) and Sandbox (slice 2c)
- Semantic search subsystem `/api/search` (slice 2a)
- Pipeline / health UI surfaces (slice 3a+)
- Schema-evolution APIs `/api/schema/*` (slice 2b — coupled to schema_evolve LangGraph node)
- Chat / SSE APIs `/api/chat/*` (slice 2b)
- YAML preview / export endpoints (slice 3c — only needed when UI consumes them; the static `07_export_yaml.py` is enough for Phase 1)

---

## File Structure

```
data-gov/
├── app-compose.yml                          # NEW — backend service overlay
├── backend/
│   ├── __init__.py
│   ├── main.py                              # FastAPI app factory + app instance
│   ├── config.py                            # pydantic-settings — Neo4j URI/user/password from env
│   ├── metadata/
│   │   ├── __init__.py
│   │   ├── graph.py                         # Neo4j driver singleton + run_query helper
│   │   ├── models.py                        # Pydantic request/response models
│   │   └── service.py                       # CRUD + lineage Cypher (reused by HTTP routes AND future Agent tools)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── metadata.py                      # /api/tables, /api/fields, /api/lineage
│   │   └── health.py                        # /api/health (FastAPI + Neo4j only in this slice)
│   ├── seed/
│   │   ├── __init__.py
│   │   ├── tables.py                        # Single source of truth for 10 tables × fields × lineage
│   │   └── fake_data.py                     # generate_fake_data(table, rows) → writes to Hive via Spark
│   └── Dockerfile                           # Python 3.11-slim + pip install -e .
├── init-scripts/
│   ├── 05_neo4j_init.py                     # NEW — constraints + indexes
│   ├── 06_neo4j_seed.py                     # NEW — calls backend.seed.tables → writes Neo4j
│   ├── 07_export_yaml.py                    # NEW — Neo4j → metadata-yaml/L*-*/ *.yaml
│   └── 04_sample_data.py                    # MODIFIED — append Hive seed via backend.seed.fake_data
├── metadata-yaml/                           # generated at runtime; git-tracked starting from 07's output
│   ├── L1-ODS/
│   ├── L2-DWD/
│   ├── L3-DWS/
│   ├── L4-ADS/
│   └── L5-EVAL/
├── tests/
│   ├── conftest.py                          # MODIFIED — add `api_client` fixture wrapping httpx
│   ├── infra/
│   │   ├── test_neo4j_init.py               # P1-5b
│   │   ├── test_neo4j_seed.py               # P1-5 (Neo4j counts)
│   │   ├── test_yaml_export.py              # P1-5 (YAML files)
│   │   └── test_hive_reverse_synth.py       # P1-8
│   └── api/
│       ├── __init__.py
│       ├── test_metadata_crud.py            # P1-6
│       └── test_lineage.py                  # P1-7
└── scripts/
    └── init-stack.sh                        # MODIFIED — add 05/06/07 + ensure backend up before testing API
```

**Responsibility per file:**
- `backend/metadata/graph.py` — exposes `get_driver()` returning a process-singleton `neo4j.Driver`, and `run_query(cypher, **params) -> list[dict]`. No business logic.
- `backend/metadata/service.py` — pure Cypher functions; takes a `session` or uses `get_driver()`; throws domain errors (`TableNotFound`, `FieldHasDownstream`, `CycleDetected`). HTTP routes and Agent tools both depend on these.
- `backend/metadata/models.py` — Pydantic v2 models matching spec §6.7 wire shapes. Single source of HTTP DTOs.
- `backend/api/metadata.py` — thin FastAPI router; only HTTP plumbing + DTO conversion.
- `backend/seed/tables.py` — Python constant `SEED_TABLES: list[TableSeed]` and `SEED_LINEAGE: list[LineageEdge]`. Single source consumed by `06_neo4j_seed.py`, `07_export_yaml.py`, and tests verifying seed counts. Avoids duplicating field lists across scripts.
- `backend/seed/fake_data.py` — `generate_fake_data(table_name: str, rows: int)` writes deterministic rows via ephemeral Spark container subprocess. Pure function; no FastAPI dependency.
- `init-scripts/0{5,6,7}_*.py` — thin entry points; import from `backend.seed` so the truth lives in one place.

---

## Task 0: Extend backend deps + package skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `backend/__init__.py`
- Create: `backend/config.py`
- Create: `backend/metadata/__init__.py`
- Create: `backend/api/__init__.py`
- Create: `backend/seed/__init__.py`

- [ ] **Step 1: Extend `pyproject.toml` with runtime + test deps**

Replace the `[project.optional-dependencies]` block with:

```toml
[project.optional-dependencies]
runtime = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "neo4j>=5.18",
    "pydantic-settings>=2.2",
    "PyYAML>=6.0",
]
test = [
    "pytest>=7.4",
    "pytest-timeout>=2.2",
    "requests>=2.31",
    "kafka-python>=2.0.2",
    "PyMySQL>=1.1",
    "httpx>=0.27",
]
dev = [
    "data-gov[runtime,test]",
]
```

Add a `[tool.setuptools.packages.find]` block at the bottom (FastAPI app needs to be importable):

```toml
[tool.setuptools.packages.find]
include = ["backend*"]
exclude = ["tests*"]
```

- [ ] **Step 2: Write `backend/__init__.py`** (empty file, marks package)

Create `backend/__init__.py` with content:

```python
"""Wireless RNO Data Semantic Service — FastAPI backend."""
__version__ = "0.1.0"
```

- [ ] **Step 3: Write `backend/config.py`**

```python
"""Application settings loaded from environment / .env."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    neo4j_uri: str = Field("bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field("neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field("data-gov-neo4j", alias="NEO4J_PASSWORD")
    neo4j_database: str = Field("neo4j", alias="NEO4J_DATABASE")

    metadata_yaml_dir: str = Field("metadata-yaml", alias="METADATA_YAML_DIR")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Write package marker files**

Create these as empty (zero-byte) files:
- `backend/metadata/__init__.py`
- `backend/api/__init__.py`
- `backend/seed/__init__.py`
- `tests/api/__init__.py`

- [ ] **Step 5: Add Neo4j env vars to `.env.example`**

Append to `.env.example`:

```env

# Backend → Neo4j connection (defaults match base-compose Neo4j service)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=data-gov-neo4j
NEO4J_DATABASE=neo4j
METADATA_YAML_DIR=metadata-yaml
```

- [ ] **Step 6: Verify installable**

Run:

```bash
pip install -e ".[dev]"
python -c "from backend.config import get_settings; print(get_settings().neo4j_uri)"
```

Expected: prints `bolt://localhost:7687` (or whatever the local `.env` overrides). No import errors.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml backend/ tests/api/__init__.py .env.example
git commit -m "chore(backend): scaffold FastAPI package and Neo4j settings"
```

---

## Task 1: Neo4j driver wrapper

**Files:**
- Create: `backend/metadata/graph.py`
- Create: `tests/api/test_neo4j_driver.py`

- [ ] **Step 1: Write the failing test**

`tests/api/test_neo4j_driver.py`:

```python
import pytest

from backend.metadata.graph import get_driver, run_query


@pytest.mark.infra
def test_run_query_returns_single_int():
    rows = run_query("RETURN 1 AS n")
    assert rows == [{"n": 1}]


@pytest.mark.infra
def test_run_query_with_params():
    rows = run_query("RETURN $x AS x, $y AS y", x="hello", y=42)
    assert rows == [{"x": "hello", "y": 42}]


@pytest.mark.infra
def test_driver_singleton():
    d1 = get_driver()
    d2 = get_driver()
    assert d1 is d2, "get_driver must memoize"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/api/test_neo4j_driver.py -v`
Expected: FAIL — `backend.metadata.graph` does not exist (ImportError).

- [ ] **Step 3: Implement `backend/metadata/graph.py`**

```python
"""Neo4j driver singleton + thin query helper."""
from functools import lru_cache
from typing import Any

from neo4j import Driver, GraphDatabase

from backend.config import get_settings


@lru_cache(maxsize=1)
def get_driver() -> Driver:
    s = get_settings()
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    driver.verify_connectivity()
    return driver


def run_query(cypher: str, **params: Any) -> list[dict]:
    """Execute a Cypher query and return all records as plain dicts."""
    driver = get_driver()
    with driver.session(database=get_settings().neo4j_database) as session:
        result = session.run(cypher, params)
        return [dict(record) for record in result]


def close_driver() -> None:
    """Close the singleton — called from FastAPI lifespan shutdown and test teardown."""
    driver = get_driver.__wrapped__()  # bypass cache to avoid creating a second driver
    if driver:
        driver.close()
    get_driver.cache_clear()
```

> **Note:** `get_driver.__wrapped__()` reads the underlying function reference; calling it would reconstruct the driver. The pattern in `close_driver` is intentionally defensive — we use `get_driver()` directly via cache and then `cache_clear()` so the next `get_driver()` reconstructs.

Rewrite `close_driver` simpler:

```python
def close_driver() -> None:
    """Close the singleton driver if it exists. Idempotent."""
    info = get_driver.cache_info()
    if info.currsize == 0:
        return
    get_driver().close()
    get_driver.cache_clear()
```

- [ ] **Step 4: Re-run the test**

Run: `pytest tests/api/test_neo4j_driver.py -v`
Expected: PASS — Neo4j responds to `RETURN 1` and parametrized query.

> Pre-condition: `docker compose -f base-compose.yml up -d neo4j` from slice 1a; `.env` has `NEO4J_PASSWORD=data-gov-neo4j`.

- [ ] **Step 5: Commit**

```bash
git add backend/metadata/graph.py tests/api/test_neo4j_driver.py
git commit -m "feat(backend): Neo4j driver singleton with parametrized run_query"
```

---

## Task 2: Neo4j init script — `05_neo4j_init.py`

**Files:**
- Create: `init-scripts/05_neo4j_init.py`
- Create: `tests/infra/test_neo4j_init.py`

- [ ] **Step 1: Write the failing P1-5b test**

`tests/infra/test_neo4j_init.py`:

```python
"""P1-5b: SHOW CONSTRAINTS returns >= 4; SHOW INDEXES returns >= 3 expected indexes."""
import pytest

from backend.metadata.graph import run_query


@pytest.mark.infra
def test_p1_5b_constraints_exist():
    rows = run_query("SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties")
    names = {r["name"] for r in rows}
    required = {"table_id_unique", "table_name_unique", "field_id_unique", "change_id_unique"}
    missing = required - names
    assert not missing, f"missing constraints: {missing}; got: {names}"


@pytest.mark.infra
def test_p1_5b_indexes_exist():
    rows = run_query("SHOW INDEXES YIELD name, labelsOrTypes, properties WHERE type <> 'LOOKUP'")
    names = {r["name"] for r in rows}
    required = {"field_name_idx", "change_changed_at_idx", "change_table_name_idx"}
    missing = required - names
    assert not missing, f"missing indexes: {missing}; got: {names}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/infra/test_neo4j_init.py -v`
Expected: FAIL — no constraints / indexes exist yet on a fresh Neo4j.

- [ ] **Step 3: Implement `init-scripts/05_neo4j_init.py`**

```python
"""05_neo4j_init.py — create constraints and indexes on the metadata graph.

Idempotent: all statements use `IF NOT EXISTS`. Safe to re-run.

Run from repo root:
    python init-scripts/05_neo4j_init.py
"""
from __future__ import annotations

import sys

from backend.metadata.graph import run_query


CONSTRAINTS = [
    "CREATE CONSTRAINT table_id_unique IF NOT EXISTS FOR (t:Table) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT table_name_unique IF NOT EXISTS FOR (t:Table) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT field_id_unique IF NOT EXISTS FOR (f:Field) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT change_id_unique IF NOT EXISTS FOR (c:Change) REQUIRE c.id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX field_name_idx IF NOT EXISTS FOR (f:Field) ON (f.name)",
    "CREATE INDEX change_changed_at_idx IF NOT EXISTS FOR (c:Change) ON (c.changed_at)",
    "CREATE INDEX change_table_name_idx IF NOT EXISTS FOR (c:Change) ON (c.table_name)",
]


def main() -> int:
    for stmt in CONSTRAINTS + INDEXES:
        print(f"executing: {stmt}")
        run_query(stmt)
    print("Neo4j schema initialized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the script and re-run the test**

Run:

```bash
python init-scripts/05_neo4j_init.py
pytest tests/infra/test_neo4j_init.py -v
```

Expected: script prints 7 `executing:` lines + `Neo4j schema initialized.`; test passes.

- [ ] **Step 5: Commit**

```bash
git add init-scripts/05_neo4j_init.py tests/infra/test_neo4j_init.py
git commit -m "feat(infra): 05_neo4j_init.py + P1-5b constraint/index acceptance"
```

---

## Task 3: Seed data definition — `backend/seed/tables.py`

**Files:**
- Create: `backend/seed/tables.py`
- Create: `tests/api/test_seed_data.py`

- [ ] **Step 1: Write the failing test**

`tests/api/test_seed_data.py`:

```python
"""Sanity-check the SEED_TABLES + SEED_LINEAGE constants — they're the single source
of truth used by 06_neo4j_seed.py, 07_export_yaml.py, and several acceptance tests."""
import pytest

from backend.seed.tables import SEED_TABLES, SEED_LINEAGE, LAYER_PRIORITY


def test_ten_tables():
    assert len(SEED_TABLES) == 10
    names = {t["name"] for t in SEED_TABLES}
    assert names == {
        "ods_ue_signal", "ods_gnb_alarm",
        "dwd_session_qos", "dwd_ho_event",
        "dws_cell_hourly", "dws_area_traffic",
        "ads_cell_profile", "ads_neighbor_pair",
        "eval_user_score", "eval_net_health",
    }


def test_field_counts_around_seventy():
    total = sum(len(t["fields"]) for t in SEED_TABLES)
    assert 60 <= total <= 80, f"expected ~70 fields total, got {total}"


def test_every_lineage_edge_references_real_fields():
    field_keys = {
        (t["name"], f["name"]) for t in SEED_TABLES for f in t["fields"]
    }
    for edge in SEED_LINEAGE:
        src = (edge["from_table"], edge["from_field"])
        dst = (edge["to_table"], edge["to_field"])
        assert src in field_keys, f"lineage from {src} references unknown field"
        assert dst in field_keys, f"lineage to {dst} references unknown field"


def test_layer_priority_complete():
    assert LAYER_PRIORITY == {"ODS": 1, "DWD": 2, "DWS": 3, "ADS": 4, "EVAL": 5}
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/api/test_seed_data.py -v`
Expected: FAIL — `backend.seed.tables` does not exist.

- [ ] **Step 3: Implement `backend/seed/tables.py`**

```python
"""Single source of truth for the 10 seed tables, ~65 fields, and ~45 lineage edges.

Used by:
- init-scripts/06_neo4j_seed.py — writes nodes + relationships to Neo4j
- init-scripts/07_export_yaml.py — materializes metadata-yaml/L*-*/ *.yaml
- tests/api/test_seed_data.py — invariants
- tests/api/test_lineage.py — P1-7 expectations

Field schema:
    {"name", "type", "nullable", "partition", "expression" (optional), "description"}
"""
from __future__ import annotations

LAYER_PRIORITY = {"ODS": 1, "DWD": 2, "DWS": 3, "ADS": 4, "EVAL": 5}


SEED_TABLES: list[dict] = [
    # ---- L1 ODS ----
    {
        "name": "ods_ue_signal",
        "layer": "ODS",
        "storage_type": "KAFKA",
        "description": "UE 信号采样原始流",
        "fields": [
            {"name": "imsi",      "type": "STRING",    "nullable": False, "partition": False, "description": "用户标识 (PII)"},
            {"name": "cell_id",   "type": "STRING",    "nullable": False, "partition": False, "description": "小区标识"},
            {"name": "rsrp",      "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "参考信号接收功率 (dBm), 值域 [-140,-44]"},
            {"name": "rsrq",      "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "参考信号接收质量 (dB)"},
            {"name": "sinr",      "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "信噪比 (dB), 值域 [-20,30]"},
            {"name": "timestamp", "type": "TIMESTAMP", "nullable": False, "partition": True,  "description": "采样时刻"},
        ],
    },
    {
        "name": "ods_gnb_alarm",
        "layer": "ODS",
        "storage_type": "KAFKA",
        "description": "基站告警原始流",
        "fields": [
            {"name": "gnb_id",     "type": "STRING",    "nullable": False, "partition": False, "description": "基站标识"},
            {"name": "alarm_type", "type": "STRING",    "nullable": False, "partition": False, "description": "告警类型枚举"},
            {"name": "severity",   "type": "INT",       "nullable": False, "partition": False, "description": "严重度 1..5"},
            {"name": "alarm_time", "type": "TIMESTAMP", "nullable": False, "partition": True,  "description": "告警时刻"},
            {"name": "duration",   "type": "BIGINT",    "nullable": True,  "partition": False, "description": "持续秒数"},
        ],
    },
    # ---- L2 DWD ----
    {
        "name": "dwd_session_qos",
        "layer": "DWD",
        "storage_type": "HIVE",
        "description": "会话级 QoS 明细",
        "fields": [
            {"name": "session_id",  "type": "STRING", "nullable": False, "partition": False, "description": "会话标识"},
            {"name": "imsi",        "type": "STRING", "nullable": False, "partition": False, "description": "用户标识",
             "expression": "passthrough", "_upstream": [("ods_ue_signal", "imsi")]},
            {"name": "avg_rsrp",    "type": "DOUBLE", "nullable": True,  "partition": False, "description": "会话平均 RSRP",
             "expression": "AVG(rsrp)", "_upstream": [("ods_ue_signal", "rsrp")]},
            {"name": "avg_rsrq",    "type": "DOUBLE", "nullable": True,  "partition": False, "description": "会话平均 RSRQ",
             "expression": "AVG(rsrq)", "_upstream": [("ods_ue_signal", "rsrq")]},
            {"name": "avg_sinr",    "type": "DOUBLE", "nullable": True,  "partition": False, "description": "会话平均 SINR",
             "expression": "AVG(sinr)", "_upstream": [("ods_ue_signal", "sinr")]},
            {"name": "packet_loss", "type": "DOUBLE", "nullable": True,  "partition": False, "description": "丢包率"},
            {"name": "latency",     "type": "DOUBLE", "nullable": True,  "partition": False, "description": "端到端时延 (ms)"},
            {"name": "throughput",  "type": "DOUBLE", "nullable": True,  "partition": False, "description": "吞吐量 (Mbps)"},
            {"name": "drop_flag",   "type": "INT",    "nullable": False, "partition": False, "description": "掉话标记 0/1"},
        ],
    },
    {
        "name": "dwd_ho_event",
        "layer": "DWD",
        "storage_type": "HIVE",
        "description": "切换事件明细",
        "fields": [
            {"name": "imsi",        "type": "STRING", "nullable": False, "partition": False, "description": "用户标识",
             "expression": "passthrough", "_upstream": [("ods_ue_signal", "imsi")]},
            {"name": "source_cell", "type": "STRING", "nullable": False, "partition": False, "description": "源小区",
             "expression": "passthrough", "_upstream": [("ods_ue_signal", "cell_id")]},
            {"name": "target_cell", "type": "STRING", "nullable": False, "partition": False, "description": "目标小区"},
            {"name": "ho_type",     "type": "STRING", "nullable": False, "partition": False, "description": "切换类型"},
            {"name": "ho_result",   "type": "STRING", "nullable": False, "partition": False, "description": "SUCCESS/FAIL"},
            {"name": "ho_cause",    "type": "STRING", "nullable": True,  "partition": False, "description": "失败原因"},
            {"name": "ho_latency",  "type": "DOUBLE", "nullable": True,  "partition": False, "description": "切换时延 (ms)"},
        ],
    },
    # ---- L3 DWS ----
    {
        "name": "dws_cell_hourly",
        "layer": "DWS",
        "storage_type": "HIVE",
        "description": "小区小时粒度汇总指标",
        "fields": [
            {"name": "cell_id",         "type": "STRING",    "nullable": False, "partition": False, "description": "小区标识",
             "expression": "passthrough", "_upstream": [("dwd_session_qos", "imsi")]},
            {"name": "hour_bucket",     "type": "TIMESTAMP", "nullable": False, "partition": True,  "description": "小时窗口起点"},
            {"name": "avg_rsrp",        "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "小时均 RSRP",
             "expression": "AVG(rsrp)", "_upstream": [("dwd_session_qos", "avg_rsrp")]},
            {"name": "avg_sinr",        "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "小时均 SINR",
             "expression": "AVG(sinr)", "_upstream": [("dwd_session_qos", "avg_sinr")]},
            {"name": "total_sessions",  "type": "BIGINT",    "nullable": True,  "partition": False, "description": "会话数",
             "expression": "COUNT(DISTINCT session_id)", "_upstream": [("dwd_session_qos", "session_id")]},
            {"name": "drop_rate",       "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "掉话率",
             "expression": "SUM(drop_flag)/COUNT(*)", "_upstream": [("dwd_session_qos", "drop_flag")]},
            {"name": "avg_throughput",  "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "平均吞吐",
             "expression": "AVG(throughput)", "_upstream": [("dwd_session_qos", "throughput")]},
            {"name": "ho_success_rate", "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "切换成功率",
             "expression": "AVG(CASE WHEN ho_result='SUCCESS' THEN 1 ELSE 0 END)",
             "_upstream": [("dwd_ho_event", "ho_result")]},
        ],
    },
    {
        "name": "dws_area_traffic",
        "layer": "DWS",
        "storage_type": "HIVE",
        "description": "区域小时流量汇总",
        "fields": [
            {"name": "area_id",          "type": "STRING",    "nullable": False, "partition": False, "description": "区域标识"},
            {"name": "hour_bucket",      "type": "TIMESTAMP", "nullable": False, "partition": True,  "description": "小时窗口"},
            {"name": "total_throughput", "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "总吞吐",
             "expression": "SUM(throughput)", "_upstream": [("dwd_session_qos", "throughput")]},
            {"name": "active_users",     "type": "BIGINT",    "nullable": True,  "partition": False, "description": "活跃用户",
             "expression": "COUNT(DISTINCT imsi)", "_upstream": [("dwd_session_qos", "imsi")]},
            {"name": "avg_latency",      "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "平均时延",
             "expression": "AVG(latency)", "_upstream": [("dwd_session_qos", "latency")]},
            {"name": "peak_throughput",  "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "峰值吞吐",
             "expression": "MAX(throughput)", "_upstream": [("dwd_session_qos", "throughput")]},
        ],
    },
    # ---- L4 ADS ----
    {
        "name": "ads_cell_profile",
        "layer": "ADS",
        "storage_type": "STARROCKS",
        "description": "小区日画像 KPI",
        "fields": [
            {"name": "cell_id",         "type": "STRING", "nullable": False, "partition": False, "description": "小区标识",
             "expression": "passthrough", "_upstream": [("dws_cell_hourly", "cell_id")]},
            {"name": "date",            "type": "DATE",   "nullable": False, "partition": True,  "description": "日期"},
            {"name": "coverage_score",  "type": "DOUBLE", "nullable": True,  "partition": False, "description": "覆盖得分 0-100",
             "expression": "weighted(avg_rsrp)", "_upstream": [("dws_cell_hourly", "avg_rsrp")]},
            {"name": "capacity_score",  "type": "DOUBLE", "nullable": True,  "partition": False, "description": "容量得分",
             "expression": "weighted(avg_throughput)", "_upstream": [("dws_cell_hourly", "avg_throughput")]},
            {"name": "stability_score", "type": "DOUBLE", "nullable": True,  "partition": False, "description": "稳定性得分",
             "expression": "1 - drop_rate", "_upstream": [("dws_cell_hourly", "drop_rate")]},
            {"name": "composite_kpi",   "type": "DOUBLE", "nullable": True,  "partition": False, "description": "复合 KPI",
             "expression": "0.4*coverage_score + 0.3*capacity_score + 0.3*stability_score"},
        ],
    },
    {
        "name": "ads_neighbor_pair",
        "layer": "ADS",
        "storage_type": "STARROCKS",
        "description": "邻区切换对统计",
        "fields": [
            {"name": "source_cell",        "type": "STRING", "nullable": False, "partition": False, "description": "源小区",
             "expression": "passthrough", "_upstream": [("dwd_ho_event", "source_cell")]},
            {"name": "target_cell",        "type": "STRING", "nullable": False, "partition": False, "description": "目标小区",
             "expression": "passthrough", "_upstream": [("dwd_ho_event", "target_cell")]},
            {"name": "ho_count",           "type": "BIGINT", "nullable": True,  "partition": False, "description": "切换次数",
             "expression": "COUNT(*)", "_upstream": [("dwd_ho_event", "ho_result")]},
            {"name": "ho_success_rate",    "type": "DOUBLE", "nullable": True,  "partition": False, "description": "切换成功率",
             "expression": "AVG(CASE WHEN ho_result='SUCCESS' THEN 1 ELSE 0 END)",
             "_upstream": [("dwd_ho_event", "ho_result")]},
            {"name": "avg_ho_latency",     "type": "DOUBLE", "nullable": True,  "partition": False, "description": "平均切换时延",
             "expression": "AVG(ho_latency)", "_upstream": [("dwd_ho_event", "ho_latency")]},
            {"name": "recommend_priority", "type": "INT",    "nullable": True,  "partition": False, "description": "邻区优先级建议"},
        ],
    },
    # ---- L5 EVAL ----
    {
        "name": "eval_user_score",
        "layer": "EVAL",
        "storage_type": "STARROCKS",
        "description": "用户日 QoE 评分",
        "fields": [
            {"name": "imsi",               "type": "STRING", "nullable": False, "partition": False, "description": "用户标识"},
            {"name": "date",               "type": "DATE",   "nullable": False, "partition": True,  "description": "日期"},
            {"name": "qoe_score",          "type": "DOUBLE", "nullable": True,  "partition": False, "description": "复合 QoE 评分 0-100",
             "expression": "0.5*signal_quality + 0.3*mobility_score + 0.2*service_continuity"},
            {"name": "signal_quality",     "type": "DOUBLE", "nullable": True,  "partition": False, "description": "信号质量分量",
             "expression": "f(coverage_score)", "_upstream": [("ads_cell_profile", "coverage_score")]},
            {"name": "mobility_score",     "type": "DOUBLE", "nullable": True,  "partition": False, "description": "移动性分量",
             "expression": "f(capacity_score)", "_upstream": [("ads_cell_profile", "capacity_score")]},
            {"name": "service_continuity", "type": "DOUBLE", "nullable": True,  "partition": False, "description": "业务连续性分量",
             "expression": "f(stability_score)", "_upstream": [("ads_cell_profile", "stability_score")]},
        ],
    },
    {
        "name": "eval_net_health",
        "layer": "EVAL",
        "storage_type": "STARROCKS",
        "description": "区域日网络健康指数",
        "fields": [
            {"name": "area_id",                 "type": "STRING", "nullable": False, "partition": False, "description": "区域标识"},
            {"name": "date",                    "type": "DATE",   "nullable": False, "partition": True,  "description": "日期"},
            {"name": "health_index",            "type": "DOUBLE", "nullable": True,  "partition": False, "description": "健康指数",
             "expression": "0.5*(1-alarm_severity_weighted) + 0.5*health_from_qoe"},
            {"name": "alarm_severity_weighted", "type": "DOUBLE", "nullable": True,  "partition": False, "description": "加权告警严重度",
             "expression": "SUM(severity*duration)", "_upstream": [("ods_gnb_alarm", "severity"), ("ods_gnb_alarm", "duration")]},
            {"name": "user_complaint_ratio",    "type": "DOUBLE", "nullable": True,  "partition": False, "description": "用户投诉比",
             "expression": "f(qoe_score)", "_upstream": [("eval_user_score", "qoe_score")]},
            {"name": "degradation_trend",       "type": "DOUBLE", "nullable": True,  "partition": False, "description": "退化趋势",
             "expression": "trend(total_throughput)", "_upstream": [("dws_area_traffic", "total_throughput")]},
        ],
    },
]


def _derive_lineage() -> list[dict]:
    """Flatten the _upstream hints embedded in each field into explicit edges."""
    edges: list[dict] = []
    for tbl in SEED_TABLES:
        for field in tbl["fields"]:
            for upstream_table, upstream_field in field.get("_upstream", []):
                edges.append({
                    "from_table": upstream_table,
                    "from_field": upstream_field,
                    "to_table": tbl["name"],
                    "to_field": field["name"],
                    "transform_expr": field.get("expression", "passthrough"),
                })
    return edges


SEED_LINEAGE: list[dict] = _derive_lineage()
```

- [ ] **Step 4: Re-run the test**

Run: `pytest tests/api/test_seed_data.py -v`
Expected: PASS — 10 tables, field count in 60-80, all lineage edges reference real fields.

- [ ] **Step 5: Commit**

```bash
git add backend/seed/tables.py tests/api/test_seed_data.py
git commit -m "feat(backend): seed-data source of truth (10 tables, ~65 fields, lineage)"
```

---

## Task 4: Neo4j seed script — `06_neo4j_seed.py`

**Files:**
- Create: `init-scripts/06_neo4j_seed.py`
- Create: `tests/infra/test_neo4j_seed.py`

- [ ] **Step 1: Write the failing P1-5 test**

`tests/infra/test_neo4j_seed.py`:

```python
"""P1-5 (Neo4j part): MATCH (t:Table) RETURN count(t) == 10 after seeding."""
import pytest

from backend.metadata.graph import run_query


@pytest.mark.infra
def test_p1_5_table_count_is_ten():
    rows = run_query("MATCH (t:Table) RETURN count(t) AS n")
    assert rows[0]["n"] == 10


@pytest.mark.infra
def test_field_count_around_seventy():
    rows = run_query("MATCH (f:Field) RETURN count(f) AS n")
    assert 60 <= rows[0]["n"] <= 80


@pytest.mark.infra
def test_has_field_edges_cover_all_fields():
    rows = run_query("""
        MATCH (t:Table)-[:HAS_FIELD]->(f:Field)
        RETURN count(*) AS n
    """)
    field_total = run_query("MATCH (f:Field) RETURN count(f) AS n")[0]["n"]
    assert rows[0]["n"] == field_total


@pytest.mark.infra
def test_derives_from_edges_present():
    rows = run_query("""
        MATCH ()-[r:DERIVES_FROM]->()
        RETURN count(r) AS n
    """)
    assert rows[0]["n"] >= 30
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/infra/test_neo4j_seed.py -v`
Expected: FAIL — graph is empty after `05_neo4j_init.py` (only schema, no data).

- [ ] **Step 3: Implement `init-scripts/06_neo4j_seed.py`**

```python
"""06_neo4j_seed.py — write 10 tables + ~65 fields + ~45 lineage edges to Neo4j.

Idempotent: MERGE used everywhere; safe to re-run. Re-running with edited
backend.seed.tables will add new nodes/edges but won't remove stale ones —
for a clean re-seed, wipe Neo4j first (MATCH (n) DETACH DELETE n).
"""
from __future__ import annotations

import sys
import uuid

from backend.metadata.graph import run_query
from backend.seed.tables import LAYER_PRIORITY, SEED_TABLES, SEED_LINEAGE


def seed_tables_and_fields() -> tuple[int, int]:
    table_count = 0
    field_count = 0
    for tbl in SEED_TABLES:
        run_query(
            """
            MERGE (t:Table {name: $name})
            ON CREATE SET t.id = $id,
                          t.layer = $layer,
                          t.layer_priority = $layer_priority,
                          t.storage_type = $storage_type,
                          t.description = $description
            """,
            id=str(uuid.uuid4()),
            name=tbl["name"],
            layer=tbl["layer"],
            layer_priority=LAYER_PRIORITY[tbl["layer"]],
            storage_type=tbl["storage_type"],
            description=tbl["description"],
        )
        table_count += 1
        for field in tbl["fields"]:
            run_query(
                """
                MATCH (t:Table {name: $table})
                MERGE (t)-[:HAS_FIELD]->(f:Field {name: $name})
                ON CREATE SET f.id = $id,
                              f.field_type = $field_type,
                              f.is_nullable = $is_nullable,
                              f.is_partition = $is_partition,
                              f.expression = $expression,
                              f.description = $description,
                              f.version = 1,
                              f.previous_expr = '[]'
                """,
                table=tbl["name"],
                id=str(uuid.uuid4()),
                name=field["name"],
                field_type=field["type"],
                is_nullable=field["nullable"],
                is_partition=field["partition"],
                expression=field.get("expression", ""),
                description=field["description"],
            )
            field_count += 1
    return table_count, field_count


def seed_lineage() -> int:
    edge_count = 0
    for edge in SEED_LINEAGE:
        run_query(
            """
            MATCH (t_src:Table {name: $src_t})-[:HAS_FIELD]->(f_src:Field {name: $src_f})
            MATCH (t_dst:Table {name: $dst_t})-[:HAS_FIELD]->(f_dst:Field {name: $dst_f})
            MERGE (f_dst)-[r:DERIVES_FROM]->(f_src)
            ON CREATE SET r.transform_expr = $transform_expr,
                          r.created_at = datetime()
            """,
            src_t=edge["from_table"],
            src_f=edge["from_field"],
            dst_t=edge["to_table"],
            dst_f=edge["to_field"],
            transform_expr=edge["transform_expr"],
        )
        edge_count += 1
    return edge_count


def main() -> int:
    t, f = seed_tables_and_fields()
    e = seed_lineage()
    print(f"Seeded {t} tables, {f} fields, {e} lineage edges.")
    return 0 if (t == 10 and 60 <= f <= 80) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the script and re-run tests**

Run:

```bash
python init-scripts/06_neo4j_seed.py
pytest tests/infra/test_neo4j_seed.py -v
```

Expected: script prints `Seeded 10 tables, 65 fields, N lineage edges.` (N depends on `_upstream` hints, ~30-50); tests pass.

- [ ] **Step 5: Commit**

```bash
git add init-scripts/06_neo4j_seed.py tests/infra/test_neo4j_seed.py
git commit -m "feat(infra): 06_neo4j_seed.py + P1-5 Neo4j seed acceptance"
```

---

## Task 5: YAML export — `07_export_yaml.py`

**Files:**
- Create: `init-scripts/07_export_yaml.py`
- Create: `tests/infra/test_yaml_export.py`

- [ ] **Step 1: Write the failing P1-5 (YAML) test**

`tests/infra/test_yaml_export.py`:

```python
"""P1-5 (YAML part): metadata-yaml/L*-*/ contains 10 yaml files matching seed."""
import pathlib

import pytest
import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
METADATA_YAML = REPO_ROOT / "metadata-yaml"

EXPECTED = {
    "L1-ODS": ["ods_ue_signal", "ods_gnb_alarm"],
    "L2-DWD": ["dwd_session_qos", "dwd_ho_event"],
    "L3-DWS": ["dws_cell_hourly", "dws_area_traffic"],
    "L4-ADS": ["ads_cell_profile", "ads_neighbor_pair"],
    "L5-EVAL": ["eval_user_score", "eval_net_health"],
}


@pytest.mark.infra
def test_p1_5_yaml_files_exist_per_layer():
    for layer_dir, table_names in EXPECTED.items():
        for name in table_names:
            path = METADATA_YAML / layer_dir / f"{name}.yaml"
            assert path.exists(), f"missing {path}"


@pytest.mark.infra
def test_yaml_dws_cell_hourly_has_expected_fields():
    path = METADATA_YAML / "L3-DWS" / "dws_cell_hourly.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert payload["table_name"] == "dws_cell_hourly"
    assert payload["layer"] == "DWS"
    assert payload["storage_type"] == "HIVE"
    field_names = {f["name"] for f in payload["fields"]}
    assert {"cell_id", "hour_bucket", "avg_rsrp", "avg_sinr", "drop_rate", "ho_success_rate"}.issubset(field_names)
    avg_rsrp = next(f for f in payload["fields"] if f["name"] == "avg_rsrp")
    assert avg_rsrp.get("expression") == "AVG(rsrp)"
    assert {"table": "dwd_session_qos", "field": "avg_rsrp"} in avg_rsrp["upstream"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/infra/test_yaml_export.py -v`
Expected: FAIL — `metadata-yaml/` does not exist.

- [ ] **Step 3: Implement `init-scripts/07_export_yaml.py`**

```python
"""07_export_yaml.py — render Neo4j graph state as YAML副本 under metadata-yaml/.

Output structure:
    metadata-yaml/L1-ODS/ods_ue_signal.yaml
    metadata-yaml/L2-DWD/dwd_session_qos.yaml
    ...

This script reads from Neo4j (authoritative store), not from backend.seed.tables —
so it works after schema_evolve operations too.
"""
from __future__ import annotations

import pathlib
import sys

import yaml

from backend.config import get_settings
from backend.metadata.graph import run_query


LAYER_DIR = {"ODS": "L1-ODS", "DWD": "L2-DWD", "DWS": "L3-DWS", "ADS": "L4-ADS", "EVAL": "L5-EVAL"}


def fetch_tables() -> list[dict]:
    return run_query("""
        MATCH (t:Table)
        RETURN t.name AS name, t.layer AS layer, t.layer_priority AS layer_priority,
               t.storage_type AS storage_type, t.description AS description
        ORDER BY t.layer_priority, t.name
    """)


def fetch_fields(table_name: str) -> list[dict]:
    rows = run_query("""
        MATCH (t:Table {name: $name})-[:HAS_FIELD]->(f:Field)
        OPTIONAL MATCH (f)-[r:DERIVES_FROM]->(up:Field)<-[:HAS_FIELD]-(up_t:Table)
        WITH f, collect(DISTINCT {table: up_t.name, field: up.name}) AS upstream
        RETURN f.name AS name, f.field_type AS type, f.is_nullable AS nullable,
               f.is_partition AS partition, f.expression AS expression,
               f.description AS description, upstream
        ORDER BY f.name
    """, name=table_name)
    # Normalize: drop empty `[{table: null, field: null}]` artifacts when no upstream
    for row in rows:
        row["upstream"] = [u for u in row["upstream"] if u["table"] and u["field"]]
    return rows


def write_yaml(out_dir: pathlib.Path, table: dict) -> pathlib.Path:
    layer_dir = out_dir / LAYER_DIR[table["layer"]]
    layer_dir.mkdir(parents=True, exist_ok=True)
    path = layer_dir / f"{table['name']}.yaml"
    fields = fetch_fields(table["name"])
    payload = {
        "table_name": table["name"],
        "layer": table["layer"],
        "layer_priority": table["layer_priority"],
        "description": table["description"],
        "storage_type": table["storage_type"],
        "fields": [
            {
                "name": f["name"],
                "type": f["type"],
                "nullable": f["nullable"],
                "partition": f["partition"],
                **({"expression": f["expression"]} if f["expression"] else {}),
                "description": f["description"],
                **({"upstream": f["upstream"]} if f["upstream"] else {}),
            }
            for f in fields
        ],
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def main() -> int:
    out = pathlib.Path(get_settings().metadata_yaml_dir)
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    for table in fetch_tables():
        write_yaml(out, table)
        count += 1
    print(f"Wrote {count} YAML files under {out}/")
    return 0 if count == 10 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the script and re-run tests**

Run:

```bash
python init-scripts/07_export_yaml.py
pytest tests/infra/test_yaml_export.py -v
```

Expected: script prints `Wrote 10 YAML files under metadata-yaml/`; tests pass.

- [ ] **Step 5: Track YAML output in git**

The `metadata-yaml/` tree is now valuable as a versioned snapshot. Don't gitignore it.

Run:

```bash
git add metadata-yaml/
```

Verify there are exactly 10 files staged.

- [ ] **Step 6: Commit**

```bash
git add init-scripts/07_export_yaml.py tests/infra/test_yaml_export.py metadata-yaml/
git commit -m "feat(infra): 07_export_yaml.py + P1-5 YAML export acceptance"
```

---

## Task 6: Pydantic models for the wire API

**Files:**
- Create: `backend/metadata/models.py`
- Create: `tests/api/test_models.py`

- [ ] **Step 1: Write the failing test**

`tests/api/test_models.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/api/test_models.py -v`
Expected: FAIL — `backend.metadata.models` doesn't exist.

- [ ] **Step 3: Implement `backend/metadata/models.py`**

```python
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
    from_table: str
    from_field: str
    to_table: str
    to_field: str
    transform_expr: str


class LineageResponse(BaseModel):
    root_table: str
    direction: Literal["up", "down"]
    depth: int
    edges: list[LineageEdge]
```

- [ ] **Step 4: Re-run the test**

Run: `pytest tests/api/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/metadata/models.py tests/api/test_models.py
git commit -m "feat(backend): pydantic models for metadata API"
```

---

## Task 7: Metadata service — CRUD + lineage Cypher

**Files:**
- Create: `backend/metadata/service.py`
- Create: `tests/api/test_metadata_service.py`

- [ ] **Step 1: Write the failing test**

`tests/api/test_metadata_service.py`:

```python
"""Service-level tests — exercise the Cypher implementations directly.
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
    # P1-7 expects at least dws_cell_hourly and dws_area_traffic appear downstream
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
    # ods_ue_signal.rsrp has downstream dwd_session_qos.avg_rsrp
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/api/test_metadata_service.py -v`
Expected: FAIL — `backend.metadata.service` does not exist.

- [ ] **Step 3: Implement `backend/metadata/service.py`**

```python
"""Cypher implementations for table/field CRUD + lineage queries.

This module is the single source of truth for graph mutations and reads.
Both HTTP routes (backend/api/metadata.py) and future Agent tools depend on it.
"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from backend.metadata.graph import run_query
from backend.metadata.models import (
    CreateFieldRequest,
    CreateTableRequest,
    FieldResponse,
    LineageEdge,
    TableResponse,
    TableSummary,
    UpdateFieldRequest,
    UpstreamRef,
)


LAYER_PRIORITY = {"ODS": 1, "DWD": 2, "DWS": 3, "ADS": 4, "EVAL": 5}


class TableNotFound(Exception):
    pass


class FieldNotFound(Exception):
    pass


class FieldHasDownstream(Exception):
    def __init__(self, downstream: list[tuple[str, str]]):
        self.downstream = downstream
        super().__init__(f"field has {len(downstream)} downstream dependents")


class CycleDetected(Exception):
    pass


# ----------------------- Tables -----------------------

def list_tables(layer: Optional[str] = None, search: Optional[str] = None) -> list[TableSummary]:
    cypher_filters = []
    params: dict = {}
    if layer:
        cypher_filters.append("t.layer = $layer")
        params["layer"] = layer
    if search:
        cypher_filters.append("toLower(t.name) CONTAINS toLower($search) OR toLower(t.description) CONTAINS toLower($search)")
        params["search"] = search
    where = ("WHERE " + " AND ".join(cypher_filters)) if cypher_filters else ""
    rows = run_query(
        f"""
        MATCH (t:Table)
        {where}
        OPTIONAL MATCH (t)-[:HAS_FIELD]->(f:Field)
        RETURN t.id AS id, t.name AS name, t.layer AS layer, t.layer_priority AS layer_priority,
               t.storage_type AS storage_type, t.description AS description, count(f) AS field_count
        ORDER BY t.layer_priority, t.name
        """,
        **params,
    )
    return [TableSummary(**r) for r in rows]


def get_table_by_name(name: str, optional: bool = False) -> Optional[TableResponse]:
    rows = run_query(
        """
        MATCH (t:Table {name: $name})
        OPTIONAL MATCH (t)-[:HAS_FIELD]->(f:Field)
        OPTIONAL MATCH (f)-[:DERIVES_FROM]->(up:Field)<-[:HAS_FIELD]-(up_t:Table)
        WITH t, f, collect(DISTINCT {table: up_t.name, field: up.name}) AS upstream
        WITH t, collect({
            id: f.id, name: f.name, field_type: f.field_type,
            is_nullable: f.is_nullable, is_partition: f.is_partition,
            expression: f.expression, description: f.description,
            version: f.version, upstream: upstream
        }) AS fields
        RETURN t.id AS id, t.name AS name, t.layer AS layer, t.layer_priority AS layer_priority,
               t.storage_type AS storage_type, t.description AS description, fields
        """,
        name=name,
    )
    if not rows:
        if optional:
            return None
        raise TableNotFound(name)
    row = rows[0]
    # Clean fields: when table has zero fields, OPTIONAL MATCH yields a single {None,None} placeholder.
    raw_fields = [f for f in row["fields"] if f.get("name") is not None]
    fields = []
    for f in raw_fields:
        upstream = [UpstreamRef(**u) for u in f["upstream"] if u["table"] is not None]
        fields.append(FieldResponse(
            id=f["id"], name=f["name"], field_type=f["field_type"],
            is_nullable=f["is_nullable"], is_partition=f["is_partition"],
            expression=f["expression"] or None, description=f["description"] or "",
            version=f["version"], upstream=upstream,
        ))
    return TableResponse(
        id=row["id"], name=row["name"], layer=row["layer"], layer_priority=row["layer_priority"],
        storage_type=row["storage_type"], description=row["description"], fields=fields,
    )


def get_table_by_id(table_id: str) -> TableResponse:
    rows = run_query("MATCH (t:Table {id: $id}) RETURN t.name AS name", id=table_id)
    if not rows:
        raise TableNotFound(table_id)
    return get_table_by_name(rows[0]["name"])


def create_table(req: CreateTableRequest) -> TableResponse:
    table_id = str(uuid.uuid4())
    run_query(
        """
        CREATE (t:Table {
            id: $id, name: $name, layer: $layer, layer_priority: $layer_priority,
            storage_type: $storage_type, description: $description
        })
        """,
        id=table_id, name=req.name, layer=req.layer,
        layer_priority=LAYER_PRIORITY[req.layer],
        storage_type=req.storage_type, description=req.description,
    )
    return get_table_by_name(req.name)


def delete_table(name: str) -> None:
    run_query("MATCH (t:Table {name: $name}) DETACH DELETE t", name=name)


# ----------------------- Fields -----------------------

def create_field(req: CreateFieldRequest) -> FieldResponse:
    field_id = str(uuid.uuid4())
    run_query(
        """
        MATCH (t:Table {id: $table_id})
        CREATE (t)-[:HAS_FIELD]->(f:Field {
            id: $id, name: $name, field_type: $field_type,
            is_nullable: $is_nullable, is_partition: $is_partition,
            expression: $expression, description: $description,
            version: 1, previous_expr: '[]'
        })
        """,
        table_id=req.table_id, id=field_id, name=req.name, field_type=req.field_type,
        is_nullable=req.is_nullable, is_partition=req.is_partition,
        expression=req.expression or "", description=req.description,
    )
    for up in req.upstream:
        run_query(
            """
            MATCH (f:Field {id: $field_id})
            MATCH (t_up:Table {name: $up_t})-[:HAS_FIELD]->(f_up:Field {name: $up_f})
            MERGE (f)-[r:DERIVES_FROM]->(f_up)
            ON CREATE SET r.transform_expr = $transform_expr, r.created_at = datetime()
            """,
            field_id=field_id, up_t=up.table, up_f=up.field,
            transform_expr=req.expression or "passthrough",
        )
    return _load_field(field_id)


def _load_field(field_id: str) -> FieldResponse:
    rows = run_query(
        """
        MATCH (f:Field {id: $id})
        OPTIONAL MATCH (f)-[:DERIVES_FROM]->(up:Field)<-[:HAS_FIELD]-(up_t:Table)
        WITH f, collect(DISTINCT {table: up_t.name, field: up.name}) AS upstream
        RETURN f.id AS id, f.name AS name, f.field_type AS field_type,
               f.is_nullable AS is_nullable, f.is_partition AS is_partition,
               f.expression AS expression, f.description AS description,
               f.version AS version, upstream
        """,
        id=field_id,
    )
    if not rows:
        raise FieldNotFound(field_id)
    r = rows[0]
    upstream = [UpstreamRef(**u) for u in r["upstream"] if u["table"] is not None]
    return FieldResponse(
        id=r["id"], name=r["name"], field_type=r["field_type"],
        is_nullable=r["is_nullable"], is_partition=r["is_partition"],
        expression=r["expression"] or None, description=r["description"] or "",
        version=r["version"], upstream=upstream,
    )


def update_field_expression(field_id: str, new_expression: str) -> FieldResponse:
    rows = run_query("MATCH (f:Field {id: $id}) RETURN f.expression AS expr, f.version AS v, f.previous_expr AS prev", id=field_id)
    if not rows:
        raise FieldNotFound(field_id)
    old_expr = rows[0]["expr"]
    old_version = rows[0]["v"]
    history = json.loads(rows[0]["prev"] or "[]")
    history.append({"v": old_version, "expr": old_expr})
    run_query(
        """
        MATCH (f:Field {id: $id})
        SET f.expression = $expr, f.version = f.version + 1, f.previous_expr = $history
        """,
        id=field_id, expr=new_expression, history=json.dumps(history),
    )
    return _load_field(field_id)


def update_field(field_id: str, req: UpdateFieldRequest) -> FieldResponse:
    sets: list[str] = []
    params: dict = {"id": field_id}
    for attr, prop in [
        ("field_type", "field_type"), ("is_nullable", "is_nullable"),
        ("is_partition", "is_partition"), ("description", "description"),
    ]:
        value = getattr(req, attr)
        if value is not None:
            sets.append(f"f.{prop} = ${attr}")
            params[attr] = value
    if sets:
        run_query(f"MATCH (f:Field {{id: $id}}) SET {', '.join(sets)}", **params)
    if req.expression is not None:
        update_field_expression(field_id, req.expression)
    if req.upstream is not None:
        run_query("MATCH (f:Field {id: $id})-[r:DERIVES_FROM]->() DELETE r", id=field_id)
        for up in req.upstream:
            run_query(
                """
                MATCH (f:Field {id: $id})
                MATCH (t_up:Table {name: $up_t})-[:HAS_FIELD]->(f_up:Field {name: $up_f})
                MERGE (f)-[r:DERIVES_FROM]->(f_up)
                ON CREATE SET r.transform_expr = $expr, r.created_at = datetime()
                """,
                id=field_id, up_t=up.table, up_f=up.field,
                expr=req.expression or "passthrough",
            )
    return _load_field(field_id)


def delete_field(field_id: str) -> None:
    rows = run_query(
        """
        MATCH (f:Field {id: $id})
        OPTIONAL MATCH (downstream:Field)-[:DERIVES_FROM]->(f)
        OPTIONAL MATCH (down_t:Table)-[:HAS_FIELD]->(downstream)
        RETURN collect(DISTINCT [down_t.name, downstream.name]) AS downstream
        """,
        id=field_id,
    )
    if not rows:
        raise FieldNotFound(field_id)
    downstream = [(p[0], p[1]) for p in rows[0]["downstream"] if p and p[0] is not None]
    if downstream:
        raise FieldHasDownstream(downstream)
    run_query("MATCH (f:Field {id: $id}) DETACH DELETE f", id=field_id)


# ----------------------- Lineage -----------------------

def get_lineage(table: str, direction: str = "down", depth: int = 5) -> list[LineageEdge]:
    if direction not in ("up", "down"):
        raise ValueError(f"direction must be 'up' or 'down', got {direction!r}")
    if not 1 <= depth <= 5:
        raise ValueError(f"depth must be in [1,5], got {depth}")
    # `down` = follow DERIVES_FROM backward (i.e., find fields that derive FROM this table's fields).
    # `up`   = follow DERIVES_FROM forward (i.e., find fields that this table's fields are derived FROM).
    pattern = (
        f"MATCH (root_t:Table {{name: $name}})-[:HAS_FIELD]->(root_f:Field)<-[:DERIVES_FROM*1..{depth}]-(down_f:Field)<-[:HAS_FIELD]-(down_t:Table)"
        if direction == "down"
        else
        f"MATCH (root_t:Table {{name: $name}})-[:HAS_FIELD]->(root_f:Field)-[:DERIVES_FROM*1..{depth}]->(up_f:Field)<-[:HAS_FIELD]-(up_t:Table)"
    )
    cypher = pattern + " RETURN root_t.name AS root_t, root_f.name AS root_f, " + (
        "down_t.name AS other_t, down_f.name AS other_f"
        if direction == "down"
        else "up_t.name AS other_t, up_f.name AS other_f"
    )
    rows = run_query(cypher, name=table)
    seen: set[tuple] = set()
    edges: list[LineageEdge] = []
    for r in rows:
        if direction == "down":
            key = (r["root_t"], r["root_f"], r["other_t"], r["other_f"])
            if key in seen:
                continue
            seen.add(key)
            edges.append(LineageEdge(
                from_table=r["root_t"], from_field=r["root_f"],
                to_table=r["other_t"], to_field=r["other_f"], transform_expr="",
            ))
        else:
            key = (r["other_t"], r["other_f"], r["root_t"], r["root_f"])
            if key in seen:
                continue
            seen.add(key)
            edges.append(LineageEdge(
                from_table=r["other_t"], from_field=r["other_f"],
                to_table=r["root_t"], to_field=r["root_f"], transform_expr="",
            ))
    return edges
```

- [ ] **Step 4: Re-run the test**

Run: `pytest tests/api/test_metadata_service.py -v`
Expected: PASS — all 8 service-level tests pass against the seeded graph.

- [ ] **Step 5: Commit**

```bash
git add backend/metadata/service.py tests/api/test_metadata_service.py
git commit -m "feat(backend): metadata service — CRUD + lineage Cypher implementations"
```

---

## Task 8: FastAPI app + HTTP routes

**Files:**
- Create: `backend/api/metadata.py`
- Create: `backend/api/health.py`
- Create: `backend/main.py`
- Create: `tests/api/test_http_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

`tests/api/test_http_smoke.py`:

```python
"""Smoke test: FastAPI app boots, /api/health returns 200."""
from fastapi.testclient import TestClient

from backend.main import create_app


def test_health_endpoint_returns_ok():
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "neo4j" in body["components"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/api/test_http_smoke.py -v`
Expected: FAIL — `backend.main.create_app` does not exist.

- [ ] **Step 3: Implement `backend/api/health.py`**

```python
"""GET /api/health — Phase 1 slice 1b scope: only FastAPI + Neo4j.
Other components join in later slices as their subsystems land."""
import time

from fastapi import APIRouter

from backend.metadata.graph import run_query


router = APIRouter()
_BOOT_TS = time.monotonic()


@router.get("/api/health")
def health() -> dict:
    components: dict = {}
    try:
        start = time.perf_counter()
        run_query("RETURN 1")
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        node_count_rows = run_query("MATCH (n) RETURN count(n) AS n")
        components["neo4j"] = {
            "status": "ok",
            "latency_ms": latency_ms,
            "node_count": node_count_rows[0]["n"],
        }
        overall = "healthy"
    except Exception as e:
        components["neo4j"] = {"status": "error", "error": str(e)}
        overall = "degraded"
    return {
        "status": overall,
        "uptime_seconds": int(time.monotonic() - _BOOT_TS),
        "components": components,
    }
```

- [ ] **Step 4: Implement `backend/api/metadata.py`**

```python
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
    # Phase 1 scope: name is immutable, only layer/storage/description editable.
    table = service.get_table_by_id(table_id)
    if req.layer is not None or req.storage_type is not None or req.description is not None:
        service.run_query_update_table(table_id, req)  # see below
    return service.get_table_by_id(table_id)


@router.delete("/api/tables/{table_id}", status_code=204)
def delete_table_endpoint(table_id: str):
    table = service.get_table_by_id(table_id)
    # Reject if any field has downstream — same rule as delete_field, applied per table.
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
    direction: str = Query("down", regex="^(up|down)$"),
    depth: int = Query(5, ge=1, le=5),
):
    try:
        edges = service.get_lineage(table=table, direction=direction, depth=depth)
    except service.TableNotFound:
        raise HTTPException(status_code=404, detail="table not found")
    return LineageResponse(root_table=table, direction=direction, depth=depth, edges=edges)
```

> The `update_table` route references a helper `service.run_query_update_table` that the current service file does not yet define. Add it now to `backend/metadata/service.py`:

Append to `backend/metadata/service.py`:

```python
def run_query_update_table(table_id: str, req) -> None:
    sets: list[str] = []
    params: dict = {"id": table_id}
    if req.layer is not None:
        sets.append("t.layer = $layer")
        sets.append("t.layer_priority = $layer_priority")
        params["layer"] = req.layer
        params["layer_priority"] = LAYER_PRIORITY[req.layer]
    if req.storage_type is not None:
        sets.append("t.storage_type = $storage_type")
        params["storage_type"] = req.storage_type
    if req.description is not None:
        sets.append("t.description = $description")
        params["description"] = req.description
    if not sets:
        return
    run_query(f"MATCH (t:Table {{id: $id}}) SET {', '.join(sets)}", **params)
```

- [ ] **Step 5: Implement `backend/main.py`**

```python
"""FastAPI app factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api import health, metadata
from backend.metadata.graph import close_driver, get_driver


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eagerly verify Neo4j connectivity at startup
    get_driver()
    yield
    close_driver()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Wireless RNO Data Semantic Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(metadata.router, tags=["metadata"])
    return app


app = create_app()
```

- [ ] **Step 6: Run the smoke test**

Run: `pytest tests/api/test_http_smoke.py -v`
Expected: PASS — health endpoint returns `status=healthy`, neo4j component reachable.

- [ ] **Step 7: Boot the app locally and curl**

Run:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
sleep 3
curl -s http://localhost:8000/api/health | python -m json.tool
curl -s "http://localhost:8000/api/tables?layer=ODS" | python -m json.tool
kill %1
```

Expected: first call shows `"status":"healthy"`; second call lists 2 ODS tables.

- [ ] **Step 8: Commit**

```bash
git add backend/api/health.py backend/api/metadata.py backend/main.py backend/metadata/service.py tests/api/test_http_smoke.py
git commit -m "feat(backend): FastAPI app with /api/tables, /api/fields, /api/lineage, /api/health"
```

---

## Task 9: Backend Dockerfile + `app-compose.yml`

**Files:**
- Create: `backend/Dockerfile`
- Create: `app-compose.yml`

- [ ] **Step 1: Write `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps for any future Maven/Spark needs in later slices; minimal for now.
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy package metadata first to leverage Docker layer cache for deps.
COPY pyproject.toml /app/
COPY backend/ /app/backend/

RUN pip install --no-cache-dir -e ".[runtime]"

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Write `app-compose.yml`**

```yaml
name: data-gov

services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    container_name: data-gov-backend
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: ${NEO4J_AUTH#neo4j/}
      NEO4J_DATABASE: neo4j
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8000/api/health | grep -q '\"status\":\"healthy\"'"]
      interval: 10s
      timeout: 5s
      retries: 18
      start_period: 20s

networks:
  default:
    name: data-gov_default
    external: true
```

> The `external: true` flag tells compose to join the network created by `base-compose.yml` rather than spawning a new one. `${NEO4J_AUTH#neo4j/}` strips the `neo4j/` prefix from the auth string (POSIX shell parameter expansion compose supports).

- [ ] **Step 3: Bring up the backend**

Run:

```bash
docker compose -f base-compose.yml up -d   # ensure infra is running
docker compose -f app-compose.yml up -d --build
docker compose -f app-compose.yml ps
curl -fsS http://localhost:8000/api/health
```

Expected: `backend` reports running + healthy within 30s; curl returns the health JSON.

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile app-compose.yml
git commit -m "feat(infra): app-compose.yml with FastAPI backend service"
```

---

## Task 10: P1-6 acceptance — metadata CRUD API roundtrip

**Files:**
- Create: `tests/api/test_metadata_crud.py`

- [ ] **Step 1: Write the failing P1-6 test**

```python
"""P1-6: POST new table → GET /api/tables → GET /api/fields → PUT field expression → GET verifies.
Each step returns 200 (or 201 for create); data is consistent across calls."""
import httpx
import pytest


BASE = "http://localhost:8000"


@pytest.mark.infra
def test_p1_6_metadata_crud_roundtrip():
    with httpx.Client(base_url=BASE, timeout=10) as c:
        # Cleanup from previous test runs
        existing = c.get("/api/tables").json()
        for t in existing:
            if t["name"] == "test_temp_table":
                c.delete(f"/api/tables/{t['id']}")

        # 1. POST new table
        r = c.post("/api/tables", json={
            "name": "test_temp_table",
            "layer": "DWS",
            "storage_type": "HIVE",
            "description": "temporary CRUD acceptance",
        })
        assert r.status_code == 201, r.text
        new_table = r.json()
        assert new_table["name"] == "test_temp_table"
        assert new_table["fields"] == []
        table_id = new_table["id"]

        # 2. GET /api/tables — list contains new table
        r = c.get("/api/tables")
        assert r.status_code == 200
        names = {t["name"] for t in r.json()}
        assert "test_temp_table" in names

        # 3. POST new field on the table
        r = c.post("/api/fields", json={
            "table_id": table_id,
            "name": "crud_test_field",
            "field_type": "DOUBLE",
            "is_nullable": True,
            "is_partition": False,
            "expression": "AVG(value)",
            "description": "smoke test",
            "upstream": [],
        })
        assert r.status_code == 201, r.text
        field = r.json()
        field_id = field["id"]
        assert field["version"] == 1

        # 4. GET /api/fields/:id — verify creation
        r = c.get(f"/api/fields/{field_id}")
        assert r.status_code == 200
        assert r.json()["expression"] == "AVG(value)"

        # 5. PUT — update expression; version bumps
        r = c.put(f"/api/fields/{field_id}", json={"expression": "SUM(value)/COUNT(*)"})
        assert r.status_code == 200, r.text
        assert r.json()["version"] == 2

        # 6. GET — verify update persisted
        r = c.get(f"/api/fields/{field_id}")
        assert r.status_code == 200
        assert r.json()["expression"] == "SUM(value)/COUNT(*)"
        assert r.json()["version"] == 2

        # Cleanup
        c.delete(f"/api/fields/{field_id}")
        c.delete(f"/api/tables/{table_id}")
```

- [ ] **Step 2: Run the test**

Pre-condition: `app-compose` backend is running on :8000.

Run: `pytest tests/api/test_metadata_crud.py -v`
Expected: PASS — every step returns the expected status; field version increments correctly.

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_metadata_crud.py
git commit -m "test(api): P1-6 — metadata CRUD roundtrip"
```

---

## Task 11: P1-7 acceptance — lineage query API

**Files:**
- Create: `tests/api/test_lineage.py`

- [ ] **Step 1: Write the failing P1-7 test**

```python
"""P1-7: GET /api/lineage?table=dwd_session_qos&direction=down returns at least 2
field-level edges pointing to dws_cell_hourly and dws_area_traffic."""
import httpx
import pytest


BASE = "http://localhost:8000"


@pytest.mark.infra
def test_p1_7_lineage_downstream_dwd_session_qos():
    with httpx.Client(base_url=BASE, timeout=10) as c:
        r = c.get("/api/lineage", params={"table": "dwd_session_qos", "direction": "down", "depth": 1})
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["root_table"] == "dwd_session_qos"
        assert payload["direction"] == "down"
        edges = payload["edges"]
        downstream_tables = {e["to_table"] for e in edges}
        assert {"dws_cell_hourly", "dws_area_traffic"}.issubset(downstream_tables), \
            f"expected dws_cell_hourly and dws_area_traffic in downstream, got {downstream_tables}"
        # Count edges touching the two expected tables
        target_edges = [e for e in edges if e["to_table"] in {"dws_cell_hourly", "dws_area_traffic"}]
        assert len(target_edges) >= 2, f"expected ≥2 edges to dws_*; got {len(target_edges)}"


@pytest.mark.infra
def test_lineage_upstream_dws_cell_hourly():
    with httpx.Client(base_url=BASE, timeout=10) as c:
        r = c.get("/api/lineage", params={"table": "dws_cell_hourly", "direction": "up", "depth": 1})
        assert r.status_code == 200
        upstream_tables = {e["from_table"] for e in r.json()["edges"]}
        assert "dwd_session_qos" in upstream_tables


@pytest.mark.infra
def test_lineage_rejects_invalid_direction():
    with httpx.Client(base_url=BASE, timeout=10) as c:
        r = c.get("/api/lineage", params={"table": "ods_ue_signal", "direction": "sideways"})
        assert r.status_code == 422
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/api/test_lineage.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_lineage.py
git commit -m "test(api): P1-7 — lineage downstream/upstream queries"
```

---

## Task 12: P1-8 — Hive reverse-synth seed via Spark

**Files:**
- Create: `backend/seed/fake_data.py`
- Modify: `init-scripts/04_sample_data.py`
- Create: `tests/infra/test_hive_reverse_synth.py`

- [ ] **Step 1: Write the failing P1-8 test**

`tests/infra/test_hive_reverse_synth.py`:

```python
"""P1-8: generate_fake_data(table='dwd_session_qos', rows=5) writes 5 rows into Hive.
Spark SELECT shows fields are in valid ranges (rsrp ∈ [-140,-44], sinr ∈ [-20,30])."""
import subprocess
from pathlib import Path

import pytest

from backend.seed.fake_data import generate_fake_data


REPO_ROOT = Path(__file__).resolve().parents[2]


def _spark_sql(sql: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "docker", "run", "--rm",
            "--network", "data-gov_default",
            "-v", f"{REPO_ROOT}/docker/hadoop-conf:/etc/hadoop/conf:ro",
            "apache/spark:3.5.4",
            "/opt/spark/bin/spark-sql",
            "--conf", "spark.sql.catalogImplementation=hive",
            "--conf", "spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083",
            "--conf", "spark.hadoop.fs.defaultFS=hdfs://namenode:8020",
            "-e", sql,
        ],
        capture_output=True, text=True, check=False, timeout=300,
    )


@pytest.mark.infra
def test_p1_8_generate_fake_data_dwd_session_qos():
    result = generate_fake_data(table="dwd_session_qos", rows=5)
    assert result["rows_written"] == 5

    sql = "SELECT COUNT(*) AS c, MIN(avg_rsrp) AS min_rsrp, MAX(avg_rsrp) AS max_rsrp, " \
          "MIN(avg_sinr) AS min_sinr, MAX(avg_sinr) AS max_sinr FROM data_gov.dwd_session_qos"
    output = _spark_sql(sql)
    assert output.returncode == 0, output.stderr
    # Parse the row Spark prints — split on whitespace, last numeric tokens.
    # Format: "5\t-105.3\t-78.1\t12.4\t27.8"
    data_lines = [l for l in output.stdout.splitlines() if "\t" in l and not l.startswith("Time")]
    assert data_lines, f"no result row in stdout: {output.stdout!r}"
    parts = data_lines[-1].split("\t")
    count, min_rsrp, max_rsrp, min_sinr, max_sinr = (
        int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
    )
    assert count >= 5
    assert -140 <= min_rsrp <= max_rsrp <= -44
    assert -20 <= min_sinr <= max_sinr <= 30
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/infra/test_hive_reverse_synth.py -v`
Expected: FAIL — `backend.seed.fake_data` does not exist.

- [ ] **Step 3: Implement `backend/seed/fake_data.py`**

```python
"""Deterministic fake-data generator. Slice 1b: dwd_session_qos only.

Later slices will add reverse-synth flows for other tables driven by the Agent's
reverse_synth path. The signature is kept stable.
"""
from __future__ import annotations

import random
import subprocess
import tempfile
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _generate_dwd_session_qos_rows(rows: int, seed: int = 42) -> list[tuple]:
    rng = random.Random(seed)
    out = []
    for i in range(rows):
        rsrp = round(rng.uniform(-140, -44), 2)
        rsrq = round(rng.uniform(-19.5, -3), 2)
        sinr = round(rng.uniform(-20, 30), 2)
        packet_loss = round(rng.uniform(0, 0.05), 4)
        latency = round(rng.uniform(5, 200), 2)
        throughput = round(rng.uniform(0.1, 200), 2)
        drop_flag = 1 if rng.random() < 0.02 else 0
        out.append((
            f"sess_{i:08d}",          # session_id
            f"460{rng.randrange(10**12):012d}",  # imsi
            rsrp, rsrq, sinr,
            packet_loss, latency, throughput, drop_flag,
        ))
    return out


def _write_rows_via_spark(rows: list[tuple]) -> None:
    """Build a VALUES clause and INSERT via spark-sql in an ephemeral Spark container."""
    values_sql = ",".join(
        f"('{r[0]}', '{r[1]}', {r[2]}, {r[3]}, {r[4]}, {r[5]}, {r[6]}, {r[7]}, {r[8]})"
        for r in rows
    )
    sql = textwrap.dedent(f"""
        USE data_gov;
        INSERT INTO dwd_session_qos VALUES {values_sql};
    """).strip()

    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as f:
        f.write(sql)
        sql_path = Path(f.name)

    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--network", "data-gov_default",
                "-v", f"{REPO_ROOT}/docker/hadoop-conf:/etc/hadoop/conf:ro",
                "-v", f"{sql_path}:/work/insert.sql:ro",
                "apache/spark:3.5.4",
                "/opt/spark/bin/spark-sql",
                "--conf", "spark.sql.catalogImplementation=hive",
                "--conf", "spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083",
                "--conf", "spark.hadoop.fs.defaultFS=hdfs://namenode:8020",
                "-f", "/work/insert.sql",
            ],
            capture_output=True, text=True, check=False, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"spark-sql INSERT failed: {result.stderr}")
    finally:
        sql_path.unlink(missing_ok=True)


def generate_fake_data(table: str, rows: int) -> dict:
    """Generate `rows` deterministic rows into `table` via Spark.

    Returns: {"rows_written": int, "table": str}.
    Raises NotImplementedError for unsupported tables (will land in later slices).
    """
    if table != "dwd_session_qos":
        raise NotImplementedError(f"slice 1b only supports dwd_session_qos; got {table!r}")
    data = _generate_dwd_session_qos_rows(rows)
    _write_rows_via_spark(data)
    return {"rows_written": len(data), "table": table}
```

- [ ] **Step 4: Wire it into `init-scripts/04_sample_data.py`**

Append at the bottom of `init-scripts/04_sample_data.py` (which already seeds StarRocks from slice 1a):

```python
def seed_hive_dwd_session_qos(rows: int = 10) -> int:
    """Phase 1 slice 1b extension — Hive seed via Spark."""
    from backend.seed.fake_data import generate_fake_data
    return generate_fake_data(table="dwd_session_qos", rows=rows)["rows_written"]
```

And modify the script's `main()` to also call the new seeder. Open the file, find the existing `def main()` (from slice 1a Task 12), and replace it with:

```python
def main() -> int:
    starrocks_count = seed_ads_cell_profile()
    print(f"Inserted {starrocks_count} rows into ads_cell_profile.")
    hive_count = seed_hive_dwd_session_qos(rows=10)
    print(f"Inserted {hive_count} rows into dwd_session_qos.")
    return 0 if (starrocks_count > 0 and hive_count > 0) else 1
```

- [ ] **Step 5: Run the script and re-run the test**

Run:

```bash
python init-scripts/04_sample_data.py
pytest tests/infra/test_hive_reverse_synth.py -v
```

Expected: script prints both StarRocks and Hive seed lines; test asserts ≥5 rows in Hive with values in valid ranges. First-run latency: ~30-60s (Spark client invocation).

- [ ] **Step 6: Commit**

```bash
git add backend/seed/fake_data.py init-scripts/04_sample_data.py tests/infra/test_hive_reverse_synth.py
git commit -m "feat(seed): generate_fake_data + P1-8 Hive reverse-synth acceptance"
```

---

## Task 13: Update `init-stack.sh` to bring up slice 1b fully

**Files:**
- Modify: `scripts/init-stack.sh`
- Modify: `README.md`

- [ ] **Step 1: Update `scripts/init-stack.sh`**

Replace the slice 1a body with the slice 1b version (commit at this point already had `[1/5]`..`[5/5]`):

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[1/8] Waiting for base infrastructure healthy ..."
./scripts/wait-for-healthy.sh 300

echo "[2/8] Applying 01_hive_init.sql ..."
docker run --rm \
  --network data-gov_default \
  -v "$REPO_ROOT/init-scripts:/work:ro" \
  -v "$REPO_ROOT/docker/hadoop-conf:/etc/hadoop:ro" \
  apache/spark:3.5.4 \
  /opt/spark/bin/spark-sql \
    --conf spark.sql.catalogImplementation=hive \
    --conf spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083 \
    --conf spark.hadoop.fs.defaultFS=hdfs://namenode:8020 \
    -f /work/01_hive_init.sql

echo "[3/8] Creating Kafka topics ..."
./init-scripts/02_kafka_init.sh

echo "[4/8] Applying 03_starrocks_init.sql ..."
docker exec -i starrocks mysql -h 127.0.0.1 -P 9030 -u root < init-scripts/03_starrocks_init.sql

echo "[5/8] Initializing Neo4j schema (constraints + indexes) ..."
python init-scripts/05_neo4j_init.py

echo "[6/8] Seeding Neo4j (10 tables + ~65 fields + lineage) ..."
python init-scripts/06_neo4j_seed.py

echo "[7/8] Exporting YAML副本 ..."
python init-scripts/07_export_yaml.py

echo "[8/8] Seeding sample data (StarRocks + Hive) ..."
python init-scripts/04_sample_data.py

echo "Bringing up FastAPI backend ..."
docker compose -f app-compose.yml up -d --build

echo "Waiting for backend healthy ..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "Backend healthy."
    echo "Init complete."
    exit 0
  fi
  sleep 2
done

echo "Backend did not become healthy in 60s." >&2
docker compose -f app-compose.yml logs --tail=100 backend >&2
exit 1
```

- [ ] **Step 2: Update `README.md` Quick-start + acceptance table**

Replace the relevant sections of `README.md`:

```markdown
## Quick start (Phase 1, slices 1a + 1b)

```bash
cp .env.example .env
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh        # runs all 7 init scripts + brings up backend
pip install -e ".[dev]"
pytest -m infra                # P1-1..P1-8 should all pass
```

## Acceptance coverage (Phase 1)

| Case | Verifies | Test |
|------|----------|------|
| P1-1 | All 9 base-compose services healthy + NN/RM UIs reachable | `tests/infra/test_compose_health.py::test_p1_1_all_services_healthy` |
| P1-2 | Hive external table create/insert/select via Spark | `tests/infra/test_hive_external_table.py::test_p1_2_hive_external_table_roundtrip` |
| P1-3 | Kafka produce/consume on `ods_ue_signal` | `tests/infra/test_kafka_pubsub.py::test_p1_3_kafka_produce_consume_ods_ue_signal` |
| P1-4 | StarRocks `ads_cell_profile` rows after seeding | `tests/infra/test_starrocks_query.py::test_p1_4_starrocks_ads_cell_profile_has_rows` |
| P1-5 | Neo4j seeded (10 tables / ~65 fields) + 10 YAML files | `tests/infra/test_neo4j_seed.py` + `tests/infra/test_yaml_export.py` |
| P1-5b | Neo4j constraints + indexes present | `tests/infra/test_neo4j_init.py::test_p1_5b_*` |
| P1-6 | Metadata CRUD API roundtrip | `tests/api/test_metadata_crud.py::test_p1_6_metadata_crud_roundtrip` |
| P1-7 | Lineage `?direction=down` returns dws_* downstream of dwd_session_qos | `tests/api/test_lineage.py::test_p1_7_lineage_downstream_dwd_session_qos` |
| P1-8 | `generate_fake_data(table="dwd_session_qos", rows=5)` writes valid rows | `tests/infra/test_hive_reverse_synth.py::test_p1_8_generate_fake_data_dwd_session_qos` |

Deferred to Phase 2 (slices 2a-c): semantic search, LangGraph Agent, sandbox.
```

- [ ] **Step 3: Cold-start the full Phase 1 stack and run the entire acceptance suite**

Run:

```bash
docker compose -f app-compose.yml down 2>/dev/null || true
docker compose -f base-compose.yml down
rm -rf ./data ./metadata-yaml
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh
pytest -m infra -v
```

Expected: all `tests/infra/*` and `tests/api/*` tests pass. Total runtime: ~10-15 minutes on first cold start.

- [ ] **Step 4: Commit**

```bash
git add scripts/init-stack.sh README.md
git commit -m "docs: slice 1b — full Phase 1 init orchestrator and acceptance table"
```

---

## Self-Review

### 1. Spec coverage

| Spec ref | Requirement | Plan task |
|----------|-------------|-----------|
| §2.3 Neo4j schema — Table/Field/Change nodes + HAS_FIELD/DERIVES_FROM relationships | Task 4 (06_neo4j_seed.py) creates Table + Field + HAS_FIELD + DERIVES_FROM; Change writes deferred to slice 2b (schema_evolve flow) |
| §2.3 Constraints (table_id, table_name, field_id, change_id unique) | Task 2 |
| §2.3 Indexes (field_name, change.changed_at, change.table_name) | Task 2 |
| §2.5 YAML副本 format | Task 5 (07_export_yaml.py) |
| §3.5 init-scripts 05/06/07 | Tasks 2, 4, 5 |
| §4.3 Tools `lookup_table_schema` / `lookup_lineage` "share same service function" | Task 7 — backend.metadata.service is reusable by future Agent code without HTTP |
| §6.7 Metadata HTTP endpoints (`/api/tables`, `/api/fields`, `/api/lineage`) | Task 8 |
| §6.7 `/api/health` shape | Task 8 — only neo4j component this slice; spec format preserved |
| §7 backend/ structure (metadata/graph.py, metadata/service.py, api/metadata.py) | Tasks 1, 7, 8 |
| §7 `app-compose.yml` | Task 9 |
| §8 P1-5 | Tasks 4, 5 (Neo4j seed + YAML export) |
| §8 P1-5b | Task 2 |
| §8 P1-6 | Task 10 |
| §8 P1-7 | Task 11 |
| §8 P1-8 | Task 12 |

**Identified gaps (deferred — documented in plan header):**
- `:Change` audit nodes — added in slice 2b (`schema_apply` LangGraph node will write them). Without schema_evolve flow, no Change rows are produced. Plan header lists this under "Out of scope".
- `/api/schema/*`, `/api/chat/*`, `/api/yaml/*`, `/api/search`, `/api/pipeline` — deferred to slices 2b/3a as their dependent subsystems land.
- Reverse-synth seed for tables other than `dwd_session_qos` — `generate_fake_data` raises `NotImplementedError` for them; this is the deliberate slice-1b scope.
- `previous_expr` field history — Task 7 `update_field_expression` appends to it correctly, but the `Field` node `previous_expr` property is initialized to `'[]'` (JSON string) in Task 4. The Cypher type is STRING per spec §2.3 — matches.

### 2. Placeholder scan

Searched for `TBD`, `TODO`, `implement later`, `fill in`, `appropriate`, `similar to Task`:
- No `TODO`/`TBD` placeholders in plan body. Every code block is complete.
- One `NotImplementedError` in `backend/seed/fake_data.py` is a deliberate runtime error for unsupported tables, not a planning placeholder — the function fully implements its slice-1b scope (`dwd_session_qos`).

### 3. Type / name consistency

- Neo4j node labels: `Table`, `Field`, `Change` — used consistently across Tasks 2, 4, 7, 8. Spec §2.3 names match.
- Relationship types: `HAS_FIELD`, `DERIVES_FROM` — consistent.
- Service exception classes: `TableNotFound`, `FieldNotFound`, `FieldHasDownstream`, `CycleDetected` — defined in Task 7, imported in Task 8 routes, raised consistently.
- Pydantic DTOs (`TableResponse`, `FieldResponse`, `LineageEdge`, etc.) — defined in Task 6, used in Tasks 7 (return types) and 8 (response_model).
- Endpoint paths: `/api/tables`, `/api/tables/{table_id}`, `/api/fields/{field_id}`, `/api/lineage`, `/api/health` — exactly per spec §6.7.
- LineageEdge fields: `from_table`, `from_field`, `to_table`, `to_field`, `transform_expr` — consistent between models (Task 6), service (Task 7), and test (Task 11).
- Layer literal values: `ODS`/`DWD`/`DWS`/`ADS`/`EVAL` — consistent. `LAYER_PRIORITY` defined twice (in `backend/seed/tables.py` and `backend/metadata/service.py`) — minor duplication, but the source-of-truth is `backend.seed.tables.LAYER_PRIORITY`; the service-side copy exists only because the service module shouldn't import from `seed` (seed depends on service in some scenarios). The two are kept identical by the seed-data invariant test in Task 3. **Acceptable duplication** for layer boundary cleanliness.
- App-compose network name: `data-gov_default` — declared `external: true` in Task 9, must match the `name: data-gov` declaration at top of `base-compose.yml` (slice 1a Task 1). Consistent.
- StarRocks database `data_gov` — slice 1a vs slice 1b: slice 1b doesn't touch StarRocks tables directly; only extends 04_sample_data.py which already uses `data_gov`. Consistent.
- Hive database `data_gov` — Task 12 `generate_fake_data` uses `data_gov.dwd_session_qos`; matches slice 1a Task 9 DDL.

Verified — no name drift.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-14-phase1-slice1b-metadata-service.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task with two-stage review. This plan touches many files and has natural checkpoint moments after Task 4 (seed), Task 8 (HTTP routes), and Task 12 (Hive seed). Fast iteration with focused agent context.

**2. Inline Execution** — Use `superpowers:executing-plans` and execute through this conversation. Heavier on context window.

Which approach?
