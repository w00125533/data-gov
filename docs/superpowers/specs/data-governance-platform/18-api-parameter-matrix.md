# 18. API 参数矩阵

本文展开正式 API 的请求参数、响应字段、校验规则和 DTO 口径。所有路径均以 `/rest/oss/inner/modelengineservice/v1` 为前缀。

## 1. 注册请求参数

| 参数 | 类型 | 必选 | 说明 | 校验 |
| --- | --- | --- | --- | --- |
| `producer` | object | 是 | 注册方信息。 | 非空。 |
| `producer.serviceName` | string | 是 | 服务、作业或应用名。 | 1 到 128 字符。 |
| `producer.serviceType` | string | 是 | 注册方类型。 | `MICROSERVICE`、`FLINK`、`SPARK`、`MANUAL`。 |
| `producer.owner` | string | 是 | 注册方负责人。 | 1 到 128 字符。 |
| `producer.environment` | string | 是 | 环境。 | 建议 local、dev、test、staging、prod。 |
| `producer.instanceId` | string | 否 | 运行实例。 | 0 到 256 字符。 |
| `syncMode` | string | 是 | 同步模式。 | 当前固定 `FULL`。 |
| `declarationHash` | string | 否 | 声明 hash。 | 建议 `sha256:<hex>`。 |
| `metadataList` | array | 是 | 完整元数据快照。 | 至少 1 项。 |
| `metadataList[].assetCode` | string | 是 | 业务稳定编码。 | 1 到 128 字符，建议小写下划线。 |
| `metadataList[].assetName` | string | 是 | 展示名称。 | 1 到 256 字符。 |
| `metadataList[].metadataType` | string | 是 | 元数据类型。 | `TABLE`、`VIEW`、`TOPIC`。 |
| `metadataList[].domain` | string | 是 | 业务域。 | 1 到 128 字符。 |
| `metadataList[].owner` | string | 是 | 负责人。 | 1 到 128 字符。 |
| `metadataList[].description` | string | 否 | 描述。 | 0 到 1024 字符。 |
| `metadataList[].queryable` | boolean | 是 | 是否允许查询。 | Kafka/TOPIC 通常为 false。 |
| `metadataList[].fields` | array | 是 | 字段列表。 | TABLE/VIEW 至少 1 项。 |
| `metadataList[].fields[].fieldName` | string | 是 | 字段名。 | 1 到 128 字符，同 metadata 内唯一。 |
| `metadataList[].fields[].fieldType` | string | 是 | 字段类型。 | 非空，保留源系统类型。 |
| `metadataList[].fields[].nullable` | boolean | 是 | 是否可空。 | true 或 false。 |
| `metadataList[].fields[].description` | string | 否 | 字段描述。 | 0 到 512 字符。 |
| `metadataList[].binding` | object | 是 | 物理绑定。 | 非空。 |
| `metadataList[].binding.sourceType` | string | 是 | 数据源类型。 | `HIVE`、`STARROCKS`、`GAUSSDB`、`ICEBERG`、`KAFKA`。 |
| `metadataList[].binding.catalog` | string | 否 | catalog。 | 0 到 128 字符。 |
| `metadataList[].binding.database` | string | 否 | database/schema。 | 0 到 128 字符。 |
| `metadataList[].binding.table` | string | 是 | 物理表、视图或 topic。 | 1 到 256 字符。 |
| `metadataList[].binding.properties` | object | 否 | 扩展属性。 | JSON object。 |
| `metadataList[].lineage` | object | 否 | 血缘声明。 | 可为空。 |
| `metadataList[].lineage.upstreams` | array | 否 | 上游列表。 | 可为空。 |
| `metadataList[].lineage.downstreams` | array | 否 | 下游列表。 | 可为空。 |
| `metadataList[].lineage.upstreams[].assetCode` | string | 条件 | 上游资产编码。 | 有 upstream 时必填。 |
| `metadataList[].lineage.upstreams[].lineageType` | string | 条件 | 血缘粒度。 | `TABLE`、`FIELD`。 |
| `metadataList[].lineage.upstreams[].transformType` | string | 否 | 转换类型。 | `DIRECT`、`SQL`、`JOB`、`MANUAL`。 |
| `metadataList[].lineage.upstreams[].expression` | string | 否 | 表达式或作业标识。 | 0 到 4096 字符。 |
| `metadataList[].lineage.upstreams[].fieldMappings` | array | 否 | 字段映射。 | FIELD 血缘建议必填。 |
| `metadataList[].lineage.upstreams[].fieldMappings[].sourceField` | string | 条件 | 上游字段。 | 有 mapping 时必填。 |
| `metadataList[].lineage.upstreams[].fieldMappings[].targetField` | string | 条件 | 目标字段。 | 必须存在于当前 fields。 |
| `metadataList[].lineage.upstreams[].fieldMappings[].expression` | string | 否 | 字段转换表达式。 | 0 到 1024 字符。 |

## 2. 注册响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `syncScope.serviceName` | string | 同步作用域服务名。 |
| `syncScope.environment` | string | 同步作用域环境。 |
| `createdCount` | integer | 新增数量。 |
| `updatedCount` | integer | 更新数量。 |
| `unchangedCount` | integer | 未变化数量。 |
| `removedBySnapshotCount` | integer | 快照缺失软下线数量。 |
| `items[].metadataId` | string | 生成或解析到的 metadataId。 |
| `items[].assetCode` | string | assetCode。 |
| `items[].status` | string | `REGISTERED`、`UPDATED`、`UNCHANGED`、`REMOVED_BY_SNAPSHOT`。 |
| `syncedAt` | datetime | 同步时间。 |

## 3. PATCH 参数

| 参数 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| `path.metadataId` | string | 是 | 目标 metadata。 |
| `assetName` | string | 否 | 新展示名。 |
| `description` | string | 否 | 新描述。 |
| `owner` | string | 否 | 新负责人。 |
| `domain` | string | 否 | 新业务域。 |
| `queryable` | boolean | 否 | 查询开关。 |
| `fields` | array | 否 | 字段列表或字段 upsert 集合。 |
| `binding` | object | 否 | 物理绑定局部更新。 |
| `lineage` | object | 否 | 血缘声明更新。 |
| `operator` | string | 否 | 操作人。 |
| `reason` | string | 否 | 修改原因。 |

PATCH 响应：

| 字段 | 说明 |
| --- | --- |
| `metadataId` | 目标 ID。 |
| `assetCode` | 稳定编码。 |
| `status` | `UPDATED`。 |
| `updatedAt` | 更新时间。 |
| `eventId` | 可选，生成的 metadata_event。 |

## 4. DELETE 参数

| 参数 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| `path.metadataId` | string | 是 | 目标 metadata。 |
| `reason` | string | 是 | 注销原因。 |
| `operator` | string | 是 | 操作人。 |

DELETE 响应：

| 字段 | 说明 |
| --- | --- |
| `metadataId` | 目标 ID。 |
| `assetCode` | 稳定编码。 |
| `status` | `UNREGISTERED`。 |
| `unregisteredAt` | 注销时间。 |
| `eventId` | 元数据事件 ID。 |

## 5. Metadata 列表参数

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `keyword` | string | 空 | 搜索编码、名称、描述。 |
| `domain` | string | 空 | 业务域过滤。 |
| `metadataType` | string | 空 | TABLE、VIEW、TOPIC。 |
| `sourceType` | string | 空 | HIVE、STARROCKS 等。 |
| `owner` | string | 空 | 负责人。 |
| `status` | string | ACTIVE | 状态。 |
| `page` | integer | 1 | 页码。 |
| `size` | integer | 20 | 每页数量，1 到 100。 |

列表响应：

| 字段 | 说明 |
| --- | --- |
| `items[]` | 元数据摘要。 |
| `items[].metadataId` | 资源 ID。 |
| `items[].assetCode` | 业务编码。 |
| `items[].assetName` | 名称。 |
| `items[].metadataType` | 类型。 |
| `items[].domain` | 领域。 |
| `items[].owner` | 负责人。 |
| `items[].queryable` | 查询开关。 |
| `items[].sourceType` | 可选，方便 UI 展示。 |
| `page` | 当前页。 |
| `size` | 每页大小。 |
| `total` | 总数。 |

## 6. Metadata 详情响应

| 字段 | 说明 |
| --- | --- |
| `metadataId` | 资源 ID。 |
| `assetCode` | 业务编码。 |
| `assetName` | 名称。 |
| `metadataType` | TABLE、VIEW、TOPIC。 |
| `domain` | 业务域。 |
| `owner` | 负责人。 |
| `description` | 描述。 |
| `queryable` | 查询开关。 |
| `schema[]` | 字段 schema。 |
| `schema[].fieldName` | 字段名。 |
| `schema[].fieldType` | 字段类型。 |
| `schema[].nullable` | 是否可空。 |
| `schema[].description` | 字段描述。 |
| `schema[].ordinal` | 顺序。 |
| `binding` | 物理绑定。 |
| `binding.sourceType` | 来源类型。 |
| `binding.catalog` | catalog。 |
| `binding.database` | database/schema。 |
| `binding.table` | 表或 topic。 |
| `binding.qualifiedName` | 完整物理名。 |
| `binding.properties` | 扩展属性。 |
| `createdAt` | 创建时间。 |
| `updatedAt` | 更新时间。 |

## 7. Lineage 参数和响应

查询参数：

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `direction` | string | `down` | `up` 或 `down`。 |
| `depth` | integer | 3 | 1 到 10。 |
| `includeFields` | boolean | true | 是否包含字段级边。 |

响应节点：

| 字段 | 说明 |
| --- | --- |
| `metadataId` | 节点 ID。 |
| `assetCode` | 业务编码。 |
| `assetName` | 名称。 |
| `metadataType` | 类型。 |
| `sourceType` | 可选，UI 展示。 |
| `layer` | 可选，RNO 分层。 |

响应边：

| 字段 | 说明 |
| --- | --- |
| `sourceMetadataId` | 源 metadata。 |
| `sourceAssetCode` | 源编码。 |
| `targetMetadataId` | 目标 metadata。 |
| `targetAssetCode` | 目标编码。 |
| `lineageType` | TABLE 或 FIELD。 |
| `transformType` | DIRECT、SQL、JOB、MANUAL。 |
| `direction` | 查询方向。 |
| `expression` | 表达式或作业。 |

字段级边：

| 字段 | 说明 |
| --- | --- |
| `sourceField` | 源字段。 |
| `targetField` | 目标字段。 |
| `expression` | 字段转换表达式。 |

## 8. API Query 参数

| 参数 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| `path.metadataId` | string | 是 | 查询目标。 |
| `header.X-DataGov-Subscription-Id` | string | 否 | 订阅 ID。 |
| `select` | array | 是 | 返回字段。 |
| `filters` | array | 否 | 过滤条件。 |
| `filters[].field` | string | 条件 | 过滤字段。 |
| `filters[].op` | string | 条件 | `=`、`!=`、`>`、`>=`、`<`、`<=`、`IN`、`LIKE`。 |
| `filters[].value` | any | 条件 | 过滤值。 |
| `orderBy` | array | 否 | 排序。 |
| `orderBy[].field` | string | 条件 | 排序字段。 |
| `orderBy[].direction` | string | 条件 | ASC 或 DESC。 |
| `limit` | integer | 否 | 1 到 5000，默认 100。 |

响应：

| 字段 | 说明 |
| --- | --- |
| `columns[]` | 列定义。 |
| `columns[].name` | 列名。 |
| `columns[].type` | 列类型。 |
| `rows[]` | 结果行。 |
| `rowCount` | 返回行数。 |
| `queryRecordId` | 查询记录 ID。 |

## 9. SQL Query 参数

| 参数 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| `sql` | string | 是 | 只读 SQL。 |
| `parameters` | object | 否 | 命名参数。 |
| `limit` | integer | 否 | 最大行数。 |
| `consumerId` | string | 否 | 消费方。 |
| `subscriptionId` | string | 否 | 订阅。 |

响应：

| 字段 | 说明 |
| --- | --- |
| `columns` | 列定义。 |
| `rows` | 数据行。 |
| `rowCount` | 行数。 |
| `queryRecordId` | 查询记录。 |
| `rewrittenSql` | 改写后的 SQL。 |

## 10. Subscription 参数

创建订阅：

| 参数 | 类型 | 必选 | 说明 |
| --- | --- | --- | --- |
| `path.metadataId` | string | 是 | 被订阅元数据。 |
| `consumer.consumerName` | string | 是 | 消费方名称。 |
| `consumer.consumerType` | string | 是 | MICROSERVICE、FLINK、SPARK。 |
| `consumer.owner` | string | 是 | 负责人。 |
| `consumer.environment` | string | 是 | 环境。 |
| `usageMode` | string | 是 | API_QUERY、SQL_QUERY、FLINK_JOB、SPARK_JOB、MICROSERVICE_READ。 |
| `purpose` | string | 是 | 使用目的。 |
| `fields` | array | 否 | 字段范围，空表示全字段。 |
| `notifyOn` | array | 否 | 关注事件。 |
| `notificationStrategy.delivery` | string | 否 | 当前固定 KAFKA。 |
| `notificationStrategy.sdkCallback` | boolean | 否 | 是否 SDK 回调。 |
| `notificationStrategy.consumerGroup` | string | 否 | Kafka consumer group。 |

查询订阅：

| 参数 | 说明 |
| --- | --- |
| `consumerId` | 可选，过滤消费方。 |
| `status` | ACTIVE、CANCELLED、REMOVED_BY_SNAPSHOT。 |
| `page` | 页码。 |
| `size` | 每页数量。 |

取消订阅：

| 参数 | 必选 | 说明 |
| --- | --- | --- |
| `consumerId` | 是 | 消费方 ID。 |
| `reason` | 是 | 取消原因。 |
| `operator` | 是 | 操作人。 |

## 11. Event 与 Drift

事件请求：

| 参数 | 说明 |
| --- | --- |
| `metadataId` | 关联元数据。 |
| `eventType` | SCHEMA_CHANGE、DATA_QUALITY_ALERT、DEPRECATION、METADATA_REMOVED。 |
| `eventPayload` | JSON payload。 |
| `source` | SNAPSHOT_SYNC、RUNTIME_API、ADMIN。 |

Drift 分析请求：

| 参数 | 说明 |
| --- | --- |
| `metadataId` | 可选，限定元数据。 |
| `consumerId` | 可选，限定消费方。 |
| `declaredUnusedDays` | 声明未使用阈值。 |
| `staleDeclarationDays` | 长期未刷新阈值。 |

## 12. 错误码矩阵

| errorCode | HTTP | 场景 | UI 处理 |
| --- | --- | --- | --- |
| `VALIDATION_ERROR` | 400 | 请求参数非法。 | 表单字段高亮。 |
| `METADATA_NOT_FOUND` | 404 | metadata 不存在。 | 空状态和返回列表入口。 |
| `FIELD_NOT_FOUND` | 400 | 字段不存在。 | 字段选择器刷新。 |
| `LINEAGE_TARGET_INVALID` | 400 | 字段级血缘目标非法。 | X6 draft edge 标红。 |
| `SUBSCRIPTION_MISMATCH` | 403 | 订阅不匹配。 | 提示重新订阅。 |
| `SUBSCRIPTION_CANCELLED` | 403 | 订阅已取消。 | 禁用查询按钮。 |
| `SQL_NOT_READONLY` | 400 | SQL 非只读。 | Monaco 标记错误。 |
| `ASSET_NOT_REGISTERED` | 400 | SQL 引用未注册对象。 | 提示注册或修正表名。 |
| `ASSET_NOT_QUERYABLE` | 400 | 对不可查询资产发起查询。 | 提示物化或切换数据集。 |
| `PHYSICAL_QUERY_FAILED` | 502 | 底层查询失败。 | 展示错误摘要和 traceId。 |
| `KAFKA_PUBLISH_FAILED` | 502 | 通知发布失败。 | notification 标记 FAILED。 |
