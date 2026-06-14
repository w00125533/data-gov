# 19. 项目结构与基础设施详细规格

本文恢复 2026-05-13 文档中的项目结构、Docker、初始化和健康检查信息，并按目标态 shared infra 约束改写。

## 1. 目标项目结构

```text
data-gov/
  AGENTS.md
  app-compose.yml
  metadata-yaml/
    L1-ODS/
    L2-DWD/
    L3-DWS/
    L4-ADS/
    L5-EVAL/
  docs/
    governance-acceptance-test-suite.md
    superpowers/
      specs/
        archive/
        data-governance-platform/
  data-gov-platform/
    pom.xml
    data-gov-common/
      src/main/java/
        dto/
        enums/
        errors/
    data-gov-server/
      src/main/java/
        controller/
        service/
        repository/
        config/
        query/
        notification/
        drift/
      src/main/resources/
        db/migration/
        application.yml
    data-gov-sdk/
      src/main/java/
        registrar/
        subscription/
        notification/
        physical/
  backend/
    main.py
    agent/
    search/
    sandbox/
    api/
  frontend/
    vite.config.ts
    playwright.config.ts
    src/
      api/
      pages/
      components/
      components/graphShared/
      store/
      styles.css
    tests/e2e/
  tests/
    api/
    agent/
    search/
    sandbox/
    infra/
```

## 2. 模块职责

| 模块 | 职责 |
| --- | --- |
| `data-gov-common` | DTO、枚举、错误码、共享契约测试。 |
| `data-gov-server` | Spring Boot governance-server，正式治理 API。 |
| `data-gov-sdk` | Java SDK，封装注册、订阅、查询、通知 listener。 |
| `backend/agent` | LangGraph、LLM、节点实现、提示词。 |
| `backend/search` | BM25、dense、RRF、rerank、Chroma 同步。 |
| `backend/sandbox` | 模板、编译、提交、YARN、HDFS 回读。 |
| `frontend/src/pages` | metadata、lineage、chat、pipeline、schema evolution、health。 |
| `frontend/src/components` | X6 画布、Monaco 卡片、diff、timeline、health panel。 |
| `tests/infra` | shared infra 连通性和真实组件验收。 |

## 3. shared infra 复用

目标态基础设施来源：

```text
../shared-data-infra
```

应由 shared infra 提供：

- GaussDB。
- Kafka / ZooKeeper。
- StarRocks。
- Hive Metastore / HiveServer2。
- HDFS。
- YARN。
- Spark。
- Prometheus / Grafana。
- 如历史环境存在 Neo4j，也只作为迁移读取来源，不作为目标主存储。

本工程 `app-compose.yml` 允许提供：

- `governance-server`。
- Python backend / Agent service。
- frontend。
- Chroma。
- 应用级缓存和日志卷。

## 4. Compose 目标口径

shared infra config：

```powershell
docker compose -f ..\shared-data-infra\compose.yaml --profile data-gov config
```

app config：

```powershell
docker compose -f app-compose.yml config
docker compose -f app-compose.yml --profile governance config
```

启动顺序：

```powershell
docker compose -f ..\shared-data-infra\compose.yaml --profile data-gov up -d
docker compose -f app-compose.yml --profile governance up -d --build governance-server
docker compose -f app-compose.yml up -d backend frontend
```

## 5. 环境变量

Spring Boot：

| 变量 | 说明 |
| --- | --- |
| `SPRING_DATASOURCE_URL` | GaussDB JDBC URL。 |
| `SPRING_DATASOURCE_USERNAME` | 用户名。 |
| `SPRING_DATASOURCE_PASSWORD` | 密码。 |
| `DATA_GOV_KAFKA_BOOTSTRAP_SERVERS` | Kafka 地址。 |
| `DATA_GOV_NOTIFICATION_TOPIC` | 通知 topic。 |
| `DATA_GOV_STARROCKS_JDBC_URL` | StarRocks JDBC。 |
| `DATA_GOV_STARROCKS_USERNAME` | StarRocks 用户。 |
| `DATA_GOV_STARROCKS_PASSWORD` | StarRocks 密码。 |

Python Agent：

| 变量 | 说明 |
| --- | --- |
| `DEEPSEEK_API_KEY` | LLM key。 |
| `DEEPSEEK_BASE_URL` | OpenAI 兼容 base URL。 |
| `GOVERNANCE_API_BASE` | Spring Boot API base。 |
| `CHROMA_HOST` | Chroma 地址。 |
| `YARN_RESOURCE_MANAGER_URL` | YARN RM。 |
| `HDFS_NAMENODE_URL` | HDFS namenode。 |

Frontend：

| 变量 | 说明 |
| --- | --- |
| `VITE_GOVERNANCE_API_BASE` | 浏览器直连 API base，默认空走 Vite proxy。 |
| `VITE_GOVERNANCE_PROXY_TARGET` | Vite dev proxy 到 governance-server。 |
| `VITE_AGENT_API_BASE` | Python Agent base，可选。 |

## 6. 初始化流程

### 6.1 shared infra 初始化

由 `../shared-data-infra` 负责：

- 创建 Kafka topic。
- 初始化 Hive metastore。
- 初始化 StarRocks catalog。
- 启动 HDFS/YARN/Spark。
- 启动监控组件。

### 6.2 应用初始化

由本工程负责：

1. Spring Boot 启动。
2. Flyway migration 建表。
3. 可选注册 RNO 样例 metadata。
4. Python 搜索服务从 Spring Boot metadata API 拉取文档。
5. Chroma upsert 表级和字段级文档。
6. frontend dev server 或容器启动。

## 7. 健康检查实现

### 7.1 Spring Boot

```http
GET /actuator/health
```

应包含：

- DB health。
- Kafka health。
- StarRocks health。
- custom governance readiness。

### 7.2 Python Agent

```http
GET /health
```

应包含：

- LLM config present。
- Chroma reachable。
- governance API reachable。
- sandbox templates present。

### 7.3 Frontend Health 页面聚合

Frontend 调用：

- governance-server health。
- Python Agent health。
- 可选 Spring Boot health detail endpoint。

展示：

| 状态 | UI |
| --- | --- |
| UP | 绿色。 |
| DEGRADED | 黄色，展示降级原因。 |
| DOWN | 红色，展示错误和建议。 |
| UNKNOWN | 灰色，展示未检测。 |

## 8. 数据流

### 8.1 元数据注册流

```text
Java service starts
  -> SDK assembles metadata snapshot
  -> governance-server /metadata/register
  -> GaussDB metadata tables
  -> metadata_event
  -> optional notification
  -> frontend metadata list can query it
```

### 8.2 Agent 流

```text
UI /chat
  -> Python Agent
  -> Spring Boot metadata and lineage API
  -> semantic search / Chroma
  -> code generation
  -> sandbox
  -> structured cards to UI
  -> user confirms schema change
  -> Spring Boot PATCH metadata
```

### 8.3 查询流

```text
Consumer or UI
  -> API query / SQL Gateway
  -> governance-server validates metadata and subscription
  -> StarRocks executes rewritten SQL
  -> query_record
  -> response rows
```

### 8.4 通知流

```text
metadata changed
  -> metadata_event
  -> match subscriptions notifyOn
  -> subscription_notification
  -> Kafka publish
  -> Java SDK listener
  -> business callback
```

## 9. 本地开发命令

Frontend：

```powershell
cd frontend
npm install
npm run dev
```

Spring Boot：

```powershell
cd data-gov-platform
mvn -pl data-gov-server spring-boot:run
```

Python：

```powershell
python -m pip install -e ".[dev]"
uvicorn backend.main:app --reload
```

E2E：

```powershell
cd frontend
npm run test:e2e
npm run test:e2e:headed
```

## 10. 迁移期项目结构说明

迁移期可能同时存在：

- FastAPI 旧 API。
- Spring Boot 正式 API。
- G6 旧图组件。
- X6 新图组件。
- Neo4j 历史数据读取脚本。
- GaussDB 目标表。

文档口径：

- 正文目标态只描述 Spring Boot、GaussDB、X6。
- 迁移附录记录旧实现如何迁移。
- 实施计划必须标清某项工作是在迁移旧能力，还是新增目标能力。

## 11. 验证命令清单

文档和基础检查：

```powershell
git diff --check
```

同时应扫描文档中的未完成标记、临时说明和错误 API 前缀；发现后必须在提交前修正。

Compose：

```powershell
docker compose -f ..\shared-data-infra\compose.yaml --profile data-gov config
docker compose -f app-compose.yml config
docker compose -f app-compose.yml --profile governance config
```

Frontend：

```powershell
cd frontend
npm run lint
npm run build
npm run test:e2e
```

Spring Boot：

```powershell
cd data-gov-platform
mvn test
```

Python：

```powershell
python -m pytest tests/api tests/agent tests/search tests/sandbox -v -m "not infra"
```
