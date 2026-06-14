# 09. 验收用例集

本文件定义目标态验收分层。现有详细命令集可继续参考 `../../../governance-acceptance-test-suite.md`，后续应逐步迁移或同步到本文件。

## 1. Contract / API 验收

| ID | 场景 | 断言 |
| --- | --- | --- |
| API-META-001 | 启动快照注册 | created、updated、unchanged、removed by snapshot 行为正确。 |
| API-META-002 | 元数据发现 | 列表、详情、分页、过滤、binding 和 schema 正确。 |
| API-LIN-001 | 字段级血缘写入 | `fieldMappings` 正确持久化为 FIELD lineage。 |
| API-LIN-002 | 字段级血缘查询 | `nodes`、`edges`、`fieldEdges` 响应完整。 |
| API-SUB-001 | 订阅生命周期 | 创建、查询、取消和缺失 metadata 错误正确。 |
| API-QRY-001 | 产品 API 查询 | subscription 校验、查询记录和错误处理正确。 |
| API-QRY-002 | SQL Gateway | 只读 SQL、资产改写、join/CTE 和非法对象拒绝正确。 |
| API-EVT-001 | 事件通知 | notifyOn 匹配、Kafka publish 和失败状态正确。 |
| API-DRIFT-001 | Drift 分析 | declared unused、undeclared usage、stale declaration 正确。 |

## 2. Runtime / Docker 验收

| ID | 场景 | 断言 |
| --- | --- | --- |
| INF-001 | shared infra compose config | `../shared-data-infra` profile 合法。 |
| INF-002 | app compose config | 本工程不重复定义共享基础设施。 |
| DOCKER-GOV-001 | governance-server health | `/actuator/health` 返回 `UP`。 |
| DOCKER-API-001 | 真实注册和血缘查询 | 注册真实资产后，正式 API 返回字段级血缘。 |
| DOCKER-UI-001 | frontend proxy | `/rest/...` 通过 Vite proxy 访问 governance-server。 |

## 3. UI / E2E 验收

| ID | 页面 | 场景 |
| --- | --- | --- |
| UI-META-001 | `/metadata` | 搜索、过滤、查看详情、字段表、YAML 预览、跳转血缘。 |
| UI-LIN-001 | `/metadata/lineage` | 正式血缘搜索、加载字段边、点击边详情。 |
| UI-LIN-002 | `/metadata/lineage` | X6 字段端口、缩放、拖拽、mini map 和边选择。 |
| UI-PIPE-001 | `/pipeline` | 正向 DAG 渲染、节点选择、上下游突出。 |
| UI-PIPE-002 | `/pipeline` | 反向合成链路渲染、约束节点和跳转 Chat。 |
| UI-CHAT-001 | `/chat` | SSE 输出、意图 badge、代码卡片和 dry-run。 |
| UI-CHAT-002 | `/chat` | 从 lineage 或 pipeline 带上下文跳转。 |
| UI-SCHEMA-001 | `/schema-evolution` | timeline、diff、YAML diff、跳转血缘。 |
| UI-HEALTH-001 | `/health` | 应用服务和 shared infra 健康状态展示。 |

## 4. 真实端到端验收

| ID | 场景 | 断言 |
| --- | --- | --- |
| E2E-REAL-001 | 注册真实 RNO metadata | Spring Boot API 写入 GaussDB，UI 可搜索到。 |
| E2E-REAL-002 | 展示真实字段级血缘 | UI 加载真实 lineage，字段边详情正确。 |
| E2E-REAL-003 | 订阅后查询 | 创建订阅后 API 查询成功并写入 query_record。 |
| E2E-REAL-004 | 元数据变更通知 | PATCH metadata 后生成 event 和 notification。 |
| E2E-REAL-005 | Drift 分析 | 构造声明态和运行态差异后 UI/API 可查。 |

## 5. 发布门禁

每次涉及治理主线或 UI 的发布至少执行：

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

如果修改涉及真实基础设施、Spark/Flink dry-run、Kafka 或 StarRocks，还必须执行对应 infra 和 sandbox 集成验收。
