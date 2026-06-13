# Data Governance Acceptance Test Suite

本文整理 `data-gov` 当前需求下的端到端验收用例集，覆盖共享基础设施、旧 FastAPI 治理能力、正式 Spring Boot governance API、订阅/查询/通知/drift、Agent 沙箱和前端 UI。用例优先绑定到已有自动化测试；尚未自动化的场景标记为 `Manual / To Automate`。

## 1. 验收目标

- 证明共享 Docker 基础设施由 `../shared-data-infra` 提供，本工程不重复定义 HDFS、Hive、YARN、Kafka、StarRocks、Spark、Neo4j 等能力。
- 证明旧 FastAPI 数据治理能力仍可用：元数据 CRUD、字段级血缘、Pipeline、Schema Evolution、NL Chat、语义搜索、沙箱 dry-run。
- 证明正式治理服务可用：`/rest/oss/inner/modelengineservice/v1` 下的元数据快照、元数据发现、字段级血缘、订阅、产品 API 查询、SQL Gateway、事件通知、drift 分析。
- 证明前端能看到并操作主要治理功能，特别是正式血缘图。
- 证明 Docker 运行方式可启动应用服务，并通过前端代理访问正式治理接口。

## 2. 执行前置条件

### 2.1 本地依赖

- Docker Desktop 可用。
- Node.js 24+，frontend 已安装依赖。
- Python 环境已安装项目开发依赖：`python -m pip install -e ".[dev]"`。
- Java 17 和 Maven 可用。
- Playwright Chromium 已安装：`cd frontend && npx playwright install chromium`。

### 2.2 共享基础设施

从 `D:\agent-code\data-gov` 执行：

```powershell
docker compose -f ..\shared-data-infra\compose.yaml --profile data-gov config
docker compose -f app-compose.yml config
docker compose -f app-compose.yml --profile governance config
```

验收标准：

- 三个命令退出码为 `0`。
- `../shared-data-infra` 配置中包含共享网络 `shared-data-infra`。
- `app-compose.yml` 只定义应用级服务和卷：`backend`、`frontend`、`governance-server`、Chroma/应用数据卷等。
- 本工程没有重复新增 Neo4j、HDFS、Hive、YARN、Kafka、StarRocks、Spark、Prometheus、Grafana 服务。

## 3. 推荐执行套件

### Suite A: 快速回归

适合每次前端或正式 API 小改后执行。

```powershell
cd frontend
npm run lint
npm run build
node --test src/components/graphShared/formalLineageGraphData.test.mjs
npm run test:e2e -- tests/e2e/formal-lineage.acceptance.spec.ts
```

### Suite B: 可观察 UI 验收

用于人工观察浏览器操作。

```powershell
cd frontend
npm run test:e2e:headed
```

可通过 `PW_SLOW_MO` 放慢操作：

```powershell
$env:PW_SLOW_MO="1200"; npm run test:e2e:headed
```

### Suite C: 正式治理服务回归

```powershell
cd data-gov-platform
mvn -pl data-gov-common -Dtest=FormalLineageDtosContractTest,FormalSubscriptionDtosContractTest test
mvn -pl data-gov-server "-Dtest=MetadataControllerTest,FormalSubscriptionControllerTest,FormalQueryControllerTest,EventControllerTest,DriftControllerTest" test
```

### Suite D: 旧 FastAPI / Agent / 沙箱回归

```powershell
python -m pytest tests/api tests/search tests/agent tests/sandbox -v -m "not infra"
```

### Suite E: 共享基础设施集成验收

需要 shared infra 已启动。

```powershell
python -m pytest tests/infra -v
python -m pytest tests/search -v -m infra
docker compose -f app-compose.yml exec backend pytest tests/sandbox -v -m infra
```

### Suite F: Docker 运行验收

```powershell
docker compose -f ..\shared-data-infra\compose.yaml --profile data-gov up -d
docker compose -f app-compose.yml --profile governance up -d --build governance-server
curl.exe -fsS http://localhost:8080/actuator/health
curl.exe -fsS "http://127.0.0.1:5173/rest/oss/inner/modelengineservice/v1/metadata?size=1"
```

验收标准：

- `governance-server` health 为 `UP`。
- 前端 Vite 代理 `/rest/...` 能访问正式治理服务。

## 4. 场景矩阵

| ID | 场景 | 覆盖目标 | 自动化状态 |
| --- | --- | --- | --- |
| INF-001 | 共享基础设施配置合法 | Docker profile、external network、服务不重复 | Existing |
| INF-002 | 共享基础设施健康 | Neo4j/HDFS/YARN/Hive/Kafka/StarRocks 可达 | Existing |
| LEG-001 | 旧元数据 CRUD | FastAPI 表/字段创建、更新、删除 | Existing |
| LEG-002 | 旧字段级血缘 | `/api/lineage` 上下游字段边 | Existing |
| LEG-003 | 旧 Pipeline DAG | forward/reverse 聚合边 | Existing |
| LEG-004 | Schema Evolution | schema apply、YAML、timeline | Existing |
| SRCH-001 | 语义搜索 | 中文查询、字段文档、RRF、rerank 降级 | Existing |
| AGT-001 | NL Agent 主流程 | intent、gap、schema evolve、dry-run retry | Existing |
| SBOX-001 | 沙箱 dry-run | Spark/Flink 编译、提交、YARN 状态 | Existing |
| GOV-META-001 | 正式元数据快照注册 | 创建、更新、幂等、软下线 | Existing |
| GOV-META-002 | 正式元数据发现 | 列表、详情、过滤、分页 | Existing |
| GOV-META-003 | 运行时修改/取消注册 | `PATCH`/`DELETE metadataId` | Existing |
| GOV-LIN-001 | 正式字段级血缘写入 | snapshot lineage + fieldMappings | Existing |
| GOV-LIN-002 | 正式字段级血缘查询 | `nodes`/`edges`/`fieldEdges` | Existing |
| GOV-SUB-001 | 正式订阅生命周期 | 创建、列表、取消 | Existing |
| GOV-QRY-001 | 产品 API 查询 | `metadataId`、订阅校验、query_record | Existing |
| GOV-QRY-002 | SQL Gateway | 只读 SQL、资产改写、拒绝非法对象 | Existing |
| GOV-EVT-001 | 事件通知 | notifyOn 匹配、Kafka publish、失败标记 | Existing |
| GOV-DRIFT-001 | Drift 分析 | declared unused、undeclared usage、stale declaration | Existing |
| UI-001 | 正式血缘图可见可操作 | 搜索资产、选择、查看字段边详情 | Existing |
| UI-002 | 旧血缘模式兼容 | 正式/旧表字段模式切换 | To Automate |
| UI-003 | 元数据管理页面 | 表列表、详情、字段 CRUD、YAML 预览 | To Automate |
| UI-004 | Chat 页面 | SSE 流、上下文跳转、结果面板 | To Automate |
| UI-005 | Pipeline 页面 | DAG 渲染、方向切换、选中表 | To Automate |
| UI-006 | Schema Evolution 页面 | timeline、diff、跳转血缘 | To Automate |

## 5. 详细验收用例

### INF-001 共享基础设施配置合法

**前置条件:** `../shared-data-infra` 存在。

**步骤:**

1. 执行共享配置渲染：`docker compose -f ..\shared-data-infra\compose.yaml --profile data-gov config`。
2. 执行应用配置渲染：`docker compose -f app-compose.yml config`。
3. 执行 governance profile 配置渲染：`docker compose -f app-compose.yml --profile governance config`。

**期望:**

- 三个命令退出码为 `0`。
- 应用 compose 复用 `shared-data-infra` external network。
- 不在本工程重复定义共享基础设施服务。

**已有自动化:** Compose config 命令；共享 infra 健康见 `tests/infra/test_compose_health.py`。

### INF-002 共享基础设施健康

**步骤:**

```powershell
python -m pytest tests/infra/test_compose_health.py -v
```

**期望:**

- Neo4j HTTP 可达。
- Namenode / ResourceManager UI 可达。
- Hive Metastore thrift 端口可达。
- Kafka broker 可达。
- StarRocks FE 可达。

### LEG-001 旧元数据 CRUD

**步骤:**

```powershell
python -m pytest tests/api/test_metadata_crud.py tests/api/test_metadata_service.py -v
```

**期望:**

- 表列表返回 seed 数据。
- 表/字段创建、更新、删除 roundtrip 成功。
- 删除有下游引用字段时被拒绝。
- 字段表达式更新后版本递增。

### LEG-002 旧字段级血缘

**步骤:**

```powershell
python -m pytest tests/api/test_lineage.py -v
```

**期望:**

- `direction=down` 返回 `dwd_session_qos` 下游。
- `direction=up` 返回 `dws_cell_hourly` 上游。
- 非法 direction 返回错误。

### LEG-003 旧 Pipeline DAG

**步骤:**

```powershell
python -m pytest tests/api/test_pipeline.py -v
```

**期望:**

- forward 模式聚合表间依赖边。
- reverse 模式翻转边方向。

### LEG-004 Schema Evolution 与 YAML

**步骤:**

```powershell
python -m pytest tests/agent/test_api_schema.py tests/api/test_schema_evolution_list.py tests/api/test_yaml_metadata.py tests/agent/test_yaml_sync.py -v
```

**期望:**

- `/api/schema/apply` 执行合法 diff，拒绝非法 diff。
- schema evolution 支持按表、operation、关键字过滤。
- YAML preview/export/diff 可用。
- YAML 同步能写文件并生成 git commit hash。

### SRCH-001 语义搜索

**步骤:**

```powershell
python -m pytest tests/search -v
```

**期望:**

- 中文自然语言查询命中 `dws_cell_hourly`。
- 字段级 doc 可搜索。
- BM25 + dense RRF 结果结构合法。
- embedding 不可用时降级为 BM25。
- LLM rerank 失败时回退输入顺序。

### AGT-001 NL Agent 主流程

**步骤:**

```powershell
python -m pytest tests/agent -v
```

**期望:**

- intent classifier 支持 forward_etl、reverse_synth、schema_evolve。
- gap_check / gap_proposal 可生成 schema diff。
- schema_validate 阻断破坏下游的变更。
- dry_run 失败后按最大轮次重试。
- Chat SSE、history、result API 可用。

### SBOX-001 沙箱 dry-run

**步骤:**

```powershell
python -m pytest tests/sandbox -v -m "not infra"
docker compose -f app-compose.yml exec backend pytest tests/sandbox -v -m infra
```

**期望:**

- 模板加载和占位符注入正确。
- Maven 编译成功/失败能解析错误。
- Spark/Flink submit 能解析 app id。
- YARN 终态轮询正确。
- 真实 Spark SQL / Flink SQL dry-run 可执行。

### GOV-META-001 正式元数据快照注册

**接口:** `POST /rest/oss/inner/modelengineservice/v1/metadata/register`

**步骤:**

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=MetadataControllerTest#snapshotRegisterCreatesAndListsFormalMetadata test
mvn -pl data-gov-server -Dtest=MetadataControllerTest#repeatedSnapshotReturnsUnchangedWithoutIncrementingSchemaVersion test
mvn -pl data-gov-server -Dtest=MetadataControllerTest#changedSnapshotUpdatesExistingMetadata test
mvn -pl data-gov-server -Dtest=MetadataControllerTest#fullSnapshotMarksMissingScopedMetadataRemovedBySnapshot test
```

**期望:**

- 首次快照创建元数据、schema、binding。
- 重复提交相同快照返回 `UNCHANGED`，不重复创建。
- 声明变化返回 `UPDATED`。
- 同 producer scope 缺失资产被软下线为 `REMOVED_BY_SNAPSHOT`。
- 已离线资产不会被快照缺失再次错误处理。

### GOV-META-002 正式元数据发现

**接口:** `GET /metadata`、`GET /metadata/{metadataId}`

**步骤:**

```powershell
cd data-gov-platform
mvn -pl data-gov-server "-Dtest=MetadataControllerTest#snapshotRegisterCreatesAndListsFormalMetadata,MetadataControllerTest#metadataDetailJoinsNonBlankBindingPartsWhenCatalogIsOmitted,MetadataControllerTest#metadataListWithVeryLargePageReturnsEmptyItems" test
```

**期望:**

- 列表返回 `metadataId`、`assetCode`、`metadataType`、`sourceType`、`queryable`。
- 详情返回 schema 和 binding。
- binding qualified name 能跳过空 catalog。
- 超大 page 返回空 items，不报错。

### GOV-META-003 运行时修改和取消注册

**接口:** `PATCH /metadata/{metadataId}`、`DELETE /metadata/{metadataId}`

**步骤:**

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=MetadataControllerTest#patchAndDeleteMetadataByIdReuseRuntimeMutationBehavior test
mvn -pl data-gov-server -Dtest=AssetRuntimeMutationControllerTest test
```

**期望:**

- `metadataId` 能解析到资产并复用 runtime mutation 行为。
- 修改元数据触发 schema change notification。
- 删除资产标记 offline/unregistered，并触发下线事件。
- 不存在资产返回 404。

### GOV-LIN-001 正式字段级血缘写入

**步骤:**

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=MetadataControllerTest#snapshotRegisterReplacesDeclaredLineageForProducerScope test
mvn -pl data-gov-server -Dtest=MetadataControllerTest#fullSnapshotDeactivatesLineageForOmittedScopedAssets test
```

**期望:**

- 快照中的 `lineage.upstreams[].fieldMappings[]` 写入字段级血缘。
- 同 producer scope 重复快照替换旧血缘，不生成重复 active edge。
- 快照移除 scoped asset 时，其声明血缘被停用。
- 外部 scope 血缘不被误删。

### GOV-LIN-002 正式字段级血缘查询

**接口:** `GET /metadata/{metadataId}/lineage?direction=up|down&depth=N`

**步骤:**

```powershell
cd data-gov-platform
mvn -pl data-gov-server "-Dtest=MetadataControllerTest#formalMetadataLineageReturnsNodesEdgesAndFieldEdgesByMetadataId,MetadataControllerTest#formalMetadataLineageMissingMetadataReturns404,MetadataControllerTest#formalMetadataLineageDefaultsMalformedRuntimeLineageTypeToTable" test
```

**期望:**

- 响应包含 `metadataId`、`direction`、`depth`。
- `nodes` 使用 `metadataId`、`assetCode`、`assetName`。
- `edges` 包含源/目标 `metadataId` 和 `lineageType`。
- `fieldEdges` 包含 `sourceField`、`targetField`、字段表达式。
- 缺失 metadata 返回 404。
- 历史脏数据 lineageType 解析失败时降级为 `TABLE`。

### GOV-SUB-001 正式订阅生命周期

**接口:** `POST/GET/DELETE /subscriptions/{metadataId}`

**步骤:**

```powershell
cd data-gov-platform
mvn -pl data-gov-common -Dtest=FormalSubscriptionDtosContractTest test
mvn -pl data-gov-server -Dtest=FormalSubscriptionControllerTest test
```

**期望:**

- 创建订阅返回 `subscriptionId`、`metadataId`、`assetCode`、`consumerId`、`ACTIVE`。
- 查询订阅可按 metadata 返回 active subscription。
- 取消订阅返回 cancelled subscriptions。
- 缺失 metadata 返回 404。

### GOV-QRY-001 产品 API 查询

**接口:** `POST /apiquery/{metadataId}`

**步骤:**

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=FormalQueryControllerTest#formalApiQueryResolvesMetadataIdAndHeaderSubscription test
mvn -pl data-gov-server -Dtest=FormalQueryControllerTest#formalApiQueryRejectsMismatchedHeaderAndBodySubscription test
mvn -pl data-gov-server -Dtest=FormalQueryControllerTest#formalApiQueryRejectsCancelledSubscription test
mvn -pl data-gov-server -Dtest=FormalQueryControllerTest#formalApiQueryMissingMetadataReturns404 test
```

**期望:**

- 使用 `metadataId` 定位数据集。
- `X-DataGov-Subscription-Id` 与 body subscription 一致时允许查询。
- header/body subscription 不一致时拒绝。
- 取消订阅后拒绝查询。
- 缺失 metadata 返回 404。
- 查询尝试写入运行态 query record。

### GOV-QRY-002 SQL Gateway

**接口:** `POST /sqlquery`

**步骤:**

```powershell
cd data-gov-platform
mvn -pl data-gov-server "-Dtest=QueryControllerTest#sqlGatewayRejectsDelete,QueryControllerTest#sqlGatewayRewritesAssetCodeToPhysicalName,QueryControllerTest#sqlGatewaySupportsSimpleTwoAssetJoin,QueryControllerTest#sqlGatewaySupportsSimpleCteReferencingRegisteredAsset,QueryControllerTest#sqlGatewayRejectsJoinWhenAnyAssetIsNotFederatedQueryable,QueryControllerTest#sqlGatewayRejectsUnknownAssetCode" test
mvn -pl data-gov-server "-Dtest=FormalQueryControllerTest#formalSqlQueryUsesExistingSqlGateway,FormalQueryControllerTest#formalSqlQueryRejectsCancelledSubscription" test
```

**期望:**

- 只允许只读 SQL，拒绝 DELETE。
- 已注册 assetCode 被改写为物理 qualified name。
- 支持简单 join 和 CTE。
- 未注册对象和不可 federated queryable 对象被拒绝。
- 取消订阅后拒绝 SQL 查询。

### GOV-EVT-001 事件通知

**步骤:**

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=EventControllerTest test
```

**期望:**

- metadata event 匹配 active subscription 的 `notifyOn` 后创建 notification。
- Kafka publish 成功时 notification 标记发送。
- `notifyOn` 不匹配时不通知。
- inactive subscription 不通知。
- Kafka publish 失败时 notification 标记 `FAILED`。

### GOV-DRIFT-001 Drift 分析

**步骤:**

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=DriftControllerTest test
```

**期望:**

- 有 active subscription 但无运行态查询时产生 `DECLARED_UNUSED`。
- 有成功 query record 但无 active subscription 时产生 `UNDECLARED_USAGE`。
- 长期未刷新声明产生 `STALE_DECLARATION`。
- 重复 analyze 刷新已有 open drift，不重复创建。
- drift 列表按时间返回。

### UI-001 正式血缘图可见可操作

**入口:** `/metadata/lineage?source=formal`

**步骤:**

```powershell
cd frontend
npm run test:e2e:headed
```

**自动化动作:**

1. 打开正式血缘页面。
2. 搜索 `ads_cell_profile`。
3. 选择正式元数据资产。
4. 验证字段边数量为 `1`。
5. 点击字段血缘边。
6. 验证边详情展示 `dwd_cell_profile.rsrp_avg -> ads_cell_profile.coverage_score` 和转换表达式。

**期望:**

- 浏览器窗口可见。
- 页面不空白。
- 正式元数据模式默认可用。
- 字段级血缘图/列表和详情面板同步更新。

**已有自动化:** `frontend/tests/e2e/formal-lineage.acceptance.spec.ts`。

### UI-002 旧血缘模式兼容

**状态:** Manual / To Automate

**建议步骤:**

1. 打开 `/metadata/lineage?source=legacy&table=dws_cell_hourly`。
2. 切换到“旧表字段”。
3. 输入 `dws_cell_hourly` 并搜索。
4. 切换正向/反向。
5. 点击一条旧字段边。

**期望:**

- 旧 `/api/lineage` 数据仍能渲染。
- 边详情展示上游字段、下游字段和表达式。
- 切回正式元数据模式后不会残留旧边详情。

**建议自动化文件:** `frontend/tests/e2e/legacy-lineage.acceptance.spec.ts`。

### UI-003 元数据管理页面

**状态:** Manual / To Automate

**建议步骤:**

1. 打开 `/metadata`。
2. 搜索表名或字段名。
3. 选择一张表，检查详情、字段列表、layer、storage type。
4. 打开 YAML 预览。
5. 点击“查看血缘”，确认跳转到 `/metadata/lineage` 并携带表参数。

**期望:**

- 列表筛选、详情、字段表格、YAML drawer、血缘跳转可用。

### UI-004 Chat / NL 对话

**状态:** Manual / To Automate

**建议步骤:**

1. 从血缘页点击“用 NL 修改”。
2. 确认进入 `/chat?context=lineage&table=...`。
3. 输入 schema evolution 或 lineage 修改请求。
4. 验证 SSE 流式输出、结果面板和 dry-run 状态。

**期望:**

- chat session 创建成功。
- 上下文参数带入。
- SSE 不报错。

### UI-005 Pipeline 页面

**状态:** Manual / To Automate

**建议步骤:**

1. 打开 `/pipeline`。
2. 切换 forward/reverse。
3. 选择表。
4. 点击图中节点。

**期望:**

- DAG 正常渲染。
- reverse 模式边方向翻转。
- 节点选择和详情同步。

### UI-006 Schema Evolution 页面

**状态:** Manual / To Automate

**建议步骤:**

1. 打开 `/schema-evolution?table=dws_cell_hourly`。
2. 查看 timeline。
3. 点击某次变更。
4. 打开 YAML diff。
5. 点击血缘跳转。

**期望:**

- timeline、diff、血缘跳转可用。
- 长文本不溢出容器。

## 6. Docker API Smoke 用例

### DOCKER-GOV-001 容器化治理服务注册并查询正式血缘

**步骤:**

1. 启动 shared infra 和 governance server。
2. `POST /metadata/register` 注册 `dwd_cell_profile` 和 `ads_cell_profile`，带字段级 upstream mapping。
3. `GET /metadata?keyword=ads_cell_profile` 获取 `metadataId`。
4. `GET /metadata/{metadataId}/lineage?direction=up&depth=5`。

**期望:**

- register 返回 created/updated/unchanged item。
- lineage 返回 `lineageType=FIELD`。
- `fieldEdges[0].targetField=coverage_score`。

### DOCKER-UI-001 前端通过 Vite 代理访问治理服务

**步骤:**

```powershell
curl.exe -fsS "http://127.0.0.1:5173/rest/oss/inner/modelengineservice/v1/metadata?size=1"
```

**期望:**

- 响应包含 `items`、`page`、`size`、`total`。
- 不出现浏览器 CORS 错误。

## 7. 覆盖缺口与补齐建议

| 缺口 | 风险 | 建议新增自动化 |
| --- | --- | --- |
| 旧血缘 UI 模式未自动化 | 正式血缘改造可能破坏旧页面 | `legacy-lineage.acceptance.spec.ts` |
| 元数据管理 UI 未自动化 | 字段 CRUD/YAML drawer 可能回归 | `metadata-management.acceptance.spec.ts` |
| Chat UI 未自动化 | SSE 和上下文跳转可能只在 API 层通过 | `chat.acceptance.spec.ts` |
| Pipeline UI 未自动化 | G6 图交互可能受依赖升级影响 | `pipeline.acceptance.spec.ts` |
| Schema Evolution UI 未自动化 | timeline/diff 视觉回归难发现 | `schema-evolution.acceptance.spec.ts` |
| Docker 全链路 UI + governance 实库未自动化 | mocked E2E 不能覆盖真实服务数据差异 | 增加 `@real-governance` Playwright project |
| Kafka listener SDK 端到端未完全覆盖 | 通知消费方真实回调风险 | 增加 SDK listener integration test |
| StarRocks/Iceberg 自动建表属于设计但未落地 | SDK physical table check 需求未验收 | 落地后新增 SDK integration cases |

## 8. 发布前验收门禁

合入主干或发布前至少执行：

```powershell
git diff --check

cd frontend
npm run lint
npm run build
node --test src/components/graphShared/formalLineageGraphData.test.mjs
npm run test:e2e

cd ..\data-gov-platform
mvn test

cd ..
docker compose -f ..\shared-data-infra\compose.yaml --profile data-gov config
docker compose -f app-compose.yml config
docker compose -f app-compose.yml --profile governance config
```

如果涉及共享基础设施、Spark/Flink dry-run、Kafka 或 StarRocks 查询，还必须执行对应 `tests/infra` 和 `tests/sandbox -m infra`。
