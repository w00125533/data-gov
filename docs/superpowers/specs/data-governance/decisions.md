# 数据治理架构决策与权衡

本文记录数据治理平台第一期核心架构选择和权衡分析。

## 1. 使用 Java Spring Boot 实现治理主服务

决策：数据治理主服务采用 Java Spring Boot。

原因：

- 主要接入方是 Java 微服务、Flink Java 作业、Spark Java/Scala 作业。
- 服务端 DTO、SDK DTO、枚举和错误码可以通过多模块工程共享。
- Spring Boot 更适合承载企业内部平台服务、JDBC、多数据源、Flyway、Actuator 和治理后台 API。

代价：

- 仓库会经历 Java 服务和既有后端并存阶段。
- 前端和旧 API 需要迁移或兼容。

## 2. 元数据、血缘和订阅主库存储在 GaussDB

决策：元数据、血缘、订阅、查询记录、事件和 drift 主库存储在 GaussDB。

原因：

- 需求已经从纯图查询扩展到元数据、订阅、查询审计、作业声明、事件通知和 drift。
- 关系模型更适合事务、审计、分页查询和后台治理。
- GaussDB 更容易和企业业务系统、报表、审计和平台服务集成。

代价：

- 深层血缘遍历能力弱于图数据库，需要通过递归查询或应用层遍历实现。

## 3. API 前缀统一使用 `/rest/oss/inner/modelengineservice/v1`

决策：所有产品接口统一放在 `/rest/oss/inner/modelengineservice/v1` 前缀下。

原因：

- 符合内部服务 API 命名规范。
- 便于网关、鉴权、路由和版本治理统一处理。
- 清理早期 `/api` 和无 `/rest` 前缀的临时口径。

影响：

- SDK、前端、测试用例和文档必须统一使用新前缀。

## 4. 接口资源命名从 `assets` 收敛为 `metadata`

决策：接口路径使用 `metadata`，路径 ID 使用 `metadataId`。业务字段仍保留 `assetCode`、`assetName`、`assetType`。

原因：

- 当前能力重点是元数据治理、血缘、订阅和查询，不只是资产目录。
- `metadataId` 更符合接口资源语义。
- `assetCode` 仍作为业务稳定编码，避免影响业务侧理解。

影响：

- 数据库主键使用 `metadata_id`。
- API 路径使用 `/metadata/{metadataId}`。
- 血缘边使用 `source_metadata_id`、`target_metadata_id`。

## 5. 服务启动时复用元数据注册接口做微服务级完整快照同步

决策：不新增 `/metadata/services/{serviceName}/sync` 接口，直接复用：

```http
POST /rest/oss/inner/modelengineservice/v1/metadata/register
```

服务启动时，SDK 提交当前微服务完整元数据快照。服务端按 `producer.serviceName + producer.environment` 作用域重建该微服务的元数据声明态。

原因：

- 启动时逐个注册、逐个修改、逐个删除容易导致状态乱序和腐烂。
- 微服务发布态天然知道“当前版本完整拥有的元数据集合”。
- 快照同步能自然识别新增、更新和删除，减少人为维护变更调用。
- 复用现有注册接口可减少 API 面。

处理规则：

- 快照中存在、库中不存在：新增。
- 快照中存在、库中存在且声明变化：更新。
- 快照中存在、库中存在且声明未变：刷新同步时间。
- 快照中不存在、库中存在且归属该微服务：软下线为 `REMOVED_BY_SNAPSHOT`。
- 不归属该微服务的数据不处理。

代价：

- 注册接口语义比单条 upsert 更强，需要服务端明确支持微服务作用域快照。
- SDK 必须保证启动时提交的是完整快照。

## 6. 单项修改和取消注册只用于运行时动态变更

决策：

```http
PATCH  /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}
DELETE /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}
```

只用于运行时动态修改和运行时动态取消注册。

原因：

- 启动态已由完整快照处理新增、更新和删除。
- 运行时接口保留给管理端、应急下线、动态配置和运行期物理变化。
- 避免发布态变更后还要人为生成一组 PATCH / DELETE 调用。

## 7. StarRocks 作为统一 SQL 和基础联邦查询入口

决策：统一查询优先通过 StarRocks 执行，暂不引入 Trino。

原因：

- 现有技术栈已经包含 StarRocks。
- StarRocks 支持 Hive、Iceberg、GaussDB 等 catalog，可覆盖第一期基础跨源 join。
- 减少引入新查询引擎的部署和运维成本。

代价：

- StarRocks 联邦能力和方言覆盖需要通过实际数据源验证。
- 复杂跨源优化能力可能弱于专用联邦查询引擎。

## 8. 产品 API 优先，SQL Gateway 补充

决策：上层消费者优先使用产品 API 查询，SQL Gateway 作为补充能力。

原因：

- 产品 API 更适合微服务稳定调用，能控制字段、过滤、limit、订阅上下文和审计。
- SQL Gateway 更适合分析、探索和少量跨源 join。

代价：

- 产品 API 查询表达能力弱于 SQL。
- 需要维护 API 查询 DSL 到 SQL 的转换。

## 9. Kafka 进入元数据目录和通知体系，但不进入统一查询

决策：Kafka topic 可注册为 `TOPIC` 类型元数据，参与发现、订阅、通知和血缘，但 `queryable=false`。

原因：

- Kafka 在业务链路中是重要数据对象，应被发现和订阅。
- Kafka 不适合作为普通表进入 API / SQL 查询。
- 下游物化到 Hive、Iceberg、StarRocks 或 GaussDB 后，再以表型元数据进入查询体系。

## 10. 订阅收窄为使用意图和变化通知关注

决策：订阅不作为真实消费事实，不等同核心血缘，也不做审批流。

订阅表达：

```text
使用意图声明 + 变化通知关注
```

原因：

- 如果订阅只是人工登记“谁用什么数据”，长期容易腐烂。
- 订阅的独特价值在于数据变化后的影响触达。
- 真实使用应由 `query_record` 等运行态事实证明。

## 11. 第一阶段只做 Java SDK

决策：第一阶段只提供 Java SDK，不做 Python SDK / PySpark SDK。

原因：

- 使用方主要是 Java 微服务、Flink Java 作业、Spark Java/Scala 作业。
- Java SDK 可同时封装启动快照同步、订阅声明、产品 API 查询和 Kafka listener。
- 先缩小范围，避免多语言 SDK 模型过早发散。

## 12. 简化第一期关系模型

决策：

- `subscription_field` 合并到 `subscription.declared_fields`。
- `query_record_asset` 合并到 `query_record.referenced_asset_codes`。
- `consumer_instance` 合并到 `consumer`。
- 第一阶段不建 `job_run_record` 和 `job_io_record`。

原因：

- 第一阶段重点验证元数据、订阅、查询和通知闭环。
- 减少表数量，降低实现和迁移成本。

代价：

- 多实例在线状态和作业运行生命周期观测能力较弱。
- 后续如需强运行态观测，可再扩展独立事实表。

## 13. 查询事实和作业声明分离

决策：微服务产品 API 和 SQL Gateway 查询进入 `query_record`；Flink/Spark 作业第一期只进入 `consumer_job` 和订阅声明，不建运行生命周期记录。

原因：

- 查询记录是强运行态事实。
- Flink/Spark 作业生命周期复杂，第一期先保留声明态和输入输出声明。

## 14. 事件通知使用 Kafka 异步投递

决策：第一期通知通过 Kafka topic 异步发送，由 Java SDK listener 消费并回调业务代码。

不做：

- 通知 API 拉取
- 通知确认接口
- 邮件、IM、Webhook
- 业务处理回执

原因：

- 通知是数据变化触达，不应同步阻塞元数据修改流程。
- Kafka 更适合微服务、Flink、Spark 统一接入。
- SDK listener 可隐藏 Kafka 消费细节。

代价：

- 需要依赖 Kafka topic、consumer group 和 offset 语义。
- 业务处理成功与否由消费方自行记录。
