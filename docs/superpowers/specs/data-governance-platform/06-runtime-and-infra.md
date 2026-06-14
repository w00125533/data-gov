# 06. 运行时与基础设施

## 1. 启动快照同步

Java SDK 在服务启动时组装完整元数据快照，并调用：

```http
POST /rest/oss/inner/modelengineservice/v1/metadata/register
```

服务端按 `serviceName + environment` 作用域重建声明态。该流程必须幂等，重复提交同一快照不产生重复元数据和重复 active lineage。

## 2. 运行时动态变更

运行期管理、应急修复或 Agent 确认后的 schema/lineage 变更通过：

```http
PATCH /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}
DELETE /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}
```

运行时变更应写入 `metadata_event`，并触发订阅通知匹配。

## 3. 通知运行时

元数据事件写入后，服务端匹配 active subscriptions：

1. 读取事件的 `metadataId` 和 `eventType`。
2. 找到 `notifyOn` 包含该事件类型的订阅。
3. 写入 `subscription_notification`。
4. 异步发布 Kafka 消息到 `data-gov.subscription-notifications`。
5. 消费方 SDK listener 回调业务处理器。

不提供通知拉取、通知确认和业务回执接口。

## 4. 查询运行时

产品 API 和 SQL Gateway 优先通过 StarRocks 执行。StarRocks 作为 Hive、Iceberg、GaussDB 等数据源的统一查询入口。

运行时约束：

- 只读查询。
- 查询前校验 metadata 状态和 queryable。
- 查询后写入 `query_record`。
- Kafka topic 不进入统一查询。

## 5. Docker 与 shared infra

基础设施复用 `../shared-data-infra`。本工程不得重复定义以下服务：

- HDFS
- Hive Metastore / HiveServer2
- Spark / YARN
- Kafka / ZooKeeper
- StarRocks
- Prometheus / Grafana
- Neo4j
- GaussDB

本工程 compose 只保留：

- Spring Boot governance-server
- Python backend / Agent service
- frontend
- Chroma 和应用级数据卷

基础设施变更后至少执行：

```powershell
docker compose -f ..\shared-data-infra\compose.yaml --profile data-gov config
docker compose -f app-compose.yml config
```

如果变更涉及 governance profile，还应执行：

```powershell
docker compose -f app-compose.yml --profile governance config
```

## 6. 健康检查

治理平台应具备以下健康检查：

- Spring Boot `/actuator/health`。
- Python Agent service health。
- GaussDB 连接。
- Kafka topic 可达。
- StarRocks 查询入口可达。
- Hive、Spark/YARN 和 HDFS 可达。
- Chroma 可达。

Frontend `/health` 页面展示这些状态，并区分应用服务和 shared infra。
