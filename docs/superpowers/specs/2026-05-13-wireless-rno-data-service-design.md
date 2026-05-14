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
| Phase 2 | NL-to-Code Agent (LangGraph + DeepSeek) + 沙箱 |
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
| 沙箱提交 | 统一 Java 打包 + spark-submit / flink CLI（均提交到 YARN） |

### 功能树全景

> 说明：功能树按"用户能用的功能"组织，编号独立于下文 `## N.` 章节编号。下文章节按实现视角组织，二者编号不一定对应。

```
无线网络感知数据语义化服务
│
├── 1. 基础设施管理
│   ├── 1.1 Docker 栈一键启动/停止
│   ├── 1.2 初始化脚本执行
│   └── 1.3 配置管理 (.env)
│
├── 2. 元数据管理 (/metadata)
│   ├── 2.1 浏览
│   │   ├── 2.1.1 分层过滤 (L1~L5)
│   │   ├── 2.1.2 搜索 (表名/字段/描述)
│   │   └── 2.1.3 表详情展示 (字段+表达式+上游)
│   ├── 2.2 维护
│   │   ├── 2.2.1 新建表 (含字段定义)
│   │   ├── 2.2.2 编辑表 (层/存储/描述)
│   │   ├── 2.2.3 删除表 (下游依赖警告)
│   │   ├── 2.2.4 新建字段
│   │   ├── 2.2.5 编辑字段 (Monaco 表达式编辑器)
│   │   └── 2.2.6 删除字段 (断链警告)
│   ├── 2.3 YAML 管理
│   │   ├── 2.3.1 导出全量/单表 YAML
│   │   ├── 2.3.2 YAML 预览 (只读)
│   │   └── 2.3.3 YAML 版本 diff (git)
│   └── 2.4 跳转演化历史
│       └── 表详情页 [演化历史] → /schema-evolution?table=xxx
│
├── 3. 血缘图 (/metadata/lineage)
│   ├── 3.1 可视化
│   │   ├── 3.1.1 字段级 DAG (G6 Graph)
│   │   ├── 3.1.2 展开/折叠层级 (1~5)
│   │   ├── 3.1.3 正向/反向切换
│   │   ├── 3.1.4 节点拖拽 + 缩放
│   │   ├── 3.1.5 边详情 (点击查看转换表达式)
│   │   ├── 3.1.6 Mini-map 导航
│   │   └── 3.1.7 全屏模式
│   ├── 3.2 维护 (右键菜单)
│   │   ├── 3.2.1 编辑节点 (表/字段)
│   │   ├── 3.2.2 新建血缘边 (拖拽连线)
│   │   ├── 3.2.3 编辑边表达式
│   │   ├── 3.2.4 删除边/节点
│   │   └── 3.2.5 从血缘图新建下游表
│   └── 3.3 与流程 3 联动
│       ├── 3.3.1 右键跳转 /chat (自动注入上下文)
│       ├── 3.3.2 NL 修改后自动刷新血缘图
│       └── 3.3.3 新建对象后血缘图实时更新
│
├── 4. NL 对话 (/chat)
│   ├── 4.1 对话管理
│   │   ├── 4.1.1 新建对话
│   │   ├── 4.1.2 对话历史列表
│   │   ├── 4.1.3 SSE 流式输出
│   │   ├── 4.1.4 意图识别 badge (正向ETL/反向合成/元数据演进)
│   │   └── 4.1.5 上下文注入 (从 /metadata /lineage /pipeline 跳转)
│   ├── 4.2 正向 ETL 流程
│   │   ├── 4.2.1 业务语义 → 表/字段自动匹配 (search_tables_by_keyword)
│   │   ├── 4.2.2 候选表推荐 (血缘预览 + 方案对比)
│   │   ├── 4.2.3 代码生成 (Spark SQL / Flink SQL / Java Flink)
│   │   ├── 4.2.4 代码卡片展示 (Monaco 高亮, 可编辑)
│   │   ├── 4.2.5 沙箱试跑 (YARN 提交)
│   │   ├── 4.2.6 预览结果表格 (1 行)
│   │   ├── 4.2.7 缺失对象自动补齐子流程 (gap_check → schema_evolve)
│   │   └── 4.2.8 失败自动重试 (最多 3 轮)
│   ├── 4.3 反向合成流程
│   │   ├── 4.3.1 业务语义 → 评估 pipeline 匹配
│   │   ├── 4.3.2 全链路上游溯源 (pipeline_parse)
│   │   ├── 4.3.3 约束反推面板 (表格: 变量 → 值域)
│   │   ├── 4.3.4 分档约束滑块调整 (值域 + 行数)
│   │   ├── 4.3.5 缺失对象自动补齐子流程
│   │   ├── 4.3.6 数据生成代码产出 (Java Flink 逐层回溯)
│   │   ├── 4.3.7 沙箱执行 + 分层写入
│   │   ├── 4.3.8 结果预览 (表格 + 分档柱状图)
│   │   └── 4.3.9 生成数据写入各表对应存储 (Kafka/Hive/StarRocks)
│   └── 4.4 元数据演进流程
│       ├── 4.4.1 业务语义 → 目标表/字段匹配
│       ├── 4.4.2 变更一致性校验 (重名/断链/循环依赖)
│       ├── 4.4.3 Diff 对比面板 (旧 vs 新, 左右对照)
│       ├── 4.4.4 下游影响分析 + 警告
│       ├── 4.4.5 确认后写入 SQLite + 重写 YAML
│       └── 4.4.6 变更历史记录 (版本 + 旧值留痕)
│   └── 4.5 语义检索 (search_tables_by_keyword)
│       ├── 4.5.1 BM25 倒排索引 (jieba 分词 + 术语保护)
│       ├── 4.5.2 Dense 向量检索 (bge-small-zh-v1.5 + ChromaDB)
│       ├── 4.5.3 RRF 融合 + LLM Rerank 兜底
│       └── 4.5.4 增量同步 (SQLite version → ChromaDB upsert)
│
├── 5. Pipeline 可视化 (/pipeline)
│   ├── 5.1 正向 ETL DAG
│   │   ├── 5.1.1 完整链路展示 (ODS → EVAL, G6 DAG)
│   │   ├── 5.1.2 选中表上下游突出 + 层级滑块
│   │   ├── 5.1.3 节点悬浮: 表信息卡片 (字段/存储/表达式)
│   │   └── 5.1.4 右键 [💬 NL 查询] → /chat 上下文注入
│   ├── 5.2 反向合成链路
│   │   ├── 5.2.1 逆向图: 目标表 → 约束推断 → 生成器
│   │   ├── 5.2.2 每层约束气泡展示
│   │   └── 5.2.3 图上直接调整约束值域
│   └── 5.3 联动
│       ├── 5.3.1 与 /chat 联动 (图上操作跳转对话)
│       ├── 5.3.2 与 /metadata/lineage 联动 (共享 G6 组件)
│       └── 5.3.3 正向/反向一键切换
│
├── 6. 元数据演进历史 (/schema-evolution)
│   ├── 6.1 变更时间线 (按时间倒序, 跨所有表)
│   ├── 6.2 按表/字段/操作类型过滤
│   ├── 6.3 变更详情展开 (旧值→新值 diff)
│   ├── 6.4 YAML 版本 git diff (调用 git show)
│   └── 6.5 从 /metadata 表详情跳转 (?table= 预过滤)
│
├── 7. Sandbox 沙箱
│   ├── 7.1 Maven 编译
│   ├── 7.2 spark-submit / flink CLI 提交 (均到 YARN)
│   ├── 7.3 HDFS 结果回读
│   ├── 7.4 自动重试 (编译失败/执行失败)
│   └── 7.5 临时目录自动清理
│
└── 8. 健康检查面板 (/health)
    ├── 8.1 各组件连通性状态卡片
    ├── 8.2 自动刷新 (30s)
    └── 8.3 异常组件高亮提示
```

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
    storage_type TEXT              -- KAFKA / HIVE / STARROCKS
);

-- 字段元数据
CREATE TABLE metadata_fields (
    id INTEGER PRIMARY KEY,
    table_id INTEGER REFERENCES metadata_tables(id),
    field_name TEXT NOT NULL,
    field_type TEXT NOT NULL,      -- STRING / INT / BIGINT / DOUBLE / TIMESTAMP
    is_nullable INTEGER DEFAULT 1,
    is_partition INTEGER DEFAULT 0,    -- 分区字段标识 (表的分区键 = 该表 is_partition=1 的字段集)
    expression TEXT,               -- 计算表达式 (SQL fragment)
    description TEXT,
    upstream_field_refs TEXT,      -- JSON: [{"table":"x","field":"y"}], 血缘关系的唯一权威存储
    version INTEGER DEFAULT 1,
    previous_expr TEXT             -- JSON: [{"v":1,"expr":"..."}]
);

-- 元数据变更记录 (审计 + git 关联, schema_evolve 路径写入)
CREATE TABLE metadata_changes (
    id INTEGER PRIMARY KEY,
    table_name TEXT NOT NULL,
    field_name TEXT,                   -- 可空 (表级变更时为 NULL)
    operation TEXT NOT NULL,           -- ADD_TABLE / ADD_FIELD / UPDATE_FIELD / DELETE_FIELD / DELETE_TABLE
    version INTEGER NOT NULL,          -- 变更后版本号
    commit_hash TEXT,                  -- git commit hash, schema_apply 同步 commit 后回填
    old_value TEXT,                    -- JSON, 旧值快照
    new_value TEXT,                    -- JSON, 新值快照
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

血缘查询通过扫描所有字段的 `upstream_field_refs` 构建 DAG。血缘边的新增/编辑/删除通过对目标字段的 `upstream_field_refs` 变更完成，复用字段 CRUD API。不设独立血缘表。表的分区键集合通过聚合该表所有 `is_partition=1` 的字段得到，不在表级冗余存储。

### 2.4 元数据演进策略

- 通过 NL 驱动元数据变更 (schema_evolve 路径)
- 增/删/改字段前执行一致性校验 (循环依赖检测、断链检测)
- 变更记录 version + previous_expr 留痕（SQLite 内轻量版本链），非完整 temporal versioning
- YAML 文件纳入 git 版本控制，提供 git diff 级别的完整历史追溯（与 SQLite 内 version 链互补：version 链用于逻辑追溯，git diff 用于 YAML 级别的审计和回滚）

### 2.5 YAML 元数据副本

每张表在 SQLite 之外同步生成一份 YAML 文件，用于人工查阅和版本 diff。存储路径：

```
metadata-yaml/
├── L1-ODS/
│   ├── ods_ue_signal.yaml
│   └── ods_gnb_alarm.yaml
├── L2-DWD/
│   ├── dwd_session_qos.yaml
│   └── dwd_ho_event.yaml
├── L3-DWS/
│   ├── dws_cell_hourly.yaml
│   └── dws_area_traffic.yaml
├── L4-ADS/
│   ├── ads_cell_profile.yaml
│   └── ads_neighbor_pair.yaml
└── L5-EVAL/
    ├── eval_user_score.yaml
    └── eval_net_health.yaml
```

YAML 格式示例 (`dws_cell_hourly.yaml`):

```yaml
table_name: dws_cell_hourly
layer: DWS
layer_priority: 3
description: 小区小时粒度汇总指标
storage_type: HIVE
fields:
  - name: cell_id
    type: STRING
    nullable: false
    partition: false
    description: 小区标识
    # 无 expression → 原始字段，来自上游
    upstream:
      - table: dwd_session_qos
        field: cell_id
  - name: hour_bucket
    type: TIMESTAMP
    nullable: false
    partition: true
    description: 小时窗口起点
    expression: "DATE_TRUNC('HOUR', timestamp)"
    upstream:
      - table: dwd_session_qos
        field: timestamp
  - name: avg_rsrp
    type: DOUBLE
    nullable: true
    description: 小区小时平均 RSRP
    expression: "AVG(rsrp)"
    upstream:
      - table: dwd_session_qos
        field: avg_rsrp
  - name: avg_sinr
    type: DOUBLE
    nullable: true
    description: 小区小时平均 SINR
    expression: "AVG(sinr)"
    upstream:
      - table: dwd_session_qos
        field: avg_sinr
  - name: total_sessions
    type: BIGINT
    nullable: true
    description: 会话总数
    expression: "COUNT(DISTINCT session_id)"
    upstream:
      - table: dwd_session_qos
        field: session_id
  - name: drop_rate
    type: DOUBLE
    nullable: true
    description: 掉话率
    expression: "CAST(SUM(CASE WHEN drop_flag=1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*)"
    upstream:
      - table: dwd_session_qos
        field: drop_flag
  - name: avg_throughput
    type: DOUBLE
    nullable: true
    description: 平均吞吐量 (Mbps)
    expression: "AVG(throughput)"
    upstream:
      - table: dwd_session_qos
        field: throughput
  - name: ho_success_rate
    type: DOUBLE
    nullable: true
    description: 切换成功率
    expression: "CAST(SUM(CASE WHEN ho_result='SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*)"
    upstream:
      - table: dwd_ho_event
        field: ho_result
```

- SQLite 为运行时权威数据源，YAML 为人工可读副本
- 元数据演进 (schema_evolve) 变更应用后，同步重写对应 YAML 文件
- YAML 纳入 git 版本控制，变更历史可通过 git diff 追溯

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
├── 05_sqlite_seed.py          # 10 张表元数据写入 SQLite
└── 06_export_yaml.py          # SQLite → metadata-yaml/ 导出 YAML
```

### 3.6 服务健康检查面板

Web UI 提供健康检查面板（路由 `/health`），展示各组件连通性状态：

| 组件 | 检查方式 | 正常指标 |
|------|---------|----------|
| FastAPI | GET `/api/health` | 200 + uptime |
| SQLite | `SELECT 1` | < 1ms |
| HDFS NameNode | HTTP `:9870/jmx` | State=active |
| YARN RM | HTTP `:8088/ws/v1/cluster/info` | started=true |
| Hive Metastore | Thrift connect `:9083` | connected |
| Kafka Broker | AdminClient `:9092` | broker count > 0 |
| StarRocks FE | MySQL query `:9030` | connected |
| ChromaDB | heartbeat query | connected |
| DeepSeek API | HTTP ping (可选) | 200 OK |

后端 API：`GET /api/health` 返回 JSON：

```json
{
  "status": "healthy",
  "uptime_seconds": 1234,
  "components": {
    "sqlite": {"status": "ok", "latency_ms": 0.5},
    "hdfs": {"status": "ok", "state": "active"},
    "yarn": {"status": "ok", "nodes": 1},
    "hive": {"status": "ok"},
    "kafka": {"status": "ok", "brokers": 1},
    "starrocks": {"status": "ok"},
    "chromadb": {"status": "ok", "doc_count": 80},
    "deepseek": {"status": "ok"}
  }
}
```

> FastAPI 自身的状态由顶层 `status` 字段反映（能成功返回 200 即 healthy），故不重复列入 `components`。

前端健康面板组件 `HealthPanel.tsx` 使用 Ant Design `Card` + `Badge` 网格布局，每组件一张状态卡片，自动刷新间隔 30s。

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
    └────┬────┘└─────┬────┘   │schema_apply    │
         │           │        │(写入SQLite)     │
         ▼           ▼        └──────┬────────┘
    ┌────────────────────────────┐  │
    │   gap_check                │  │
    │  (检查业务实体→表/字段映射)   │  │
    └───────────┬────────────────┘  │
                │                   │
         ┌──────┴──────┐            │
         ▼             ▼            │
    无缺失 / 完整   有缺失           │
         │             │            │
         ▼             ▼            │
    code_generate  ┌─────────────┐  │
                   │gap_proposal │  │
                   │(生成补齐建议) │  │
                   └──────┬──────┘  │
                          │         │
                          ▼         │
                   ┌──────────────┐ │
                   │schema_evolve │←┘
                   │(子流程,自动执行)│
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │schema_lookup │
                   │(回查补齐后Schema)│
                   └──────┬───────┘
                          │
                          ▼
                     code_generate
                          │
         ┌────────────────┘
         ▼
    ┌────────┐
    │dry_run │
    └───┬────┘
        ▼
   ┌──────────┐
   │presenter │
   └────┬─────┘
        ▼
      END
```

#### gap_check 节点逻辑

```python
def gap_check(state: AgentState) -> dict:
    """检测用户需求与现有元数据之间的缺口"""
    required = extract_required_entities(state.messages[-1])
    gaps = []

    for entity in required:
        match = search_tables_by_keyword(entity.keyword)
        if match.top_score < 0.6:
            gaps.append({
                "type": "missing_table",
                "keyword": entity.keyword,
                "suggestion": f"建议新建表 {entity.pinyin}_metrics"
            })
        elif entity.field_specified and not field_exists(entity.field, match.top_table):
            gaps.append({
                "type": "missing_field",
                "keyword": entity.field,
                "table": match.top_table,
                "suggestion": f"在 {match.top_table} 中新增字段 {entity.field}"
            })

    return {"gaps": gaps, "has_gaps": len(gaps) > 0}
```

> 阈值 0.6 用于缺口检测（保守判定，宁多勿漏），不同于语义检索 RRF 置信阈值 0.15（4.6.5 节）。gap_check 的 score 来自 `search_tables_by_keyword` 的最终融合分数，0.6 以下视为"未找到可靠匹配"，触发补齐建议。

#### gap_proposal 节点行为

1. LLM 根据 gaps 生成补齐建议（新建表/新增字段 + 合理的层、存储类型、字段定义）
2. Web 端呈现建议卡片，用户可：[确认并继续] [我自己定义] [跳过,仅用已有]
3. 确认后自动进入 schema_evolve 子流程（校验 → 应用 → 写入 SQLite + YAML）
4. 子流程完成后回到 schema_lookup 重新查询，然后继续主流程 code_generate

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
    # gap_check 子流程相关
    gaps: list[dict]                           # 缺失对象列表
    resolved_gaps: dict                        # 已补齐的映射 {keyword: table_name}
    sub_flow_active: bool                      # 是否正在子流程中
    sub_flow_return_point: str                 # 子流程完成后回到哪个节点
    context_source: str                        # 上下文来源: "metadata" | "lineage" | "pipeline" | None
```

### 4.3 Tools (Agent 可调用)

| 工具 | 功能 | 路径 |
|------|------|------|
| `lookup_table_schema` | 查表/字段元数据 | 所有 |
| `lookup_lineage` | 查字段血缘路径 | 所有 |
| `search_tables_by_keyword` | 语义搜索表 (业务关键词→表/字段匹配) | 所有 |
| `check_gaps` | 检测用户需求实体与现有元数据的缺口 | forward_etl, reverse_synth |
| `propose_gap_fix` | 生成缺失表/字段的补齐建议 | forward_etl, reverse_synth |
| `generate_fake_data` | 反向合成小批量数据 | reverse_synth |
| `validate_change` | 变更一致性检查 (重名/断链/循环依赖) | schema_evolve |
| `add_table / add_field / update_field / remove_field` | 元数据变更 | schema_evolve |
| `sync_yaml` | SQLite 变更后同步重写 YAML 文件 | schema_evolve |
| `dry_run_spark_sql` | Spark SQL E2E + HDFS 回读 | forward_etl |
| `dry_run_flink_sql` | Flink SQL E2E + HDFS 回读 | forward_etl |
| `dry_run_java_flink` | Java Flink E2E + HDFS 回读 | forward_etl |

> - `lookup_table_schema` / `lookup_lineage` 是 Agent 内部工具，直接读 SQLite（与 HTTP `/api/tables`、`/api/lineage` 共享同一个 service 函数，但不经过 HTTP）。
> - `dry_run_spark_sql / dry_run_flink_sql / dry_run_java_flink` 三个工具均是 thin wrapper，统一委派给 `SandboxController.execute(code, code_type)`（§5.4）。分三个工具仅为让 Agent 通过工具名表达执行意图。

### 4.4 DeepSeek 集成

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat   # DeepSeek-V3 (模型版本与 deepseek-chat 别名绑定)
```

LangChain `ChatOpenAI` 指定 `base_url` + `api_key` 即可。

### 4.5 自动重试（双层）

重试分两层，互补不重叠：

| 层 | 触发场景 | 重试上限 | 处理方式 |
|----|---------|---------|---------|
| 沙箱层（§5.4 `execute_with_retry`） | 编译失败 / YARN 平台异常 | 2 轮 | 解析 maven / YARN 日志 → LLM 修正代码 → 重新提交 |
| Agent 层（本节） | 沙箱层耗尽后仍失败 / 业务逻辑错误 / SQL 语义错误 | 3 轮 | error_feedback 写入 State，`code_generate` 节点重新生成代码 |

Agent 层 `iteration_count` 计入包括首次执行在内的总轮次（首次 + 最多 2 次重试 = 3 轮）。沙箱层重试在单次 dry-run 内部完成，不计入 Agent 层 `iteration_count`。

### 4.6 语义检索技术实现

`search_tables_by_keyword` 是 Agent 三条路径的入口工具。用户只讲业务指标（"小区每小时的覆盖强度"），不知道 `dws_cell_hourly` / `avg_rsrp`。该工具将业务语义映射到表/字段。

#### 4.6.1 检索空间

SQLite 中 10 张表 + ~70 个字段，每条生成一个索引文本：

```python
# 表级
table_doc = {
    "id": "table:dws_cell_hourly",
    "type": "table",
    "text": "dws_cell_hourly 小区小时粒度汇总指标 cell_id 小区标识 "
            "hour_bucket 小时窗口起点 avg_rsrp 小区小时平均RSRP覆盖强度 "
            "avg_sinr 小区小时平均SINR信噪比 total_sessions 会话总数 "
            "drop_rate 掉话率 avg_throughput 平均吞吐量Mbps "
            "ho_success_rate 切换成功率",
    "metadata": {
        "table_name": "dws_cell_hourly",
        "layer": "DWS",
        "storage_type": "HIVE",
        "version": 1
    }
}

# 字段级
field_doc = {
    "id": "field:dws_cell_hourly.avg_rsrp",
    "type": "field",
    "text": "avg_rsrp DOUBLE 小区小时平均RSRP覆盖强度dBm "
            "表达式 AVG(dwd_session_qos.avg_rsrp)",
    "metadata": {
        "table_name": "dws_cell_hourly",
        "field_name": "avg_rsrp",
        "data_type": "DOUBLE",
        "version": 1
    }
}
```

#### 4.6.2 组件选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 中文分词 | jieba | 轻量、纯 Python、RNO 术语词典可自定义 |
| Embedding 模型 | `BAAI/bge-small-zh-v1.5` | 24MB、512 维、MIT 开源、CLS pooling、批量编码 ~5ms/条 (CPU) |
| 关键词检索 | BM25 (rank-bm25) | 对 RSRP/SINR/cell_id 等技术术语精确匹配，与分词互补 |
| 向量存储 | ChromaDB (persistent) | Python 原生、SQLite 底层自动持久化、内置 metadata filter、upsert 增量更新 |
| 精排兜底 | DeepSeek Chat | 口语化/模糊表达时做 LLM rerank |

#### 4.6.3 文本预处理

```python
import jieba

# 自定义技术术语词典，保护不被切分
jieba.add_word("覆盖强度", freq=100)
jieba.add_word("信噪比", freq=100)
jieba.add_word("掉话率", freq=100)
jieba.add_word("切换成功率", freq=100)
jieba.add_word("RSRP", freq=100)
jieba.add_word("SINR", freq=100)

def tokenize(text: str) -> list[str]:
    words = jieba.lcut(text)
    return [w.strip().lower() for w in words if w.strip()]
```

#### 4.6.4 初始化与增量同步

```
FastAPI 启动时:
  1. 加载 bge-small-zh-v1.5 到内存 (24MB, ~1s)
  2. ChromaDB PersistentClient 连接 ./data/chroma/
  3. 如果 Chroma 为空 → 从 SQLite 加载元数据 → 构建索引文本
     → 向量化 → 写入 Chroma → 构建 BM25 倒排
  4. 如果 Chroma 已有 → 对比 Chroma index_version 与 SQLite MAX(version)
     → 仅 upsert 变更的 docs → 重建 BM25 (增量, <1ms)
```

```python
class HybridSearcher:
    def __init__(self, chroma_path: str = "./data/chroma"):
        self.encoder = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(
            name="metadata_index",
            metadata={"hnsw:space": "cosine"}
        )
        self.bm25 = None

    def build_index(self, docs: list[dict]):
        texts = [d["text"] for d in docs]
        embeddings = self.encoder.encode(texts, normalize_embeddings=True).tolist()
        self.collection.upsert(
            ids=[d["id"] for d in docs],
            embeddings=embeddings,
            metadatas=[d["metadata"] for d in docs],
            documents=texts
        )
        from rank_bm25 import BM25Okapi
        self.bm25_docs = docs
        self.bm25 = BM25Okapi([tokenize(t) for t in texts])
        self.collection.modify(metadata={"index_version": self._db_version()})
```

异常处理:

- bge-small-zh-v1.5 模型下载失败：FastAPI 启动时 `SentenceTransformer` 加载失败 → 降级为纯 BM25 模式 + 日志告警，语义搜索仍可用（仅 Dense 向量检索不可用）
- ChromaDB 数据损坏：`PersistentClient` 连接失败 → 自动重建（删除 `./data/chroma/` → 从 SQLite 全量重建索引）
- 内存压力：bge 模型 24MB + ChromaDB 持久化文件 < 10MB (80 docs × 512维)，总计 < 50MB，无需特殊处理

#### 4.6.5 混合检索流程

```
用户输入: "每个小区的每小时信号覆盖强度"
        │
        ├─→ jieba 分词: ["每个","小区","每小时","信号","覆盖强度"]
        │   → BM25 Okapi 倒排检索 → Top 10
        │
        ├─→ bge-small-zh 编码 → 512维归一化向量
        │   → ChromaDB cosine 检索 → Top 10
        │
        ▼
    RRF (Reciprocal Rank Fusion):
      score(doc) = Σ 1/(k + rank_i)
      k = 60 (阻尼常数，防止 Top-1 过主导)

      融合后 → Top 10
        │
        ├─→ 置信度判断:
        │     Top-1 RRF score > 0.15  → 直接返回 (约 80% 查询)
        │     否则                     → LLM rerank
        │
        ▼
    返回: [{"table": "dws_cell_hourly", "score": 0.87, "fields": [...], "match_type": "hybrid"}, ...]
```

```python
def search(self, query: str, k: int = 10,
           use_rerank: bool = True) -> list[dict]:
    # 1. BM25
    bm25_scores = self.bm25.get_scores(tokenize(query))
    bm25_ranked = sorted(zip(self.bm25_docs, bm25_scores),
                         key=lambda x: -x[1])

    # 2. Dense (ChromaDB)
    query_vec = self.encoder.encode(
        [query], normalize_embeddings=True
    ).tolist()[0]
    dense = self.collection.query(
        query_embeddings=[query_vec],
        n_results=k,
        include=["metadatas", "documents", "distances"]
    )

    # 3. RRF 融合
    fused = self._rrf_fuse(bm25_ranked, dense, k=k)

    # 4. LLM rerank (仅低置信度触发)
    if use_rerank and fused[0][1] < self.RERANK_THRESHOLD:
        fused = self._llm_rerank(query, fused)

    return [{"doc": d, "score": s,
             "table": d["metadata"]["table_name"]}
            for d, s in fused]
```

#### 4.6.6 RRF 融合公式

```python
def _rrf_fuse(self, bm25_ranked, dense_result, k=60, top_k=10):
    scores = {}
    for rank, (doc, _) in enumerate(bm25_ranked):
        scores[doc["id"]] = scores.get(doc["id"], 0) + 1.0 / (k + rank + 1)

    for rank, doc_id in enumerate(dense_result["ids"][0]):
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    doc_map = {d["id"]: d for d in self.bm25_docs}
    return [(doc_map[id_], scoring) for id_, scoring in ranked[:top_k]]
```

#### 4.6.7 LLM Rerank (兜底)

仅在 RRF Top-1 score < 0.15 时触发，约占 20% 查询：

```python
RERANK_PROMPT = """你是无线网络数据专家。用户用自然语言描述了业务需求，
请从以下候选元数据对象中选出最匹配的表和字段。

用户需求: {user_query}

候选对象 (JSON):
{candidates_json}

返回严格的 JSON 格式 (不要 Markdown 包裹):
{{
  "top_table": {{"name": "...", "score": 0.95, "reason": "..."}},
  "top_fields": [{{"name": "...", "table": "...", "score": 0.88, "reason": "..."}}],
  "alternative_tables": [{{"name": "...", "score": 0.72, "reason": "..."}}]
}}
"""

def _llm_rerank(self, query: str, candidates) -> list:
    """用 DeepSeek Chat 做最后一次精排"""
    cand_json = json.dumps([{
        "name": d["metadata"]["table_name"],
        "type": d["type"],
        "description": d["text"][:200]
    } for d, _ in candidates[:10]], ensure_ascii=False)

    resp = self.deepseek_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content":
                   RERANK_PROMPT.format(user_query=query,
                                        candidates_json=cand_json)}],
        temperature=0,
        response_format={"type": "json_object"}
    )
    return self._parse_rerank_result(resp, candidates)
```

#### 4.6.8 延时预算

| 阶段 | 耗时 | 占比 |
|------|------|------|
| jieba 分词 | ~1ms | — |
| BM25 检索 | ~2ms | — |
| bge-small 编码 (CPU) | ~5ms | — |
| ChromaDB query | ~1ms | — |
| RRF 融合 | <1ms | — |
| **小计 (无 LLM)** | **~10ms** | 80% 查询 |
| LLM rerank (触发时) | ~500-800ms | 20% 查询 |

### 4.7 语义检索 Benchmark

#### 4.7.1 测试集构建

从元数据 YAML 自动生成 60 条 queries，覆盖 3 种构造方式 + 3 个难度：

```yaml
# benchmark_queries.yaml

# 类型 A: 规则生成 (30条) — 从 field.description 做同义词替换+语序变化
- id: Q001
  query: "小区小时粒度的平均覆盖强度"
  expected_table: "dws_cell_hourly"
  expected_fields: ["avg_rsrp"]
  difficulty: easy
- id: Q002
  query: "每个基站每小时的掉话比例"
  expected_table: "dws_cell_hourly"
  expected_fields: ["drop_rate"]
  difficulty: medium
- id: Q003
  query: "用户打电话时从一个塔切到另一个塔的成功率"
  expected_table: "dwd_ho_event"
  expected_fields: ["ho_result"]
  difficulty: hard   # 口语化: 塔→cell, 打电话→会话, 切→handover

# 类型 B: LLM 生成 (20条) — 给 DeepSeek 元数据，模拟不同角色提问
- id: Q031
  query: "帮我看看最近一段时间信号质量差的用户都有哪些"
  expected_table: "dwd_session_qos"
  expected_fields: ["avg_sinr", "avg_rsrp"]
  difficulty: medium

# 类型 C: 对抗样本 (10条) — 故意模糊/歧义/跨域
- id: Q051
  query: "网络状况怎么样"
  expected_table: "eval_net_health"
  expected_fields: ["health_index"]
  difficulty: hard   # 极度模糊
```

#### 4.7.2 评估指标

```python
@dataclass
class SearchBenchmark:
    # 表级检索
    table_recall_at_1: float    # Top-1 命中率
    table_recall_at_3: float    # Top-3 出现率
    table_mrr: float            # 平均倒数排名  Σ(1/rank) / N

    # 字段级检索
    field_recall_at_3: float
    field_ndcg_at_5: float      # 含多目标字段时

    # 效率
    avg_latency_ms: float
    p99_latency_ms: float

    # 分层
    by_difficulty: dict         # {easy: {}, medium: {}, hard: {}}
```

#### 4.7.3 目标值

| 指标 | 目标 |
|------|------|
| Table Recall@1 | > 0.85 |
| Table Recall@3 | > 0.95 |
| Table MRR | > 0.90 |
| Field Recall@3 | > 0.80 |
| Avg latency (无 LLM) | < 20ms |
| Avg latency (含 LLM rerank) | < 1s |
| Hard Recall@1 | > 0.65 |

#### 4.7.4 CI 门禁与增量回归

```
scripts/benchmark_semantic_search.py

冷启动:
  $ python scripts/benchmark_semantic_search.py --queries benchmark_queries.yaml
  → 输出完整指标表 + 每条 query 的检索链路日志
  → CI: 核心指标不得低于目标的 90%

增量 (每次 schema_evolve 后):
  $ python scripts/benchmark_semantic_search.py --mode incremental
  → 自动生成 5 条针对新增对象的 queries
  → 验证: 新对象可被检索 + 旧对象不受影响 (无回归)
  → 回归检测: 重新跑全量 60 条，对比上次 score 差异
```

---

## 5. 沙箱

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
│   └── src/main/java/SandboxFlinkSQLJob.java # ${user_sql} 注入点 (替换 SQL 字符串)，sink → hdfs:///tmp/sandbox/{uuid}/
└── flink-java/
    ├── pom.xml
    └── src/main/java/                        # 整个 src/ 目录替换，约定 sink 路径 hdfs:///tmp/sandbox/{uuid}/
```

### 5.3 提交方式

| 路径 | 编译 | 提交方式 | 结果读回 |
|------|------|----------|----------|
| Spark SQL | `mvn package` | `subprocess`: `spark-submit --master yarn --deploy-mode cluster jar` | `spark.read.json(hdfs://tmp/sandbox/{uuid})` → 1 行 |
| Flink SQL | `mvn package` | `subprocess`: `flink run -m yarn-cluster jar` | 同上 |
| Java Flink | `mvn package` | `subprocess`: `flink run -m yarn-cluster jar` | 同上 |

### 5.4 控制器封装

```python
class YarnSandbox:
    async def compile(self, code: str, code_type: str) -> CompileResult
    async def submit_spark(self, jar_hdfs_path: str) -> str      # → applicationId (subprocess: spark-submit)
    async def submit_flink(self, jar_hdfs_path: str) -> str      # → applicationId (subprocess: flink run)
    async def wait_complete(self, app_id: str, engine: str) -> bool   # 轮询 YARN RM REST :8088
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

    async def execute_with_retry(self, code: str, code_type: str,
                                 max_retries: int = 2) -> DryRunResult:
        """沙箱级自动重试：针对编译失败和 YARN 执行失败，最多 2 轮。
        编译失败: 解析 maven 错误 → 提取行号/错误类型 → 修正 → 重试
        执行失败: 解析 YARN 日志 → 提取异常 → 修正 → 重试
        与 Agent 层重试 (4.5 节) 分层互补：沙箱层解决编译/平台问题，
        Agent 层解决业务逻辑/SQL 语义问题。
        """
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
| 代码高亮 | Monaco Editor (readonly + 可编辑切换) |
| 图表 | @antv/g2 (柱状图等) |
| SSE | fetch + ReadableStream |
| 状态 | React Query (服务端) + Zustand (客户端) |

### 6.2 页面 & 路由

| 路由 | 页面 | 核心功能 |
|------|------|----------|
| `/metadata` | 元数据管理 | 表浏览/搜索/CRUD + 字段编辑 + YAML 导出 |
| `/metadata/lineage` | 血缘图 | 字段级 DAG 可视化 + 右键维护 + 跳转 /chat |
| `/chat` | NL 对话 | 对话面板 + 代码卡片 + dry-run 预览 |
| `/pipeline` | Pipeline 可视化 | 正向 ETL DAG + 反向合成链路 |
| `/schema-evolution` | 演化历史 | 变更时间线 + 版本 diff |
| `/health` | 健康检查 | Docker 组件连通性状态面板 (30s 自动刷新) |

### 6.3 元数据管理界面 (/metadata)

#### 页面布局

```
┌──────────────────────────────────────────────────────────────┐
│  [搜索框: 表名/字段/描述...]          [+ 新建表]  [导出 YAML]  │
├──────────────────────┬───────────────────────────────────────┤
│ 左侧面板 (320px)      │ 右侧面板                               │
│                      │                                       │
│ 分层过滤:             │ ┌── 表信息卡片 ──────────────────┐    │
│  ● L1 接入层 (2)     │ │ dws_cell_hourly                │    │
│  ○ L2 明细层 (2)     │ │ 层: DWS │ 存储: HIVE           │    │
│  ○ L3 汇总层 (2)     │ │ 分区: hour_bucket              │    │
│  ○ L4 宽表层 (2)     │ │ 描述: 小区小时粒度汇总指标...    │    │
│  ○ L5 评估层 (2)     │ │ [编辑] [删除] [查看血缘]        │    │
│                      │ └────────────────────────────────┘    │
│ 表列表:               │                                       │
│ ┌──────────────────┐ │ ┌── 字段列表 (可搜索) ───────────┐    │
│ │★ dws_cell_hourly │ │ │ [搜索字段...]                  │    │
│ │  小区小时汇总      │ │ ├──────┬─────┬────┬────────────┤    │
│ │  7字段·DWS·HIVE  │ │ │ 字段  │ 类型 │可空│ 表达式      │    │
│ │                  │ │ │cell_id│STRING│ ✗ │ (原始)      │    │
│ │ dwd_session_qos  │ │ │hour   │TIMEST│ ✗ │ TRUNC()    │    │
│ │  会话QoS明细      │ │ │avg_   │DOUBLE│ ✓ │ AVG()      │    │
│ │  8字段·DWD·HIVE  │ │ │rsrp   │      │   │            │    │
│ │                  │ │ │avg_   │DOUBLE│ ✓ │ AVG()      │    │
│ │ ods_ue_signal    │ │ │sinr   │      │   │            │    │
│ │  UE信号采集       │ │ │...    │...   │...│ ...        │    │
│ │  6字段·ODS·Kafka │ │ └──────┴─────┴────┴────────────┘    │
│ └──────────────────┘ │ [+ 新建字段]                          │
│                      │                                       │
│ [hover 表行]: 描述    │ [hover 字段行]: 上游引用 tooltip       │
│ [点击表行]: 显示详情  │ [点击字段行]: 打开编辑抽屉             │
└──────────────────────┴───────────────────────────────────────┘
```

#### 功能详单

| 功能 | 入口 | 说明 |
|------|------|------|
| 分层浏览 | 左侧 radio button | 单选层过滤表列表 |
| 搜索表 | 顶部搜索框 | 模糊匹配表名/字段名/描述 |
| 表详情 | 点击表行 | 右侧面板显示表信息卡片 + 字段列表 |
| 字段详情+编辑 | 点击字段行 | 右侧滑出抽屉，含 Monaco 表达式编辑器 |
| 上游 tooltip | hover 字段行 | 浮层显示该字段依赖的上游字段和表达式 |
| 新建表 | 顶部 [+ 新建表] | 弹窗: 表名/层/存储/分区/描述 + 字段定义列表 |
| 编辑表 | 表卡片 [编辑] | 修改层/存储/描述 |
| 删除表 | 表卡片 [删除] | 二次确认 + 下游影响检查 |
| 新建字段 | 字段列表 [+ 新建字段] | 行内或弹窗添加 |
| 删除字段 | 字段行 ✕ | 下游依赖检查 → 警告或拒绝 |
| 导出 YAML | 顶部 [导出 YAML] | 全量或按选定表导出到 metadata-yaml/ |
| YAML 预览 | 表卡片 [预览 YAML] | 只读弹窗展示当前表 YAML 内容 (Monaco 语法高亮)，不落盘 |
| 查看血缘 | 表卡片 [查看血缘] | 跳转到 `/metadata/lineage?table=xxx` |
| 创建下游表 | 表卡片 [创建下游表] | 打开新建表弹窗，预填上游引用 |

#### 新建/编辑表弹窗

```
┌── 新建表 ──────────────────────────────────┐
│                                              │
│  表名:  [ods_core_gnb_load        ]          │
│  层级:  [ODS ▼]  [1]                        │
│  存储:  [Kafka ▼]                            │
│  分区键: [timestamp          ] [+ 添加]       │
│  描述:  [基站 CPU/内存/负载 原始采集数据  ]    │
│                                              │
│  ── 字段定义 ────────────────────────        │
│  ┌────┬──────┬──────┬──────────────┐        │
│  │字段 │ 类型   │ 可空  │ 表达式/描述    │        │
│  ├────┼──────┼──────┼──────────────┤        │
│  │gnb_id│STRING │ ✗   │ 基站ID        │ ✕     │
│  │cpu   │DOUBLE │ ✓   │ CPU使用率(%)   │ ✕     │
│  │mem   │DOUBLE │ ✓   │ 内存使用率(%)   │ ✕     │
│  │+ 添加字段                               │
│  └────┴──────┴──────┴──────────────┘        │
│                                              │
│  [保存] (SQLite)  [保存并导出 YAML]  [取消]     │
└──────────────────────────────────────────────┘
```

- [保存]：仅写入 SQLite（运行时立即可用）
- [保存并导出 YAML]：写入 SQLite + 同步导出对应 YAML 文件到 `metadata-yaml/` 目录 + git commit

#### 字段编辑抽屉 (右侧滑出)

```
┌── 编辑字段: avg_rsrp ───────────────────────┐
│                                               │
│  字段名:  [avg_rsrp                 ]          │
│  类型:    [DOUBLE ▼]                          │
│  可空:    [✓]                                 │
│  描述:    [小区小时平均 RSRP 覆盖强度  ]        │
│                                               │
│  ── 计算逻辑 ────────────────                 │
│  表达式:                                       │
│  ┌──────────────────────────────────────┐     │
│  │ AVG(dwd_session_qos.avg_rsrp)         │     │
│  │                              Monaco   │     │
│  └──────────────────────────────────────┘     │
│                                               │
│  ── 上游引用 ────────────────                  │
│  ┌─────────────┬───────────────┐              │
│  │ 源表          │ 源字段         │    [+ 添加]  │
│  ├─────────────┼───────────────┤              │
│  │dwd_session  │ avg_rsrp      │    ✕         │
│  │_qos         │               │              │
│  └─────────────┴───────────────┘              │
│                                               │
│  _变更将自动更新血缘图_                         │
│                                               │
│               [保存]   [取消]                   │
└───────────────────────────────────────────────┘
```

### 6.4 血缘图界面 (/metadata/lineage)

#### 页面布局

```
┌──────────────────────────────────────────────────────────────┐
│  血缘图: dws_cell_hourly                  [正向 ↑] [反向 ↓]  │
│                              [展开层级: 2 ▼] [全屏]          │
├──────────────────────────────────────────┬───────────────────┤
│                                          │ 右侧信息面板 (320px)│
│  ┌─────────┐                             │                    │
│  │ods_ue    │  ← L1 ODS                  │ ┌──────────────┐   │
│  │_signal  │                             │ │ 选中边详情:    │   │
│  │         │                             │ │              │   │
│  │ rsrp ●──┼── AVG(rsrp) ──────┐        │ │ 源: ods_ue    │   │
│  │ sinr ●──┼── AVG(sinr) ──┐   │        │ │  _signal.rsrp│   │
│  │ imsi ●──┤               │   │        │ │              │   │
│  │cell_id●─┤   COUNT(DIST) │   │        │ │ 目标: dwd     │   │
│  └─────────┘           │   │   │        │ │ _session_qos  │   │
│             │          │   │   │        │ │ .avg_rsrp    │   │
│             │          ▼   ▼   ▼        │ │              │   │
│  ┌──────────┴──────────────────┐        │ │ 转换: AVG(rsrp)│   │
│  │ dwd_session_qos ← L2 DWD   │        │ │              │   │
│  │   avg_rsrp ●────────────────┤        │ │ [编辑] [删除] │   │
│  │   avg_sinr ●────────────────┤        │ └──────────────┘   │
│  │ session_id ●───────────────→│        │                    │
│  └──────────┬──────────────────┘        │                    │
│             │                            │                    │
│  ┌──────────┴─────┐                     │                    │
│  │ dwd_ho_event    │ ← L2 DWD            │                    │
│  │  ho_result ●───→│                     │                    │
│  └──────────┬──────┘                     │                    │
│             │                            │                    │
│             ▼                            │ [Mini-map]        │
│  ┌─────────────────────┐                │ ┌──────────────┐   │
│  │ dws_cell_hourly ★    │ ← L3 DWS       │ │ ○ ○ ○ ○ ○ ○ │   │
│  │  当前表               │                │ │ ○ ○ ○ ○ ○ ○ │   │
│  └──────────┬──────────┘                │ │ ○ ○ ○ ○ ○ ○ │   │
│             │                            │ └──────────────┘   │
│             ▼                            │                    │
│  ┌──────────────────┐                   │                    │
│  │ ads_cell_profile  │ ← L4 ADS          │                    │
│  └─────────┬─────────┘                   │                    │
│            │                             │                    │
│            ▼                             │                    │
│  ┌──────────────────┐                   │                    │
│  │ eval_user_score   │ ← L5 EVAL         │                    │
│  └──────────────────┘                   │                    │
└──────────────────────────────────────────┴───────────────────┘
```

#### 交互清单

| 交互 | 操作 | 效果 |
|------|------|------|
| 定位中心表 | URL param `?table=` | 该表节点高亮 + 自动居中 |
| 展开层级 | 滑块 [1~5] 或双击节点 | 展开/折叠上下游 |
| 方向切换 | [正向] [反向] toggle | 正向:源→目标 ; 反向:目标→约束 |
| 节点拖拽 | 鼠标拖拽 | G6 画布自由移动 |
| 缩放 | 滚轮/手势 | 放大缩小 |
| 节点 hover | 鼠标悬停 | tooltip: 表名/层/存储/字段数 |
| 字段节点 | ● 点 click | 展开该字段的上下游 |
| 边详情 | 点击边 | 右侧面板显示源→目标+转换表达式 |
| Mini-map | 右下角 | 大图定位导航 |
| 全屏 | [全屏] 按钮 | 全屏模式 |

### 6.5 血缘图维护 & 与流程 3 联动

#### 右键菜单

```
右键节点 (表):
  ┌──────────────────────┐
  │ ✎ 编辑表名/描述       │  → 打开编辑弹窗 (复用 /metadata)
  │ ✚ 在此表上加字段       │  → 打开字段编辑抽屉
  │ ✚ 创建下游表          │  → 打开新建表弹窗, 预填上游引用
  │ ✕ 删除此表 (无下游时)  │  → 二次确认 + 下游影响检查
  │ ⊕ 新建血缘边          │  → 拖拽模式: 从此节点画线
  ├──────────────────────┤
  │ 💬 用 NL 修改...      │  → 跳转 /chat?context=lineage&table=xxx
  └──────────────────────┘

右键边:
  ┌──────────────────────┐
  │ ✎ 编辑转换表达式       │  → Monaco 编辑器弹出
  │ ✕ 删除此血缘边         │  → 确认后从目标字段 upstream_field_refs 中移除该引用
  ├──────────────────────┤
  │ 💬 用 NL 修改...      │  → 跳转 /chat
  └──────────────────────┘

右键空白画布:
  ┌──────────────────────┐
  │ ✚ 新建表             │  → 打开新建表弹窗
  │ 💬 用 NL 描述血缘...  │  → 跳转 /chat, 注入上下文
  └──────────────────────┘
```

#### 拖拽新建血缘边

```
1. 右键节点 → [⊕ 新建血缘边] → 进入拖拽模式
2. 从源字段点拖到目标字段点
3. 弹出面板:
   ┌── 新建血缘边 ─────────────────────────┐
   │ 源: ods_ue_signal.imsi                │
   │ 目标: dwd_ho_event.imsi                │
   │                                       │
   │ 转换表达式: [直通映射            ]       │
   │ 描述: [UE 标识关联切换事件               │
   │                                       │
   │          [保存] [取消]                  │
   └───────────────────────────────────────┘
4. 保存 → 更新目标字段 upstream_field_refs → G6 图实时刷新
```

#### 跳转 /chat 联动的上下文注入

右键选择「用 NL 修改...」时：

1. 路由切换到 `/chat?context=lineage&table=dws_cell_hourly&field=drop_rate`
2. Agent State 注入 context_prompt (对用户不可见):

```python
context_prompt = """
当前用户来自血缘图页面，正在查看:
  表: dws_cell_hourly
  字段: drop_rate
  当前表达式: CAST(SUM(CASE WHEN drop_flag=1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*)
  上游: dwd_session_qos.drop_flag
"""
```

3. 用户输入 NL → Agent 走 schema_evolve 路径
4. 变更完成后自动刷新血缘图

### 6.6 对话面板 (/chat)

#### 页面布局

```
┌──────────────────────────────────────────────────────────────┐
│  [会话列表 ☰]  NL 对话 — 新建对话                    [⊕ 新对话]│
├────────────────────────────────┬─────────────────────────────┤
│ 左侧: 对话流 (flex: 1)          │ 右侧: 产出面板 (400px)        │
│                                │                             │
│ ┌────────────────────────────┐ │ ┌─ 意图 Badge: 正向ETL ──┐  │
│ │ 🧑 我想看每个小区每小时的    │ │ │                         │  │
│ │   信号质量，覆盖强度和信噪比 │ │ │ 代码: Spark SQL         │  │
│ └────────────────────────────┘ │ │ ┌─────────────────────┐ │  │
│                                │ │ │ SELECT              │ │  │
│ ┌────────────────────────────┐ │ │ │   cell_id,           │ │  │
│ │ 🤖 找到两条相关链路。        │ │ │ │   hour_bucket,      │ │  │
│ │   推荐直接用已聚合好的       │ │ │ │   AVG(rsrp) AS      │ │  │
│ │   dws_cell_hourly。         │ │ │ │   avg_rsrp,         │ │  │
│ │                            │ │ │ │   ...               │ │  │
│ │ ┌─ 血缘预览 ─────────────┐ │ │ │ └─────────────────────┘ │  │
│ │ │ ods → dwd → dws ★     │ │ │ │ Monaco 高亮, 可编辑     │  │
│ │ └────────────────────────┘ │ │ └─────────────────────────┘  │
│ │                            │ │                             │
│ │ [✓ 直接用 dws_cell_hourly] │ │ ┌─ DryRun 结果 ─────────┐  │
│ │ [▸ 从明细自己聚合]         │ │ │ ✅ 成功  耗时 12.3s     │  │
│ └────────────────────────────┘ │ │ ┌────────┬───────────┐ │  │
│                                │ │ │cell_id │avg_rsrp   │ │  │
│ ┌────────────────────────────┐ │ │ │C00042  │-98.3      │ │  │
│ │ 🧑 直接用, 加掉话率>5%过滤  │ │ │ └────────┴───────────┘ │  │
│ └────────────────────────────┘ │ │ 仅展示 1 行             │  │
│                                │ └─────────────────────────┘  │
│ ┌────────────────────────────┐ │                             │
│ │ 🤖 生成完毕。确认跑沙箱？    │ │                             │
│ │ [▶ 沙箱试跑] [✎ 编辑代码]  │ │                             │
│ └────────────────────────────┘ │                             │
│                                │                             │
├────────────────────────────────┴─────────────────────────────┤
│  [输入框: 输入自然语言指令...]                          [发送 →]│
└──────────────────────────────────────────────────────────────┘
```

#### 对话面板功能清单

| 功能 | 说明 |
|------|------|
| 意图 Badge | 顶部显示: 正向ETL / 反向合成 / 元数据演进 |
| SSE 流式输出 | 对话气泡逐字呈现 |
| 血缘预览 mini 图 | Agent 推荐候选表时，右侧展示精简血缘图 |
| 选项按钮 | Agent 给出多选方案时渲染为按钮 |
| 代码卡片 | Monaco Editor 只读模式，语法高亮，可切换编辑 |
| DryRun 预览表格 | 沙箱完成后的 1 行结果，Ant Table 组件 |
| 分档柱状图 | 反向合成完成后展示各档分布，@antv/g2 |
| 约束滑块 | 反向合成中调整值域，Ant Slider |
| Diff 对比面板 | 元数据演进中左右对比旧/新公式 |
| 影响分析警告 | 元数据演进中列出受影响的下游表 |
| 缺失补齐卡片 | gap_check 发现缺口时展示建议 |
| 上下文注入 | 从 /metadata /lineage /pipeline 跳转时自动注入 |
| 错误定位 | 编译/执行失败时高亮错误行 |

### 6.7 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tables` | 表列表 (支持 ?layer= ?search=) |
| GET | `/api/tables/:id` | 表详情 + 字段列表 |
| POST | `/api/tables` | 新建表 |
| PUT | `/api/tables/:id` | 编辑表 |
| DELETE | `/api/tables/:id` | 删除表 (含下游校验) |
| GET | `/api/fields/:id` | 字段详情 + 上游引用 |
| POST | `/api/fields` | 新建字段 |
| PUT | `/api/fields/:id` | 编辑字段 (含表达式/上游引用) |
| DELETE | `/api/fields/:id` | 删除字段 (含断链校验) |
| GET | `/api/lineage` | 血缘图数据 (?table= ?direction=up/down ?depth=1-5) (扫描所有字段 upstream_field_refs 构建) |
| POST | `/api/chat/start` | 新建对话 |
| POST | `/api/chat/message` | 发送消息 → SSE stream |
| GET | `/api/chat/:id/result` | 获取 dry-run 结果 |
| GET | `/api/chat/:id/history` | 获取对话历史 |
| POST | `/api/schema/apply` | 确认元数据变更 |
| GET | `/api/schema/evolution/:table` | 表级变更历史 |
| GET | `/api/yaml/export` | 导出 YAML (?table= 可选) |
| GET | `/api/yaml/preview/:table` | YAML 预览 (只读, 返回原始 YAML 文本) |
| GET | `/api/search` | 语义搜索 (?q= ?type=table/field) — BM25 + Dense + RRF |
| GET | `/api/pipeline` | 全局 Pipeline DAG 数据 (?mode=forward/reverse ?table=) |
| GET | `/api/health` | 服务健康检查 (FastAPI + Docker 各组件连通性) |

> 分页: 当前元数据规模较小 (10 表 / ~70 字段)，列表接口暂不分页。当表数超过 50 时，`GET /api/tables` 和 `GET /api/fields` 需增加 `?page=&size=` 参数。

### 6.8 Pipeline 可视化页面 (/pipeline)

> **表级血缘聚合规则**：Pipeline 页面展示的是表级 DAG（节点 = 表）。表级血缘 = 该表所有字段 `upstream_field_refs` 引用的上游表的去重集合；边权 = 引用该上游表的字段数。后端 `/api/pipeline` 通过聚合字段级血缘构建表级 DAG，不在 SQLite 冗余存储表级血缘。

#### 页面布局

```
┌──────────────────────────────────────────────────────────────┐
│  Pipeline 可视化                    [正向 ETL ●] [反向合成 ○]  │
│                          [搜索表: dws_cell_hourly___]        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  正向 ETL 模式:                                               │
│                                                              │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────┐        │
│  │ods_ue   │    │dwd_session   │    │dws_cell      │        │
│  │_signal  │───→│_qos          │───→│_hourly       │        │
│  │ L1·Kafka│    │ L2·Hive      │    │ L3·Hive      │        │
│  │ 6字段    │    │ 8字段         │    │ 7字段         │        │
│  └─────────┘    └──────┬───────┘    └──────┬───────┘        │
│                        │                   │                │
│  ┌─────────┐           │                   │                │
│  │ods_gnb  │           │           ┌───────┴───────┐        │
│  │_alarm   │──┐        │           │ads_cell       │        │
│  │ L1·Kafka│  │        │           │_profile       │        │
│  │ 5字段    │  │  ┌─────┴──────┐   │ L4·StarRocks  │        │
│  └─────────┘  │  │dwd_ho      │   │ 5字段          │        │
│               ├─→│_event      │   └───────┬───────┘        │
│               │  │ L2·Hive    │           │                │
│               │  │ 7字段       │           ▼                │
│               │  └─────┬──────┘   ┌───────────────┐        │
│               │        │          │eval_user      │        │
│  ┌────────────┴────────┴──────────┤_score         │        │
│  │ dws_area_traffic               │ L5·StarRocks  │        │
│  │ L3·Hive                        │ 5字段          │        │
│  │ 6字段                           └───────────────┘        │
│  └────────────────────────────────┘                        │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ 左侧图例                      右侧信息面板 (悬浮/选中时)       │
│ ┌──────────┐     ┌──────────────────────────────────────┐   │
│ │ ● ODS 层 │     │ 选中: dws_cell_hourly                  │   │
│ │ ● DWD 层 │     │ 层: DWS · Hive · 7 字段               │   │
│ │ ● DWS 层 │     │ 描述: 小区小时粒度汇总                 │   │
│ │ ● ADS 层 │     │ 上游: dwd_session_qos, dwd_ho_event  │   │
│ │ ● EVAL层 │     │ 下游: ads_cell_profile                │   │
│ └──────────┘     │ [查看字段详情] [💬 NL 查询]            │   │
│                  └──────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

#### 正向模式

- G6 DAG (有向无环图)，节点 = 表，边 = 血缘引用
- 节点颜色按层区分 (ODS绿 → DWD蓝 → DWS橙 → ADS紫 → EVAL红)
- 节点大小 = 字段数量映射
- 边标签显示引用字段数 (如 "3 字段引用于")
- 搜索框搜索表名 → 该节点高亮 + 上下游路径突出
- 层级滑块 [1~5] 控制展开半径
- 悬浮节点: 弹出表信息卡片 (字段/存储/描述/行数)
- 点击节点: 右侧面板展示详情 + [💬 NL 查询] 按钮 → /chat 跳转

#### 反向合成模式

- 切换 toggle 后图方向反转 (从右到左)
- 节点从目标表 (如 eval_user_score) 开始
- 每层边标签显示约束推断结果 (值域/分布)
- 点击节点可展开约束详情气泡

```
   反向模式:  ← 约束推断 ←
  ┌─────────┐    ┌──────────────┐    ┌──────────────────┐
  │ods_ue   │←───│dwd_session   │←───│ads_cell_profile  │←───┐
  │_signal  │    │_qos          │    │ 覆盖[0,100]       │    │
  │ rsrp    │    │ avg_rsrp     │    │ 容量[0,100]       │    │
  │ [-140,  │    │ AVG(rsrp)    │    │ 稳定[0,100]       │    │
  │  -44]   │    │              │    │ 移动[0,100]       │    │
  └─────────┘    └──────────────┘    └──────────┬─────────┘    │
                                                │              │
                                                ▼              │
                                     ┌──────────────────┐      │
                                     │eval_user_score ★│←─────┘
                                     │ qoe_score        │
                                     │ =0.5×cov+0.3×cap │
                                     │  +0.2×stab       │
                                     └──────────────────┘
```

#### 与 /chat 联动

1. 悬浮节点 → [💬 NL 查询] → 路由 `/chat?context=pipeline&table=dws_cell_hourly&mode=forward`
2. Agent State 注入上下文: 当前表、上下游链路、已有字段
3. 用户输入如 "从这个表出发查掉话率高于 5% 的小区" → 走正向 ETL 流程
4. 反向模式下类似: `/chat?context=pipeline&table=eval_user_score&mode=reverse`

### 6.9 元数据演化历史页面 (/schema-evolution)

#### 页面布局

```
┌──────────────────────────────────────────────────────────────┐
│  元数据演化历史                                                │
│  [搜索: 表名/字段...]  [表: 全部 ▼]  [操作: 全部 ▼]          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  变更时间线                                                   │
│                                                              │
│  ┌─ 2026-05-13 14:22 ──────────────────────────────────┐    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │ ✏ UPDATE  eval_user_score.qoe_score  v1 → v2 │    │    │
│  │  │                                               │    │    │
│  │  │ 旧: 0.5×coverage + 0.3×capacity + 0.2×stab    │    │    │
│  │  │ 新: 0.6×signal_quality + 0.4×mobility_score   │    │    │
│  │  │                                               │    │    │
│  │  │ 影响下游: eval_net_health ⚠                    │    │    │
│  │  │                  [查看 YAML diff]              │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  │                                                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ 2026-05-13 10:32 ──────────────────────────────────┐    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │ ➕ ADD  dwd_session_qos.jitter  (v1)          │    │    │
│  │  │                                               │    │    │
│  │  │ 类型: DOUBLE                                   │    │    │
│  │  │ 表达式: STDDEV(latency) OVER (...)             │    │    │
│  │  │ 上游: dwd_session_qos.latency                 │    │    │
│  │  │                  [查看 YAML diff]              │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │ ✚ ADD  ods_gnb_load  (新表, v1)               │    │    │
│  │  │                                               │    │    │
│  │  │ 层: ODS · 存储: Kafka · 5 字段                  │    │    │
│  │  │ 分区键: timestamp                              │    │    │
│  │  │                  [查看 YAML]  [查看血缘]        │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  │                                                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ 2026-05-13 09:00 (初始) ───────────────────────────┐    │
│  │  ➕ 批量初始化: 10 张表, ~70 字段                     │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 功能详单

| 功能 | 入口 | 说明 |
|------|------|------|
| 时间线浏览 | 页面主体 | Ant Timeline 组件，按时间倒序 |
| 按表过滤 | 顶部 [表: 全部 ▼] | Select dropdown，列出所有表 |
| 按操作过滤 | 顶部 [操作: 全部 ▼] | ADD / UPDATE / DELETE |
| 按关键词搜索 | 顶部搜索框 | 模糊匹配表名/字段名 |
| 变更卡片 | 时间线内 | 显示操作类型 icon + 表.字段 + 版本号 + 旧→新 diff |
| 字段级 diff | 卡片内 inline | 旧公式 → 新公式 左右对比 |
| YAML diff | [查看 YAML diff] 按钮 | 调 `git diff HEAD~1 -- metadata-yaml/...yaml` 展示 |
| 查看血缘 | [查看血缘] 按钮 | 跳转 `/metadata/lineage?table=xxx` |
| 跳转来源 | URL `?table=xxx` | 从 /metadata 跳转时预过滤 |

#### YAML diff 实现

```python
@router.get("/api/schema/evolution/yaml-diff")
async def get_yaml_diff(table_name: str, version: int):
    """用 git show 取历史版本 YAML"""
    import subprocess
    yaml_path = f"metadata-yaml/{get_layer(table_name)}/{table_name}.yaml"

    # 当前版本
    current = Path(yaml_path).read_text(encoding="utf-8")

    # 历史版本: git show COMMIT:path
    # 通过 version→commit 映射表查找对应 commit
    commit = get_commit_for_version(table_name, version)
    if commit:
        historical = subprocess.check_output(
            ["git", "show", f"{commit}:{yaml_path}"],
            text=True
        )
    else:
        historical = "(初始版本)"

    return {"current": current, "historical": historical, "yaml_path": yaml_path}
```

#### 版本↔commit 映射

元数据变更时在 commit message 中标注 `table:xxx version:N`，反向查找即可：

```python
# schema_apply 节点写入后 commit 时：
commit_msg = f"schema_evolve: UPDATE {table_name}.{field_name} v{old}→v{new}"
# git log --grep "table:dws_cell_hourly version:2" → commit hash
```

---

## 7. 项目结构

```
data-gov/
├── .env                          # DeepSeek + DB 配置
├── base-compose.yml              # 基础设施容器
├── app-compose.yml               # FastAPI + React
├── metadata-yaml/                # 人工可读的 YAML 元数据副本
│   ├── L1-ODS/
│   ├── L2-DWD/
│   ├── L3-DWS/
│   ├── L4-ADS/
│   └── L5-EVAL/
├── init-scripts/
│   ├── 01_hive_init.sql
│   ├── 02_kafka_init.sh
│   ├── 03_starrocks_init.sql
│   ├── 04_sample_data.py
│   ├── 05_sqlite_seed.py
│   └── 06_export_yaml.py
├── scripts/
│   ├── benchmark_semantic_search.py   # 语义检索 benchmark
│   └── generate_benchmark_queries.py  # 测试集生成
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
│   ├── search/
│   │   ├── searcher.py           # HybridSearcher (BM25+Dense+RRF)
│   │   └── embedder.py           # bge-small-zh embedding + ChromaDB
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
        │   ├── SchemaEvolution.tsx
        │   └── Health.tsx
        ├── components/
        │   ├── LineageGraph.tsx   # G6 血缘图封装 (字段级, 被 /metadata/lineage 使用)
        │   ├── PipelineDAG.tsx    # G6 Pipeline DAG 封装 (表级, 被 /pipeline 使用)
        │   ├── graphShared/       # 与 LineageGraph/PipelineDAG 共享: G6 注册行为 (tooltip/drag/zoom/minimap), 层颜色映射, 节点/边样式
        │   ├── CodeCard.tsx       # Monaco 代码卡片
        │   ├── DryRunPreview.tsx  # 1 行预览表格
        │   ├── ConstraintSlider.tsx # 反向合成约束调整
        │   ├── DiffPanel.tsx      # 旧/新公式左右对比
        │   ├── EvolutionTimeline.tsx # 变更时间线
        │   ├── HealthPanel.tsx    # 健康检查面板
        │   └── ChatStream.tsx     # SSE 流式对话
        └── api/
            └── client.ts          # fetch 封装 (含 SSE ReadableStream)
```

---

## 8. 实施阶段 & E2E 验收用例

| Phase | 内容 |
|-------|------|
| **Phase 1** | Docker 栈搭建 + SQLite 元数据初始化 + 元数据 CRUD API |
| **Phase 2** | LangGraph Agent 搭建 + 3 条对话路径 + 沙箱 |
| **Phase 3** | React 前端 + 血缘图 + 对话面板 + Pipeline 可视化 |

### 依赖关系

```
Phase 1 ⇒ Phase 2 ⇒ Phase 3
    (Docker  + 元数据必须先就绪，Agent 才能查 Schema；UI 需要 Agent 和 API 都好)
```

### Phase 1 验收用例

| # | 用例 | 步骤 | 预期结果 |
|---|------|------|----------|
| P1-1 | 一键启动基础设施 | 执行 `docker compose -f base-compose.yml up -d` | 所有 10 个服务 Running (Health: healthy)，HDFS NameNode UI :9870 可访问，YARN RM UI :8088 可访问 |
| P1-2 | Hive 外部表可读写 | 通过 Spark Shell 建外部表 → INSERT 10 行 → SELECT COUNT(*) | 返回 10 |
| P1-3 | Kafka Topic 可生产消费 | 往 `ods_ue_signal` topic 生产 5 条 JSON → consumer 从 earliest 消费 | 消费到 5 条，内容一致 |
| P1-4 | StarRocks 可查询 | `04_sample_data.py` 执行后，StarRocks FE 查询 `SELECT COUNT(*) FROM ads_cell_profile` | 返回 > 0 |
| P1-5 | SQLite 元数据初始化 + YAML 导出 | 执行 `05_sqlite_seed.py`，查询 `SELECT COUNT(*) FROM metadata_tables`；执行 `06_export_yaml.py` | 返回 10；`metadata-yaml/` 下生成 10 个 .yaml 文件，按层分目录，gate-lint 通过 |
| P1-6 | 元数据 CRUD API | POST 建一张新表 → GET /api/tables → GET /api/fields → PUT 修改字段表达式 → GET 校验 | 每步返回 200，数据一致 |
| P1-7 | 血缘查询 API | GET `/api/lineage?table=dwd_session_qos&direction=down` 查下游血缘 | 返回 `dws_cell_hourly`, `dws_area_traffic` 中至少 2 条字段级血缘边 |
| P1-8 | 反向合成数据入对应存储 | 调用 `generate_fake_data(table="dwd_session_qos", rows=5)` → Spark SQL 查询 Hive 表 `dwd_session_qos` | 返回 5 行，字段值域合法 (rsrp ∈ [-140,-44], sinr ∈ [-20,30]) |

### Phase 2 验收用例

| # | 用例 | 步骤 | 预期结果 |
|---|------|------|----------|
| P2-1 | 正向 ETL: NL→Spark SQL | 发送消息 "用 `ods_ue_signal` 按 cell_id 计算每小区小时的平均 RSRP 和 SINR，写入 Hive 表 `dws_cell_hourly`" | 返回 Spark SQL，schema_lookup 工具被调用过，代码语法正确 |
| P2-2 | 正向 ETL: NL→Flink SQL | 发送消息 "从 Kafka `ods_gnb_alarm` 读告警，按 gnb_id 做 5 分钟滚动窗口 COUNT" | 返回 Flink SQL，含 CREATE TABLE (Kafka source) + TUMBLE 窗口 + sink 定义 |
| P2-3 | 正向 ETL: NL→Java Flink | 发送消息 "写一个 Flink DataStream 程序，从 Kafka 读 UE 信号，过滤 RSRP<-110 的弱覆盖，写入 HDFS" | 返回完整 Java main class，含 Kafka source / filter / StreamingFileSink |
| P2-4 | Spark SQL 沙箱执行 | 对 P2-1 生成的 SQL 调 dry_run | 返回 `DryRunResult(success=True, preview_row={...})`，preview_row 含 cell_id/h avg_rsrp/avg_sinr |
| P2-5 | Flink SQL 沙箱执行 | 对 P2-2 生成的 Flink SQL 调 dry_run | HDFS sink 写入成功，回读 1 行，字段匹配 |
| P2-6 | Java Flink 沙箱执行 | 对 P2-3 生成的 Java 代码调 dry_run | 编译成功 → JAR 上传 → YARN 提交 → FINISHED → HDFS 回读 1 行，弱覆盖 IMSI 列表合法 |
| P2-7 | 沙箱编译失败自动重试 | 注入一个有语法错误的 Flink SQL (故意拼错 `SLECT`)，观察沙箱层 `execute_with_retry` 行为 | 沙箱层第 1 轮编译失败 → 解析 maven 错误 → LLM 修正 → 第 2 轮通过；返回 `DryRunResult(success=True)`，Agent 层 `iteration_count = 1`（沙箱层重试不计入 Agent 层） |
| P2-8 | 元数据演进: NL→新增字段 | 发送消息 "给 `dwd_session_qos` 加一个 `jitter` 字段，用相邻采样的 latency 标准差计算" | schema_diff 预览显示 1 条新增字段，用户确认后 SQLite 写入 + 对应 YAML 文件更新，GET /api/fields 可查到，`dwd_session_qos.yaml` 含 `jitter` 字段 |
| P2-9 | 元数据演进: 一致性校验 | 发送消息 "删除 `ods_ue_signal` 的 `rsrp` 字段" | schema_validate 检测到 `dwd_session_qos.avg_rsrp` 和 `dwd_ho_event` 依赖此字段，返回警告不执行，要求先处理下游 |
| P2-10 | 反向合成数据生成 | 发送消息 "给定 `eval_user_score` 的评估逻辑，生成 10 行测试数据，覆盖优秀/良好/差三档" | 反推约束 (qoe_score 0-100) → 生成 3 档数据 → 写入 HDFS → 读回校验: 确实有 >80 / 50-80 / <50 的行 |
| P2-11 | 缺失对象检测 (gap_check) | 发送消息 "我要每个小区每小时的平均基站负载和信号质量" — 信号质量已有，基站负载无 | gap_check 返回 1 条 missing_table gap，Web 端展示补齐建议卡片，含建议表名/字段/层级 |
| P2-12 | 缺失对象自动补齐 | 在 P2-11 的补齐建议卡片点击 [确认并继续] | schema_evolve 子流程自动执行: 新建 ods_gnb_load (ODS, Kafka, 5 字段) → SQLite 写入 + YAML 生成 → schema_lookup 重新查询 → 继续 code_generate 产出含基站负载的 SQL |
| P2-13 | 缺失字段检测 | 人为删除 dwd_session_qos.avg_sinr 字段后，发送 "从会话 QoS 查信噪比分布" | gap_check 检测到 keyword=信噪比 field=avg_sinr 缺失，建议在 dwd_session_qos 补回该字段 |

### Phase 3 验收用例

| # | 用例 | 步骤 | 预期结果 |
|---|------|------|----------|
| P3-1 | 元数据浏览页面: 分层+搜索 | 打开 `/metadata` → 看到 10 张表按层分组 → 切换 L1 过滤 → 仅显示 2 张 ODS 表 → 搜索框输入 "会话" | 列表过滤为 dwd_session_qos，右侧字段列表含 avg_rsrp/avg_sinr 等 |
| P3-2 | 元数据浏览: 字段详情+上游 tooltip | 点击 `dws_cell_hourly` → hover `avg_rsrp` 字段 | tooltip 浮层显示上游: dwd_session_qos.avg_rsrp，表达式: AVG(rsrp) |
| P3-3 | 元数据维护: 新建表 | 点击 [+ 新建表] → 填写表名/层/存储 → 添加 5 个字段 → 保存 | SQLite 写入成功，GET /api/tables 新增 1 条，metadata-yaml/ 下生成对应 .yaml |
| P3-4 | 元数据维护: 编辑字段表达式 | 点击 `dws_cell_hourly.drop_rate` → 抽屉打开 → Monaco 编辑表达式 → 保存 | metadata_fields 表达式更新，version +1，previous_expr 留痕 |
| P3-5 | 元数据维护: 删除字段被拒绝 | 点击删除 `ods_ue_signal.rsrp` | 系统检测到 dwd_session_qos.avg_rsrp 依赖此字段，弹出下游影响警告，拒绝删除 |
| P3-6 | 字段级血缘图: G6 渲染 | 在表详情页点击「查看血缘」→ URL 跳转 `/metadata/lineage?table=dws_cell_hourly` | G6 TreeGraph 渲染完整上下游: ods → dwd → dws → ads → eval，节点含字段 ● 点 |
| P3-7 | 血缘图交互 | 双击节点展开/折叠 → 拖拽画布 → 滚轮缩放 → 点击边查看 transform_expr → Mini-map 导航 | 所有交互流畅，边详情在右侧面板显示 |
| P3-8 | 血缘图维护: 右键菜单 | 右键 `dwd_session_qos` 节点 → 选择 [✚ 在此表上加字段] | 弹出字段编辑抽屉，预填 table=dwd_session_qos |
| P3-9 | 血缘图维护: 拖拽新建边 | 右键节点 → [⊕ 新建血缘边] → 从 ods_ue_signal.imsi 拖线到 dwd_ho_event.imsi → 填写转换表达式 "直通映射" → 保存 | 目标字段 upstream_field_refs 更新，G6 图实时刷新显示新边 |
| P3-10 | 血缘图→/chat 联动 | 右键 `dws_cell_hourly.drop_rate` → [💬 用 NL 修改...] | 路由跳转 `/chat?context=lineage&table=dws_cell_hourly&field=drop_rate`，Agent State 上下文已注入当前表达式和上游信息 |
| P3-11 | 对话面板: 流式输出 + Badge | 打开 `/chat` → 新建对话 → 输入 "计算每小区小时平均覆盖强度" | SSE 逐字流式输出，classifier badge 显示「正向ETL」，右侧展示血缘 mini 图推荐方案 |
| P3-12 | 对话面板: 代码卡片 + DryRun 预览 | 对话完成 → 代码卡片显示 Spark SQL (Monaco 高亮) → 点击 [▶ 沙箱试跑] | 右侧代码面板可编辑，DryRun 结果卡片显示 ✅ 成功 + 1 行 Ant Table |
| P3-13 | 对话面板: 缺失补齐子流程 UI | 输入 "按基站负载和信号质量做评估" → gap_check 发现缺失 | 对话气泡下方显示补齐建议卡片，[确认并继续] [我自己定义] [跳过] 三个按钮 |
| P3-14 | 对话面板: 反向合成约束滑块 | 输入 "给用户评分流程造测试数据" → 约束反推面板展示 | 三档约束表格每行有 Slider 可拖拽调整值域，行数可输入 |
| P3-15 | 对话面板: 反向合成结果图表 | 点击 [生成数据] → 等待沙箱完成 | 结果区显示写入概览 (各层行数) + 预览 Ant Table + 分档 G2 柱状图 |
| P3-16 | 对话面板: 元数据演进 Diff | 输入 "把 qoe_score 公式权重改成 0.6/0.4" → diff 预览 | 左右对比面板: 旧公式 vs 新公式，下方 ⚠ eval_net_health 影响警告 |
| P3-17 | 元数据演进: UI 变更确认 | 点击 [确认更新] | SQLite + YAML 写入，跳转 `/schema-evolution` 可看到变更时间线，字段版本 v1→v2 |
| P3-18 | Pipeline 可视化: 正向 ETL | 打开 `/pipeline` → 正向模式 → 搜索链路 | G6 渲染完整 DAG: ods_ue_signal → dwd_session_qos → dws_cell_hourly → ads_cell_profile → eval_user_score |
| P3-19 | Pipeline 可视化: 反向合成 | 切换反向模式 → 选 eval_user_score pipeline | 逆向图: eval → 约束推断 → 逐层回溯 → 数据生成器入口 |
| P3-20 | Pipeline→/chat 联动 | 在 Pipeline 图上选中 `dws_cell_hourly` 节点 → 点击 [💬 NL 查询] | 跳转 /chat，自动注入上下文，用户输入 "加一个切换成功率过滤" → 走正向 ETL 流程 |
| P3-21 | 全链路: 搜索→血缘→对话→预览 | `/metadata` 搜索 "信噪比" → 进入血缘图 → 右键 [NL 过滤低 SINR] → /chat 生成 SQL → 沙箱跑通 → 预览 1 行 | 60s 内完成，页面跳转流程通顺 |
| P3-22 | 元数据演化历史 | `/schema-evolution` 查看变更时间线 → 按 dwd_session_qos 过滤 → 点击 v1→v2 | 左右 diff 面板显示字段新增详情 |

---

## 9. 非功能要求

- **安全**: `.env` 不提交，`.gitignore` 排除；API 无鉴权 (本地验证栈)
- **可调试**: SQLite 文件在 `./data/` 直接查看；HDFS 数据本地可读
- **清理**: Sandbox 临时目录自动清理；Docker `docker-compose down -v` 全清
- **文档**: 代码即文档，10 张表元数据自带描述和表达式
