# 数据产品治理、订阅、统一查询与血缘设计

本文是数据治理 Spec 文档集的主入口。详细设计拆分到 `docs/superpowers/specs/data-governance/` 目录，便于 API、数据模型、运行时机制、架构视图和技术决策独立维护。

## 1. 背景与目标

在现有 `data-gov` 项目基础上，新增数据注册、发现、订阅、消费、元数据查询和血缘查询能力。现有技术栈包括 Hive、StarRocks、GaussDB、Iceberg、Flink、Spark SQL 和 Kafka。

目标：

- 统一注册散落在微服务、Flink、Spark 和数据平台中的数据集元数据。
- 支持数据发现、字段 schema、物理绑定和血缘查询。
- 提供产品 API 查询和 SQL Gateway 查询。
- 用订阅表达使用意图和变化通知关注。
- 用查询记录表达真实运行态消费。
- 通过 Kafka 将数据变化通知异步投递给 Java SDK listener。

## 2. 数据治理 Spec 文档集

本文档集描述数据注册、发现、订阅、查询、元数据和血缘治理的一期设计。专题文档如下：

| 文档 | 内容 |
| --- | --- |
| [API 设计](data-governance/api-spec.md) | 数据注册、数据发现、数据查询、数据订阅接口定义。 |
| [数据模型](data-governance/data-model.md) | GaussDB 表定义、字段说明、枚举和关系模型。 |
| [运行时设计](data-governance/runtime-design.md) | 启动快照同步、运行时修改/取消注册、订阅、查询、通知和 drift。 |
| [架构视图](data-governance/architecture-views.md) | 用例视图、逻辑视图、数据模型视图、运行时序、技术视图、部署视图。 |
| [架构决策](data-governance/decisions.md) | 关键技术决策与权衡分析。 |

## 3. 当前核心设计

- 接口前缀统一使用 `/rest/oss/inner/modelengineservice/v1`。
- 接口资源统一使用 `metadata`，路径 ID 使用 `metadataId`。
- 业务稳定编码保留 `assetCode`。
- 服务启动时复用 `POST /rest/oss/inner/modelengineservice/v1/metadata/register` 提交微服务级完整元数据快照。
- 服务端按 `producer.serviceName + producer.environment` 作用域重建该微服务元数据声明态。
- `PATCH /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}` 和 `DELETE /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}` 只用于运行时动态变更。
- 订阅接口面向单个 `metadataId`，用于声明态和变化通知关注。
- 查询事实进入 `query_record`，用于回答谁实际使用了什么数据。
- 元数据、血缘、订阅、事件、通知、查询记录和 drift 主库存储在 GaussDB。
- 统一查询优先通过 StarRocks 执行，Kafka topic 不进入统一查询。

## 4. 实施阶段

| 阶段 | 内容 |
| --- | --- |
| 阶段 1 | Spring Boot 治理服务骨架、GaussDB 接入、基础 Flyway 迁移。 |
| 阶段 2 | 元数据、字段、物理绑定、血缘的注册和发现。 |
| 阶段 3 | Java SDK 启动快照同步、订阅声明、Kafka listener。 |
| 阶段 4 | 产品 API 查询、SQL Gateway 查询、StarRocks catalog 验证。 |
| 阶段 5 | 元数据事件、订阅通知、drift 分析和治理后台能力。 |

## 5. 验收标准

- 微服务启动后可通过 Java SDK 提交完整元数据快照。
- 已注册元数据可通过 `/rest/oss/inner/modelengineservice/v1/metadata` 检索和查询详情。
- 字段 schema、物理绑定和血缘关系可查询。
- 产品 API 可通过 `metadataId` 查询表型数据集。
- SQL Gateway 可执行只读查询，并拒绝未注册对象和 Kafka topic。
- 数据变化事件可匹配订阅并发送 Kafka 通知。
- Java SDK 可监听通知 topic 并回调业务处理器。
- 查询记录可支撑声明态和运行态 drift 分析。

## 6. 基础设施约束

- 新增或修改 Docker Compose 基础设施前，必须先检查 `../shared-data-infra` 是否已经定义同类服务或 profile。
- 如果 `../shared-data-infra` 已定义 HDFS、Hive Metastore、HiveServer2、Spark、YARN、Kafka、ZooKeeper、StarRocks、Prometheus、Grafana 等能力，不在本工程重复新增。
- 本工程本地只保留 backend、frontend、Chroma 数据卷等应用资源。
- 修改基础设施后，至少运行 `docker compose -f ../shared-data-infra/compose.yaml --profile data-gov config` 和 `docker compose -f app-compose.yml config`。
