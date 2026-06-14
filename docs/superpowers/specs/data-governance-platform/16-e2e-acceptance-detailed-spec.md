# 16. 端到端验收详细规格

本文恢复 2026-05-13 文档中的 Phase 1 到 Phase 3 验收信息，并扩展为目标态 Phase 0 到 Phase 7。每个阶段都必须有可执行命令、UI 可视化路径或明确的人工观察标准。

## 1. 验收环境

基础环境：

- Docker Desktop 可用。
- `../shared-data-infra` 存在并包含 data-gov profile。
- Java 17 和 Maven 可用。
- Node.js 和 frontend 依赖可用。
- Python 环境可运行 Agent、搜索和沙箱测试。
- Playwright Chromium 已安装。

基础配置检查：

```powershell
docker compose -f ..\shared-data-infra\compose.yaml --profile data-gov config
docker compose -f app-compose.yml config
docker compose -f app-compose.yml --profile governance config
```

通过标准：

- 三个命令退出码为 0。
- 本工程 compose 不重复定义 shared infra 已有服务。
- app compose 只保留应用服务和应用级卷。

## 2. Phase 0 文档统一验收

| ID | 用例 | 步骤 | 预期 |
| --- | --- | --- | --- |
| DOC-001 | 新文档入口存在 | 打开 `data-governance-platform/index.md`。 | 能看到权威口径、导航和状态。 |
| DOC-002 | 历史文档归档 | 检查 `archive/`。 | 5 月文档、6 月入口和 6 月子文档都在 archive。 |
| DOC-003 | 冲突口径明确 | 搜索 Spring Boot、GaussDB、X6、FastAPI、Neo4j。 | 正文目标态使用 Spring Boot/GaussDB/X6，迁移附录说明历史实现。 |
| DOC-004 | API 前缀一致 | 搜索正式 API 前缀和常见拼写错误。 | 只使用正确前缀 `/rest/oss/inner/modelengineservice/v1`。 |

## 3. Phase 1 治理核心验收

### 3.1 元数据注册

命令：

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=MetadataControllerTest#snapshotRegisterCreatesAndListsFormalMetadata test
```

预期：

- 创建 metadata。
- 创建字段。
- 创建 binding。
- 返回 metadataId。
- 列表可检索到 assetCode。

### 3.2 快照幂等

命令：

```powershell
mvn -pl data-gov-server -Dtest=MetadataControllerTest#repeatedSnapshotReturnsUnchangedWithoutIncrementingSchemaVersion test
```

预期：

- 重复快照返回 unchanged。
- 不重复创建 metadata。
- 不重复创建 active lineage。

### 3.3 快照软下线

命令：

```powershell
mvn -pl data-gov-server -Dtest=MetadataControllerTest#fullSnapshotMarksMissingScopedMetadataRemovedBySnapshot test
```

预期：

- 同一 producer scope 中缺失的 metadata 标记为 `REMOVED_BY_SNAPSHOT`。
- 其他 producer scope 不受影响。

### 3.4 字段级血缘

命令：

```powershell
mvn -pl data-gov-server -Dtest=MetadataControllerTest#formalMetadataLineageReturnsNodesEdgesAndFieldEdgesByMetadataId test
```

预期：

- 响应包含 nodes。
- 响应包含 edges。
- 响应包含 fieldEdges。
- `sourceField` 和 `targetField` 正确。

## 4. Phase 2 旧能力迁移验收

| ID | 用例 | 步骤 | 预期 |
| --- | --- | --- | --- |
| MIG-001 | 旧 `/api/lineage` 对齐正式 lineage | 用同一 RNO 样例资产分别查询旧 API 和正式 API。 | 正式 API 能表达旧 API 的字段级边。 |
| MIG-002 | Neo4j 血缘迁移 | 将旧 `DERIVES_FROM` 样例映射为 `lineage_edge`。 | Spring Boot lineage API 返回等价 fieldEdges。 |
| MIG-003 | Python Agent 不直写主库 | 触发 schema evolve。 | 最终写入通过 Spring Boot API 完成。 |
| MIG-004 | 前端治理页默认走 `/rest` | 浏览器打开 metadata 和 lineage。 | Network 请求使用 `/rest/oss/inner/modelengineservice/v1`。 |

## 5. Phase 3 UI 基础闭环验收

### 5.1 Metadata 页面

路径：

```text
http://127.0.0.1:5173/metadata
```

步骤：

1. 打开页面。
2. 输入 `ads_cell_profile`。
3. 选择结果。
4. 查看字段表。
5. 打开 YAML 预览。
6. 点击查看血缘。

预期：

- 页面非空。
- 无框架错误 overlay。
- console 无相关 error/warn。
- 字段表包含 `coverage_score`。
- 跳转到 `/metadata/lineage` 并携带 metadataId。

### 5.2 Lineage 页面

步骤：

1. 打开 `/metadata/lineage?source=formal`。
2. 搜索 `ads_cell_profile`。
3. 选择资产。
4. 点击字段级边。

预期：

- 字段级血缘图可见。
- 字段边数量正确。
- 边详情显示 `dwd_cell_profile.rsrp_avg -> ads_cell_profile.coverage_score`。
- 表达式显示 `case when rsrp_avg >= -95 then 100 else 60 end`。

### 5.3 Pipeline 页面

步骤：

1. 打开 `/pipeline`。
2. 选择正向模式。
3. 搜索或选择 `dws_cell_hourly`。
4. 切换反向模式。
5. 点击节点。

预期：

- 正向 DAG 显示 ODS 到 EVAL 链路。
- 反向图显示目标表到约束和生成器。
- 节点详情同步更新。

### 5.4 Schema Evolution 页面

步骤：

1. 打开 `/schema-evolution?table=dwd_session_qos`。
2. 查看时间线。
3. 点击变更卡片。
4. 打开 diff。
5. 点击查看血缘。

预期：

- timeline 可见。
- diff 显示旧值和新值。
- 跳转血缘带目标表上下文。

## 6. Phase 4 X6 画布验收

### 6.1 X6 血缘画布

步骤：

1. 加载 `ads_cell_profile` 上游血缘。
2. 验证 X6 canvas 存在。
3. 验证节点内部字段端口可见。
4. 点击 `rsrp_avg -> coverage_score` 边。
5. 缩放画布。
6. 拖动节点。
7. 打开 mini map。

预期：

- 画布非空。
- 字段级端口可见。
- 边详情正确。
- 缩放和拖动不报错。
- mini map 与主画布同步。

### 6.2 X6 拖拽建边

步骤：

1. 从上游字段 port 拖到下游字段 port。
2. 填写 expression。
3. 保存。

预期：

- UI 创建 draft edge。
- Spring Boot 校验通过。
- 保存后刷新图。
- API 返回新增 fieldEdge。

### 6.3 X6 Pipeline

步骤：

1. 打开 `/pipeline`。
2. 验证正向 X6 DAG。
3. 切换反向。
4. 调整约束节点。

预期：

- 正向和反向都使用 X6。
- 节点可选中。
- 约束节点状态更新。

## 7. Phase 5 Agent 全链路验收

### 7.1 正向 ETL

用户输入：

```text
用 ods_ue_signal 按 cell_id 计算每小时平均 RSRP 和 SINR，写入 dws_cell_hourly。
```

预期：

- intent 为 `forward_etl`。
- schema_lookup 命中 `ods_ue_signal` 和 `dws_cell_hourly`。
- 生成 Spark SQL。
- dry-run 成功。
- previewRows 至少 1 行。
- lineage preview 包含 `ods_ue_signal.rsrp -> dws_cell_hourly.avg_rsrp`。

### 7.2 反向合成

用户输入：

```text
给 eval_user_score 生成 10 行测试数据，覆盖优秀、良好、较差三档。
```

预期：

- intent 为 `reverse_synth`。
- 展示约束反推面板。
- 三档 qoe_score 范围可见。
- 生成代码。
- dry-run 或 sandbox 写入成功。
- 结果图表显示三档数据。

### 7.3 元数据演进

用户输入：

```text
给 dwd_session_qos 增加 jitter 字段，用 latency 的标准差计算。
```

预期：

- intent 为 `schema_evolve`。
- 展示新增字段 diff。
- 展示上游字段 `latency`。
- 用户确认后调用 Spring Boot API。
- `/schema-evolution` 可看到变更记录。

## 8. Phase 6 治理后台增强验收

| ID | 用例 | 步骤 | 预期 |
| --- | --- | --- | --- |
| GOV-UI-001 | 订阅可见 | 打开 metadata 详情订阅 tab。 | 看到 active subscriptions。 |
| GOV-UI-002 | 查询记录可见 | 执行 API query 后查看查询记录。 | query_record 显示 consumer、字段、行数。 |
| GOV-UI-003 | 通知状态可见 | PATCH metadata 触发事件。 | notification 显示 SENT 或 FAILED。 |
| GOV-UI-004 | Drift 可见 | 构造未声明使用。 | drift 列表出现 UNDECLARED_USAGE。 |

## 9. Phase 7 高级维护验收

| ID | 用例 | 步骤 | 预期 |
| --- | --- | --- | --- |
| ADV-001 | 字段表达式 Monaco 编辑 | 右键字段编辑表达式。 | Monaco 打开，保存后 API 更新。 |
| ADV-002 | 删除字段影响分析 | 删除 `ods_ue_signal.rsrp`。 | 阻断并展示下游影响。 |
| ADV-003 | YAML diff | 修改字段后打开 YAML diff。 | 显示旧 YAML 和新 YAML 差异。 |
| ADV-004 | 从血缘图新建下游表 | 右键节点选择新建下游表。 | 打开表单并预填上游。 |

## 10. 可视化执行命令

常规 E2E：

```powershell
cd frontend
npm run test:e2e
```

可视化 E2E：

```powershell
cd frontend
npm run test:e2e:headed
```

慢速观察：

```powershell
$env:PW_SLOW_MO="1200"
npm run test:e2e:headed
```

真实 Docker E2E 前置：

```powershell
docker compose -f ..\shared-data-infra\compose.yaml --profile data-gov up -d
docker compose -f app-compose.yml --profile governance up -d --build governance-server
curl.exe -fsS http://localhost:8080/actuator/health
```

## 11. 发布门禁

```powershell
git diff --check

cd frontend
npm run lint
npm run build
npm run test:e2e

cd ..\data-gov-platform
mvn test

cd ..
docker compose -f ..\shared-data-infra\compose.yaml --profile data-gov config
docker compose -f app-compose.yml config
docker compose -f app-compose.yml --profile governance config
```

若涉及 Kafka、StarRocks、Spark/Flink 或 shared infra，必须增加对应集成验收。
