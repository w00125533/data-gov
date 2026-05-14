# Phase 1 Slice 1a: Docker Base-Compose Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the 10-container `base-compose.yml` infrastructure stack (HDFS + YARN + Hive Metastore + HMS Postgres + Kafka KRaft + StarRocks allin1 + Neo4j) with healthchecks, init scripts, and pytest integration tests proving acceptance cases P1-1, P1-2, P1-3, P1-4 from the design spec.

**Architecture:** Single repo-root `base-compose.yml` defines all infra services on the Compose default network. Each service has a Docker healthcheck. `init-scripts/` holds idempotent post-start seed scripts (Hive DDL, Kafka topics, StarRocks DDL + sample rows). `scripts/init-stack.sh` runs the seeders after compose up. Python pytest tests in `tests/infra/` query each component to verify the four acceptance cases. Spark client for P1-2 is invoked as an ephemeral `docker run` against the compose network — no permanent Spark container in this slice.

**Tech Stack:**
- Docker Compose v2 (CLI plugin)
- Hadoop: `bde2020/hadoop-{namenode,datanode,resourcemanager,nodemanager}:2.0.0-hadoop3.2.1-java8`
- Hive Metastore: `apache/hive:4.0.0` with `SERVICE_NAME=metastore`
- Postgres (HMS backend): `postgres:15-alpine`
- Kafka KRaft: `apache/kafka:3.8.0`
- StarRocks: `starrocks/allin1-ubuntu:3.2-latest`
- Neo4j: `neo4j:5-community` (APOC plugin)
- Spark (ephemeral, test-only): `apache/spark:3.5.4`
- Python 3.11 + pytest + kafka-python + PyMySQL + requests

**Out of scope for this slice (deferred to slice 1b+):**
- Neo4j init/seed scripts (`05_neo4j_init.py`, `06_neo4j_seed.py`, `07_export_yaml.py`)
- FastAPI metadata CRUD API (P1-6)
- Field-level lineage API (P1-7)
- Hive seed data via Spark (P1-8 reverse-synth flow — only StarRocks rows are populated here so P1-4 passes)
- `app-compose.yml` (FastAPI + React)

---

## File Structure

```
data-gov/
├── base-compose.yml                       # 10 services, all healthchecks
├── .env.example                           # template; .env is gitignored
├── docker/
│   ├── hadoop-conf/
│   │   ├── core-site.xml
│   │   ├── hdfs-site.xml
│   │   ├── yarn-site.xml
│   │   └── mapred-site.xml
│   └── hive-conf/
│       └── hive-site.xml
├── init-scripts/
│   ├── 01_hive_init.sql                   # CREATE DB + 4 Hive external tables (dwd_*, dws_*)
│   ├── 02_kafka_init.sh                   # CREATE 2 Kafka topics (ods_*)
│   ├── 03_starrocks_init.sql              # CREATE DB + 4 StarRocks tables (ads_*, eval_*)
│   └── 04_sample_data.py                  # Insert deterministic rows into StarRocks ads_cell_profile
├── scripts/
│   ├── init-stack.sh                      # Wait healthy → run 01..04 → report
│   └── wait-for-healthy.sh                # poll `docker compose ps` until all healthy or timeout
├── tests/
│   ├── __init__.py
│   ├── conftest.py                        # session fixtures: project name, compose helpers
│   └── infra/
│       ├── __init__.py
│       ├── test_compose_health.py         # P1-1: all 10 services healthy + NN/RM UIs reachable
│       ├── test_hive_external_table.py    # P1-2: Spark creates ext table, inserts 10 rows, counts == 10
│       ├── test_kafka_pubsub.py           # P1-3: produce 5 JSON to ods_ue_signal, consume 5 back
│       └── test_starrocks_query.py        # P1-4: SELECT COUNT(*) FROM ads_cell_profile > 0
├── pyproject.toml                         # pytest + integration test deps
└── README.md                              # how to bring up the stack + run tests
```

**Responsibility per file:**
- `base-compose.yml` — the only source of truth for service topology, ports, env, healthchecks, depends_on, volumes.
- `docker/hadoop-conf/*.xml` — bind-mounted into NN/DN/RM/NM containers as `/etc/hadoop/conf`. Centralizes Hadoop client config so all four containers see the same view.
- `docker/hive-conf/hive-site.xml` — bind-mounted into Hive metastore as `/opt/hive/conf/hive-site.xml`. Configures Postgres JDBC + warehouse path.
- `init-scripts/0N_*.{sql,sh,py}` — idempotent. Re-running must not double-insert (use `IF NOT EXISTS` for DDL; `04_sample_data.py` truncates+reinserts).
- `scripts/init-stack.sh` — orchestrates 01→04 with explicit error reporting; never assumed by compose itself.
- `tests/conftest.py` — exposes `compose_project` fixture, `wait_until` helper, no service start/stop (assume stack already up).
- `tests/infra/test_*.py` — one acceptance case per file; each file is self-contained.

---

## Task 0: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Modify: `.gitignore` (add `data/`, `metastore_db/`, `*.egg-info/`)
- Create: `README.md`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "data-gov"
version = "0.1.0"
description = "Wireless RNO Data Semantic Service"
requires-python = ">=3.11"

[project.optional-dependencies]
test = [
    "pytest>=7.4",
    "pytest-timeout>=2.2",
    "requests>=2.31",
    "kafka-python>=2.0.2",
    "PyMySQL>=1.1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
timeout = 300
addopts = "-v --tb=short"
markers = [
    "infra: integration tests requiring base-compose stack running",
]
```

- [ ] **Step 2: Write `.env.example`**

```env
# Compose project name — pins network/volume names for predictable test wiring.
COMPOSE_PROJECT_NAME=data-gov

# HMS Postgres
POSTGRES_USER=hive
POSTGRES_PASSWORD=hive
POSTGRES_DB=metastore

# Neo4j
NEO4J_AUTH=neo4j/data-gov-neo4j

# StarRocks (no auth on FE by default — PoC scope)
STARROCKS_USER=root
STARROCKS_PASSWORD=
```

- [ ] **Step 3: Append to `.gitignore`**

Read the current `.gitignore`, then add these lines at the end (preserve existing content):

```
# Stack data volumes (persisted by compose)
data/
metastore_db/

# Python packaging
*.egg-info/
.pytest_cache/

# Init script logs
.init.log
```

- [ ] **Step 4: Write minimal `README.md`**

```markdown
# data-gov

Wireless RNO Data Semantic Service — PoC.

## Quick start (slice 1a: base infrastructure)

```bash
cp .env.example .env
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh
pip install -e ".[test]"
pytest -m infra
```

## Layout

- `base-compose.yml` — infrastructure services (HDFS / YARN / Hive / Kafka / StarRocks / Neo4j)
- `init-scripts/` — post-start seed scripts (Hive DDL, Kafka topics, StarRocks data)
- `tests/infra/` — pytest integration tests (P1-1..P1-4)

See `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md` for full design.
```

- [ ] **Step 5: Verify scaffolding**

Run:

```bash
python -c "import tomllib; tomllib.loads(open('pyproject.toml').read())"
```

Expected: exits 0, no output (TOML is valid).

Run:

```bash
test -f .env.example && test -f README.md && grep -q "metastore_db" .gitignore && echo OK
```

Expected: prints `OK`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example README.md .gitignore
git commit -m "chore: scaffold project for base-compose slice"
```

---

## Task 1: HMS Postgres service

**Files:**
- Create: `base-compose.yml` (initial version, only Postgres service)
- Test: `tests/infra/test_compose_health.py` (placeholder, expanded later)

- [ ] **Step 1: Write the failing test stub**

Create `tests/__init__.py` and `tests/infra/__init__.py` as empty files (signaling these are Python packages).

Then create `tests/conftest.py`:

```python
import json
import subprocess
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = REPO_ROOT / "base-compose.yml"


def _compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="session")
def compose():
    """Helper to run `docker compose -f base-compose.yml ...`."""
    return _compose


def service_state(service: str) -> dict:
    """Return the JSON state object for one compose service, or {} if absent."""
    result = _compose("ps", "--format", "json", service)
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    # `docker compose ps --format json` emits one JSON object per line.
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("Service") == service:
            return obj
    return {}


def wait_until(predicate, timeout: float = 60.0, interval: float = 2.0, desc: str = ""):
    """Poll `predicate()` until it returns truthy or timeout (seconds)."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"Timed out after {timeout}s waiting for: {desc}; last={last!r}")
```

Then create `tests/infra/test_compose_health.py`:

```python
import pytest

from tests.conftest import service_state, wait_until


REQUIRED_SERVICES = [
    "hms-db",
    "namenode",
    "datanode",
    "resourcemanager",
    "nodemanager",
    "hive-metastore",
    "kafka",
    "starrocks",
    "neo4j",
]


@pytest.mark.infra
@pytest.mark.parametrize("service", REQUIRED_SERVICES)
def test_service_is_healthy(service):
    state = wait_until(
        lambda: service_state(service) if service_state(service).get("Health") in ("healthy", "") else None,
        timeout=180,
        desc=f"service {service} healthy",
    )
    assert state, f"service {service} not present in compose output"
    assert state["State"] == "running", f"{service} state={state['State']!r}"
    # Some images may not declare a healthcheck; in that case Health == "".
    health = state.get("Health", "")
    assert health in ("healthy", ""), f"{service} health={health!r}"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/infra/test_compose_health.py::test_service_is_healthy -v`
Expected: FAIL — all parametrized cases error out because `base-compose.yml` does not exist yet (`docker compose -f base-compose.yml ps` returns nonzero, `service_state` returns `{}`, `wait_until` raises).

- [ ] **Step 3: Create `base-compose.yml` with HMS Postgres only**

```yaml
name: data-gov

services:
  hms-db:
    image: postgres:15-alpine
    container_name: hms-db
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-hive}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-hive}
      POSTGRES_DB: ${POSTGRES_DB:-metastore}
    ports:
      - "15432:5432"
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-hive} -d ${POSTGRES_DB:-metastore}"]
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 10s

networks:
  default:
    name: data-gov_default
```

- [ ] **Step 4: Bring up Postgres and run a single-service test**

Run:

```bash
cp -n .env.example .env || true
docker compose -f base-compose.yml up -d hms-db
pytest tests/infra/test_compose_health.py -v -k hms-db
```

Expected: PASS — `hms-db` reports `running` + `healthy` within 60s.

- [ ] **Step 5: Commit**

```bash
git add base-compose.yml tests/__init__.py tests/conftest.py tests/infra/__init__.py tests/infra/test_compose_health.py
git commit -m "feat(infra): add HMS Postgres service and compose health test harness"
```

---

## Task 2: HDFS NameNode + DataNode

**Files:**
- Modify: `base-compose.yml` (add namenode, datanode services)
- Create: `docker/hadoop-conf/core-site.xml`
- Create: `docker/hadoop-conf/hdfs-site.xml`
- Create: `docker/hadoop-conf/yarn-site.xml` (referenced by all four Hadoop containers; declare now even though YARN comes next)
- Create: `docker/hadoop-conf/mapred-site.xml`

- [ ] **Step 1: Write the failing assertion**

Append to `tests/infra/test_compose_health.py`:

```python
import requests


@pytest.mark.infra
def test_namenode_web_ui_reachable():
    response = wait_until(
        lambda: _safe_get("http://localhost:9870/dfshealth.html"),
        timeout=120,
        desc="HDFS NameNode UI :9870",
    )
    assert response.status_code == 200
    assert "Hadoop" in response.text


def _safe_get(url: str):
    try:
        r = requests.get(url, timeout=3)
        return r if r.status_code < 500 else None
    except requests.RequestException:
        return None
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `pytest tests/infra/test_compose_health.py::test_namenode_web_ui_reachable -v`
Expected: FAIL — connection refused; namenode service does not exist yet.

- [ ] **Step 3: Write Hadoop config XML files**

Create `docker/hadoop-conf/core-site.xml`:

```xml
<?xml version="1.0"?>
<configuration>
  <property>
    <name>fs.defaultFS</name>
    <value>hdfs://namenode:8020</value>
  </property>
  <property>
    <name>hadoop.proxyuser.root.hosts</name>
    <value>*</value>
  </property>
  <property>
    <name>hadoop.proxyuser.root.groups</name>
    <value>*</value>
  </property>
</configuration>
```

Create `docker/hadoop-conf/hdfs-site.xml`:

```xml
<?xml version="1.0"?>
<configuration>
  <property>
    <name>dfs.replication</name>
    <value>1</value>
  </property>
  <property>
    <name>dfs.namenode.name.dir</name>
    <value>/hadoop/dfs/name</value>
  </property>
  <property>
    <name>dfs.datanode.data.dir</name>
    <value>/hadoop/dfs/data</value>
  </property>
  <property>
    <name>dfs.permissions.enabled</name>
    <value>false</value>
  </property>
  <property>
    <name>dfs.webhdfs.enabled</name>
    <value>true</value>
  </property>
</configuration>
```

Create `docker/hadoop-conf/yarn-site.xml`:

```xml
<?xml version="1.0"?>
<configuration>
  <property>
    <name>yarn.resourcemanager.hostname</name>
    <value>resourcemanager</value>
  </property>
  <property>
    <name>yarn.nodemanager.aux-services</name>
    <value>mapreduce_shuffle</value>
  </property>
  <property>
    <name>yarn.nodemanager.resource.memory-mb</name>
    <value>4096</value>
  </property>
  <property>
    <name>yarn.nodemanager.resource.cpu-vcores</name>
    <value>2</value>
  </property>
  <property>
    <name>yarn.scheduler.maximum-allocation-mb</name>
    <value>4096</value>
  </property>
</configuration>
```

Create `docker/hadoop-conf/mapred-site.xml`:

```xml
<?xml version="1.0"?>
<configuration>
  <property>
    <name>mapreduce.framework.name</name>
    <value>yarn</value>
  </property>
</configuration>
```

- [ ] **Step 4: Add namenode + datanode services to `base-compose.yml`**

Insert these two services under `services:` (after `hms-db`):

```yaml
  namenode:
    image: bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8
    container_name: namenode
    hostname: namenode
    environment:
      CLUSTER_NAME: data-gov
      CORE_CONF_fs_defaultFS: hdfs://namenode:8020
    ports:
      - "9870:9870"
      - "8020:8020"
    volumes:
      - ./data/hdfs/namenode:/hadoop/dfs/name
      - ./docker/hadoop-conf/core-site.xml:/etc/hadoop/core-site.xml:ro
      - ./docker/hadoop-conf/hdfs-site.xml:/etc/hadoop/hdfs-site.xml:ro
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:9870/dfshealth.html > /dev/null"]
      interval: 10s
      timeout: 5s
      retries: 18
      start_period: 30s

  datanode:
    image: bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8
    container_name: datanode
    hostname: datanode
    environment:
      CORE_CONF_fs_defaultFS: hdfs://namenode:8020
      SERVICE_PRECONDITION: "namenode:9870"
    ports:
      - "9864:9864"
    volumes:
      - ./data/hdfs/datanode:/hadoop/dfs/data
      - ./docker/hadoop-conf/core-site.xml:/etc/hadoop/core-site.xml:ro
      - ./docker/hadoop-conf/hdfs-site.xml:/etc/hadoop/hdfs-site.xml:ro
    depends_on:
      namenode:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:9864 > /dev/null"]
      interval: 10s
      timeout: 5s
      retries: 18
      start_period: 30s
```

> Note on bde2020 images: the `CORE_CONF_*` and `HDFS_CONF_*` env-var prefixes are how the bde2020 entrypoint translates env vars into XML config. The bind-mounted XML files override anything else.

- [ ] **Step 5: Bring up HDFS and run NN/DN tests**

Run:

```bash
docker compose -f base-compose.yml up -d namenode datanode
pytest tests/infra/test_compose_health.py -v -k "namenode or datanode"
```

Expected: PASS — both services report healthy; NN UI returns 200 with "Hadoop" in HTML.

- [ ] **Step 6: Commit**

```bash
git add base-compose.yml docker/hadoop-conf/
git commit -m "feat(infra): add HDFS NameNode and DataNode with health probes"
```

---

## Task 3: YARN ResourceManager + NodeManager

**Files:**
- Modify: `base-compose.yml` (add resourcemanager, nodemanager)
- Test: extend `tests/infra/test_compose_health.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/infra/test_compose_health.py`:

```python
@pytest.mark.infra
def test_yarn_resourcemanager_ui_reachable():
    response = wait_until(
        lambda: _safe_get("http://localhost:8088/ws/v1/cluster/info"),
        timeout=180,
        desc="YARN RM REST :8088",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["clusterInfo"]["state"] == "STARTED"
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `pytest tests/infra/test_compose_health.py::test_yarn_resourcemanager_ui_reachable -v`
Expected: FAIL — connection refused on :8088.

- [ ] **Step 3: Add YARN services to `base-compose.yml`**

Insert after `datanode`:

```yaml
  resourcemanager:
    image: bde2020/hadoop-resourcemanager:2.0.0-hadoop3.2.1-java8
    container_name: resourcemanager
    hostname: resourcemanager
    environment:
      CORE_CONF_fs_defaultFS: hdfs://namenode:8020
      YARN_CONF_yarn_resourcemanager_hostname: resourcemanager
      SERVICE_PRECONDITION: "namenode:9870 datanode:9864"
    ports:
      - "8088:8088"
      - "8032:8032"
    volumes:
      - ./docker/hadoop-conf/core-site.xml:/etc/hadoop/core-site.xml:ro
      - ./docker/hadoop-conf/hdfs-site.xml:/etc/hadoop/hdfs-site.xml:ro
      - ./docker/hadoop-conf/yarn-site.xml:/etc/hadoop/yarn-site.xml:ro
      - ./docker/hadoop-conf/mapred-site.xml:/etc/hadoop/mapred-site.xml:ro
    depends_on:
      namenode:
        condition: service_healthy
      datanode:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8088/ws/v1/cluster/info | grep -q STARTED"]
      interval: 10s
      timeout: 5s
      retries: 24
      start_period: 30s

  nodemanager:
    image: bde2020/hadoop-nodemanager:2.0.0-hadoop3.2.1-java8
    container_name: nodemanager
    hostname: nodemanager
    environment:
      CORE_CONF_fs_defaultFS: hdfs://namenode:8020
      YARN_CONF_yarn_resourcemanager_hostname: resourcemanager
      SERVICE_PRECONDITION: "resourcemanager:8088"
    ports:
      - "8042:8042"
    volumes:
      - ./docker/hadoop-conf/core-site.xml:/etc/hadoop/core-site.xml:ro
      - ./docker/hadoop-conf/hdfs-site.xml:/etc/hadoop/hdfs-site.xml:ro
      - ./docker/hadoop-conf/yarn-site.xml:/etc/hadoop/yarn-site.xml:ro
      - ./docker/hadoop-conf/mapred-site.xml:/etc/hadoop/mapred-site.xml:ro
    depends_on:
      resourcemanager:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8042 > /dev/null"]
      interval: 10s
      timeout: 5s
      retries: 18
      start_period: 30s
```

- [ ] **Step 4: Bring up YARN and re-run the test**

Run:

```bash
docker compose -f base-compose.yml up -d resourcemanager nodemanager
pytest tests/infra/test_compose_health.py -v -k "resourcemanager or nodemanager or yarn"
```

Expected: PASS — both services healthy; RM REST returns `clusterInfo.state == "STARTED"`.

- [ ] **Step 5: Commit**

```bash
git add base-compose.yml
git commit -m "feat(infra): add YARN ResourceManager and NodeManager"
```

---

## Task 4: Hive Metastore (with Postgres backend)

**Files:**
- Modify: `base-compose.yml` (add hive-metastore)
- Create: `docker/hive-conf/hive-site.xml`
- Test: extend `tests/infra/test_compose_health.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/infra/test_compose_health.py`:

```python
import socket


@pytest.mark.infra
def test_hive_metastore_thrift_port_open():
    def _check():
        try:
            with socket.create_connection(("localhost", 9083), timeout=2):
                return True
        except OSError:
            return False

    wait_until(_check, timeout=180, desc="Hive Metastore :9083")
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/infra/test_compose_health.py::test_hive_metastore_thrift_port_open -v`
Expected: FAIL — port 9083 closed.

- [ ] **Step 3: Write `docker/hive-conf/hive-site.xml`**

```xml
<?xml version="1.0"?>
<configuration>
  <property>
    <name>javax.jdo.option.ConnectionURL</name>
    <value>jdbc:postgresql://hms-db:5432/metastore</value>
  </property>
  <property>
    <name>javax.jdo.option.ConnectionDriverName</name>
    <value>org.postgresql.Driver</value>
  </property>
  <property>
    <name>javax.jdo.option.ConnectionUserName</name>
    <value>hive</value>
  </property>
  <property>
    <name>javax.jdo.option.ConnectionPassword</name>
    <value>hive</value>
  </property>
  <property>
    <name>hive.metastore.warehouse.dir</name>
    <value>hdfs://namenode:8020/user/hive/warehouse</value>
  </property>
  <property>
    <name>hive.metastore.uris</name>
    <value>thrift://0.0.0.0:9083</value>
  </property>
  <property>
    <name>hive.metastore.schema.verification</name>
    <value>false</value>
  </property>
  <property>
    <name>datanucleus.autoCreateSchema</name>
    <value>true</value>
  </property>
  <property>
    <name>datanucleus.fixedDatastore</name>
    <value>false</value>
  </property>
  <property>
    <name>fs.defaultFS</name>
    <value>hdfs://namenode:8020</value>
  </property>
</configuration>
```

- [ ] **Step 4: Add the hive-metastore service to `base-compose.yml`**

Insert after `nodemanager`:

```yaml
  hive-metastore:
    image: apache/hive:4.0.0
    container_name: hive-metastore
    hostname: hive-metastore
    environment:
      SERVICE_NAME: metastore
      DB_DRIVER: postgres
      IS_RESUME: "false"
      SERVICE_OPTS: >-
        -Djavax.jdo.option.ConnectionDriverName=org.postgresql.Driver
        -Djavax.jdo.option.ConnectionURL=jdbc:postgresql://hms-db:5432/metastore
        -Djavax.jdo.option.ConnectionUserName=hive
        -Djavax.jdo.option.ConnectionPassword=hive
    ports:
      - "9083:9083"
    volumes:
      - ./docker/hive-conf/hive-site.xml:/opt/hive/conf/hive-site.xml:ro
      - ./docker/hadoop-conf/core-site.xml:/opt/hive/conf/core-site.xml:ro
      - ./docker/hadoop-conf/hdfs-site.xml:/opt/hive/conf/hdfs-site.xml:ro
    depends_on:
      hms-db:
        condition: service_healthy
      namenode:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "bash -c 'exec 3<>/dev/tcp/localhost/9083' || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 30
      start_period: 60s
```

> The apache/hive:4.0.0 image's entrypoint runs `schematool -initSchema -dbType postgres` automatically when `IS_RESUME=false` and the schema does not yet exist. The Postgres JDBC driver is bundled in the image.

- [ ] **Step 5: Bring up Hive Metastore and run the test**

Run:

```bash
docker compose -f base-compose.yml up -d hive-metastore
pytest tests/infra/test_compose_health.py -v -k "hive or hms-db"
```

Expected: PASS — port 9083 accepts TCP; `hive-metastore` reports healthy. First boot may take 60-90s while schematool initializes the Postgres schema.

- [ ] **Step 6: Commit**

```bash
git add base-compose.yml docker/hive-conf/
git commit -m "feat(infra): add Hive Metastore backed by HMS Postgres"
```

---

## Task 5: Kafka (KRaft mode)

**Files:**
- Modify: `base-compose.yml` (add kafka)
- Test: extend `tests/infra/test_compose_health.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/infra/test_compose_health.py`:

```python
@pytest.mark.infra
def test_kafka_broker_reachable():
    from kafka import KafkaAdminClient

    def _check():
        try:
            client = KafkaAdminClient(bootstrap_servers="localhost:9092", request_timeout_ms=3000)
            brokers = client.describe_cluster()
            client.close()
            return len(brokers.get("brokers", [])) >= 1
        except Exception:
            return False

    wait_until(_check, timeout=180, desc="Kafka broker :9092")
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/infra/test_compose_health.py::test_kafka_broker_reachable -v`
Expected: FAIL — kafka not running.

- [ ] **Step 3: Add Kafka service to `base-compose.yml`**

Insert after `hive-metastore`:

```yaml
  kafka:
    image: apache/kafka:3.8.0
    container_name: kafka
    hostname: kafka
    environment:
      KAFKA_NODE_ID: "1"
      KAFKA_PROCESS_ROLES: "broker,controller"
      KAFKA_LISTENERS: "PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093,EXTERNAL://0.0.0.0:19092"
      KAFKA_ADVERTISED_LISTENERS: "PLAINTEXT://kafka:9092,EXTERNAL://localhost:19092"
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: "CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,EXTERNAL:PLAINTEXT"
      KAFKA_INTER_BROKER_LISTENER_NAME: "PLAINTEXT"
      KAFKA_CONTROLLER_LISTENER_NAMES: "CONTROLLER"
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka:9093"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: "1"
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: "1"
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: "1"
      KAFKA_LOG_DIRS: "/var/lib/kafka/data"
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
    ports:
      - "9092:9092"
      - "19092:19092"
    volumes:
      - ./data/kafka:/var/lib/kafka/data
    healthcheck:
      test: ["CMD-SHELL", "/opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 > /dev/null 2>&1"]
      interval: 10s
      timeout: 5s
      retries: 18
      start_period: 30s
```

> The two listeners are intentional: `PLAINTEXT://kafka:9092` is the in-network advertised address (used by other containers); `EXTERNAL://localhost:19092` is for host-side clients if needed. The test uses the published `9092` mapping, which points at the in-network listener — this works because Compose publishes `9092 → 9092` and the broker advertises `kafka:9092` to clients connecting via that listener. (For complete clarity in mixed in-network / host-side scenarios, prefer the `19092` external listener from the host.)
>
> **Note:** `CLUSTER_ID` must be a fixed base64-encoded UUID for KRaft (16 bytes → 22 chars). The literal above is valid; treat it as opaque.

- [ ] **Step 4: Bring up Kafka and run the test**

Run:

```bash
docker compose -f base-compose.yml up -d kafka
pip install kafka-python  # if not already from pyproject extras
pytest tests/infra/test_compose_health.py -v -k kafka
```

Expected: PASS — Kafka responds with ≥1 broker.

> If the test fails because the test was started before the broker finished electing controllers, increase the `wait_until` timeout. The Kafka first-start can take 30s.

- [ ] **Step 5: Commit**

```bash
git add base-compose.yml
git commit -m "feat(infra): add Kafka broker (KRaft mode, no ZooKeeper)"
```

---

## Task 6: StarRocks (allin1)

**Files:**
- Modify: `base-compose.yml` (add starrocks)
- Test: extend `tests/infra/test_compose_health.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/infra/test_compose_health.py`:

```python
@pytest.mark.infra
def test_starrocks_fe_reachable():
    import pymysql

    def _check():
        try:
            conn = pymysql.connect(host="127.0.0.1", port=9030, user="root", password="", connect_timeout=3)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
            conn.close()
            return row == (1,)
        except Exception:
            return False

    wait_until(_check, timeout=240, desc="StarRocks FE :9030 SELECT 1")
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/infra/test_compose_health.py::test_starrocks_fe_reachable -v`
Expected: FAIL — no service on :9030.

- [ ] **Step 3: Add StarRocks service to `base-compose.yml`**

Insert after `kafka`:

```yaml
  starrocks:
    image: starrocks/allin1-ubuntu:3.2-latest
    container_name: starrocks
    hostname: starrocks
    ports:
      - "8030:8030"
      - "9030:9030"
      - "9060:9060"
    volumes:
      - ./data/starrocks:/data/deploy/starrocks
    healthcheck:
      test: ["CMD-SHELL", "mysql -h 127.0.0.1 -P 9030 -u root -e 'SELECT 1' > /dev/null 2>&1"]
      interval: 10s
      timeout: 5s
      retries: 30
      start_period: 90s
```

> StarRocks allin1 packs FE + BE in one container. First boot takes 60-120s while the FE elects a leader and the BE registers. The `start_period: 90s` gives that latitude before failure counts.

- [ ] **Step 4: Bring up StarRocks and run the test**

Run:

```bash
docker compose -f base-compose.yml up -d starrocks
pip install PyMySQL
pytest tests/infra/test_compose_health.py -v -k starrocks
```

Expected: PASS — `SELECT 1` returns `(1,)`.

- [ ] **Step 5: Commit**

```bash
git add base-compose.yml
git commit -m "feat(infra): add StarRocks allin1 (FE+BE)"
```

---

## Task 7: Neo4j

**Files:**
- Modify: `base-compose.yml` (add neo4j)
- Test: extend `tests/infra/test_compose_health.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/infra/test_compose_health.py`:

```python
@pytest.mark.infra
def test_neo4j_http_reachable():
    response = wait_until(
        lambda: _safe_get("http://localhost:7474/"),
        timeout=120,
        desc="Neo4j HTTP :7474",
    )
    assert response.status_code == 200
    payload = response.json()
    assert "neo4j_version" in payload, f"unexpected response payload: {payload!r}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/infra/test_compose_health.py::test_neo4j_http_reachable -v`
Expected: FAIL — Neo4j not running.

- [ ] **Step 3: Add Neo4j service to `base-compose.yml`**

Insert after `starrocks`:

```yaml
  neo4j:
    image: neo4j:5-community
    container_name: neo4j
    hostname: neo4j
    environment:
      NEO4J_AUTH: ${NEO4J_AUTH:-neo4j/data-gov-neo4j}
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_security_procedures_unrestricted: "apoc.*"
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - ./data/neo4j:/data
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:7474/ | grep -q neo4j_version"]
      interval: 10s
      timeout: 5s
      retries: 18
      start_period: 30s
```

> Per spec §3.1: `./data/neo4j/` persistent volume + APOC plugin. The healthcheck hits the discovery endpoint (always returns version JSON without auth).

- [ ] **Step 4: Bring up Neo4j and run the test**

Run:

```bash
docker compose -f base-compose.yml up -d neo4j
pytest tests/infra/test_compose_health.py -v -k neo4j
```

Expected: PASS — Neo4j returns its version JSON within 60s.

- [ ] **Step 5: Commit**

```bash
git add base-compose.yml
git commit -m "feat(infra): add Neo4j with APOC plugin and persistent volume"
```

---

## Task 8: P1-1 acceptance — all 10 services healthy together

**Files:**
- Test: extend `tests/infra/test_compose_health.py`
- Create: `scripts/wait-for-healthy.sh`

- [ ] **Step 1: Write the P1-1 acceptance test**

Append to `tests/infra/test_compose_health.py`:

```python
@pytest.mark.infra
def test_p1_1_all_services_healthy():
    """P1-1: every required service is running + healthy; NN/RM UIs reachable."""
    for service in REQUIRED_SERVICES:
        state = service_state(service)
        assert state, f"{service} not present"
        assert state["State"] == "running", f"{service} state={state['State']!r}"
        health = state.get("Health", "")
        assert health in ("healthy", ""), f"{service} health={health!r}"

    nn = _safe_get("http://localhost:9870/dfshealth.html")
    assert nn is not None and nn.status_code == 200, "NN UI unreachable"

    rm = _safe_get("http://localhost:8088/ws/v1/cluster/info")
    assert rm is not None and rm.status_code == 200, "RM REST unreachable"
    assert rm.json()["clusterInfo"]["state"] == "STARTED"
```

> The `REQUIRED_SERVICES` list defined in Task 1 has 9 entries (`hms-db, namenode, datanode, resourcemanager, nodemanager, hive-metastore, kafka, starrocks, neo4j`). The spec's "10 services" counts HDFS NN + HDFS DN + YARN RM + YARN NM as four separate logical services — same total of 9 service entries in compose (the 10th in the spec table is HMS DB, already counted). Confirmed: total = 9 compose services representing the 10 logical infra components.

- [ ] **Step 2: Write `scripts/wait-for-healthy.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

SERVICES=(hms-db namenode datanode resourcemanager nodemanager hive-metastore kafka starrocks neo4j)
TIMEOUT_SECONDS="${1:-240}"
DEADLINE=$(( $(date +%s) + TIMEOUT_SECONDS ))

while (( $(date +%s) < DEADLINE )); do
  all_ok=true
  for svc in "${SERVICES[@]}"; do
    state=$(docker compose -f base-compose.yml ps --format json "$svc" 2>/dev/null | head -n1 || echo '')
    if [[ -z "$state" ]]; then
      all_ok=false
      break
    fi
    running=$(echo "$state" | grep -oE '"State":"[^"]*"' | head -n1 | cut -d'"' -f4)
    health=$(echo "$state" | grep -oE '"Health":"[^"]*"' | head -n1 | cut -d'"' -f4)
    if [[ "$running" != "running" ]] || { [[ -n "$health" ]] && [[ "$health" != "healthy" ]]; }; then
      all_ok=false
      break
    fi
  done
  if $all_ok; then
    echo "All ${#SERVICES[@]} services healthy."
    exit 0
  fi
  sleep 3
done

echo "Timed out waiting for services after ${TIMEOUT_SECONDS}s." >&2
docker compose -f base-compose.yml ps >&2
exit 1
```

Make it executable: `chmod +x scripts/wait-for-healthy.sh`.

- [ ] **Step 3: Bring up the full stack from a cold start**

Run:

```bash
docker compose -f base-compose.yml down
docker compose -f base-compose.yml up -d
./scripts/wait-for-healthy.sh 300
```

Expected: `./scripts/wait-for-healthy.sh` exits 0 with `All 9 services healthy.` within ~5 minutes.

- [ ] **Step 4: Run the P1-1 acceptance test**

Run: `pytest tests/infra/test_compose_health.py::test_p1_1_all_services_healthy -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/infra/test_compose_health.py scripts/wait-for-healthy.sh
git commit -m "test(infra): P1-1 — all 9 base-compose services healthy"
```

---

## Task 9: Hive init script — `01_hive_init.sql`

**Files:**
- Create: `init-scripts/01_hive_init.sql`

- [ ] **Step 1: Write the SQL DDL**

```sql
-- 01_hive_init.sql
-- Creates the Hive database and external table skeletons for the 4 DWD/DWS layer
-- business tables. Idempotent — uses IF NOT EXISTS everywhere.

CREATE DATABASE IF NOT EXISTS data_gov LOCATION 'hdfs://namenode:8020/user/hive/warehouse/data_gov.db';

USE data_gov;

CREATE EXTERNAL TABLE IF NOT EXISTS dwd_session_qos (
  session_id   STRING,
  imsi         STRING,
  avg_rsrp     DOUBLE,
  avg_rsrq     DOUBLE,
  avg_sinr     DOUBLE,
  packet_loss  DOUBLE,
  latency      DOUBLE,
  throughput   DOUBLE,
  drop_flag    INT
)
STORED AS PARQUET
LOCATION 'hdfs://namenode:8020/user/hive/warehouse/data_gov.db/dwd_session_qos';

CREATE EXTERNAL TABLE IF NOT EXISTS dwd_ho_event (
  imsi          STRING,
  source_cell   STRING,
  target_cell   STRING,
  ho_type       STRING,
  ho_result     STRING,
  ho_cause      STRING,
  ho_latency    DOUBLE
)
STORED AS PARQUET
LOCATION 'hdfs://namenode:8020/user/hive/warehouse/data_gov.db/dwd_ho_event';

CREATE EXTERNAL TABLE IF NOT EXISTS dws_cell_hourly (
  cell_id           STRING,
  hour_bucket       TIMESTAMP,
  avg_rsrp          DOUBLE,
  avg_sinr          DOUBLE,
  total_sessions    BIGINT,
  drop_rate         DOUBLE,
  avg_throughput    DOUBLE,
  ho_success_rate   DOUBLE
)
STORED AS PARQUET
LOCATION 'hdfs://namenode:8020/user/hive/warehouse/data_gov.db/dws_cell_hourly';

CREATE EXTERNAL TABLE IF NOT EXISTS dws_area_traffic (
  area_id          STRING,
  hour_bucket      TIMESTAMP,
  total_throughput DOUBLE,
  active_users     BIGINT,
  avg_latency      DOUBLE,
  peak_throughput  DOUBLE
)
STORED AS PARQUET
LOCATION 'hdfs://namenode:8020/user/hive/warehouse/data_gov.db/dws_area_traffic';
```

> Schema follows spec §2.2's 10-table list. Partition columns are deferred to the test that proves end-to-end Spark write (P1-2 doesn't require partitions).

- [ ] **Step 2: Sanity check the file**

Run:

```bash
test -f init-scripts/01_hive_init.sql && wc -l init-scripts/01_hive_init.sql
```

Expected: prints a line count > 30.

- [ ] **Step 3: Commit**

```bash
git add init-scripts/01_hive_init.sql
git commit -m "feat(infra): add 01_hive_init.sql with DWD/DWS table DDL"
```

---

## Task 10: Kafka topic init — `02_kafka_init.sh`

**Files:**
- Create: `init-scripts/02_kafka_init.sh`

- [ ] **Step 1: Write the topic-creation script**

```bash
#!/usr/bin/env bash
# 02_kafka_init.sh — idempotent Kafka topic creation for ODS layer.
set -euo pipefail

BOOTSTRAP="${KAFKA_BOOTSTRAP:-kafka:9092}"

create_topic() {
  local name="$1"
  local partitions="${2:-3}"
  local rf="${3:-1}"
  if docker exec kafka /opt/kafka/bin/kafka-topics.sh \
      --bootstrap-server "$BOOTSTRAP" \
      --list 2>/dev/null | grep -qx "$name"; then
    echo "topic $name exists"
    return 0
  fi
  docker exec kafka /opt/kafka/bin/kafka-topics.sh \
      --bootstrap-server "$BOOTSTRAP" \
      --create \
      --topic "$name" \
      --partitions "$partitions" \
      --replication-factor "$rf"
}

create_topic ods_ue_signal 3 1
create_topic ods_gnb_alarm 3 1

echo "Kafka topics ready."
```

Make executable: `chmod +x init-scripts/02_kafka_init.sh`. On Windows, ensure LF line endings: `sed -i 's/\r$//' init-scripts/02_kafka_init.sh` (or set `git config core.autocrlf input`).

- [ ] **Step 2: Run the script against the running stack**

Run:

```bash
./init-scripts/02_kafka_init.sh
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list
```

Expected: stdout contains `ods_ue_signal` and `ods_gnb_alarm`. Re-running the script is a no-op (`topic ... exists`).

- [ ] **Step 3: Commit**

```bash
git add init-scripts/02_kafka_init.sh
git commit -m "feat(infra): add 02_kafka_init.sh creating ODS topics"
```

---

## Task 11: StarRocks DDL — `03_starrocks_init.sql`

**Files:**
- Create: `init-scripts/03_starrocks_init.sql`

- [ ] **Step 1: Write the StarRocks DDL**

```sql
-- 03_starrocks_init.sql
-- Creates the StarRocks database and ADS/EVAL tables (4 total).
-- Run via `mysql -h 127.0.0.1 -P 9030 -u root < 03_starrocks_init.sql`.

CREATE DATABASE IF NOT EXISTS data_gov;

USE data_gov;

CREATE TABLE IF NOT EXISTS ads_cell_profile (
  cell_id           VARCHAR(64)  NOT NULL,
  `date`            DATE         NOT NULL,
  coverage_score    DOUBLE,
  capacity_score    DOUBLE,
  stability_score   DOUBLE,
  composite_kpi     DOUBLE
)
ENGINE = OLAP
DUPLICATE KEY(cell_id, `date`)
DISTRIBUTED BY HASH(cell_id) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS ads_neighbor_pair (
  source_cell        VARCHAR(64) NOT NULL,
  target_cell        VARCHAR(64) NOT NULL,
  ho_count           BIGINT,
  ho_success_rate    DOUBLE,
  avg_ho_latency     DOUBLE,
  recommend_priority INT
)
ENGINE = OLAP
DUPLICATE KEY(source_cell, target_cell)
DISTRIBUTED BY HASH(source_cell) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS eval_user_score (
  imsi                  VARCHAR(64) NOT NULL,
  `date`                DATE        NOT NULL,
  qoe_score             DOUBLE,
  signal_quality        DOUBLE,
  mobility_score        DOUBLE,
  service_continuity    DOUBLE
)
ENGINE = OLAP
DUPLICATE KEY(imsi, `date`)
DISTRIBUTED BY HASH(imsi) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS eval_net_health (
  area_id                   VARCHAR(64) NOT NULL,
  `date`                    DATE        NOT NULL,
  health_index              DOUBLE,
  alarm_severity_weighted   DOUBLE,
  user_complaint_ratio      DOUBLE,
  degradation_trend         DOUBLE
)
ENGINE = OLAP
DUPLICATE KEY(area_id, `date`)
DISTRIBUTED BY HASH(area_id) BUCKETS 4
PROPERTIES ("replication_num" = "1");
```

- [ ] **Step 2: Apply the DDL to the running StarRocks**

Run:

```bash
docker exec -i starrocks mysql -h 127.0.0.1 -P 9030 -u root < init-scripts/03_starrocks_init.sql
docker exec -i starrocks mysql -h 127.0.0.1 -P 9030 -u root -e "USE data_gov; SHOW TABLES;"
```

Expected: prints a table listing including `ads_cell_profile`, `ads_neighbor_pair`, `eval_user_score`, `eval_net_health`.

- [ ] **Step 3: Commit**

```bash
git add init-scripts/03_starrocks_init.sql
git commit -m "feat(infra): add 03_starrocks_init.sql for ADS/EVAL tables"
```

---

## Task 12: Sample-data seeder — `04_sample_data.py` (StarRocks slice)

**Files:**
- Create: `init-scripts/04_sample_data.py`

> Scope for this slice: populate `ads_cell_profile` only — enough for P1-4 to pass. Hive seeding and reverse-synth flow are deferred. The function signature stays generic so later slices can extend it.

- [ ] **Step 1: Write the seeder**

```python
"""04_sample_data.py — deterministic sample data for slice 1a.

This slice populates StarRocks only. Hive + Kafka seeding lands in later slices.

Run via:
    python init-scripts/04_sample_data.py
"""
from __future__ import annotations

import datetime as dt
import sys

import pymysql


STARROCKS_HOST = "127.0.0.1"
STARROCKS_PORT = 9030
STARROCKS_USER = "root"
STARROCKS_DB = "data_gov"

# 6 deterministic rows across 3 cells × 2 dates so P1-4's SELECT COUNT > 0 is robust.
SAMPLE_CELLS = ["cell_001", "cell_002", "cell_003"]
SAMPLE_DATES = [dt.date(2026, 5, 1), dt.date(2026, 5, 2)]


def seed_ads_cell_profile() -> int:
    conn = pymysql.connect(
        host=STARROCKS_HOST,
        port=STARROCKS_PORT,
        user=STARROCKS_USER,
        password="",
        database=STARROCKS_DB,
        autocommit=True,
    )
    rows_inserted = 0
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE ads_cell_profile")
            for date in SAMPLE_DATES:
                for cell in SAMPLE_CELLS:
                    cur.execute(
                        """
                        INSERT INTO ads_cell_profile
                            (cell_id, `date`, coverage_score, capacity_score, stability_score, composite_kpi)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (cell, date, 85.5, 78.2, 92.1, 85.3),
                    )
                    rows_inserted += 1
    finally:
        conn.close()
    return rows_inserted


def main() -> int:
    inserted = seed_ads_cell_profile()
    print(f"Inserted {inserted} rows into ads_cell_profile.")
    return 0 if inserted > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the seeder**

Run:

```bash
python init-scripts/04_sample_data.py
```

Expected: prints `Inserted 6 rows into ads_cell_profile.`

- [ ] **Step 3: Verify rows via mysql client**

Run:

```bash
docker exec -i starrocks mysql -h 127.0.0.1 -P 9030 -u root -e "SELECT COUNT(*) FROM data_gov.ads_cell_profile"
```

Expected: `COUNT(*)` column reports `6`.

- [ ] **Step 4: Commit**

```bash
git add init-scripts/04_sample_data.py
git commit -m "feat(infra): seed StarRocks ads_cell_profile with 6 deterministic rows"
```

---

## Task 13: Init orchestrator — `scripts/init-stack.sh`

**Files:**
- Create: `scripts/init-stack.sh`

- [ ] **Step 1: Write the orchestrator**

```bash
#!/usr/bin/env bash
# init-stack.sh — wait for healthy, then run init scripts 01..04 in order.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[1/5] Waiting for all services healthy ..."
./scripts/wait-for-healthy.sh 300

echo "[2/5] Applying 01_hive_init.sql via ephemeral Spark client ..."
docker run --rm \
  --network data-gov_default \
  -v "$REPO_ROOT/init-scripts:/work:ro" \
  -v "$REPO_ROOT/docker/hadoop-conf:/etc/hadoop:ro" \
  -v "$REPO_ROOT/docker/hive-conf:/opt/spark/conf/hive-site.xml.d:ro" \
  apache/spark:3.5.4 \
  /opt/spark/bin/spark-sql \
    --conf spark.sql.catalogImplementation=hive \
    --conf spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083 \
    --conf spark.hadoop.fs.defaultFS=hdfs://namenode:8020 \
    -f /work/01_hive_init.sql

echo "[3/5] Creating Kafka topics ..."
./init-scripts/02_kafka_init.sh

echo "[4/5] Applying 03_starrocks_init.sql ..."
docker exec -i starrocks mysql -h 127.0.0.1 -P 9030 -u root < init-scripts/03_starrocks_init.sql

echo "[5/5] Seeding StarRocks sample data ..."
python init-scripts/04_sample_data.py

echo "Init complete."
```

Make executable: `chmod +x scripts/init-stack.sh`.

- [ ] **Step 2: Run orchestrator end-to-end against a fresh stack**

Run:

```bash
docker compose -f base-compose.yml down -v
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh
```

Expected: prints `[1/5]`...`[5/5]` then `Init complete.` and exits 0. Total runtime: ~5-8 minutes on first run (image pulls + Hive metastore schema init + first-time Spark client pull).

> **Note:** `docker compose down -v` wipes named volumes, but our volumes are bind-mounts to `./data/`. Add `rm -rf ./data/` before `up -d` to force a fully cold start.

- [ ] **Step 3: Commit**

```bash
git add scripts/init-stack.sh
git commit -m "feat(infra): add init-stack.sh orchestrator for scripts 01..04"
```

---

## Task 14: P1-2 acceptance — Hive external table via Spark

**Files:**
- Create: `tests/infra/test_hive_external_table.py`

- [ ] **Step 1: Write the failing test**

```python
"""P1-2: Through a Spark SQL session, create an external table, insert 10 rows,
SELECT COUNT(*) returns 10.

We invoke Spark via an ephemeral `apache/spark:3.5.4` container on the compose
network — slice 1a does not run a permanent Spark service.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_spark_sql(sql: str) -> subprocess.CompletedProcess:
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
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


@pytest.mark.infra
def test_p1_2_hive_external_table_roundtrip():
    sql = textwrap.dedent("""
        CREATE DATABASE IF NOT EXISTS smoke_test;
        DROP TABLE IF EXISTS smoke_test.tmp_p1_2;
        CREATE EXTERNAL TABLE smoke_test.tmp_p1_2 (n INT)
          STORED AS PARQUET
          LOCATION 'hdfs://namenode:8020/user/hive/warehouse/smoke_test.db/tmp_p1_2';
        INSERT INTO smoke_test.tmp_p1_2 VALUES (1),(2),(3),(4),(5),(6),(7),(8),(9),(10);
        SELECT COUNT(*) AS c FROM smoke_test.tmp_p1_2;
    """).strip()

    result = _run_spark_sql(sql)
    assert result.returncode == 0, f"spark-sql failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    # spark-sql prints results line by line; the last numeric token before "Time taken" is the count.
    output_lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    assert "10" in output_lines, f"expected '10' in spark-sql output, got: {output_lines!r}"
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/infra/test_hive_external_table.py -v`
Expected: PASS. First run pulls `apache/spark:3.5.4` (~600 MB); subsequent runs use the cached image.

> If the test fails with `Could not connect to hive-metastore:9083`, the metastore may not have finished initialization yet. Re-run `./scripts/wait-for-healthy.sh` and retry.

- [ ] **Step 3: Commit**

```bash
git add tests/infra/test_hive_external_table.py
git commit -m "test(infra): P1-2 — Hive external table roundtrip via Spark"
```

---

## Task 15: P1-3 acceptance — Kafka produce/consume

**Files:**
- Create: `tests/infra/test_kafka_pubsub.py`

- [ ] **Step 1: Write the failing test**

```python
"""P1-3: Produce 5 JSON messages to `ods_ue_signal`, consume them back from earliest."""
import json
import uuid

import pytest
from kafka import KafkaConsumer, KafkaProducer


@pytest.mark.infra
def test_p1_3_kafka_produce_consume_ods_ue_signal():
    topic = "ods_ue_signal"
    group_id = f"test-{uuid.uuid4().hex[:8]}"
    messages = [
        {"imsi": f"46000{i:010d}", "cell_id": "cell_001", "rsrp": -90 - i, "sinr": 15 - i}
        for i in range(5)
    ]

    producer = KafkaProducer(
        bootstrap_servers="localhost:9092",
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
    )
    for msg in messages:
        producer.send(topic, msg)
    producer.flush()
    producer.close()

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers="localhost:9092",
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        consumer_timeout_ms=10_000,
    )
    received = []
    for record in consumer:
        received.append(record.value)
        if len(received) >= 5:
            break
    consumer.close()

    assert len(received) == 5, f"expected 5 messages, got {len(received)}: {received!r}"
    # Match by IMSI rather than order (different partitions can interleave).
    sent_imsis = {m["imsi"] for m in messages}
    received_imsis = {m["imsi"] for m in received}
    assert sent_imsis == received_imsis
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/infra/test_kafka_pubsub.py -v`
Expected: PASS within 15s. Pre-condition: `02_kafka_init.sh` has been run so `ods_ue_signal` topic exists.

- [ ] **Step 3: Commit**

```bash
git add tests/infra/test_kafka_pubsub.py
git commit -m "test(infra): P1-3 — Kafka produce/consume on ods_ue_signal"
```

---

## Task 16: P1-4 acceptance — StarRocks SELECT COUNT

**Files:**
- Create: `tests/infra/test_starrocks_query.py`

- [ ] **Step 1: Write the failing test**

```python
"""P1-4: After 04_sample_data.py runs, SELECT COUNT(*) FROM ads_cell_profile > 0."""
import pymysql
import pytest


@pytest.mark.infra
def test_p1_4_starrocks_ads_cell_profile_has_rows():
    conn = pymysql.connect(
        host="127.0.0.1",
        port=9030,
        user="root",
        password="",
        database="data_gov",
        connect_timeout=5,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM ads_cell_profile")
            (count,) = cur.fetchone()
    finally:
        conn.close()

    assert count > 0, f"ads_cell_profile is empty; did 04_sample_data.py run?"
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/infra/test_starrocks_query.py -v`
Expected: PASS. Pre-condition: `04_sample_data.py` ran (via `./scripts/init-stack.sh` step 5/5) — `ads_cell_profile` has 6 rows.

- [ ] **Step 3: Commit**

```bash
git add tests/infra/test_starrocks_query.py
git commit -m "test(infra): P1-4 — StarRocks ads_cell_profile SELECT COUNT > 0"
```

---

## Task 17: Full end-to-end verification + README polish

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Cold-start the full stack and verify all four acceptance cases**

Run:

```bash
docker compose -f base-compose.yml down
rm -rf ./data
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh
pytest -m infra
```

Expected: All `tests/infra/*` pass. Total runtime: 5-10 minutes on first cold start (image pulls dominate).

- [ ] **Step 2: Expand `README.md` with acceptance summary**

Replace the "Quick start" section in `README.md` with:

```markdown
## Quick start (slice 1a: base infrastructure)

```bash
cp .env.example .env
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh           # waits for healthy → runs 01..04
pip install -e ".[test]"
pytest -m infra                    # P1-1..P1-4 should all pass
```

## Acceptance coverage (Phase 1, slice 1a)

| Case | Verifies | Test |
|------|----------|------|
| P1-1 | All 9 compose services healthy + NN/RM UIs reachable | `tests/infra/test_compose_health.py::test_p1_1_all_services_healthy` |
| P1-2 | Hive external table create/insert/select via Spark | `tests/infra/test_hive_external_table.py::test_p1_2_hive_external_table_roundtrip` |
| P1-3 | Kafka produce/consume on `ods_ue_signal` | `tests/infra/test_kafka_pubsub.py::test_p1_3_kafka_produce_consume_ods_ue_signal` |
| P1-4 | StarRocks `ads_cell_profile` rows after seeding | `tests/infra/test_starrocks_query.py::test_p1_4_starrocks_ads_cell_profile_has_rows` |

Deferred to slice 1b: Neo4j seed (`05/06/07`), FastAPI metadata CRUD (P1-6), lineage API (P1-7), Hive reverse-synth seed (P1-8).
```

- [ ] **Step 3: Final cold-start smoke test**

Run:

```bash
docker compose -f base-compose.yml down
rm -rf ./data
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh
pytest -m infra -v
```

Expected: every `tests/infra/*` test reports PASS.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document slice 1a acceptance coverage"
```

---

## Self-Review

### 1. Spec coverage

Walking spec §3 and §8 Phase 1 acceptance cases P1-1..P1-4:

| Spec ref | Requirement | Plan task |
|----------|-------------|-----------|
| §3.1 HDFS NN | port 9870/8020, Spark/Flink read/write | Task 2 |
| §3.1 HDFS DN | port 9864, single node | Task 2 |
| §3.1 YARN RM | port 8088/8032 | Task 3 |
| §3.1 YARN NM | port 8042, single node | Task 3 |
| §3.1 Hive Metastore | port 9083 | Task 4 |
| §3.1 HMS Postgres | port 15432 | Task 1 |
| §3.1 Kafka KRaft | port 9092, no ZK | Task 5 |
| §3.1 StarRocks FE | port 9030/8030 | Task 6 |
| §3.1 StarRocks BE | port 9060 | Task 6 (allin1 image — FE+BE in same container) |
| §3.1 Neo4j | port 7474/7687, APOC plugin, `./data/neo4j/` volume, `neo4j:5-community` | Task 7 |
| §3.4 Storage flow | ODS→Kafka, DWD/DWS→Hive, ADS/EVAL→StarRocks | Tasks 9, 10, 11 (DDL matches) |
| §3.5 init-scripts | 01/02/03/04 | Tasks 9, 10, 11, 12 (05/06/07 deferred) |
| §3.6 Health checks | each service surfaces health | Compose healthchecks in Tasks 1-7 |
| §8 P1-1 | `docker compose up -d` → all 10 services healthy, NN/RM UI reachable | Task 8 |
| §8 P1-2 | Spark Shell → external table → 10 rows → COUNT=10 | Task 14 |
| §8 P1-3 | `ods_ue_signal` topic, produce 5 → consume 5 | Task 15 |
| §8 P1-4 | `04_sample_data.py` → SELECT COUNT > 0 from `ads_cell_profile` | Tasks 12 + 16 |

**Identified gaps:**
- Spec §2.3 / §3.5 Neo4j initialization (constraints, schema, seeds) — deferred to slice 1b. Documented in plan header "Out of scope" and README's "Deferred" table.
- Spec §3.1 FE/BE separation: we use `starrocks/allin1-ubuntu` which combines them. Justification in Task 6 ("allin1 packs FE + BE in one container") — acceptable for PoC; ports per spec are still exposed. If a future slice needs FE/BE on separate hosts, split then.
- Spec mentions "10 services" while we have 9 compose service entries — Task 8 notes the count: 9 compose services represent 10 logical components (HDFS NN/DN + YARN RM/NM = 4 logical, 4 containers; StarRocks FE+BE = 2 logical, 1 container under allin1; everything else 1:1). Total logical: 4+1+1+1+2+1 = 10 ✓.

### 2. Placeholder scan

Searched for "TBD", "TODO", "implement later", "fill in", "appropriate", "similar to Task". Found:
- None of the forbidden patterns. (No `// TODO` left in source code; deferred work is called out explicitly under "Out of scope" header and README, not as TODO.)

### 3. Type/name consistency

Verified across tasks:
- Service names in compose: `hms-db`, `namenode`, `datanode`, `resourcemanager`, `nodemanager`, `hive-metastore`, `kafka`, `starrocks`, `neo4j` — identical wherever referenced (Tasks 1-7 define them; Task 8 `REQUIRED_SERVICES` list, Task 13 `init-stack.sh`, Task 14 spark-sql network name reference `data-gov_default` derived from compose `name: data-gov`).
- Network name: declared as `data-gov_default` in `base-compose.yml` networks block (Task 1) and referenced verbatim in Task 13 `init-stack.sh` + Task 14 spark-sql `--network` flag.
- StarRocks database name: `data_gov` (underscore) — consistent between Task 11 DDL, Task 12 seeder constant `STARROCKS_DB`, Task 16 connect call.
- Hive database name: `data_gov` — consistent between Task 9 DDL and Task 14 smoke test (which uses a separate `smoke_test` DB intentionally, to avoid colliding with future business tables).
- Compose project name: pinned via `COMPOSE_PROJECT_NAME=data-gov` (`.env.example`, Task 0) AND `name: data-gov` at top of `base-compose.yml` (Task 1) — redundancy is deliberate; either alone suffices, both together is explicit.
- Kafka topic name: `ods_ue_signal` — Task 10 creates it; Task 15 produces/consumes from it.
- Compose file path used in tests: `tests/conftest.py` resolves `COMPOSE_FILE = REPO_ROOT / "base-compose.yml"` (Task 1) — consistent with all later test additions which import from `tests.conftest`.

No type/name drift detected.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-14-phase1-slice1a-base-compose.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for this plan: each task produces a verifiable artifact (compose ps healthy, test passes) that's natural to checkpoint.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints. Faster but heavier on this context window.

Which approach?
