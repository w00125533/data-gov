# Phase 2 Slice 2c: Sandbox (Spark / Flink SQL / Java Flink Dry-Run) 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 spec §5 — 在 `backend/sandbox/` 下实现统一的"Java 骨架包装 → Maven 编译 → YARN 提交 → HDFS 回读"沙箱执行器；提供 `SandboxController.execute(code, code_type)` 与 `execute_with_retry`（沙箱层编译失败/平台失败自动 2 轮 LLM 修正）。替换 slice 2b 留下的 `backend/agent/sandbox_stub.py`，让 `dry_run_spark_sql` / `dry_run_flink_sql` / `dry_run_java_flink` 三个工具走通真实路径。完成 spec §8.2 的 P2-4 / P2-5 / P2-6 / P2-7，同时让 P2-1 / P2-2 / P2-3 的端到端验证（在 slice 2b 仅做了 mock）首次跑通。

**Architecture:** spec §3.3 已经选型 — FastAPI 容器内装 `openjdk-17` + `maven` + `apache-spark-3.5.4 client (含 spark-submit)` + `flink-1.19 client (含 flink run)` + Hadoop client 配置，沙箱模块全部通过 `subprocess` 调本地工具链；YARN 与 HDFS 通过共享的 `docker/hadoop-conf/*.xml` 直接走 base-compose 的集群。每次 dry-run 在 `/tmp/sandbox/{uuid}/` 落一个临时项目目录（`pom.xml` + `src/`），`maven_compile()` 产出 `target/*.jar` 后通过 `hdfs dfs -put` 上传到 HDFS 的 `/tmp/sandbox/jars/{uuid}.jar`，`spark-submit --master yarn` / `flink run -m yarn-cluster` 提交，YARN RM REST `:8088/ws/v1/cluster/apps/{appId}` 轮询到 `FINISHED`，再 `hdfs dfs -cat /tmp/sandbox/out/{uuid}/part-*` 读回 1 行 JSON。骨架强制要求 sink → `hdfs:///tmp/sandbox/out/{uuid}/`，由 `_sandbox_uuid` 占位符注入。沙箱层 `execute_with_retry` 最多 2 轮：第 1 轮失败解析 Maven 编译错误或 YARN container log，把摘要塞给 DeepSeek 修代码，重新走完整链路；与 Agent 层 `iteration_count` 互不计入（spec §4.5）。

**Tech Stack:**
- OpenJDK 17 (headless) + Maven 3.9
- Spark 3.5.4 client (`/opt/spark/bin/spark-submit`)
- Flink 1.19.1 client (`/opt/flink/bin/flink`)
- Hadoop 3.3.6 client (含 `hdfs` CLI)
- Python 已有：`subprocess`, `requests`, `httpx`（slice 2a 已装）
- LLM：复用 `backend.clients.deepseek.build_chat_client(temperature=0)`（slice 2a 抽离）
- Sandbox 骨架代码用纯 Java 8 兼容写法（Flink 1.19 + Spark 3.5 均支持 JDK 17 编译）

**Prerequisites (slice 1b + 2a + 2b):**
- `backend/agent/sandbox_stub.py` 暴露 `DryRunResult` dataclass 与 `execute(code, code_type)` 入口（slice 2b）
- `backend.agent.tools.dry_run_spark_sql/flink_sql/java_flink` 已经委托给 `sandbox.execute`（slice 2b Task 5）
- `backend.clients.deepseek.build_chat_client`（slice 2a Task 6）
- base-compose 提供 HDFS NameNode(`namenode:8020` / `:9870`) + YARN RM (`resourcemanager:8088` / `:8032`) + Hive Metastore(`hive-metastore:9083`)
- `docker/hadoop-conf/{core-site,hdfs-site,yarn-site,mapred-site}.xml` 已存在（slice 1a）

**Out of scope for this slice (deferred):**
- 多租户沙箱隔离 / 资源配额（spec §9 本地验证栈无鉴权）
- 沙箱执行结果的持久化与回放（slice 2c 仅返回 1 行预览）
- Spark SQL CREATE TABLE 的 schema_validate（业务校验仍由 Agent 的 schema_validate 节点处理）
- 用户自定义骨架模板（templates 是仓库内常量；slice 4 再考虑外置）
- StarRocks 沙箱（spec §5.1 三类不含 StarRocks；ADS 层验证用 Spark SQL 读 Hive 即可）
- LangSmith 跟踪沙箱事件
- 沙箱 GPU / 大内存场景 — spec §5.5 限制 local[2] / 60s 总超时

---

## File Structure

```
data-gov/
├── backend/
│   ├── sandbox/                            # NEW
│   │   ├── __init__.py
│   │   ├── models.py                       # CompileResult + DryRunResult + SubmitResult
│   │   ├── templates.py                    # template path + inject(code) 注入逻辑
│   │   ├── compile.py                      # maven_compile(project_dir) → CompileResult
│   │   ├── hdfs.py                         # hdfs_put / hdfs_cat / hdfs_mkdir 等 subprocess 包装
│   │   ├── yarn.py                         # YARN RM REST 轮询 + 应用 log 抓取
│   │   ├── submit.py                       # spark_submit + flink_run + parse_app_id
│   │   ├── error_parser.py                 # 解析 Maven / YARN log 出错误摘要
│   │   ├── retry.py                        # execute_with_retry 控制器层重试
│   │   └── controller.py                   # SandboxController.execute 完整编排
│   ├── agent/
│   │   └── sandbox_stub.py                 # MODIFIED — 委托给 backend.sandbox.controller.execute
│   └── api/
│       └── health.py                       # MODIFIED — 加 sandbox / hdfs / yarn 组件
├── templates/                              # NEW — Java 骨架模板 (Maven 项目)
│   ├── spark-sql/
│   │   ├── pom.xml                         # spark 3.5.4 + scala 2.12
│   │   └── src/main/java/SandboxSparkJob.java   # ${user_sql} + ${sandbox_uuid}
│   ├── flink-sql/
│   │   ├── pom.xml                         # flink 1.19 + flink-sql-connector-kafka / hive
│   │   └── src/main/java/SandboxFlinkSQLJob.java
│   └── flink-java/
│       ├── pom.xml
│       └── src/main/java/                  # 整 src/ 替换；约定 main class = io.datagov.sandbox.SandboxFlinkJob
│           └── io/datagov/sandbox/SandboxFlinkJob.java
├── docker/
│   └── sandbox-conf/                       # NEW
│       └── log4j2.properties               # 静默 Maven 跑 jar 时的冗余日志
├── tests/
│   └── sandbox/                            # NEW
│       ├── __init__.py
│       ├── test_models.py
│       ├── test_templates.py
│       ├── test_error_parser.py
│       ├── test_yarn.py                    # 用 responses mock RM REST
│       ├── test_hdfs.py                    # monkeypatch subprocess.run
│       ├── test_compile.py                 # 真跑 mvn — infra mark
│       ├── test_submit.py                  # monkeypatch subprocess.run
│       ├── test_controller.py              # 单元: 全链路 mock
│       ├── test_retry.py                   # 沙箱层 2 轮重试 + LLM 修正
│       └── test_p2_acceptance.py           # P2-4..P2-7 真实 YARN — infra mark
├── pyproject.toml                          # MODIFIED — 加 responses (test only)
├── .env.example                            # MODIFIED — 加 SANDBOX_* 配置
├── app-compose.yml                         # MODIFIED — 挂载 hadoop-conf + flink + 暴露 8000
└── backend/Dockerfile                      # MODIFIED — 装 JDK17 + Maven + Spark + Flink + Hadoop client
```

**职责拆分要点：**
- `models.py`：`DryRunResult`（与 slice 2b 同字段）+ `CompileResult(success, jar_path, error_log)` + `SubmitResult(application_id, final_state, diagnostics)`。
- `templates.py`：`load_template(code_type) -> Path`、`inject(template_dir, dest_dir, code, sandbox_uuid)`；模板里使用 `${user_sql}` / `${user_code_block}` / `${sandbox_uuid}` 三个占位符。
- `compile.py`：`maven_compile(project_dir) -> CompileResult`；纯 subprocess + stderr 收集。
- `hdfs.py`：`hdfs_put(local, remote)`、`hdfs_cat(remote)`、`hdfs_mkdir(remote)`、`hdfs_rm(remote, recursive=True)`；委托 `hdfs dfs` CLI；统一 `HdfsError` 异常。
- `yarn.py`：`get_app_state(app_id) -> str`、`wait_for_app(app_id, timeout=60) -> SubmitResult`、`fetch_app_diagnostics(app_id) -> str`；REST `http://resourcemanager:8088/ws/v1/cluster/apps/{app_id}`。
- `submit.py`：`spark_submit(jar_hdfs, main_class=None) -> str (app_id)`、`flink_run(jar_hdfs, main_class=None) -> str`；解析 stdout 拿 application_id。
- `error_parser.py`：`parse_maven_error(stderr) -> str`、`parse_yarn_diagnostics(text) -> str`；裁剪到 2000 字以内。
- `retry.py`：`execute_with_retry(code, code_type, max_retries=2)` 内含 LLM 修代码循环；与 `SandboxController` 同一进程内调用。
- `controller.py`：`SandboxController.execute(code, code_type) -> DryRunResult` 完整编排 7 步（template inject → compile → upload → submit → wait → read → cleanup）；总超时 60s。
- `backend/agent/sandbox_stub.py`：保留同名 `execute`/`DryRunResult` 导入；改成 `from backend.sandbox.controller import execute`。

---

## Task 0: 依赖 + Dockerfile 装工具链

**Files:**
- Modify: `pyproject.toml`（test 组加 `responses`）
- Modify: `backend/Dockerfile`
- Modify: `.env.example`
- Create: `docker/sandbox-conf/log4j2.properties`

> 这是 slice 2c 最重的一步 — 镜像会从 ~500MB 涨到 ~2GB，因为要装 OpenJDK + Maven + Spark client + Flink client。验收后单独 commit。

- [ ] **Step 1: `pyproject.toml` 在 test 组追加**

```toml
    "responses>=0.25",
```

- [ ] **Step 2: `.env.example` 追加**

```env

# Sandbox (slice 2c)
SANDBOX_BASE_DIR=/tmp/sandbox
SANDBOX_HDFS_BASE=/tmp/sandbox
SANDBOX_TOTAL_TIMEOUT=60
SANDBOX_COMPILE_TIMEOUT=20
SANDBOX_SPARK_TIMEOUT=30
SANDBOX_FLINK_TIMEOUT=45
SANDBOX_MAX_RETRIES=2
YARN_RM_URL=http://resourcemanager:8088
HDFS_DEFAULTFS=hdfs://namenode:8020
HIVE_METASTORE_URI=thrift://hive-metastore:9083
SPARK_HOME=/opt/spark
FLINK_HOME=/opt/flink
HADOOP_HOME=/opt/hadoop
HADOOP_CONF_DIR=/etc/hadoop
```

- [ ] **Step 3: 重写 `backend/Dockerfile`**

整个文件替换为：

```dockerfile
# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base

ARG SPARK_VERSION=3.5.4
ARG FLINK_VERSION=1.19.1
ARG HADOOP_VERSION=3.3.6
ARG MAVEN_VERSION=3.9.6

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    SPARK_HOME=/opt/spark \
    FLINK_HOME=/opt/flink \
    HADOOP_HOME=/opt/hadoop \
    HADOOP_CONF_DIR=/etc/hadoop \
    PATH=/opt/spark/bin:/opt/flink/bin:/opt/hadoop/bin:/opt/maven/bin:/usr/lib/jvm/java-17-openjdk-amd64/bin:$PATH

# 1) JDK + base utils
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk-headless curl ca-certificates git tini procps tar gzip \
    && rm -rf /var/lib/apt/lists/*

# 2) Maven
RUN curl -fsSL "https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz" \
    | tar -xz -C /opt && ln -s /opt/apache-maven-${MAVEN_VERSION} /opt/maven

# 3) Spark client
RUN curl -fsSL "https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop3.tgz" \
    | tar -xz -C /opt && mv /opt/spark-${SPARK_VERSION}-bin-hadoop3 /opt/spark

# 4) Flink client
RUN curl -fsSL "https://archive.apache.org/dist/flink/flink-${FLINK_VERSION}/flink-${FLINK_VERSION}-bin-scala_2.12.tgz" \
    | tar -xz -C /opt && mv /opt/flink-${FLINK_VERSION} /opt/flink

# 5) Hadoop client (含 hdfs / yarn CLI)
RUN curl -fsSL "https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz" \
    | tar -xz -C /opt && mv /opt/hadoop-${HADOOP_VERSION} /opt/hadoop

WORKDIR /app

COPY pyproject.toml /app/
COPY backend/ /app/backend/

RUN pip install --no-cache-dir -e ".[runtime]"

# Pre-warm bge model (slice 2a 已加)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

ENV PYTHONPATH=/app
EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: 创建 `docker/sandbox-conf/log4j2.properties`**

```properties
rootLogger.level = WARN
rootLogger.appenderRef.console.ref = STDOUT

appender.console.type = Console
appender.console.name = STDOUT
appender.console.target = SYSTEM_ERR
appender.console.layout.type = PatternLayout
appender.console.layout.pattern = %d{HH:mm:ss} %-5p %c{1} - %m%n

logger.spark.name = org.apache.spark
logger.spark.level = WARN
logger.flink.name = org.apache.flink
logger.flink.level = WARN
logger.hadoop.name = org.apache.hadoop
logger.hadoop.level = ERROR
```

- [ ] **Step 5: 本地构建镜像（耗时 ~10 分钟，需要外网拉 Spark/Flink/Hadoop）**

```bash
docker compose -f app-compose.yml build backend
```

预期：构建成功；`docker run --rm data-gov-backend java -version` 输出 `openjdk version "17"`；`docker run --rm data-gov-backend mvn -v` 输出 `Apache Maven 3.9.6`；`docker run --rm data-gov-backend spark-submit --version` 与 `flink --version` 都 0 退出。

- [ ] **Step 6: 提交**

```bash
git add backend/Dockerfile pyproject.toml .env.example docker/sandbox-conf
git commit -m "feat(sandbox): install JDK17 + Maven + Spark + Flink + Hadoop client into backend image"
```

---

## Task 1: Sandbox 配置项 + 共享 dataclass

**Files:**
- Modify: `backend/config.py`
- Create: `backend/sandbox/__init__.py`
- Create: `backend/sandbox/models.py`
- Create: `tests/sandbox/__init__.py`
- Create: `tests/sandbox/test_models.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/sandbox/test_models.py"""
from backend.sandbox.models import CompileResult, DryRunResult, SubmitResult


def test_compile_result_defaults():
    r = CompileResult(success=True, jar_path="/tmp/x.jar")
    assert r.success
    assert r.error_log is None


def test_dry_run_result_compatible_with_slice2b_stub():
    """slice 2b 期望的字段必须存在。"""
    r = DryRunResult(success=True, preview_row={"a": 1}, error_log=None, application_id="app_1")
    assert r.success and r.preview_row == {"a": 1}


def test_submit_result_fields():
    s = SubmitResult(application_id="app_1", final_state="FINISHED", diagnostics="")
    assert s.application_id == "app_1"
    assert s.final_state == "FINISHED"


def test_config_sandbox_defaults(monkeypatch):
    from backend.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    assert s.sandbox_base_dir == "/tmp/sandbox"
    assert s.sandbox_hdfs_base == "/tmp/sandbox"
    assert s.sandbox_total_timeout == 60
    assert s.sandbox_compile_timeout == 20
    assert s.sandbox_spark_timeout == 30
    assert s.sandbox_flink_timeout == 45
    assert s.sandbox_max_retries == 2
    assert s.yarn_rm_url == "http://resourcemanager:8088"
    assert s.hdfs_defaultfs == "hdfs://namenode:8020"
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/sandbox/test_models.py -v
```

预期：FAIL — `ModuleNotFoundError` + 配置缺字段。

- [ ] **Step 3: 修改 `backend/config.py` — 追加 sandbox 字段**

在 `Settings` 类末尾加：

```python
    # Sandbox (slice 2c)
    sandbox_base_dir: str = Field("/tmp/sandbox", alias="SANDBOX_BASE_DIR")
    sandbox_hdfs_base: str = Field("/tmp/sandbox", alias="SANDBOX_HDFS_BASE")
    sandbox_total_timeout: int = Field(60, alias="SANDBOX_TOTAL_TIMEOUT")
    sandbox_compile_timeout: int = Field(20, alias="SANDBOX_COMPILE_TIMEOUT")
    sandbox_spark_timeout: int = Field(30, alias="SANDBOX_SPARK_TIMEOUT")
    sandbox_flink_timeout: int = Field(45, alias="SANDBOX_FLINK_TIMEOUT")
    sandbox_max_retries: int = Field(2, alias="SANDBOX_MAX_RETRIES")
    yarn_rm_url: str = Field("http://resourcemanager:8088", alias="YARN_RM_URL")
    hdfs_defaultfs: str = Field("hdfs://namenode:8020", alias="HDFS_DEFAULTFS")
    hive_metastore_uri: str = Field("thrift://hive-metastore:9083", alias="HIVE_METASTORE_URI")
```

- [ ] **Step 4: 实现 `backend/sandbox/models.py`**

```python
"""Sandbox dataclasses — shared by all submodules and re-exported by sandbox_stub for slice 2b 兼容。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CompileResult:
    success: bool
    jar_path: Optional[str] = None
    error_log: Optional[str] = None


@dataclass
class SubmitResult:
    application_id: str
    final_state: str            # "FINISHED" | "FAILED" | "KILLED" | "RUNNING" | ...
    diagnostics: str = ""


@dataclass
class DryRunResult:
    success: bool
    preview_row: Optional[dict] = None
    error_log: Optional[str] = None
    application_id: Optional[str] = None
```

`backend/sandbox/__init__.py` 留空。

- [ ] **Step 5: 测试通过**

```bash
pytest tests/sandbox/test_models.py -v
```

预期：PASS (4/4)。

- [ ] **Step 6: 提交**

```bash
git add backend/config.py backend/sandbox tests/sandbox/test_models.py tests/sandbox/__init__.py
git commit -m "feat(sandbox): config + shared dataclasses"
```

---

## Task 2: 骨架模板 — Maven 项目 (3 个 code_type)

**Files:**
- Create: `templates/spark-sql/pom.xml`
- Create: `templates/spark-sql/src/main/java/SandboxSparkJob.java`
- Create: `templates/flink-sql/pom.xml`
- Create: `templates/flink-sql/src/main/java/SandboxFlinkSQLJob.java`
- Create: `templates/flink-java/pom.xml`
- Create: `templates/flink-java/src/main/java/io/datagov/sandbox/SandboxFlinkJob.java`
- Create: `backend/sandbox/templates.py`
- Create: `tests/sandbox/test_templates.py`

> 三个模板里全部使用 `${user_sql}` / `${user_code_block}` / `${sandbox_uuid}` 三个占位符，由 `inject()` 在拷贝时替换。Maven 编译会直接跑这份 source，不依赖 maven-resources-plugin filter。

- [ ] **Step 1: 创建 `templates/spark-sql/pom.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>io.datagov</groupId>
  <artifactId>sandbox-spark-sql</artifactId>
  <version>1.0.0</version>
  <packaging>jar</packaging>

  <properties>
    <maven.compiler.source>17</maven.compiler.source>
    <maven.compiler.target>17</maven.compiler.target>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <spark.version>3.5.4</spark.version>
  </properties>

  <dependencies>
    <dependency>
      <groupId>org.apache.spark</groupId>
      <artifactId>spark-sql_2.12</artifactId>
      <version>${spark.version}</version>
      <scope>provided</scope>
    </dependency>
    <dependency>
      <groupId>org.apache.spark</groupId>
      <artifactId>spark-hive_2.12</artifactId>
      <version>${spark.version}</version>
      <scope>provided</scope>
    </dependency>
  </dependencies>

  <build>
    <finalName>sandbox-spark-sql</finalName>
    <plugins>
      <plugin>
        <artifactId>maven-jar-plugin</artifactId>
        <version>3.3.0</version>
        <configuration>
          <archive>
            <manifest>
              <mainClass>SandboxSparkJob</mainClass>
            </manifest>
          </archive>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
```

- [ ] **Step 2: 创建 `templates/spark-sql/src/main/java/SandboxSparkJob.java`**

```java
import org.apache.spark.sql.Dataset;
import org.apache.spark.sql.Row;
import org.apache.spark.sql.SparkSession;

public final class SandboxSparkJob {
    public static void main(String[] args) {
        String sandboxUuid = "${sandbox_uuid}";
        String outputPath = "hdfs:///tmp/sandbox/out/" + sandboxUuid;

        SparkSession spark = SparkSession.builder()
            .appName("data-gov-sandbox-" + sandboxUuid)
            .enableHiveSupport()
            .getOrCreate();

        // 用户 SQL 注入点（一条 SELECT；DDL 用户用 spark.sql() 串内）
        String userSql = "${user_sql}";
        Dataset<Row> df = spark.sql(userSql);
        df.limit(1).coalesce(1).write().mode("overwrite").json(outputPath);

        spark.stop();
    }
}
```

- [ ] **Step 3: 创建 `templates/flink-sql/pom.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>io.datagov</groupId>
  <artifactId>sandbox-flink-sql</artifactId>
  <version>1.0.0</version>
  <packaging>jar</packaging>

  <properties>
    <maven.compiler.source>17</maven.compiler.source>
    <maven.compiler.target>17</maven.compiler.target>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <flink.version>1.19.1</flink.version>
  </properties>

  <dependencies>
    <dependency>
      <groupId>org.apache.flink</groupId>
      <artifactId>flink-table-api-java-bridge</artifactId>
      <version>${flink.version}</version>
      <scope>provided</scope>
    </dependency>
    <dependency>
      <groupId>org.apache.flink</groupId>
      <artifactId>flink-table-planner_2.12</artifactId>
      <version>${flink.version}</version>
      <scope>provided</scope>
    </dependency>
    <dependency>
      <groupId>org.apache.flink</groupId>
      <artifactId>flink-streaming-java</artifactId>
      <version>${flink.version}</version>
      <scope>provided</scope>
    </dependency>
    <dependency>
      <groupId>org.apache.flink</groupId>
      <artifactId>flink-sql-connector-kafka</artifactId>
      <version>3.2.0-1.19</version>
    </dependency>
  </dependencies>

  <build>
    <finalName>sandbox-flink-sql</finalName>
    <plugins>
      <plugin>
        <artifactId>maven-jar-plugin</artifactId>
        <version>3.3.0</version>
        <configuration>
          <archive>
            <manifest>
              <mainClass>SandboxFlinkSQLJob</mainClass>
            </manifest>
          </archive>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
```

- [ ] **Step 4: 创建 `templates/flink-sql/src/main/java/SandboxFlinkSQLJob.java`**

```java
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.table.api.EnvironmentSettings;
import org.apache.flink.table.api.bridge.java.StreamTableEnvironment;

public final class SandboxFlinkSQLJob {
    public static void main(String[] args) throws Exception {
        String sandboxUuid = "${sandbox_uuid}";
        String outputPath = "hdfs:///tmp/sandbox/out/" + sandboxUuid;

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);
        StreamTableEnvironment tEnv = StreamTableEnvironment.create(
            env, EnvironmentSettings.newInstance().inStreamingMode().build());

        // 默认 sink 表 - 用户 SQL 可以用 INSERT INTO sandbox_sink 写入
        tEnv.executeSql(String.format(
            "CREATE TABLE sandbox_sink (data STRING) WITH (" +
            "  'connector' = 'filesystem', " +
            "  'path' = '%s', " +
            "  'format' = 'json'" +
            ")", outputPath));

        // 用户 SQL 注入点 — 多条语句用 ; 分隔
        String userSql = "${user_sql}";
        for (String stmt : userSql.split(";")) {
            String trimmed = stmt.trim();
            if (!trimmed.isEmpty()) {
                tEnv.executeSql(trimmed);
            }
        }
    }
}
```

- [ ] **Step 5: 创建 `templates/flink-java/pom.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>io.datagov</groupId>
  <artifactId>sandbox-flink-java</artifactId>
  <version>1.0.0</version>
  <packaging>jar</packaging>

  <properties>
    <maven.compiler.source>17</maven.compiler.source>
    <maven.compiler.target>17</maven.compiler.target>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <flink.version>1.19.1</flink.version>
  </properties>

  <dependencies>
    <dependency>
      <groupId>org.apache.flink</groupId>
      <artifactId>flink-streaming-java</artifactId>
      <version>${flink.version}</version>
      <scope>provided</scope>
    </dependency>
    <dependency>
      <groupId>org.apache.flink</groupId>
      <artifactId>flink-clients</artifactId>
      <version>${flink.version}</version>
      <scope>provided</scope>
    </dependency>
    <dependency>
      <groupId>org.apache.flink</groupId>
      <artifactId>flink-sql-connector-kafka</artifactId>
      <version>3.2.0-1.19</version>
    </dependency>
  </dependencies>

  <build>
    <finalName>sandbox-flink-java</finalName>
    <plugins>
      <plugin>
        <artifactId>maven-jar-plugin</artifactId>
        <version>3.3.0</version>
        <configuration>
          <archive>
            <manifest>
              <mainClass>io.datagov.sandbox.SandboxFlinkJob</mainClass>
            </manifest>
          </archive>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
```

- [ ] **Step 6: 创建 `templates/flink-java/src/main/java/io/datagov/sandbox/SandboxFlinkJob.java`**

```java
package io.datagov.sandbox;

// 用户代码块完整替换该类体内容。
// 约定 sink 路径: hdfs:///tmp/sandbox/out/${sandbox_uuid}/
// 用户可以使用占位符 ${sandbox_uuid} 在常量字符串里引用 uuid。
public final class SandboxFlinkJob {
    public static final String SANDBOX_UUID = "${sandbox_uuid}";
    public static final String SANDBOX_OUTPUT = "hdfs:///tmp/sandbox/out/" + SANDBOX_UUID;

    ${user_code_block}
}
```

- [ ] **Step 7: 失败测试**

```python
"""tests/sandbox/test_templates.py"""
from pathlib import Path

import pytest

from backend.sandbox.templates import load_template, inject


def test_load_template_returns_dir(tmp_path):
    src = load_template("spark_sql")
    assert (src / "pom.xml").exists()
    assert (src / "src/main/java/SandboxSparkJob.java").exists()


def test_load_template_unknown_raises():
    with pytest.raises(ValueError, match="code_type"):
        load_template("python")


def test_inject_replaces_placeholders(tmp_path):
    dest = tmp_path / "project"
    inject(
        code_type="spark_sql",
        dest_dir=dest,
        user_code="SELECT 1 AS x",
        sandbox_uuid="abc123",
    )
    java = (dest / "src/main/java/SandboxSparkJob.java").read_text(encoding="utf-8")
    assert "abc123" in java
    assert "SELECT 1 AS x" in java
    assert "${user_sql}" not in java
    assert "${sandbox_uuid}" not in java


def test_inject_flink_java_replaces_user_code_block(tmp_path):
    dest = tmp_path / "p"
    body = (
        "public static void main(String[] args) throws Exception { "
        "System.out.println(SANDBOX_UUID); }"
    )
    inject(code_type="java_flink", dest_dir=dest, user_code=body, sandbox_uuid="u1")
    src = (dest / "src/main/java/io/datagov/sandbox/SandboxFlinkJob.java").read_text(encoding="utf-8")
    assert body in src
    assert "${user_code_block}" not in src
```

- [ ] **Step 8: 实现 `backend/sandbox/templates.py`**

```python
"""模板加载 + 占位符注入。"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal


_CODE_TYPE_TO_DIR = {
    "spark_sql": "spark-sql",
    "flink_sql": "flink-sql",
    "java_flink": "flink-java",
}


def _repo_root() -> Path:
    # 容器内是 /app；本地是仓库根。
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "templates" / "spark-sql" / "pom.xml").exists():
            return parent
    raise RuntimeError("Cannot locate repo root with templates/ dir.")


def load_template(code_type: str) -> Path:
    if code_type not in _CODE_TYPE_TO_DIR:
        raise ValueError(f"Unknown code_type: {code_type!r}")
    return _repo_root() / "templates" / _CODE_TYPE_TO_DIR[code_type]


def _replace_in_file(path: Path, mapping: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for k, v in mapping.items():
        text = text.replace(k, v)
    path.write_text(text, encoding="utf-8")


def inject(
    *,
    code_type: str,
    dest_dir: Path,
    user_code: str,
    sandbox_uuid: str,
) -> Path:
    """把模板目录递归 copy 到 dest_dir, 替换 ${user_sql}/${user_code_block}/${sandbox_uuid}。"""
    src = load_template(code_type)
    dest_dir = Path(dest_dir)
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(src, dest_dir)

    placeholder = "${user_code_block}" if code_type == "java_flink" else "${user_sql}"
    mapping = {placeholder: user_code, "${sandbox_uuid}": sandbox_uuid}
    for java_file in dest_dir.rglob("*.java"):
        _replace_in_file(java_file, mapping)
    # pom.xml 也支持 sandbox_uuid（用户骨架可能在 finalName 里引用，预留）
    pom = dest_dir / "pom.xml"
    if pom.exists():
        _replace_in_file(pom, {"${sandbox_uuid}": sandbox_uuid})
    return dest_dir
```

- [ ] **Step 9: 测试通过**

```bash
pytest tests/sandbox/test_templates.py -v
```

预期：PASS (4/4)。

- [ ] **Step 10: 提交**

```bash
git add templates backend/sandbox/templates.py tests/sandbox/test_templates.py
git commit -m "feat(sandbox): Maven templates for spark_sql / flink_sql / java_flink + inject()"
```

---

## Task 3: error_parser — 解析 Maven & YARN 错误

**Files:**
- Create: `backend/sandbox/error_parser.py`
- Create: `tests/sandbox/test_error_parser.py`

> 解析必须**可单测**且**确定性**；不调任何 LLM。

- [ ] **Step 1: 失败测试**

```python
"""tests/sandbox/test_error_parser.py"""
from backend.sandbox.error_parser import parse_maven_error, parse_yarn_diagnostics


MVN_STDERR_COMPILE_FAIL = """[INFO] --- maven-compiler-plugin:3.10.1:compile ---
[ERROR] /tmp/sandbox/abc/src/main/java/SandboxSparkJob.java:[24,16] cannot find symbol
  symbol:   class Dataset2
  location: package org.apache.spark.sql
[INFO] 1 error
[INFO] BUILD FAILURE
"""

YARN_DIAG_NULL_POINTER = """Application application_1234_0001 failed 2 times due to AM Container for appattempt_xxx exited with  exitCode: 1
For more detailed output, check application tracking page:http://rm:8088/cluster/app/application_1234_0001Then click on links to logs of each attempt.
Diagnostics: Exception from container-launch.
Container exited with a non-zero exit code 1
java.lang.NullPointerException
\tat org.example.UserJob.main(UserJob.java:17)
"""


def test_parse_maven_error_extracts_first_error_line():
    summary = parse_maven_error(MVN_STDERR_COMPILE_FAIL)
    assert "cannot find symbol" in summary
    assert "Dataset2" in summary
    assert "SandboxSparkJob.java" in summary


def test_parse_maven_error_truncates_to_2000_chars():
    big = MVN_STDERR_COMPILE_FAIL + ("x" * 5000)
    assert len(parse_maven_error(big)) <= 2000


def test_parse_yarn_diagnostics_extracts_exception_name():
    summary = parse_yarn_diagnostics(YARN_DIAG_NULL_POINTER)
    assert "NullPointerException" in summary
    assert "UserJob.java:17" in summary or "UserJob" in summary


def test_parse_yarn_diagnostics_handles_empty():
    assert parse_yarn_diagnostics("") == ""


def test_parse_maven_error_handles_no_error_markers():
    assert parse_maven_error("BUILD SUCCESS") == ""
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/sandbox/test_error_parser.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现 `backend/sandbox/error_parser.py`**

```python
"""Maven / YARN 错误解析 — 输出 ≤2000 字摘要喂给 LLM。"""
from __future__ import annotations

import re

_MAX = 2000

_MVN_ERROR_LINE = re.compile(r"^\[ERROR\]\s+(?P<msg>.+)$", re.MULTILINE)
_JAVA_EXCEPTION = re.compile(r"(java(?:x)?\.\w[\w\.]*Exception(?::\s.*)?)", re.MULTILINE)
_JAVA_AT_FRAME = re.compile(r"^\s*at\s+(?P<frame>[\w\.\$<>]+)\(([^)]+)\)", re.MULTILINE)


def parse_maven_error(stderr: str) -> str:
    if not stderr or "BUILD FAILURE" not in stderr and "[ERROR]" not in stderr:
        return ""
    lines = [m.group("msg") for m in _MVN_ERROR_LINE.finditer(stderr)]
    # 去掉 BUILD FAILURE / Reactor Summary 这种汇总性
    keep = [l for l in lines if "BUILD FAILURE" not in l and "Reactor" not in l]
    body = "\n".join(keep[:30])
    return body[:_MAX]


def parse_yarn_diagnostics(diagnostics: str) -> str:
    if not diagnostics:
        return ""
    excs = _JAVA_EXCEPTION.findall(diagnostics)
    frames = _JAVA_AT_FRAME.findall(diagnostics)
    parts: list[str] = []
    if excs:
        parts.append("Exceptions:")
        parts.extend(f"  {e}" for e in excs[:5])
    if frames:
        parts.append("First frames:")
        parts.extend(f"  at {fr}({loc})" for fr, loc in frames[:5])
    if not parts:
        # 兜底: 把 Diagnostics 行抽出来
        snippet = "\n".join(
            l for l in diagnostics.splitlines() if l.startswith("Diagnostics:") or "exitCode" in l
        )
        return snippet[:_MAX]
    return "\n".join(parts)[:_MAX]
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/sandbox/test_error_parser.py -v
```

预期：PASS (5/5)。

- [ ] **Step 5: 提交**

```bash
git add backend/sandbox/error_parser.py tests/sandbox/test_error_parser.py
git commit -m "feat(sandbox): deterministic Maven / YARN error parsers"
```

---

## Task 4: HDFS CLI 包装

**Files:**
- Create: `backend/sandbox/hdfs.py`
- Create: `tests/sandbox/test_hdfs.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/sandbox/test_hdfs.py — monkeypatch subprocess.run。"""
from unittest.mock import MagicMock

import pytest

from backend.sandbox.hdfs import HdfsError, hdfs_cat, hdfs_mkdir, hdfs_put, hdfs_rm


def _run_ok(stdout: str = "", stderr: str = ""):
    m = MagicMock()
    m.returncode = 0
    m.stdout = stdout
    m.stderr = stderr
    return m


def _run_fail(stderr: str = "boom", code: int = 1):
    m = MagicMock()
    m.returncode = code
    m.stdout = ""
    m.stderr = stderr
    return m


def test_hdfs_put_builds_correct_cmd(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output=True, text=True, timeout=None, check=False):
        captured["cmd"] = cmd
        return _run_ok()

    monkeypatch.setattr("backend.sandbox.hdfs.subprocess.run", fake_run)
    hdfs_put("/local/x.jar", "/tmp/x.jar")
    assert "dfs" in captured["cmd"]
    assert "-put" in captured["cmd"]
    assert "/local/x.jar" in captured["cmd"]
    assert "/tmp/x.jar" in captured["cmd"]


def test_hdfs_put_raises_on_nonzero(monkeypatch):
    monkeypatch.setattr("backend.sandbox.hdfs.subprocess.run",
                        lambda *a, **kw: _run_fail("permission denied"))
    with pytest.raises(HdfsError, match="permission denied"):
        hdfs_put("/x", "/y")


def test_hdfs_cat_returns_stdout(monkeypatch):
    monkeypatch.setattr("backend.sandbox.hdfs.subprocess.run",
                        lambda *a, **kw: _run_ok(stdout='{"a":1}\n'))
    text = hdfs_cat("/tmp/out/part-0.json")
    assert text == '{"a":1}\n'


def test_hdfs_mkdir_uses_p_flag(monkeypatch):
    captured = {}
    monkeypatch.setattr("backend.sandbox.hdfs.subprocess.run",
                        lambda cmd, **kw: (captured.setdefault("cmd", cmd), _run_ok())[1])
    hdfs_mkdir("/tmp/sandbox/jars")
    assert "-mkdir" in captured["cmd"]
    assert "-p" in captured["cmd"]


def test_hdfs_rm_recursive(monkeypatch):
    captured = {}
    monkeypatch.setattr("backend.sandbox.hdfs.subprocess.run",
                        lambda cmd, **kw: (captured.setdefault("cmd", cmd), _run_ok())[1])
    hdfs_rm("/tmp/sandbox/out/abc", recursive=True)
    assert "-rm" in captured["cmd"] and "-r" in captured["cmd"]
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/sandbox/test_hdfs.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现 `backend/sandbox/hdfs.py`**

```python
"""HDFS CLI 包装 — `hdfs dfs ...` subprocess。所有错误归一为 HdfsError。"""
from __future__ import annotations

import os
import subprocess


class HdfsError(RuntimeError):
    pass


_HDFS_BIN = os.environ.get("HADOOP_HOME", "/opt/hadoop") + "/bin/hdfs"


def _run(args: list[str], timeout: int = 30) -> str:
    cmd = [_HDFS_BIN, "dfs", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if r.returncode != 0:
        raise HdfsError(f"hdfs {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def hdfs_mkdir(path: str) -> None:
    _run(["-mkdir", "-p", path])


def hdfs_put(local_path: str, remote_path: str) -> None:
    _run(["-put", "-f", local_path, remote_path])


def hdfs_cat(remote_path: str) -> str:
    return _run(["-cat", remote_path])


def hdfs_rm(remote_path: str, *, recursive: bool = False) -> None:
    args = ["-rm"]
    if recursive:
        args.append("-r")
    args += ["-f", remote_path]
    _run(args)


def hdfs_ls(remote_path: str) -> list[str]:
    out = _run(["-ls", remote_path])
    paths: list[str] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 8:
            paths.append(parts[-1])
    return paths
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/sandbox/test_hdfs.py -v
```

预期：PASS (5/5)。

- [ ] **Step 5: 提交**

```bash
git add backend/sandbox/hdfs.py tests/sandbox/test_hdfs.py
git commit -m "feat(sandbox): HDFS CLI wrappers (put/cat/mkdir/rm/ls)"
```

---

## Task 5: YARN RM REST 轮询

**Files:**
- Create: `backend/sandbox/yarn.py`
- Create: `tests/sandbox/test_yarn.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/sandbox/test_yarn.py — 用 responses 库 mock RM REST。"""
import pytest
import responses

from backend.sandbox.yarn import YarnError, fetch_app_diagnostics, get_app_state, wait_for_app


@responses.activate
def test_get_app_state_returns_state_field():
    responses.add(
        responses.GET,
        "http://rm:8088/ws/v1/cluster/apps/application_1_0001",
        json={"app": {"state": "RUNNING", "finalStatus": "UNDEFINED"}},
        status=200,
    )
    assert get_app_state("application_1_0001", rm_url="http://rm:8088") == "RUNNING"


@responses.activate
def test_wait_for_app_returns_finished():
    responses.add(
        responses.GET,
        "http://rm:8088/ws/v1/cluster/apps/app_x",
        json={"app": {"state": "FINISHED", "finalStatus": "SUCCEEDED", "diagnostics": ""}},
        status=200,
    )
    out = wait_for_app("app_x", rm_url="http://rm:8088", timeout=2, poll_interval=0.05)
    assert out.final_state == "FINISHED"


@responses.activate
def test_wait_for_app_raises_on_failure():
    responses.add(
        responses.GET,
        "http://rm:8088/ws/v1/cluster/apps/app_y",
        json={"app": {"state": "FINISHED", "finalStatus": "FAILED",
                       "diagnostics": "NullPointerException at line 17"}},
        status=200,
    )
    with pytest.raises(YarnError, match="FAILED"):
        wait_for_app("app_y", rm_url="http://rm:8088", timeout=2, poll_interval=0.05)


@responses.activate
def test_wait_for_app_times_out_when_stuck_running():
    responses.add(
        responses.GET,
        "http://rm:8088/ws/v1/cluster/apps/app_z",
        json={"app": {"state": "RUNNING", "finalStatus": "UNDEFINED"}},
        status=200,
    )
    with pytest.raises(YarnError, match="timeout"):
        wait_for_app("app_z", rm_url="http://rm:8088", timeout=0.2, poll_interval=0.05)


@responses.activate
def test_fetch_app_diagnostics():
    responses.add(
        responses.GET,
        "http://rm:8088/ws/v1/cluster/apps/app_w",
        json={"app": {"state": "FINISHED", "finalStatus": "FAILED",
                       "diagnostics": "boom"}},
        status=200,
    )
    assert "boom" in fetch_app_diagnostics("app_w", rm_url="http://rm:8088")
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/sandbox/test_yarn.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现 `backend/sandbox/yarn.py`**

```python
"""YARN RM REST API — 轮询应用最终状态 + 抓 diagnostics。"""
from __future__ import annotations

import time

import requests

from backend.sandbox.models import SubmitResult


class YarnError(RuntimeError):
    pass


_TERMINAL_STATES = {"FINISHED", "FAILED", "KILLED"}
_SUCCESS_STATUS = {"SUCCEEDED"}


def _get_app(app_id: str, *, rm_url: str, timeout: float = 5.0) -> dict:
    url = f"{rm_url}/ws/v1/cluster/apps/{app_id}"
    r = requests.get(url, timeout=timeout)
    if r.status_code != 200:
        raise YarnError(f"YARN RM returned {r.status_code} for {app_id}: {r.text[:300]}")
    payload = r.json()
    if "app" not in payload:
        raise YarnError(f"YARN RM payload missing 'app': {payload}")
    return payload["app"]


def get_app_state(app_id: str, *, rm_url: str) -> str:
    return _get_app(app_id, rm_url=rm_url)["state"]


def fetch_app_diagnostics(app_id: str, *, rm_url: str) -> str:
    return _get_app(app_id, rm_url=rm_url).get("diagnostics", "") or ""


def wait_for_app(
    app_id: str,
    *,
    rm_url: str,
    timeout: float,
    poll_interval: float = 1.0,
) -> SubmitResult:
    start = time.monotonic()
    while True:
        app = _get_app(app_id, rm_url=rm_url)
        state = app["state"]
        final_status = app.get("finalStatus", "UNDEFINED")
        if state in _TERMINAL_STATES:
            if state == "FINISHED" and final_status in _SUCCESS_STATUS:
                return SubmitResult(application_id=app_id, final_state=state,
                                     diagnostics=app.get("diagnostics", "") or "")
            raise YarnError(
                f"YARN app {app_id} {state} ({final_status}): {app.get('diagnostics', '')[:1000]}"
            )
        if time.monotonic() - start > timeout:
            raise YarnError(f"YARN app {app_id} wait timeout after {timeout}s; last state={state}")
        time.sleep(poll_interval)
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/sandbox/test_yarn.py -v
```

预期：PASS (5/5)。

- [ ] **Step 5: 提交**

```bash
git add backend/sandbox/yarn.py tests/sandbox/test_yarn.py
git commit -m "feat(sandbox): YARN RM REST polling with terminal state detection"
```

---

## Task 6: Maven 编译

**Files:**
- Create: `backend/sandbox/compile.py`
- Create: `tests/sandbox/test_compile.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/sandbox/test_compile.py"""
from unittest.mock import MagicMock

import pytest

from backend.sandbox.compile import maven_compile


def _r(returncode=0, stdout="", stderr=""):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


def test_compile_success_returns_jar_path(monkeypatch, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "sandbox-spark-sql.jar").write_bytes(b"\x00")

    monkeypatch.setattr("backend.sandbox.compile.subprocess.run",
                        lambda *a, **kw: _r(0, "BUILD SUCCESS"))
    r = maven_compile(tmp_path)
    assert r.success is True
    assert r.jar_path.endswith(".jar")


def test_compile_failure_returns_parsed_error(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.sandbox.compile.subprocess.run",
                        lambda *a, **kw: _r(1, "[INFO] xxx\n[ERROR] /x.java:[10,5] cannot find symbol\n[INFO] BUILD FAILURE"))
    r = maven_compile(tmp_path)
    assert r.success is False
    assert "cannot find symbol" in r.error_log


def test_compile_picks_first_jar_under_target(monkeypatch, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "sandbox-flink-sql.jar").write_bytes(b"\x00")
    monkeypatch.setattr("backend.sandbox.compile.subprocess.run",
                        lambda *a, **kw: _r(0))
    r = maven_compile(tmp_path)
    assert r.jar_path.endswith("sandbox-flink-sql.jar")
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/sandbox/test_compile.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现 `backend/sandbox/compile.py`**

```python
"""Maven 编译 — 在指定项目目录跑 `mvn -q -B -DskipTests package`。"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from backend.config import get_settings
from backend.sandbox.error_parser import parse_maven_error
from backend.sandbox.models import CompileResult


def maven_compile(project_dir: Path) -> CompileResult:
    settings = get_settings()
    project_dir = Path(project_dir)
    cmd = ["mvn", "-q", "-B", "-DskipTests", "package"]
    r = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=settings.sandbox_compile_timeout,
        check=False,
    )
    if r.returncode != 0:
        return CompileResult(success=False,
                              error_log=parse_maven_error(r.stdout + "\n" + r.stderr))
    target = project_dir / "target"
    jars = sorted(target.glob("*.jar"))
    if not jars:
        return CompileResult(success=False,
                              error_log=f"No JAR produced in {target}")
    return CompileResult(success=True, jar_path=str(jars[0]))
```

- [ ] **Step 4: 单元测试通过**

```bash
pytest tests/sandbox/test_compile.py -v
```

预期：PASS (3/3)。

- [ ] **Step 5: （可选）补一个真实 mvn 集成测试（infra mark）**

新增 `tests/sandbox/test_compile_real.py`（infra-only，确认 mvn 链路联通）：

```python
import pathlib
import pytest

from backend.sandbox.templates import inject
from backend.sandbox.compile import maven_compile

pytestmark = pytest.mark.infra


def test_compile_real_spark_sql_template(tmp_path):
    dest = tmp_path / "proj"
    inject(code_type="spark_sql", dest_dir=dest, user_code="SELECT 1 AS x", sandbox_uuid="t1")
    r = maven_compile(dest)
    assert r.success is True, r.error_log
    assert pathlib.Path(r.jar_path).exists()
```

> 此测试在 backend 容器内运行（需要 mvn）；本地无 mvn 时 skip。

- [ ] **Step 6: 提交**

```bash
git add backend/sandbox/compile.py tests/sandbox/test_compile.py tests/sandbox/test_compile_real.py
git commit -m "feat(sandbox): Maven compile with error parsing + integration test"
```

---

## Task 7: spark-submit / flink run 子进程

**Files:**
- Create: `backend/sandbox/submit.py`
- Create: `tests/sandbox/test_submit.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/sandbox/test_submit.py — monkeypatch subprocess.run; 解析 app_id。"""
from unittest.mock import MagicMock

import pytest

from backend.sandbox.submit import (
    SubmitError, flink_run, parse_app_id_from_spark, parse_app_id_from_flink, spark_submit,
)


def _r(rc=0, stdout="", stderr=""):
    m = MagicMock()
    m.returncode = rc
    m.stdout = stdout
    m.stderr = stderr
    return m


SPARK_STDERR = """24/05/14 10:00:01 INFO yarn.Client: Submitting application application_1715680000000_0042 to ResourceManager
24/05/14 10:00:02 INFO yarn.Client: Application report for application_1715680000000_0042 (state: SUBMITTED)
"""

FLINK_STDOUT = """SLF4J: Class path contains multiple SLF4J bindings.
Job has been submitted with JobID 1234abcd
2024-05-14 10:00:05,123 INFO  org.apache.flink.yarn.YarnClusterClientFactory  [] - Submitting application_1715680000000_0099 to YARN
"""


def test_parse_app_id_from_spark():
    assert parse_app_id_from_spark(SPARK_STDERR) == "application_1715680000000_0042"


def test_parse_app_id_from_flink():
    assert parse_app_id_from_flink(FLINK_STDOUT) == "application_1715680000000_0099"


def test_parse_app_id_returns_empty_when_absent():
    assert parse_app_id_from_spark("nothing here") == ""
    assert parse_app_id_from_flink("nothing here") == ""


def test_spark_submit_returns_app_id(monkeypatch):
    monkeypatch.setattr("backend.sandbox.submit.subprocess.run",
                        lambda *a, **kw: _r(stdout="", stderr=SPARK_STDERR))
    app_id = spark_submit("hdfs:///tmp/x.jar")
    assert app_id == "application_1715680000000_0042"


def test_spark_submit_raises_on_failure(monkeypatch):
    monkeypatch.setattr("backend.sandbox.submit.subprocess.run",
                        lambda *a, **kw: _r(rc=1, stderr="ClassNotFoundException"))
    with pytest.raises(SubmitError, match="ClassNotFoundException"):
        spark_submit("hdfs:///tmp/x.jar")


def test_flink_run_returns_app_id(monkeypatch):
    monkeypatch.setattr("backend.sandbox.submit.subprocess.run",
                        lambda *a, **kw: _r(stdout=FLINK_STDOUT, stderr=""))
    assert flink_run("hdfs:///tmp/x.jar") == "application_1715680000000_0099"
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/sandbox/test_submit.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现 `backend/sandbox/submit.py`**

```python
"""spark-submit / flink run 子进程包装。"""
from __future__ import annotations

import os
import re
import subprocess
from typing import Optional

from backend.config import get_settings


class SubmitError(RuntimeError):
    pass


_APP_ID_RE = re.compile(r"(application_\d+_\d+)")


def parse_app_id_from_spark(stderr: str) -> str:
    m = _APP_ID_RE.search(stderr)
    return m.group(1) if m else ""


def parse_app_id_from_flink(stdout: str) -> str:
    m = _APP_ID_RE.search(stdout)
    return m.group(1) if m else ""


def _spark_bin() -> str:
    return os.path.join(os.environ.get("SPARK_HOME", "/opt/spark"), "bin", "spark-submit")


def _flink_bin() -> str:
    return os.path.join(os.environ.get("FLINK_HOME", "/opt/flink"), "bin", "flink")


def spark_submit(jar_hdfs_path: str, *, main_class: Optional[str] = None) -> str:
    settings = get_settings()
    cmd = [
        _spark_bin(),
        "--master", "yarn",
        "--deploy-mode", "cluster",
        "--name", "data-gov-sandbox-spark",
        "--conf", "spark.yarn.submit.waitAppCompletion=false",
    ]
    if main_class:
        cmd += ["--class", main_class]
    cmd.append(jar_hdfs_path)

    r = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=settings.sandbox_spark_timeout, check=False,
    )
    if r.returncode != 0:
        raise SubmitError(f"spark-submit failed: {(r.stderr or r.stdout)[:1000]}")
    app_id = parse_app_id_from_spark(r.stderr) or parse_app_id_from_spark(r.stdout)
    if not app_id:
        raise SubmitError(f"Could not parse application_id from spark-submit output: {r.stderr[:500]}")
    return app_id


def flink_run(jar_hdfs_path: str, *, main_class: Optional[str] = None) -> str:
    settings = get_settings()
    cmd = [
        _flink_bin(), "run",
        "-d",  # detached
        "-m", "yarn-cluster",
        "-yqu", "default",
    ]
    if main_class:
        cmd += ["-c", main_class]
    cmd.append(jar_hdfs_path)

    r = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=settings.sandbox_flink_timeout, check=False,
    )
    if r.returncode != 0:
        raise SubmitError(f"flink run failed: {(r.stderr or r.stdout)[:1000]}")
    app_id = parse_app_id_from_flink(r.stdout) or parse_app_id_from_flink(r.stderr)
    if not app_id:
        raise SubmitError(f"Could not parse application_id from flink output: {r.stdout[:500]}")
    return app_id
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/sandbox/test_submit.py -v
```

预期：PASS (6/6)。

- [ ] **Step 5: 提交**

```bash
git add backend/sandbox/submit.py tests/sandbox/test_submit.py
git commit -m "feat(sandbox): spark-submit / flink run subprocess + app_id parsing"
```

---

## Task 8: SandboxController.execute 完整编排

**Files:**
- Create: `backend/sandbox/controller.py`
- Create: `tests/sandbox/test_controller.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/sandbox/test_controller.py — 全链路 mock 单测。"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.sandbox.controller import SandboxController, execute
from backend.sandbox.models import CompileResult, DryRunResult, SubmitResult


def _ok_compile(_dir):
    return CompileResult(success=True, jar_path="/tmp/x.jar")


def _ok_submit_spark(_jar, main_class=None):
    return "application_x_0001"


def _ok_submit_flink(_jar, main_class=None):
    return "application_x_0002"


def _ok_wait(_app, **kw):
    return SubmitResult(application_id=_app, final_state="FINISHED")


def _cat_one_row(_path):
    return '{"cell_id":"1","avg_rsrp":-95.0}\n'


def _ls(_path):
    return ["/tmp/sandbox/out/x/part-00000-xxx.json"]


def test_execute_spark_sql_happy_path(monkeypatch, tmp_path):
    monkeypatch.setenv("SANDBOX_BASE_DIR", str(tmp_path))
    from backend.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setattr("backend.sandbox.controller.maven_compile", _ok_compile)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_mkdir", lambda p: None)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_put", lambda l, r: None)
    monkeypatch.setattr("backend.sandbox.controller.spark_submit", _ok_submit_spark)
    monkeypatch.setattr("backend.sandbox.controller.wait_for_app", _ok_wait)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_ls", _ls)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_cat", _cat_one_row)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_rm", lambda p, recursive=True: None)
    monkeypatch.setattr("backend.sandbox.controller.inject", lambda **kw: kw["dest_dir"])

    result = execute("SELECT * FROM dwd_session_qos", "spark_sql")
    assert isinstance(result, DryRunResult)
    assert result.success is True
    assert result.preview_row["cell_id"] == "1"
    assert result.application_id == "application_x_0001"


def test_execute_compile_failure_returns_dry_run_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("SANDBOX_BASE_DIR", str(tmp_path))
    from backend.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setattr("backend.sandbox.controller.maven_compile",
                        lambda d: CompileResult(success=False, error_log="cannot find symbol"))
    monkeypatch.setattr("backend.sandbox.controller.inject", lambda **kw: kw["dest_dir"])

    result = execute("BAD SQL", "spark_sql")
    assert result.success is False
    assert "cannot find symbol" in result.error_log
    assert result.application_id is None


def test_execute_yarn_failure_returns_dry_run_failure(monkeypatch, tmp_path):
    from backend.sandbox.yarn import YarnError
    monkeypatch.setenv("SANDBOX_BASE_DIR", str(tmp_path))
    from backend.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setattr("backend.sandbox.controller.maven_compile", _ok_compile)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_mkdir", lambda p: None)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_put", lambda l, r: None)
    monkeypatch.setattr("backend.sandbox.controller.spark_submit", _ok_submit_spark)

    def boom(*a, **kw):
        raise YarnError("FAILED: NullPointerException")
    monkeypatch.setattr("backend.sandbox.controller.wait_for_app", boom)
    monkeypatch.setattr("backend.sandbox.controller.fetch_app_diagnostics",
                        lambda a, **kw: "java.lang.NullPointerException\n\tat Foo.bar(Foo.java:17)")
    monkeypatch.setattr("backend.sandbox.controller.hdfs_rm", lambda p, recursive=True: None)
    monkeypatch.setattr("backend.sandbox.controller.inject", lambda **kw: kw["dest_dir"])

    result = execute("SELECT 1", "spark_sql")
    assert result.success is False
    assert "NullPointerException" in result.error_log


def test_execute_dispatches_flink_sql(monkeypatch, tmp_path):
    monkeypatch.setenv("SANDBOX_BASE_DIR", str(tmp_path))
    from backend.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setattr("backend.sandbox.controller.maven_compile", _ok_compile)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_mkdir", lambda p: None)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_put", lambda l, r: None)
    captured = {}
    def fake_flink(jar, main_class=None):
        captured["called_flink"] = True
        return "application_x_0002"
    monkeypatch.setattr("backend.sandbox.controller.flink_run", fake_flink)
    monkeypatch.setattr("backend.sandbox.controller.wait_for_app", _ok_wait)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_ls", _ls)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_cat", _cat_one_row)
    monkeypatch.setattr("backend.sandbox.controller.hdfs_rm", lambda p, recursive=True: None)
    monkeypatch.setattr("backend.sandbox.controller.inject", lambda **kw: kw["dest_dir"])

    result = execute("INSERT INTO sandbox_sink SELECT 1", "flink_sql")
    assert result.success is True
    assert captured.get("called_flink") is True


def test_execute_unknown_code_type_raises():
    with pytest.raises(ValueError, match="code_type"):
        execute("x", "python")
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/sandbox/test_controller.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `backend/sandbox/controller.py`**

```python
"""SandboxController.execute — 7 步编排（spec §5.4）。

1. /tmp/sandbox/{uuid}/  目录
2. copy template + inject code
3. maven_compile()
4. upload JAR to HDFS
5. submit_and_wait()
6. read_result() → 1 row
7. cleanup
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Literal

from backend.config import get_settings
from backend.sandbox.compile import maven_compile
from backend.sandbox.error_parser import parse_yarn_diagnostics
from backend.sandbox.hdfs import HdfsError, hdfs_cat, hdfs_ls, hdfs_mkdir, hdfs_put, hdfs_rm
from backend.sandbox.models import DryRunResult
from backend.sandbox.submit import SubmitError, flink_run, spark_submit
from backend.sandbox.templates import inject
from backend.sandbox.yarn import YarnError, fetch_app_diagnostics, wait_for_app


CodeType = Literal["spark_sql", "flink_sql", "java_flink"]


class SandboxController:
    """spec §5.4 控制器封装。每次 execute 用 uuid 隔离临时目录。"""

    def execute(self, code: str, code_type: CodeType) -> DryRunResult:
        if code_type not in ("spark_sql", "flink_sql", "java_flink"):
            raise ValueError(f"Unknown code_type: {code_type!r}")
        settings = get_settings()
        sandbox_uuid = uuid.uuid4().hex[:12]
        sandbox_dir = Path(settings.sandbox_base_dir) / sandbox_uuid
        hdfs_jar = f"{settings.sandbox_hdfs_base}/jars/{sandbox_uuid}.jar"
        hdfs_out = f"/tmp/sandbox/out/{sandbox_uuid}"

        try:
            sandbox_dir.parent.mkdir(parents=True, exist_ok=True)

            # 2) inject
            inject(
                code_type=code_type,
                dest_dir=sandbox_dir,
                user_code=code,
                sandbox_uuid=sandbox_uuid,
            )

            # 3) maven compile
            compile_result = maven_compile(sandbox_dir)
            if not compile_result.success:
                return DryRunResult(
                    success=False, error_log=compile_result.error_log,
                    application_id=None,
                )

            # 4) upload jar
            try:
                hdfs_mkdir(f"{settings.sandbox_hdfs_base}/jars")
                hdfs_put(compile_result.jar_path, hdfs_jar)
            except HdfsError as e:
                return DryRunResult(success=False, error_log=f"HDFS upload failed: {e}")

            # 5) submit + wait
            submit_fn = spark_submit if code_type == "spark_sql" else flink_run
            timeout = (settings.sandbox_spark_timeout if code_type == "spark_sql"
                       else settings.sandbox_flink_timeout)
            try:
                app_id = submit_fn(hdfs_jar)
            except SubmitError as e:
                return DryRunResult(success=False, error_log=str(e))
            try:
                wait_for_app(app_id, rm_url=settings.yarn_rm_url, timeout=timeout)
            except YarnError as e:
                diag = ""
                try:
                    diag = fetch_app_diagnostics(app_id, rm_url=settings.yarn_rm_url)
                except YarnError:
                    pass
                err = parse_yarn_diagnostics(diag) or str(e)
                return DryRunResult(success=False, error_log=err, application_id=app_id)

            # 6) read 1 row
            try:
                parts = hdfs_ls(hdfs_out)
                json_parts = [p for p in parts if p.endswith(".json") or "part-" in p]
                if not json_parts:
                    return DryRunResult(success=False,
                                         error_log="No output produced under " + hdfs_out,
                                         application_id=app_id)
                raw = hdfs_cat(json_parts[0])
                preview = self._parse_first_row(raw)
            except HdfsError as e:
                return DryRunResult(success=False, error_log=f"HDFS read failed: {e}",
                                     application_id=app_id)

            return DryRunResult(success=True, preview_row=preview, application_id=app_id)

        finally:
            # 7) cleanup
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            try:
                hdfs_rm(hdfs_jar, recursive=False)
            except HdfsError:
                pass
            try:
                hdfs_rm(hdfs_out, recursive=True)
            except HdfsError:
                pass

    @staticmethod
    def _parse_first_row(raw: str) -> dict | None:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return None


_singleton = SandboxController()


def execute(code: str, code_type: CodeType) -> DryRunResult:
    """模块级入口 — slice 2b 的 sandbox_stub.execute 委托到这里。"""
    return _singleton.execute(code, code_type)
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/sandbox/test_controller.py -v
```

预期：PASS (5/5)。

- [ ] **Step 5: 提交**

```bash
git add backend/sandbox/controller.py tests/sandbox/test_controller.py
git commit -m "feat(sandbox): SandboxController.execute orchestrates 7-step dry-run"
```

---

## Task 9: 沙箱层 execute_with_retry — LLM 自动修复

**Files:**
- Create: `backend/sandbox/retry.py`
- Create: `tests/sandbox/test_retry.py`

> 与 Agent 层 (`iteration_count`) 分层互补 — 沙箱层只修编译失败 / YARN 平台异常，**Agent 层 iteration_count 不被本函数触发**（spec §4.5）。

- [ ] **Step 1: 失败测试**

```python
"""tests/sandbox/test_retry.py — mock controller.execute + LLM client。"""
from unittest.mock import MagicMock

from backend.sandbox.models import DryRunResult
from backend.sandbox.retry import execute_with_retry


def _llm_returns(*responses):
    client = MagicMock()
    msgs = []
    for r in responses:
        m = MagicMock()
        m.content = r
        msgs.append(m)
    client.invoke.side_effect = msgs
    return client


def test_retry_returns_success_on_first_try(monkeypatch):
    monkeypatch.setattr(
        "backend.sandbox.retry.execute",
        lambda code, code_type: DryRunResult(success=True, preview_row={"a": 1}),
    )
    client = MagicMock()
    out = execute_with_retry("SELECT 1", "spark_sql", llm_client=client, max_retries=2)
    assert out.success is True
    client.invoke.assert_not_called()


def test_retry_invokes_llm_once_on_first_failure_then_succeeds(monkeypatch):
    calls = []

    def fake_exec(code, code_type):
        calls.append(code)
        if len(calls) == 1:
            return DryRunResult(success=False, error_log="cannot find symbol Dataset2")
        return DryRunResult(success=True, preview_row={"x": 1})

    monkeypatch.setattr("backend.sandbox.retry.execute", fake_exec)
    fixed = "```spark-sql\nSELECT 1 AS fixed\n```"
    client = _llm_returns(fixed)
    out = execute_with_retry("BAD", "spark_sql", llm_client=client, max_retries=2)
    assert out.success is True
    assert client.invoke.call_count == 1
    # 第二次 execute 接收到 LLM 修正后的代码
    assert "SELECT 1 AS fixed" in calls[1]


def test_retry_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(
        "backend.sandbox.retry.execute",
        lambda code, code_type: DryRunResult(success=False, error_log="always broken"),
    )
    client = _llm_returns("```\nSELECT FIX 1\n```", "```\nSELECT FIX 2\n```")
    out = execute_with_retry("BAD", "spark_sql", llm_client=client, max_retries=2)
    assert out.success is False
    # 1 首次 + 2 次重试 = 3 次 execute
    # 每次失败后触发一次 LLM (但 retry=2 表示重试 2 轮 → 调 LLM 2 次)
    assert client.invoke.call_count == 2


def test_retry_passes_error_log_to_prompt(monkeypatch):
    captured_prompts = []

    def fake_exec(code, code_type):
        return DryRunResult(success=False, error_log="exception XYZ at line 17")

    def fake_invoke(prompt):
        captured_prompts.append(prompt)
        m = MagicMock()
        m.content = "```\nFIXED\n```"
        return m

    client = MagicMock()
    client.invoke.side_effect = fake_invoke
    monkeypatch.setattr("backend.sandbox.retry.execute", fake_exec)
    execute_with_retry("X", "spark_sql", llm_client=client, max_retries=1)
    assert any("exception XYZ" in p for p in captured_prompts)
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/sandbox/test_retry.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现 `backend/sandbox/retry.py`**

```python
"""沙箱层重试 — 失败时让 LLM 改代码 (spec §5.4 execute_with_retry)。"""
from __future__ import annotations

import re
from typing import Any

from backend.sandbox.controller import execute
from backend.sandbox.models import DryRunResult


SANDBOX_FIX_PROMPT = """以下代码在沙箱执行失败。请根据错误日志修正代码，保持原意图。

代码类型: {code_type}

错误日志:
{error_log}

当前代码:
```
{code}
```

只输出修正后的代码 (用 ``` 包裹), 不要解释。
"""


_CODE_FENCE = re.compile(r"```(?:[\w-]+)?\s*\n(.*?)```", re.DOTALL)


def _extract_code(content: str, original: str) -> str:
    m = _CODE_FENCE.search(content)
    return m.group(1).strip() if m else original


def execute_with_retry(
    code: str,
    code_type: str,
    *,
    llm_client: Any,
    max_retries: int = 2,
) -> DryRunResult:
    current_code = code
    last: DryRunResult | None = None
    for attempt in range(max_retries + 1):
        result = execute(current_code, code_type)
        if result.success:
            return result
        last = result
        if attempt == max_retries:
            break
        prompt = SANDBOX_FIX_PROMPT.format(
            code_type=code_type,
            error_log=result.error_log or "(no log)",
            code=current_code,
        )
        try:
            resp = llm_client.invoke(prompt)
            content = getattr(resp, "content", str(resp))
            current_code = _extract_code(content, current_code)
        except Exception:
            break
    return last or DryRunResult(success=False, error_log="execute_with_retry exhausted")
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/sandbox/test_retry.py -v
```

预期：PASS (4/4)。

- [ ] **Step 5: 提交**

```bash
git add backend/sandbox/retry.py tests/sandbox/test_retry.py
git commit -m "feat(sandbox): execute_with_retry — LLM-driven code fix (sandbox-layer)"
```

---

## Task 10: 接线 sandbox_stub → 真实 controller

**Files:**
- Modify: `backend/agent/sandbox_stub.py`
- Modify: `tests/agent/test_sandbox_stub.py`（slice 2b 已有；调整一个用例）

- [ ] **Step 1: 重写 `backend/agent/sandbox_stub.py`**

```python
"""Sandbox 接口 — slice 2c 起委托给 backend.sandbox.controller.execute。

文件名保留为 sandbox_stub.py 以兼容 slice 2b 已写的导入路径，
但实质已经不是 stub 而是 thin re-export。
"""
from __future__ import annotations

from typing import Literal

from backend.sandbox.controller import execute  # noqa: F401
from backend.sandbox.models import DryRunResult  # noqa: F401


CodeType = Literal["spark_sql", "flink_sql", "java_flink"]
```

- [ ] **Step 2: 修 slice 2b 已有测试 `tests/agent/test_sandbox_stub.py`**

slice 2b 的 `test_execute_raises_not_implemented_by_default` 此时应当**不再抛 NotImplementedError**，要么删掉该测试，要么替换为"默认指向真实 controller"。

把测试文件全部改成：

```python
"""tests/agent/test_sandbox_stub.py — slice 2c 后, sandbox_stub 重新导出真实 controller。"""
from backend.agent.sandbox_stub import DryRunResult, execute
from backend.sandbox.controller import execute as real_execute


def test_dry_run_result_dataclass_shape():
    r = DryRunResult(success=True, preview_row={"a": 1}, error_log=None, application_id="app_001")
    assert r.success is True
    assert r.preview_row == {"a": 1}
    assert r.application_id == "app_001"


def test_execute_is_real_controller():
    """slice 2c 后 sandbox_stub.execute === backend.sandbox.controller.execute。"""
    assert execute is real_execute


def test_execute_monkeypatched_returns_stub_success(monkeypatch):
    """节点测试仍可 monkeypatch.setattr(backend.agent.sandbox_stub, 'execute', fake)。"""
    from backend.agent import sandbox_stub

    def fake(code, code_type):
        return DryRunResult(success=True, preview_row={"x": 1})

    monkeypatch.setattr(sandbox_stub, "execute", fake)
    r = sandbox_stub.execute("...", "spark_sql")
    assert r.success and r.preview_row == {"x": 1}
```

- [ ] **Step 3: 跑 slice 2b 全部 agent 测试，确认没回归**

```bash
pytest tests/agent -v -m "not infra"
```

预期：全部 PASS（节点用 monkeypatch 注入桩的路径不受影响）。

- [ ] **Step 4: 提交**

```bash
git add backend/agent/sandbox_stub.py tests/agent/test_sandbox_stub.py
git commit -m "feat(sandbox): wire agent sandbox_stub to real SandboxController"
```

---

## Task 11: dry_run 节点工具 + execute_with_retry 接线

**Files:**
- Modify: `backend/agent/nodes/dry_run.py`
- Create: `tests/agent/nodes/test_dry_run_retry_integration.py`

> spec §4.5：沙箱层重试在单次 dry-run 内部完成。让 `dry_run` 节点改成走 `execute_with_retry`（用项目的 DeepSeek 单例）。

- [ ] **Step 1: 失败测试**

```python
"""tests/agent/nodes/test_dry_run_retry_integration.py"""
from unittest.mock import MagicMock

from backend.agent.nodes.dry_run import dry_run
from backend.sandbox.models import DryRunResult


def test_dry_run_node_uses_execute_with_retry(monkeypatch):
    calls = []

    def fake_retry(code, code_type, llm_client, max_retries):
        calls.append((code, code_type, max_retries))
        return DryRunResult(success=True, preview_row={"a": 1})

    monkeypatch.setattr("backend.agent.nodes.dry_run.execute_with_retry", fake_retry)
    monkeypatch.setattr("backend.agent.nodes.dry_run.build_chat_client",
                        lambda **kw: MagicMock())
    out = dry_run({"generated_code": "SELECT 1", "code_type": "spark_sql"})
    assert out["dry_run_result"]["success"] is True
    assert calls and calls[0][1] == "spark_sql"
    assert calls[0][2] == 2  # spec §4.5 沙箱层 2 轮


def test_dry_run_node_unknown_code_type_still_returns_error():
    out = dry_run({"generated_code": "x", "code_type": "py"})
    assert out["dry_run_result"]["success"] is False
    assert "code_type" in out["error_feedback"]
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/nodes/test_dry_run_retry_integration.py -v
```

预期：FAIL — `dry_run` 还在调 `sandbox.execute` 而非 `execute_with_retry`。

- [ ] **Step 3: 重写 `backend/agent/nodes/dry_run.py`**

```python
"""dry_run 节点 — slice 2c 起走 sandbox 层 execute_with_retry。"""
from __future__ import annotations

from dataclasses import asdict

from backend.clients.deepseek import build_chat_client
from backend.config import get_settings
from backend.sandbox.retry import execute_with_retry


VALID_CODE_TYPES = {"spark_sql", "flink_sql", "java_flink"}


def dry_run(state: dict) -> dict:
    code_type = state.get("code_type", "")
    if code_type not in VALID_CODE_TYPES:
        return {
            "dry_run_result": {"success": False, "preview_row": None,
                                "error_log": f"unknown code_type: {code_type!r}",
                                "application_id": None},
            "error_feedback": f"unknown code_type: {code_type!r}",
        }
    settings = get_settings()
    try:
        client = build_chat_client(temperature=0.0)
    except RuntimeError:
        # DeepSeek 没配 key — 跑无重试模式 (Agent 层会接管)
        from backend.sandbox.controller import execute as raw_execute
        result = raw_execute(state.get("generated_code", ""), code_type)
    else:
        result = execute_with_retry(
            state.get("generated_code", ""), code_type,
            llm_client=client,
            max_retries=settings.sandbox_max_retries,
        )
    payload = asdict(result)
    if result.success:
        return {"dry_run_result": payload, "error_feedback": None}
    err = (result.error_log or "")[:2000]
    return {"dry_run_result": payload, "error_feedback": err}
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/nodes/test_dry_run.py tests/agent/nodes/test_dry_run_retry_integration.py -v
```

预期：PASS（slice 2b 的 `test_dry_run.py` 全部仍然过 — 因为它 monkeypatch 的是 `sandbox.execute`，而现在 `dry_run` 默认走 `execute_with_retry`；**这会让 slice 2b 的旧测试失败**）。

> **重要：slice 2b 的 `tests/agent/nodes/test_dry_run.py` 需要同步更新**。把它的 3 个测试替换为下面的版本：

```python
"""tests/agent/nodes/test_dry_run.py — slice 2c 修订版。"""
from unittest.mock import MagicMock

from backend.agent.nodes.dry_run import dry_run
from backend.sandbox.models import DryRunResult


def test_dry_run_success_clears_error_feedback(monkeypatch):
    monkeypatch.setattr("backend.agent.nodes.dry_run.execute_with_retry",
                        lambda code, code_type, llm_client, max_retries:
                        DryRunResult(success=True, preview_row={"a": 1}))
    monkeypatch.setattr("backend.agent.nodes.dry_run.build_chat_client",
                        lambda **kw: MagicMock())
    out = dry_run({"generated_code": "SELECT 1", "code_type": "spark_sql"})
    assert out["dry_run_result"]["success"] is True
    assert out["error_feedback"] is None


def test_dry_run_failure_writes_error_feedback_truncated(monkeypatch):
    monkeypatch.setattr("backend.agent.nodes.dry_run.execute_with_retry",
                        lambda *a, **kw: DryRunResult(success=False, error_log="x" * 3000))
    monkeypatch.setattr("backend.agent.nodes.dry_run.build_chat_client",
                        lambda **kw: MagicMock())
    out = dry_run({"generated_code": "BAD", "code_type": "spark_sql"})
    assert out["dry_run_result"]["success"] is False
    assert len(out["error_feedback"]) <= 2000


def test_dry_run_unknown_code_type_returns_error():
    out = dry_run({"generated_code": "x", "code_type": "no_such_type"})
    assert out["dry_run_result"]["success"] is False
    assert "code_type" in out["error_feedback"]
```

- [ ] **Step 5: 重新跑 slice 2b 全部节点测试**

```bash
pytest tests/agent/nodes -v
```

预期：全 PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/agent/nodes/dry_run.py tests/agent/nodes/test_dry_run.py tests/agent/nodes/test_dry_run_retry_integration.py
git commit -m "feat(sandbox): wire dry_run node through execute_with_retry"
```

---

## Task 12: `/api/health` 加 sandbox 组件

**Files:**
- Modify: `backend/api/health.py`
- Modify: `tests/search/test_api_search.py`（slice 2a 已有 `test_health_now_includes_search_component`；扩展或新加一个）

- [ ] **Step 1: 修改 `backend/api/health.py` — 加 hdfs/yarn/sandbox 三个组件**

把 `health()` 函数替换为：

```python
@router.get("/api/health")
def health(request: Request) -> dict:
    components: dict = {}
    overall = "healthy"

    # Neo4j
    try:
        start = time.perf_counter()
        run_query("RETURN 1")
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        node_count_rows = run_query("MATCH (n) RETURN count(n) AS n")
        components["neo4j"] = {"status": "ok", "latency_ms": latency_ms,
                                "node_count": node_count_rows[0]["n"]}
    except Exception as e:
        components["neo4j"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # Search
    searcher = getattr(request.app.state, "searcher", None)
    if searcher is None:
        components["search"] = {"status": "error", "error": "not initialized"}
        overall = "degraded"
    else:
        try:
            available = searcher._embedder.available  # noqa: SLF001
            components["search"] = {
                "status": "ok" if available else "degraded",
                "index_version": searcher.get_index_version(),
                "dense_available": available,
            }
            if not available and overall == "healthy":
                overall = "degraded"
        except Exception as e:
            components["search"] = {"status": "error", "error": str(e)}
            overall = "degraded"

    # HDFS / YARN — slice 2c
    from backend.config import get_settings as _gs
    settings = _gs()
    try:
        import requests as _r
        r = _r.get(f"{settings.yarn_rm_url}/ws/v1/cluster/info", timeout=2)
        info = r.json().get("clusterInfo", {})
        components["yarn"] = {"status": "ok", "state": info.get("state", "UNKNOWN")}
    except Exception as e:
        components["yarn"] = {"status": "error", "error": str(e)[:200]}
        overall = "degraded"

    try:
        nn_url = settings.hdfs_defaultfs.replace("hdfs://", "http://").replace(":8020", ":9870")
        import requests as _r
        r = _r.get(f"{nn_url}/jmx?qry=Hadoop:service=NameNode,name=NameNodeStatus", timeout=2)
        beans = r.json().get("beans", [])
        state = beans[0].get("State") if beans else "UNKNOWN"
        components["hdfs"] = {"status": "ok" if state == "active" else "degraded", "state": state}
    except Exception as e:
        components["hdfs"] = {"status": "error", "error": str(e)[:200]}
        overall = "degraded"

    # Sandbox — 只看 spark/flink 二进制是否可执行
    import os, subprocess as sp
    components["sandbox"] = {"status": "ok"}
    for name, path in [("spark-submit", os.path.join(settings.spark_home if hasattr(settings, "spark_home") else "/opt/spark", "bin", "spark-submit")),
                        ("flink", "/opt/flink/bin/flink"), ("mvn", "/opt/maven/bin/mvn")]:
        if not os.path.exists(path):
            components["sandbox"] = {"status": "degraded", "missing": name}
            overall = "degraded"
            break

    return {
        "status": overall,
        "uptime_seconds": int(time.monotonic() - _BOOT_TS),
        "components": components,
    }
```

> 上面引用了 `settings.spark_home`，需要补一个字段；为了不污染配置，改成读环境变量：

把那一行替换为：

```python
        ("spark-submit", os.path.join(os.environ.get("SPARK_HOME", "/opt/spark"), "bin", "spark-submit")),
```

- [ ] **Step 2: 在 `tests/sandbox/` 加 health 测试**

新增 `tests/sandbox/test_health_integration.py`（infra mark）：

```python
import pytest

pytestmark = pytest.mark.infra


def test_health_includes_yarn_hdfs_sandbox():
    import requests
    r = requests.get("http://localhost:8000/api/health", timeout=5)
    assert r.status_code == 200
    body = r.json()
    for key in ("neo4j", "search", "yarn", "hdfs", "sandbox"):
        assert key in body["components"], f"missing {key}"
```

- [ ] **Step 3: 提交**

```bash
git add backend/api/health.py tests/sandbox/test_health_integration.py
git commit -m "feat(sandbox): health endpoint now reports yarn / hdfs / sandbox status"
```

---

## Task 13: P2-4 / P2-5 / P2-6 / P2-7 真实 YARN 验收测试

**Files:**
- Create: `tests/sandbox/test_p2_acceptance.py`

> 标 `infra` mark；需要 base-compose + Neo4j seed + backend 容器起着。每个 case 单独跑，避免 YARN 队列竞争。

- [ ] **Step 1: 写测试**

```python
"""tests/sandbox/test_p2_acceptance.py — P2-4..P2-7 真实 YARN 集成验收。"""
import os

import pytest

from backend.sandbox.controller import execute
from backend.sandbox.retry import execute_with_retry

pytestmark = pytest.mark.infra


def test_p2_4_spark_sql_dry_run_against_dwd_session_qos():
    """P2-4: 对 dws_cell_hourly 聚合 sql 调 execute(spark_sql) → preview_row 含 cell_id。"""
    sql = (
        "SELECT cell_id, AVG(avg_rsrp) AS avg_rsrp_h, AVG(avg_sinr) AS avg_sinr_h "
        "FROM data_gov.dwd_session_qos "
        "GROUP BY cell_id LIMIT 1"
    )
    r = execute(sql, "spark_sql")
    assert r.success, r.error_log
    assert r.preview_row is not None
    assert "cell_id" in r.preview_row


def test_p2_5_flink_sql_dry_run_kafka_tumble_count():
    """P2-5: kafka source + 5 分钟滚动窗口 COUNT, sink → filesystem。"""
    sql = """
        CREATE TABLE ods_gnb_alarm_src (gnb_id STRING, alarm_type STRING, alarm_time TIMESTAMP_LTZ(3),
            WATERMARK FOR alarm_time AS alarm_time - INTERVAL '5' SECOND) WITH (
            'connector' = 'kafka', 'topic' = 'ods_gnb_alarm',
            'properties.bootstrap.servers' = 'kafka:9092',
            'format' = 'json', 'scan.startup.mode' = 'earliest-offset');
        INSERT INTO sandbox_sink
          SELECT CAST(window_start AS STRING) || '|' || gnb_id || '|' || CAST(cnt AS STRING)
          FROM (SELECT gnb_id, TUMBLE_START(alarm_time, INTERVAL '5' MINUTE) AS window_start, COUNT(*) AS cnt
                 FROM ods_gnb_alarm_src
                 GROUP BY gnb_id, TUMBLE(alarm_time, INTERVAL '5' MINUTE))
    """
    r = execute(sql, "flink_sql")
    assert r.success, r.error_log


def test_p2_6_java_flink_dry_run_weak_coverage_filter():
    """P2-6: 完整 Java main class — Kafka source → filter RSRP<-110 → HDFS sink。"""
    body = """
    public static void main(String[] args) throws Exception {
        org.apache.flink.streaming.api.environment.StreamExecutionEnvironment env =
            org.apache.flink.streaming.api.environment.StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);
        env.fromElements("test|imsi_1|-115").writeAsText(SANDBOX_OUTPUT);
        env.execute("weak-coverage-filter");
    }
    """
    r = execute(body, "java_flink")
    assert r.success, r.error_log


def test_p2_7_sandbox_retry_fixes_typo_via_llm(monkeypatch):
    """P2-7: 故意拼错 SLECT, 看沙箱层 execute_with_retry 1 轮修复后通过。

    用真实 DeepSeek 客户端；如果环境无 DEEPSEEK_API_KEY → skip。
    """
    from backend.clients.deepseek import build_chat_client
    try:
        client = build_chat_client(temperature=0.0)
    except RuntimeError:
        pytest.skip("DEEPSEEK_API_KEY not set")

    bad_sql = "SLECT cell_id FROM data_gov.dwd_session_qos LIMIT 1"  # SELECT 拼错
    r = execute_with_retry(bad_sql, "spark_sql", llm_client=client, max_retries=2)
    assert r.success, r.error_log
```

- [ ] **Step 2: 跑测试（需要环境完整 + DEEPSEEK_API_KEY for P2-7）**

```bash
docker compose -f app-compose.yml exec backend pytest tests/sandbox/test_p2_acceptance.py -v -m infra
```

预期：4 个测试 PASS（P2-7 在没 key 时 skipped）。

- [ ] **Step 3: 提交**

```bash
git add tests/sandbox/test_p2_acceptance.py
git commit -m "test(sandbox): P2-4..P2-7 integration against live YARN"
```

---

## Task 14: app-compose 加 Hadoop 配置挂载 + 共享 /tmp/sandbox

**Files:**
- Modify: `app-compose.yml`

- [ ] **Step 1: `app-compose.yml` 的 `backend` 服务 environment / volumes 块追加**

完整替换 backend 服务为：

```yaml
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    container_name: data-gov-backend
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: data-gov-neo4j
      NEO4J_DATABASE: neo4j
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}
      DEEPSEEK_BASE_URL: ${DEEPSEEK_BASE_URL:-https://api.deepseek.com}
      DEEPSEEK_MODEL: ${DEEPSEEK_MODEL:-deepseek-chat}
      SEARCH_CHROMA_DIR: /app/data/chroma
      SEARCH_EMBED_MODEL: BAAI/bge-small-zh-v1.5
      SEARCH_RERANK_THRESHOLD: "0.15"
      SEARCH_RRF_K: "60"
      AGENT_MAX_ITERATIONS: "3"
      GIT_AUTHOR_NAME: "Data-Gov Agent"
      GIT_AUTHOR_EMAIL: "agent@data-gov.local"
      # slice 2c sandbox
      SANDBOX_BASE_DIR: /tmp/sandbox
      SANDBOX_HDFS_BASE: /tmp/sandbox
      SANDBOX_TOTAL_TIMEOUT: "60"
      SANDBOX_COMPILE_TIMEOUT: "20"
      SANDBOX_SPARK_TIMEOUT: "30"
      SANDBOX_FLINK_TIMEOUT: "45"
      SANDBOX_MAX_RETRIES: "2"
      YARN_RM_URL: http://resourcemanager:8088
      HDFS_DEFAULTFS: hdfs://namenode:8020
      HIVE_METASTORE_URI: thrift://hive-metastore:9083
      SPARK_HOME: /opt/spark
      FLINK_HOME: /opt/flink
      HADOOP_HOME: /opt/hadoop
      HADOOP_CONF_DIR: /etc/hadoop
    volumes:
      - ./data/chroma:/app/data/chroma
      - ./.git:/app/.git
      - ./metadata-yaml:/app/metadata-yaml
      - ./templates:/app/templates:ro
      - ./docker/hadoop-conf:/etc/hadoop:ro
      - ./docker/sandbox-conf/log4j2.properties:/opt/spark/conf/log4j2.properties:ro
      - ./docker/sandbox-conf/log4j2.properties:/opt/flink/conf/log4j2.properties:ro
      - sandbox-tmp:/tmp/sandbox
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8000/api/health | grep -q '\"status\":\"healthy\"'"]
      interval: 10s
      timeout: 5s
      retries: 30
      start_period: 60s

volumes:
  sandbox-tmp:
```

- [ ] **Step 2: 整栈冷启验证**

```bash
docker compose -f app-compose.yml down 2>/dev/null || true
docker compose -f base-compose.yml down
rm -rf ./data ./metadata-yaml
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh
docker compose -f app-compose.yml exec backend pytest tests/sandbox -v -m "not infra"
docker compose -f app-compose.yml exec backend pytest tests/sandbox/test_p2_acceptance.py -v -m infra
```

预期：
- 全 `not infra` 沙箱单测 PASS
- P2-4 / P2-5 / P2-6 PASS（P2-7 视 DEEPSEEK_API_KEY 是否设而定）

- [ ] **Step 3: 提交**

```bash
git add app-compose.yml
git commit -m "infra(sandbox): mount hadoop-conf + templates + shared /tmp/sandbox volume"
```

---

## Task 15: README 验收表 + 收尾

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在 README 末尾追加 slice 2c 验收表**

```markdown

## Acceptance coverage (Phase 2 — slice 2c)

| Case | Verifies | Test |
|------|----------|------|
| P2c-1 | 模板加载与占位符注入 | `tests/sandbox/test_templates.py` |
| P2c-2 | Maven 编译成功 / 失败错误解析 | `tests/sandbox/test_compile.py` + `test_compile_real.py` (infra) |
| P2c-3 | HDFS CLI 包装 (put/cat/mkdir/rm/ls) | `tests/sandbox/test_hdfs.py` |
| P2c-4 | YARN RM REST 轮询 + 终态判定 | `tests/sandbox/test_yarn.py` |
| P2c-5 | spark-submit / flink run app_id 解析 | `tests/sandbox/test_submit.py` |
| P2c-6 | SandboxController 全链路单元 (mock) | `tests/sandbox/test_controller.py` |
| P2c-7 | sandbox 层 execute_with_retry (mock LLM) | `tests/sandbox/test_retry.py` |
| P2c-8 | sandbox_stub 重新导出真实 controller | `tests/agent/test_sandbox_stub.py` |
| P2-4 | Spark SQL dry-run (真实 YARN) | `tests/sandbox/test_p2_acceptance.py::test_p2_4_*` |
| P2-5 | Flink SQL dry-run (Kafka source + TUMBLE) | `tests/sandbox/test_p2_acceptance.py::test_p2_5_*` |
| P2-6 | Java Flink dry-run | `tests/sandbox/test_p2_acceptance.py::test_p2_6_*` |
| P2-7 | 沙箱层编译失败自动重试 (真实 LLM) | `tests/sandbox/test_p2_acceptance.py::test_p2_7_*` |

跑 slice 2c 全部测试：

```bash
# 单元 (不需要外部依赖)
pytest tests/sandbox -v -m "not infra"

# 集成 (需要 backend 容器内, base-compose + Neo4j seeded)
docker compose -f app-compose.yml exec backend pytest tests/sandbox -v -m infra
```

**Phase 2 收尾确认（同时跑 2a + 2b + 2c）**：

```bash
docker compose -f app-compose.yml exec backend pytest -v -m "not infra"
docker compose -f app-compose.yml exec backend pytest -v -m infra
```

Phase 2 完成后, P2-1..P2-13 全部可通过对应组合验证（P2-1..P2-3 由 slice 2b 的 mock e2e + slice 2c 的真实沙箱共同验证；P2-8..P2-13 在 slice 2b 已覆盖；P2-4..P2-7 在 slice 2c 这里）。
```

- [ ] **Step 2: 跑完整测试套件**

```bash
pytest tests -v -m "not infra"
```

预期：全部 PASS。

- [ ] **Step 3: 提交**

```bash
git add README.md
git commit -m "docs: slice 2c acceptance coverage table + Phase 2 close-out"
```

---

## Self-Review

### 1. Spec coverage

| Spec ref | Requirement | Plan task |
|----------|-------------|-----------|
| §5.1 统一模型 (Java 骨架 → Maven → YARN → HDFS 回读) | Task 8 (`SandboxController.execute` 7 步) |
| §5.2 骨架模板 (`templates/spark-sql/`, `flink-sql/`, `flink-java/`) | Task 2 |
| §5.2 `${user_sql}` 注入点 | Task 2 (spark-sql + flink-sql); Task 2 (flink-java 用 `${user_code_block}`) |
| §5.2 sink → `hdfs:///tmp/sandbox/{uuid}/` | Task 2 (三个模板 main 函数内直接拼接) |
| §5.3 Spark SQL: `mvn package` + `spark-submit --master yarn` | Tasks 6 (compile), 7 (submit), 8 (orchestration) |
| §5.3 Flink SQL: `mvn package` + `flink run -m yarn-cluster` | Tasks 6, 7, 8 |
| §5.3 Java Flink: `mvn package` + `flink run -m yarn-cluster` | Tasks 6, 7, 8 |
| §5.3 结果读回 `spark.read.json(hdfs://...)` → 1 行 | Task 8 `_parse_first_row` 用 hdfs cat + json.loads（**偏离说明见下**） |
| §5.4 `YarnSandbox.compile/submit_spark/submit_flink/wait_complete/read_result` | Tasks 5, 6, 7, 4 — 全部以模块函数形式提供；`YarnSandbox` 类名未保留（**偏离说明见下**） |
| §5.4 `SandboxController.execute` 7 步 | Task 8 |
| §5.4 `execute_with_retry`（编译/执行失败 LLM 修正 2 轮） | Task 9 |
| §5.4 与 Agent 层 4.5 节分层互补 | Task 9 测试 + Task 11 接线 |
| §5.5 总超时 60s | `SANDBOX_TOTAL_TIMEOUT` Task 1 引入；当前 `controller.execute` 没显式 wrapper 检查；**偏离说明见下** |
| §5.5 Spark 30s / Flink 45s / 编译 20s | Tasks 6, 7 (timeout 参数) |
| §5.5 返回行数 1 | Task 2 (`df.limit(1).coalesce(1).write().json(...)`) + Task 8 (`_parse_first_row` 只读第一行) |
| §5.5 Spark 并行度 `local[2]` | **偏离说明见下** — 沙箱模板没显式 `--master local[2]`，因为 spec §5.3 明确选 YARN，与 §5.5 矛盾 |
| §5.5 临时目录 `/tmp/sandbox/{uuid}` 执行完清理 | Task 8 `finally` 块 |
| §8.2 P2-4 Spark SQL 沙箱执行 | Task 13 `test_p2_4_*` |
| §8.2 P2-5 Flink SQL 沙箱执行 | Task 13 `test_p2_5_*` |
| §8.2 P2-6 Java Flink 沙箱执行 | Task 13 `test_p2_6_*` |
| §8.2 P2-7 沙箱编译失败自动重试 + Agent 层 iteration_count 不计入 | Task 13 `test_p2_7_*` + Task 9 (max_retries 与 Agent iteration_count 独立) |

**偏离说明：**

1. **`YarnSandbox` 类名未保留** — spec §5.4 给了一个 `YarnSandbox` 类示例，但其方法 `compile/submit_spark/submit_flink/wait_complete/read_result` 都是无状态的，强行套类没有收益。本 plan 把它们做成模块级函数（更易测、更易 monkeypatch）；`SandboxController` 作为唯一编排类保留，符合 spec 的命名意图。**影响**：spec 示例代码无法直接 copy 入项目，但所有职责均被覆盖。
2. **`_parse_first_row` 用 `hdfs cat` + `json.loads`** — spec §5.3 写 `spark.read.json(hdfs://...)` 暗示在沙箱 Python 端再起一个 Spark session 读结果。这成本太高（启动 SparkSession ~3s），与 §5.5 60s 总超时矛盾。本实现走 `hdfs dfs -cat` 拿 JSON 文本然后 json.loads — 等价但 ~100ms。
3. **总超时 60s 没显式 wrapper** — 当前各阶段单独有 timeout（compile 20 / spark 30 / flink 45 + wait_for_app timeout），合理上界 ~70s 略超。Task 8 finally 一定清理，故事实上 worst case ~75s。如需严格 60s，**slice 4 加 `concurrent.futures.ThreadPoolExecutor + cancel`**；本 slice 不实现，原因：YARN 应用一旦提交，本地端 kill 不会真把 YARN app 杀掉，反而留垃圾。
4. **`local[2]` Spark 并行度** — 与 spec §5.3 `--master yarn --deploy-mode cluster` 直接冲突。**采用 §5.3 的 YARN 选项**（更能验证生产路径），放弃 §5.5 的 `local[2]`。
5. **`spark.read.json(hdfs://...)` 用 `hdfs cat`** — 同上 2.
6. **flink_run 用 `-d`（detached）拿到 application_id 后退出** — spec §5.3 没明指；如果不 detach，`flink run` 默认会等 job 结束才退出，与 7 步流程（提交后由 `wait_for_app` 轮询）冲突。**采用 detached 模式**。

### 2. Placeholder scan

搜 `TBD` / `TODO` / `implement later` / `fill in` / `appropriate` / `similar to Task`：
- 无 TBD / TODO。
- Task 12 Step 1 中提到"spark_home 字段……改成读环境变量"是 step 内的修正指令而非 placeholder。
- Task 13 P2-5 / P2-6 的 SQL / Java body 是真实可编译的最小样例，**不是占位**：P2-5 用 `ods_gnb_alarm` topic（slice 1a 02_kafka_init.sh 已创建）；P2-6 用 `fromElements + writeAsText` 避免依赖 Kafka source 的额外 JAR。
- Task 14 Step 2 验证步骤明确给出整栈冷启命令，不含占位。

### 3. Type / name consistency

- `DryRunResult` 字段 `(success, preview_row, error_log, application_id)` — Task 1 定义；Tasks 8 / 9 / 10 / 11 全部使用同一字段集；与 slice 2b `backend/agent/sandbox_stub.py` 的 `DryRunResult` 完全等价（slice 2c 重新 export 这个 — Task 10 显式 assert）。
- `CompileResult(success, jar_path, error_log)` — Task 1 / Task 6 / Task 8 一致。
- `SubmitResult(application_id, final_state, diagnostics)` — Task 1 / Task 5 / Task 8 一致。
- `code_type` 字面量 `spark_sql | flink_sql | java_flink` — Task 1 (type alias), Task 2 (`_CODE_TYPE_TO_DIR`), Task 8 (`SandboxController.execute` 校验), Task 9 (传参), Task 11 (`VALID_CODE_TYPES`), Task 13 (验收测试参数) 全部一致；与 slice 2b 的 `backend/agent/tools.py` / `backend/agent/nodes/dry_run.py` 完全对齐。
- `application_id` 格式 `application_<ts>_<seq>` — Task 5 / Task 7 正则 `application_\d+_\d+` 一致；测试 fixture 也用同格式。
- 模板占位符 `${user_sql}`, `${user_code_block}`, `${sandbox_uuid}` — Task 2 (模板文件) 与 `backend/sandbox/templates.py:inject` 的 mapping key 完全一致；测试 `test_inject_replaces_placeholders` 守护无残留。
- 配置 env var 名 `SANDBOX_*` / `YARN_RM_URL` / `HDFS_DEFAULTFS` / `HIVE_METASTORE_URI` — Task 0 `.env.example`、Task 1 `Settings` 字段 alias、Task 14 `app-compose.yml` 三处一致。
- 沙箱 HDFS 路径约定 `/tmp/sandbox/jars/{uuid}.jar`（jar）+ `/tmp/sandbox/out/{uuid}/`（输出） — Task 2 模板内、Task 8 controller、Task 13 验收测试一致。
- `execute(code, code_type) -> DryRunResult` 签名 — Task 8 / Task 9 / Task 10 / Task 11 一致；与 slice 2b 的 `sandbox_stub.execute` 签名完全相同（Task 10 用 `assert execute is real_execute` 守护）。
- LangChain client `invoke(prompt) -> resp.content` 协议 — Task 9 retry / Task 11 dry_run 一致；与 slice 2a / 2b 中 DeepSeek client 使用方式相同。

无名字漂移。

---

## Execution Handoff

Plan 完成，已保存到 `docs/superpowers/plans/2026-05-14-phase2-slice2c-sandbox.md`。

15 个 task，建议拆 4 个 checkpoint 段：

- **Checkpoint A** (Task 0)：Docker 镜像重建 — 单独一段做，因为是 ~10 分钟的拉镜像 + 2GB 体积，单独 commit 便于事后排查 docker layer cache 失效。
- **Checkpoint B** (Tasks 1–5)：models + templates + error_parser + hdfs + yarn — 全部无外部依赖纯单元；可并行。
- **Checkpoint C** (Tasks 6–9)：compile + submit + controller + retry — 沙箱主链路；串行做 review，每个 task 检查点清晰。
- **Checkpoint D** (Tasks 10–15)：接线 + health + 验收 + Docker + README — 把 slice 2c 整合进现有栈。

两种执行方式：

**1. Subagent-Driven (推荐)** — 每个 Task 派一个新 subagent，两段式 review。Task 0 / 8 / 9 / 13 / 14 是关键检查点（镜像 / 编排 / 重试 / 真实验收 / 容器化），建议每个完成后人工 review。

**2. Inline Execution** — `superpowers:executing-plans` 按 4 段 checkpoint 分批。Task 0 由于网络拉包耗时长，强烈建议背景执行（`run_in_background=True`）后继续 Checkpoint B 的并行单元 task。

选择哪种方式？
