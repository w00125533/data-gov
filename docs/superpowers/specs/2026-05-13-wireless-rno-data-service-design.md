# 无线网络感知数据语义化服务 — 设计文档

> 2026-05-13 | Status: Approved

## 1. 概述

构建一个语义化元数据管理 + 数据加工逻辑生成 + 反向样例数据生成的服务平台。

### 核心能力

1. **NL-to-Code Agent**：多轮自然语言对话，生成可执行 Flink SQL / Spark SQL / Java (Flink Stream API)
2. **正向 ETL**：用户描述目标数据集 → Agent 在已有数据 (Hive/Kafka/StarRocks) 上加工
3. **反向合成数据**：用户给出评估 pipeline → Agent 反推输入约束并生成测试/压测数据
4. **元数据演进**：通过自然语言增强元数据模型，自动更新字段、表达式、血缘
5. **Web 可视化**：元数据浏览、字段级血缘、正向/反向 pipeline 呈现

### 范围

全部 6 个子系统统一规划，按依赖顺序分 3 个 Phase 实现：

| Phase | 内容 |
|-------|------|
| Phase 1 | 基础设施 (Docker 栈) + 语义元数据服务 |
| Phase 2 | NL-to-Code Agent (LangGraph + DeepSeek) + E2E 沙箱 |
| Phase 3 | Web 可视化 UI (React + Ant Design + AntV G6) |

### 技术决策总表

| 决策点 | 选择 |
|--------|------|
| 后端框架 | Python FastAPI |
| 元数据存储 | SQLite |
| Agent 框架 | LangChain + LangGraph |
| 外部 LLM | DeepSeek (OpenAI 兼容接口) |
| 配置管理 | `.env` |
| Docker 编排 | base-compose (基础设施) + app-compose (应用) |
| 前端 | React 18 + TypeScript + Vite |
| UI 库 | Ant Design |
| 血缘图 | AntV G6 |
| 沙箱提交 | 统一 Java 打包 + YARN REST (Spark) / flink CLI (Flink) |

---

## 2. 元数据设计

### 2.1 分层结构

```
L1 接入层 (ODS)         L2 明细层 (DWD)        L3 汇总层 (DWS)        L4 宽表层 (ADS)        L5 评估层 (EVAL)
┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ ods_ue_signal │      │dwd_session_qos│     │dws_cell_hourly│     │ads_cell_profile│     │eval_user_score│
│ ods_gnb_alarm │      │dwd_ho_event   │     │dws_area_traffic│    │ads_neighbor_pair│    │eval_net_health│
└──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘
```

### 2.2 10 张样例表

| # | 表名 | 层 | 存储类型 | 核心字段 | 上游依赖 |
|---|------|-----|----------|----------|----------|
| 1 | `ods_ue_signal` | L1-ODS | Kafka | imsi, cell_id, rsrp, rsrq, sinr, timestamp | 无 (原始采集) |
| 2 | `ods_gnb_alarm` | L1-ODS | Kafka | gnb_id, alarm_type, severity, alarm_time, duration | 无 |
| 3 | `dwd_session_qos` | L2-DWD | Hive | session_id, imsi, avg_rsrp, avg_rsrq, avg_sinr, packet_loss, latency, throughput | `ods_ue_signal` |
| 4 | `dwd_ho_event` | L2-DWD | Hive | imsi, source_cell, target_cell, ho_type, ho_result, ho_cause, ho_latency | `ods_ue_signal` |
| 5 | `dws_cell_hourly` | L3-DWS | Hive | cell_id, hour_bucket, avg_rsrp, avg_sinr, total_sessions, drop_rate, avg_throughput, ho_success_rate | `dwd_session_qos`, `dwd_ho_event` |
| 6 | `dws_area_traffic` | L3-DWS | Hive | area_id, hour_bucket, total_throughput, active_users, avg_latency, peak_throughput | `dwd_session_qos` |
| 7 | `ads_cell_profile` | L4-ADS | StarRocks | cell_id, date, coverage_score, capacity_score, stability_score, composite_kpi | `dws_cell_hourly` |
| 8 | `ads_neighbor_pair` | L4-ADS | StarRocks | source_cell, target_cell, ho_count, ho_success_rate, avg_ho_latency, recommend_priority | `dwd_ho_event` |
| 9 | `eval_user_score` | L5-EVAL | StarRocks | imsi, date, qoe_score, signal_quality, mobility_score, service_continuity | `ads_cell_profile` |
| 10 | `eval_net_health` | L5-EVAL | StarRocks | area_id, date, health_index, alarm_severity_weighted, user_complaint_ratio, degradation_trend | `dws_area_traffic`, `ods_gnb_alarm`, `eval_user_score` |

### 2.3 SQLite Schema

```sql
-- 表元数据
CREATE TABLE metadata_tables (
    id INTEGER PRIMARY KEY,
    table_name TEXT UNIQUE NOT NULL,
    layer TEXT NOT NULL,           -- ODS / DWD / DWS / ADS / EVAL
    layer_priority INTEGER,
    description TEXT,
    storage_type TEXT,             -- KAFKA / HIVE / STARROCKS
    partition_keys TEXT            -- JSON array
);

-- 字段元数据
CREATE TABLE metadata_fields (
    id INTEGER PRIMARY KEY,
    table_id INTEGER REFERENCES metadata_tables(id),
    field_name TEXT NOT NULL,
    field_type TEXT NOT NULL,      -- STRING / INT / BIGINT / DOUBLE / TIMESTAMP
    is_nullable INTEGER DEFAULT 1,
    is_partition INTEGER DEFAULT 0,
    expression TEXT,               -- 计算表达式 (SQL fragment)
    description TEXT,
    upstream_field_refs TEXT,      -- JSON: [{"table":"x","field":"y"}]
    version INTEGER DEFAULT 1,
    previous_expr TEXT             -- JSON: [{"v":1,"expr":"..."}]
);

-- 血缘关系 (计算加速用)
CREATE TABLE metadata_lineage (
    id INTEGER PRIMARY KEY,
    source_table TEXT NOT NULL,
    source_field TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_field TEXT NOT NULL,
    transform_expr TEXT
);
```

### 2.4 元数据演进策略

- 通过 NL 驱动元数据变更 (schema_evolve 路径)
- 增/删/改字段前执行一致性校验 (循环依赖检测、断链检测)
- 变更记录 version + previous_expr 留痕，非完整 temporal versioning

---

## 3. Docker 一体化验证栈

### 3.1 Base Compose (基础设施，常驻)

| 服务 | 端口 | 说明 |
|------|------|------|
| HDFS NameNode | 9870 / 8020 | Spark / Flink 读写 |
| HDFS DataNode | 9864 | 数据节点 (1 个) |
| YARN ResourceManager | 8088 / 8032 | 统一资源调度 |
| YARN NodeManager | 8042 | 执行容器 (1 个) |
| Hive Metastore | 9083 | Spark SQL 外部表元数据 |
| HMS DB (Postgres) | 15432 | HMS 后端 |
| Kafka Broker | 9092 | KRaft 模式 (无 ZK) |
| StarRocks FE | 9030 / 8030 | OLAP 查询 |
| StarRocks BE | 9060 | 存储计算 |

### 3.2 App Compose (应用层，独立启停)

| 服务 | 端口 | 说明 |
|------|------|------|
| FastAPI App | 8000 | 元数据 API + Agent + 沙箱控制器 |
| React Dev Server | 5173 | Vite HMR |

### 3.3 FastAPI 容器能力

```dockerfile
FROM python:3.11-slim
RUN apt-get install -y openjdk-17-jdk-headless maven
RUN pip install pyspark==3.5.4   # 含 spark-submit, SparkSession
# Flink 提交通过 subprocess: flink run -m yarn-cluster
```

### 3.4 存储流向

- ODS 层 → Kafka topic
- DWD / DWS 层 → Hive 外部表 (Parquet on HDFS)
- ADS / EVAL 层 → StarRocks (OLAP)

### 3.5 初始化

```
init-scripts/
├── 01_hive_init.sql
├── 02_kafka_init.sh
├── 03_starrocks_init.sql
├── 04_sample_data.py          # 反向合成小批量数据，灌入 Hive + StarRocks
└── 05_sqlite_seed.py          # 10 张表元数据写入 SQLite
```

---

## 4. NL-to-Code Agent

### 4.1 LangGraph StateGraph

```
               ┌───────────┐
    START ────→│ classifier │
               └─────┬─────┘
          ┌──────────┼──────────┐
          ▼          ▼          ▼
    ┌──────────┐┌──────────┐┌────────────────┐
    │forward   ││reverse   ││schema_evolve   │
    │_etl      ││_synth    ││                │
    └────┬─────┘└────┬─────┘└───────┬────────┘
         │           │             │
         ▼           ▼        ┌────┴────────┐
    ┌─────────┐┌──────────┐   │schema_validate│
    │schema   ││pipeline  │   └──────┬────────┘
    │_lookup  ││_parse    │   ┌──────┴────────┐
    └────┬────┘└────┬─────┘   │schema_apply    │
         │          │         │(写入SQLite)     │
         ▼          ▼         └──────┬────────┘
    ┌─────────┐┌──────────┐         │
    │code     ││constraint│         │
    │_generate││_gen      │         │
    └────┬────┘└────┬─────┘         │
         └────┬─────┘               │
              ▼                     │
         ┌────────┐                │
         │dry_run │←───────────────┘
         └───┬────┘
              ▼
         ┌──────────┐
         │presenter │
         └────┬─────┘
              ▼
            END
```

### 4.2 Agent State

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]   # 对话历史
    intent: str                                # "forward_etl" | "reverse_synth" | "schema_evolve"
    target_tables: list[str]
    source_tables: list[str]
    generated_code: str
    code_type: str                             # "spark_sql" | "flink_sql" | "java_flink"
    dry_run_result: dict
    schema_diff: dict                          # schema_evolve 的变更预览
    error_feedback: str
    iteration_count: int
```

### 4.3 Tools (Agent 可调用)

| 工具 | 功能 | 路径 |
|------|------|------|
| `lookup_table_schema` | 查表/字段元数据 | 所有 |
| `lookup_lineage` | 查字段血缘路径 | 所有 |
| `search_tables_by_keyword` | 语义搜索表 | 所有 |
| `generate_fake_data` | 反向合成小批量数据 | reverse_synth |
| `validate_change` | 变更一致性检查 | schema_evolve |
| `add_table / add_field / update_field / remove_field` | 元数据变更 | schema_evolve |
| `dry_run_spark_sql` | Spark SQL E2E + HDFS 回读 | forward_etl |
| `dry_run_flink_sql` | Flink SQL E2E + HDFS 回读 | forward_etl |
| `dry_run_java_flink` | Java Flink E2E + HDFS 回读 | forward_etl |

### 4.4 DeepSeek 集成

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

LangChain `ChatOpenAI` 指定 `base_url` + `api_key` 即可。

### 4.5 自动重试

Dry-run 失败时 error_feedback 写入 State，code_generate 自动修正，最多 3 轮。

---

## 5. E2E 沙箱

### 5.1 统一模型

三种代码类型全部: Java 骨架包装 → Maven 编译 → YARN 提交 → HDFS 结果回读 → 返回 1 行

### 5.2 骨架模板

```bash
templates/
├── spark-sql/
│   ├── pom.xml
│   └── src/main/java/SandboxSparkJob.java   # ${user_sql} 注入点, sink → hdfs:///tmp/sandbox/{uuid}/
├── flink-sql/
│   ├── pom.xml
│   └── src/main/java/SandboxFlinkSQLJob.java
└── flink-java/
    ├── pom.xml
    └── src/main/java/                        # 整个 src 替换，约定 sink 路径
```

### 5.3 提交方式

| 路径 | 编译 | 提交方式 | 结果读回 |
|------|------|----------|----------|
| Spark SQL | `mvn package` | Spark REST Submission Server (POST `:6066/v1/submissions/create`) | `spark.read.json(hdfs://tmp/sandbox/{uuid})` → 1 行 |
| Flink SQL | `mvn package` | `subprocess`: `flink run -m yarn-cluster jar` | 同上 |
| Java Flink | `mvn package` | `subprocess`: `flink run -m yarn-cluster jar` | 同上 |

### 5.4 控制器封装

```python
class YarnSandbox:
    async def compile(self, code: str, code_type: str) -> CompileResult
    async def submit_spark(self, jar_hdfs_path: str) -> str      # → submissionId
    async def submit_flink(self, jar_hdfs_path: str) -> str      # → jobId (subprocess)
    async def wait_complete(self, id: str, engine: str) -> bool
    async def read_result(self, uuid: str) -> dict               # → 1 row

class SandboxController:
    async def execute(self, code: str, code_type: str) -> DryRunResult:
        1. sandbox_dir = /tmp/sandbox/{uuid}
        2. copy_template + inject_code
        3. maven_compile()
        4. upload JAR to HDFS
        5. submit_and_wait()
        6. read_result() → 1 row
        7. cleanup sandbox_dir
```

### 5.5 资源限制

| 项 | 限制 |
|----|------|
| 总超时 | 60s |
| Spark job | 30s |
| Flink job | 45s |
| Java 编译 | 20s |
| 返回行数 | 1 行 |
| Spark 并行度 | local[2] |
| 临时目录 | `/tmp/sandbox/{uuid}` → 执行完清理 |

---

## 6. Web UI

### 6.1 技术栈

| 层 | 选型 |
|----|------|
| 框架 | React 18 + TypeScript |
| 构建 | Vite |
| UI 库 | Ant Design |
| 血缘图 | AntV G6 |
| 代码高亮 | Monaco Editor (readonly) |
| SSE | fetch + ReadableStream |
| 状态 | React Query (服务端) + Zustand (客户端) |

### 6.2 页面

| 路由 | 功能 |
|------|------|
| `/metadata` | 表列表 (分层过滤) + 表详情 (字段 + 计算逻辑) + 字段级血缘图 (G6 TreeGraph) |
| `/chat` | 多轮 NL 对话 (SSE streaming) + 代码卡片 (语法高亮) + dry-run 预览 (单行表格) |
| `/pipeline` | 正向 ETL DAG + 反向合成链路，切换 toggle |
| `/schema-evolution` | 元数据变更时间线 + 字段版本 diff |

### 6.3 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tables` | 表列表 (支持 ?layer= 过滤) |
| GET | `/api/tables/:id` | 表详情 + 字段列表 |
| GET | `/api/fields/:id` | 字段详情 + 上游引用 |
| GET | `/api/lineage` | 血缘图数据 (?direction=up/down) |
| POST | `/api/chat/start` | 新建对话 |
| POST | `/api/chat/message` | 发送消息 → SSE stream |
| GET | `/api/chat/:id/result` | 获取 dry-run 结果 |
| POST | `/api/schema/apply` | 确认元数据变更 |

### 6.4 血缘图 (G6)

- 使用 G6 TreeGraph 而非 ReactFlow
- 理由: Canvas 渲染支持大量节点、内置 Dagre/TreeGraph 布局、展开折叠开箱即用、Ant Design 同体系
- 节点: 表.字段，边: transform_expr
- 双击节点展开上下游多层
- 右侧面板显示边详情 (表达式)

---

## 7. 项目结构 (预览)

```
data-gov/
├── .env                          # DeepSeek + DB 配置
├── base-compose.yml              # 基础设施容器
├── app-compose.yml               # FastAPI + React
├── init-scripts/
│   ├── 01_hive_init.sql
│   ├── 02_kafka_init.sh
│   ├── 03_starrocks_init.sql
│   ├── 04_sample_data.py
│   └── 05_sqlite_seed.py
├── templates/                    # Sandbox 骨架
│   ├── spark-sql/
│   ├── flink-sql/
│   └── flink-java/
├── backend/
│   ├── main.py                   # FastAPI entry
│   ├── config.py                 # .env 加载
│   ├── metadata/
│   │   ├── models.py             # SQLite ORM (SQLAlchemy)
│   │   ├── service.py            # CRUD
│   │   └── seed.py               # 10 张表初始化
│   ├── agent/
│   │   ├── graph.py              # LangGraph StateGraph
│   │   ├── tools.py              # Agent tools
│   │   ├── prompts.py            # System prompts
│   │   └── deepseek.py           # LLM 连接
│   ├── sandbox/
│   │   ├── controller.py         # 编排
│   │   ├── yarn_submit.py        # YARN REST + subprocess
│   │   └── templates.py          # 模板注入
│   └── api/
│       ├── metadata.py           # /api/tables, /api/fields, /api/lineage
│       ├── chat.py               # /api/chat/*   SSE streaming
│       └── schema_evolution.py   # /api/schema/*
└── frontend/
    ├── vite.config.ts
    └── src/
        ├── pages/
        │   ├── Metadata.tsx
        │   ├── Chat.tsx
        │   ├── Pipeline.tsx
        │   └── SchemaEvolution.tsx
        ├── components/
        │   ├── LineageGraph.tsx   # G6 封装
        │   ├── CodeCard.tsx       # Monaco 只读
        │   ├── DryRunPreview.tsx  # 1 行表格
        │   └── ChatStream.tsx     # SSE 流式对话
        └── api/
            └── client.ts          # fetch 封装
```

---

## 8. 实施阶段

| Phase | 内容 | 估时 |
|-------|------|------|
| **Phase 1** | Docker 栈搭建 + SQLite 元数据初始化 + 元数据 CRUD API | 基础设施先行 |
| **Phase 2** | LangGraph Agent 搭建 + 3 条对话路径 + E2E 沙箱 | 核心逻辑 |
| **Phase 3** | React 前端 + 血缘图 + 对话面板 + Pipeline 可视化 | 可视化呈现 |

### 依赖关系

```
Phase 1 ⇒ Phase 2 ⇒ Phase 3
    (Docker  + 元数据必须先就绪，Agent 才能查 Schema；UI 需要 Agent 和 API 都好)
```

---

## 9. 非功能要求

- **安全**: `.env` 不提交，`.gitignore` 排除；API 无鉴权 (本地验证栈)
- **可调试**: SQLite 文件在 `./data/` 直接查看；HDFS 数据本地可读
- **清理**: Sandbox 临时目录自动清理；Docker `docker-compose down -v` 全清
- **文档**: 代码即文档，10 张表元数据自带描述和表达式
