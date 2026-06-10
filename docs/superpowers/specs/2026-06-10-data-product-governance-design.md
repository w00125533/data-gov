# 数据产品治理、订阅、统一查询与血缘设计

> 2026-06-10 | Status: Draft for review

## 1. 背景与目标

在现有 `data-gov` 项目基础上，新增数据注册、发现、订阅、消费、元数据查询和血缘查询能力。现有技术栈包括 Hive、StarRocks、GaussDB、Iceberg、Flink、Spark SQL 和 Kafka。

本设计确认以下方向：

- 数据治理主服务采用 Java Spring Boot 实现。
- 元数据和血缘主库从 Neo4j 改为 GaussDB。
- StarRocks 作为统一 SQL 查询和基础联邦查询入口。
- 产品 API 优先，SQL Gateway 作为补充查询入口。
- Kafka 进入资产目录和订阅通知体系，但不进入统一查询。
- 订阅不是消费事实，也不是核心血缘；订阅表示使用意图和变化通知关注。
- 运行态消费事实由查询记录和作业运行记录表达。
- Java SDK 用于降低微服务、Flink、Spark 作业接入成本。

## 2. 范围

### 2.1 第一期开启

- 数据资产注册、发现、Schema 查询。
- GaussDB 关系模型承载元数据、血缘、订阅、运行态记录、事件和 drift。
- StarRocks 查询网关，支持产品 API 查询和受控 SQL 查询。
- 基础跨源 join：StarRocks 内表、Hive、Iceberg、GaussDB 之间的只读查询。
- Kafka 资产注册、发现、Schema、订阅声明、通知和血缘关系。
- Java SDK 启动注册订阅声明。
- Java SDK 上报 Flink/Spark 作业运行。
- 事件通知和声明态/运行态差异分析。

### 2.2 第一阶段不做

- Python SDK / PySpark SDK。
- CI manifest 同步和 Git webhook。
- 审批流。
- Kafka 统一 SQL 查询。
- 写入类 SQL Gateway。
- 大结果集导出和异步长查询。
- 跨源大表 join SLA。
- 复杂权限、脱敏和 `security_level`。

## 3. 总体架构

```text
上层消费者
  - Java 微服务
  - Flink Java 作业
  - Spark Java/Scala 作业
  - 分析平台 / 前端

Java SDK
  - 启动注册订阅声明
  - 产品 API 查询透传 subscription_id
  - Flink/Spark 作业运行上报
  - 通知拉取

Data-Gov Server (Spring Boot)
  - Asset Registry
  - Discovery Service
  - Subscription Service
  - Query Service
  - SQL Gateway
  - Lineage Service
  - Event / Notification Service
  - Governance Drift Service

GaussDB
  - 元数据主库
  - 血缘主库
  - 订阅声明
  - 查询审计
  - 作业运行记录
  - 事件、通知、drift

StarRocks
  - 统一 SQL 执行入口
  - internal catalog
  - Hive external catalog
  - Iceberg external catalog
  - GaussDB JDBC external catalog

Kafka
  - STREAM 资产
  - 注册、发现、订阅、通知、血缘
  - 不进入统一查询
```

StarRocks 是默认 SQL 执行入口，但不替代 Flink/Spark 的生产和加工职责。Flink 负责流处理，Spark 负责批处理和复杂离线加工，StarRocks 负责交互式查询、产品 API 查询、基础跨源 join 和 OLAP 加速。

## 4. 核心语义

### 4.1 数据资产

统一资产基类为 `data_asset`：

- `TABLE`：Hive、StarRocks、GaussDB、Iceberg 表。
- `STREAM`：Kafka topic。
- `VIEW`：逻辑视图或查询视图。
- `API`：API 型数据产品。
- `JOB_OUTPUT`：作业产物。

Kafka 不强行抽象成普通表。Kafka 可以统一注册、发现、订阅、通知和参与血缘，但 `queryable=false`。

### 4.2 订阅

订阅定义为：

```text
订阅 = 使用意图声明 + 变化通知关注
```

订阅不承担以下职责：

- 不证明真实消费。
- 不等同于数据血缘。
- 不做审批流。

订阅用于：

- 声明服务/作业关心哪些资产和字段。
- 声明用途和使用模式。
- 声明关心哪些变化事件。
- 支持字段变更、资产下线、质量异常、刷新延迟、血缘变化后的通知。
- 为影响分析提供声明态视角。

### 4.3 运行态

运行态事实由以下记录表达：

- `query_record`：产品 API 和 SQL Gateway 查询。
- `job_run_record`：Flink/Spark 作业运行。

运行态回答“谁实际使用了什么、什么时候、成功与否、使用了哪些字段”。

### 4.4 血缘

血缘只表达生产、派生和作业读写链路：

```text
source asset -> job -> target asset
```

第一期资产级血缘优先，字段级血缘建表保留并支持手工或后续解析。

## 5. GaussDB 表模型

### 5.1 资产

```text
data_asset
- asset_id              varchar primary key
- asset_code            varchar unique not null
- asset_name            varchar
- asset_type            varchar not null
- engine                varchar not null
- domain                varchar
- owner                 varchar
- description           text
- lifecycle_status      varchar not null
- schema_version        integer default 1
- queryable             boolean default false
- federated_queryable   boolean default false
- created_at            timestamp
- updated_at            timestamp
```

建议枚举：

- `asset_type`: `TABLE`, `STREAM`, `VIEW`, `API`, `JOB_OUTPUT`
- `engine`: `STARROCKS`, `HIVE`, `ICEBERG`, `GAUSSDB`, `KAFKA`
- `lifecycle_status`: `DRAFT`, `ACTIVE`, `DEPRECATED`, `OFFLINE`

### 5.2 字段

```text
asset_field
- field_id              varchar primary key
- asset_id              varchar not null references data_asset(asset_id)
- field_name            varchar not null
- field_type            varchar not null
- ordinal_position      integer
- nullable              boolean default true
- partition_key         boolean default false
- primary_key           boolean default false
- event_time            boolean default false
- description           text
- expression            text
- version               integer default 1
- created_at            timestamp
- updated_at            timestamp
```

约束：

```text
unique(asset_id, field_name)
index(asset_id)
index(field_name)
```

Kafka key/value schema 不在第一期拆成 `schema_part` 或 `key_field`，相关细节放入物理绑定扩展信息。

### 5.3 物理绑定

```text
asset_physical_binding
- binding_id            varchar primary key
- asset_id              varchar not null references data_asset(asset_id)
- engine                varchar not null
- catalog_name          varchar
- database_name         varchar
- schema_name           varchar
- table_name            varchar
- topic_name            varchar
- format                varchar
- location_uri          text
- connection_ref        varchar
- query_adapter         varchar
- properties            jsonb
- active                boolean default true
- created_at            timestamp
- updated_at            timestamp
```

`properties` 用于 Kafka retention、partition、bootstrap alias、serialization 等扩展信息。

### 5.4 Consumer 和订阅

```text
consumer
- consumer_id           varchar primary key
- consumer_type         varchar not null
- consumer_name         varchar not null
- owner                 varchar
- environment           varchar
- runtime_version       varchar
- instance_id           varchar
- last_seen_at          timestamp
- created_at            timestamp
- updated_at            timestamp
```

```text
subscription
- subscription_id       varchar primary key
- asset_id              varchar not null references data_asset(asset_id)
- consumer_id           varchar not null references consumer(consumer_id)
- usage_mode            varchar not null
- purpose               text
- source_type           varchar not null
- declaration_hash      varchar
- declared_fields       jsonb
- notify_on             jsonb
- status                varchar not null
- last_registered_at    timestamp
- last_runtime_seen_at  timestamp
- created_at            timestamp
- updated_at            timestamp
```

建议枚举：

- `consumer_type`: `MICROSERVICE`, `FLINK_JOB`, `SPARK_JOB`, `USER`, `BI`
- `usage_mode`: `API_QUERY`, `SQL_QUERY`, `FLINK_CONSUME`, `SPARK_CONSUME`, `MICROSERVICE_READ`, `KAFKA_CONSUME`
- `source_type`: `SDK_STARTUP`, `API`, `RUNTIME_REPORT`, `INFERRED`
- `status`: `ACTIVE`, `STALE`, `PAUSED`, `REVOKED`

第一期不拆 `subscription_field`，字段声明放入 `declared_fields`。

### 5.5 查询记录

```text
query_record
- query_id              varchar primary key
- subscription_id       varchar null references subscription(subscription_id)
- consumer_id           varchar null references consumer(consumer_id)
- query_type            varchar not null
- referenced_asset_ids  jsonb
- referenced_asset_codes jsonb
- selected_fields       jsonb
- sql_text              text
- normalized_sql        text
- query_engine          varchar not null
- status                varchar not null
- row_count             bigint
- elapsed_ms            bigint
- error_message         text
- started_at            timestamp
- finished_at           timestamp
```

第一期不拆 `query_record_asset`，多资产引用放入 JSON。

### 5.6 作业运行

```text
consumer_job
- job_id                varchar primary key
- consumer_id           varchar references consumer(consumer_id)
- job_name              varchar not null
- job_type              varchar not null
- owner                 varchar
- code_ref              text
- runtime_config        jsonb
- status                varchar
- created_at            timestamp
- updated_at            timestamp
```

```text
job_run_record
- run_id                varchar primary key
- job_id                varchar references consumer_job(job_id)
- subscription_id       varchar null references subscription(subscription_id)
- input_asset_ids       jsonb
- output_asset_ids      jsonb
- input_asset_codes     jsonb
- output_asset_codes    jsonb
- input_fields          jsonb
- output_fields         jsonb
- status                varchar not null
- rows_read             bigint
- rows_written          bigint
- started_at            timestamp
- finished_at           timestamp
- error_message         text
```

第一期不建 `job_io_record`。

### 5.7 血缘

```text
lineage_edge
- edge_id               varchar primary key
- source_asset_id       varchar references data_asset(asset_id)
- target_asset_id       varchar references data_asset(asset_id)
- relation_type         varchar not null
- producer_job_id       varchar null references consumer_job(job_id)
- transform_type        varchar
- transform_ref         text
- confidence            numeric
- created_at            timestamp
- updated_at            timestamp
```

```text
lineage_field_edge
- edge_id               varchar primary key
- source_field_id       varchar references asset_field(field_id)
- target_field_id       varchar references asset_field(field_id)
- asset_lineage_edge_id varchar references lineage_edge(edge_id)
- transform_expr        text
- confidence            numeric
```

递归查询使用 GaussDB recursive CTE，默认限制深度。

### 5.8 事件、通知、差异分析

```text
asset_event
- event_id              varchar primary key
- asset_id              varchar references data_asset(asset_id)
- event_type            varchar not null
- event_payload         jsonb
- severity              varchar
- created_at            timestamp
```

```text
subscription_notification
- notification_id       varchar primary key
- event_id              varchar references asset_event(event_id)
- subscription_id       varchar references subscription(subscription_id)
- consumer_id           varchar references consumer(consumer_id)
- status                varchar not null
- channel               varchar
- created_at            timestamp
- sent_at               timestamp
- acked_at              timestamp
```

```text
usage_drift
- drift_id              varchar primary key
- drift_type            varchar not null
- asset_id              varchar references data_asset(asset_id)
- consumer_id           varchar references consumer(consumer_id)
- subscription_id       varchar null references subscription(subscription_id)
- evidence              jsonb
- status                varchar not null
- detected_at           timestamp
- resolved_at           timestamp
```

事件类型：

- `SCHEMA_CHANGE`
- `DATA_QUALITY_ALERT`
- `FRESHNESS_DELAY`
- `DEPRECATION`
- `ASSET_OFFLINE`
- `LINEAGE_CHANGE`
- `BINDING_CHANGE`

Drift 类型：

- `STALE_DECLARATION`
- `USED_BUT_UNDECLARED`
- `FIELD_USED_BUT_UNDECLARED`
- `DECLARED_BUT_UNUSED`
- `DECLARED_FIELD_UNUSED`
- `BROKEN_BY_SCHEMA_CHANGE`

## 6. Spring Boot 服务设计

建议新增 Java 多模块工程：

```text
data-gov-platform/
  pom.xml
  data-gov-common/
  data-gov-server/
  data-gov-sdk/
```

`data-gov-server` 模块：

```text
asset                 -- 资产注册、发现、schema、binding
metadata              -- 原 metadata 能力的 GaussDB 实现
subscription          -- 订阅声明、通知偏好
query                 -- 产品 API、SQL Gateway、StarRocks 执行
lineage               -- 血缘、影响分析
sdk                   -- SDK 启动注册、作业上报
event                 -- 资产事件、通知
governance            -- usage_drift
job                   -- consumer_job、job_run_record
```

建议技术栈：

- Spring Boot 3.x
- Java 17+
- MyBatis / MyBatis Plus
- Flyway
- HikariCP
- GaussDB PostgreSQL/JDBC driver
- StarRocks MySQL JDBC driver

MyBatis 优先，因为递归 CTE、JSON 查询、复杂 upsert 和 SQL Gateway 审计会比 JPA 更直接。

## 7. API 设计

### 7.1 资产 API

```http
POST /api/assets/register
GET  /api/assets
GET  /api/assets/{assetId}
GET  /api/assets/{assetId}/schema
GET  /api/assets/{assetId}/binding
GET  /api/assets/{assetId}/consume-guide
```

### 7.2 订阅 API

```http
POST /api/assets/{assetId}/subscriptions
GET  /api/subscriptions
GET  /api/subscriptions/{subscriptionId}
PATCH /api/subscriptions/{subscriptionId}
```

### 7.3 SDK API

`/api/sdk/*` 是给 Java SDK 自动调用的内部治理接口，不是普通用户或前端直接调用的业务 API。

```http
POST /api/sdk/subscriptions/register
POST /api/sdk/jobs/register
POST /api/sdk/jobs/{jobId}/runs/start
POST /api/sdk/jobs/{jobId}/runs/{runId}/finish
```

启动注册请求示例：

```json
{
  "consumer": {
    "consumerName": "rno-dashboard",
    "consumerType": "MICROSERVICE",
    "owner": "network-team",
    "environment": "prod",
    "runtimeVersion": "1.8.3",
    "instanceId": "pod-rno-dashboard-7d8f"
  },
  "declarationHash": "sha256:xxx",
  "subscriptions": [
    {
      "assetCode": "ads_cell_profile",
      "usageMode": "API_QUERY",
      "purpose": "展示小区画像指标",
      "fields": ["cell_id", "coverage_score"],
      "notifyOn": ["SCHEMA_CHANGE", "DATA_QUALITY_ALERT", "DEPRECATION"]
    }
  ]
}
```

### 7.4 查询 API

```http
POST /api/assets/{assetId}/query
POST /api/sql
```

产品 API 查询仅查询单个资产，字段和过滤条件必须来自 `asset_field`。

SQL Gateway 支持只读 `SELECT` 和基础跨源 join，要求引用已注册资产，禁止 Kafka 和未注册表。

### 7.5 血缘、影响分析、通知和治理

```http
GET  /api/assets/{assetId}/lineage?direction=up&depth=5
GET  /api/assets/{assetId}/impact
POST /api/assets/{assetId}/events
GET  /api/notifications
PATCH /api/notifications/{notificationId}/ack
POST /api/governance/drift-check
GET  /api/governance/drifts
PATCH /api/governance/drifts/{driftId}
```

## 8. StarRocks 查询网关

### 8.1 Catalog 规划

```text
default_catalog.data_gov.*        -- StarRocks 本地表
hive_catalog.data_gov.*           -- Hive 表
iceberg_catalog.data_gov.*        -- Iceberg 表
gaussdb_catalog.public.*          -- GaussDB 表
```

`asset_physical_binding` 保存资产到 StarRocks 三段名的映射。

### 8.2 产品 API 查询

请求：

```json
{
  "select": ["cell_id", "coverage_score"],
  "filters": [
    {"field": "date", "op": "=", "value": "2026-06-10"}
  ],
  "limit": 100
}
```

服务端流程：

```text
查资产和 binding
-> 校验 queryable=true
-> 拒绝 Kafka
-> 校验字段
-> 生成参数化 StarRocks SQL
-> 执行
-> 写 query_record
```

### 8.3 SQL Gateway

SQL Gateway 流程：

```text
SQL Guard 校验只读
-> 提取表名
-> 映射 asset_code 到 binding
-> 拒绝未注册资产和 Kafka
-> 改写为 catalog.database.table
-> 执行 StarRocks
-> 写 query_record
```

第一期限制：

- 只允许 `SELECT` / `WITH SELECT`。
- 禁止 `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `ALTER`。
- 默认要求或自动补充 `LIMIT`。
- 查询超时默认 30 秒。
- 返回行数上限默认 5000。
- 不承诺跨源大表 join SLA。

## 9. Java SDK

第一期只做 Java SDK，不做 Python。

### 9.1 Spring Boot 微服务集成

```yaml
data-gov:
  enabled: true
  endpoint: http://data-gov-server:8080
  consumer:
    name: rno-dashboard
    type: MICROSERVICE
    owner: network-team
    environment: prod
    version: 1.8.3
  subscriptions:
    - asset-code: ads_cell_profile
      usage-mode: API_QUERY
      purpose: 展示小区画像指标
      fields: [cell_id, coverage_score]
      notify-on: [SCHEMA_CHANGE, DATA_QUALITY_ALERT, DEPRECATION]
```

SDK 在 `ApplicationReadyEvent` 自动注册：

```text
读取配置
-> 计算 declaration_hash
-> POST /api/sdk/subscriptions/register
-> 缓存 asset_code -> subscription_id
```

业务查询：

```java
QueryResult result = dataGovClient.asset("ads_cell_profile")
    .select("cell_id", "coverage_score")
    .where("date", "=", LocalDate.now())
    .limit(100)
    .query();
```

### 9.2 Flink/Spark Java 作业集成

```java
DataGovJobReporter reporter = DataGovJobReporter.builder()
    .endpoint("http://data-gov-server:8080")
    .jobName("cell-hourly-agg")
    .jobType(JobType.FLINK)
    .owner("network-team")
    .inputAsset("ods_ue_signal")
    .outputAsset("dwd_session_qos")
    .build();

reporter.register();
String runId = reporter.startRun();

try {
    // job logic
    reporter.finishRun(runId, JobRunStatus.SUCCESS);
} catch (Exception e) {
    reporter.finishRun(runId, JobRunStatus.FAILED, e);
    throw e;
}
```

作业完成时，服务端 upsert `lineage_edge`。

### 9.3 SDK 错误处理

默认不阻断业务启动：

- 注册失败：记录 warning，业务继续。
- 作业上报失败：记录 warning，可重试。
- 查询失败：作为业务查询异常抛出。

可配置：

```yaml
data-gov:
  fail-fast: false
  register-timeout-ms: 3000
  report-timeout-ms: 3000
  retry:
    max-attempts: 3
```

## 10. 事件通知与 Drift

资产变化写入 `asset_event`，再根据 `subscription.notify_on` 生成 `subscription_notification`。

第一期通知通道只做 API 拉取：

```http
GET /api/notifications?consumerName=rno-dashboard&status=PENDING
PATCH /api/notifications/{notificationId}/ack
```

SDK 可定时拉取通知，默认写日志，不自动 ack。

Drift 检测第一期实现：

- `STALE_DECLARATION`
- `USED_BUT_UNDECLARED`
- `FIELD_USED_BUT_UNDECLARED`

订阅负责声明和通知，运行态记录负责证明真实使用，drift 负责发现两者不一致。

## 11. 迁移和实施

### 阶段 1：Spring Boot 服务骨架

- 新建 Java 多模块工程。
- 接入 GaussDB、StarRocks。
- Flyway 建表。
- 健康检查。

### 阶段 2：GaussDB 元数据替换 Neo4j

- 实现资产、字段、物理绑定、血缘。
- 现有样例表迁移为 GaussDB seed。
- Spring Boot 提供 `/api/assets/*`。
- 如前端短期依赖旧接口，可提供兼容 `/api/tables`、`/api/fields`、`/api/lineage`。

### 阶段 3：订阅和 Java SDK

- 实现 SDK 启动注册。
- 实现 job 注册和运行上报。
- 支持 `declaration_hash`、`last_registered_at`、`last_runtime_seen_at`。

### 阶段 4：StarRocks 查询网关

- 实现产品 API 查询。
- 实现 SQL Gateway。
- 验证 StarRocks 本地表、Hive、Iceberg、GaussDB catalog。
- 验证基础跨源 join。

### 阶段 5：事件、通知、影响分析和 drift

- 实现资产事件。
- 实现通知拉取和 ack。
- 实现影响分析。
- 实现第一批 drift 检测。

## 12. 验收标准

- 现有 10 张样例表可注册到 GaussDB。
- Kafka topic 可注册为 `STREAM` 资产，查询时返回明确错误。
- 资产发现、Schema 查询、上下游血缘查询可用。
- Java 微服务启动后可自动注册订阅。
- Flink/Spark Java 作业可注册 job、上报运行，并生成资产级血缘。
- 产品 API 可通过 StarRocks 查询表型资产。
- SQL Gateway 可执行只读查询并改写已注册资产为 StarRocks 三段名。
- 至少验证一个基础跨源 join。
- 查询写入 `query_record`。
- Schema 变化事件能生成订阅通知。
- 未声明使用或字段超声明能生成 drift。

## 13. 基础设施约束

遵守项目 `AGENTS.md`：

- 新增或修改 Docker Compose 基础设施前，必须先检查 `../shared-data-infra`。
- 如果 shared infra 已定义 GaussDB、HDFS、Hive、Spark、YARN、Kafka、StarRocks、Prometheus、Grafana 等能力，不在本工程重复新增。
- 修改基础设施后至少运行：

```bash
docker compose -f ../shared-data-infra/compose.yaml --profile data-gov config
docker compose -f app-compose.yml config
```

本设计倾向复用 shared infra，本工程只保留治理服务、前端和必要应用级资源。
