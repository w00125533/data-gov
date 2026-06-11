# 数据治理 Spec 文档集

本文档集描述数据注册、发现、订阅、查询、元数据和血缘治理的一期设计。主文档拆分为多个专题文件，便于 API、数据模型、运行时机制和架构决策独立评审。

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [API 设计](api-spec.md) | 数据注册、数据发现、数据查询、数据订阅接口定义。 |
| [数据模型](data-model.md) | GaussDB 表定义、字段说明、枚举和关系模型。 |
| [运行时设计](runtime-design.md) | 启动快照同步、运行时修改/取消注册、订阅、查询、通知和 drift。 |
| [架构视图](architecture-views.md) | 用例视图、逻辑视图、数据模型视图、运行时序、技术视图、部署视图。 |
| [架构决策](decisions.md) | 关键技术决策与权衡分析。 |

## 当前核心口径

- 接口前缀统一使用 `/rest/oss/inner/modelengineservice/v1`。
- 接口资源统一使用 `metadata`，路径 ID 使用 `metadataId`。
- 业务稳定编码保留 `assetCode`。
- 服务启动时复用 `POST /rest/oss/inner/modelengineservice/v1/metadata/register` 提交微服务级完整元数据快照。
- `PATCH /metadata/{metadataId}` 和 `DELETE /metadata/{metadataId}` 只用于运行时动态变更。
- 订阅面向单个 `metadataId`，用于声明态和变化通知关注。
- 查询事实写入 `query_record`，用于证明真实运行态消费。
- 通知通过 Kafka 异步投递，由 Java SDK listener 消费并回调业务处理器。

## 基础设施约束

- 新增或修改 Docker Compose 基础设施前，必须先检查 `../shared-data-infra` 是否已有同类服务或 profile。
- 如果 shared infra 已定义 GaussDB、HDFS、Hive、Spark、YARN、Kafka、StarRocks、Prometheus、Grafana 等能力，不在本工程重复新增。
- 本工程本地只保留 backend、frontend 和应用数据卷等资源。
