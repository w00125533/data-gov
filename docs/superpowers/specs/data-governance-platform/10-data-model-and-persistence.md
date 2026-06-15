# 10 数据模型与持久化

## 1. 持久化模式

| 模式 | 默认 | 说明 |
| --- | --- | --- |
| `graph` | 是 | 保留原有图数据库持久化层，适合血缘遍历、影响分析和图 UI。 |
| `gaussdb` | 否 | 关系模型兼容实现，适合 SQL 报表、审计和组织内标准数据库部署。 |

Spring Boot governance-server 通过 persistence adapter 访问持久化层，业务服务不直接依赖具体数据库。

## 2. 图数据库默认模型

### 2.1 节点

| 节点 | 属性 | 说明 |
| --- | --- | --- |
| `Table` | `id`, `name`, `layer`, `layer_priority`, `description`, `storage_type`, `asset_code`, `domain`, `owner`, `queryable`, `status` | 元数据表或 topic。 |
| `Field` | `id`, `name`, `field_type`, `is_nullable`, `is_partition`, `expression`, `description`, `version`, `previous_expr` | 字段。 |
| `Change` | `id`, `table_name`, `field_name`, `operation`, `old_value`, `new_value`, `changed_at`, `source`, `operator` | 元数据变更。 |
| `Consumer` | `id`, `name`, `type`, `owner`, `environment` | 消费方。 |
| `Subscription` | `id`, `usage_mode`, `purpose`, `declared_fields`, `notify_on`, `status` | 订阅声明。 |
| `QueryRecord` | `id`, `query_mode`, `referenced_asset_codes`, `selected_fields`, `status`, `created_at` | 查询事实。 |
| `Notification` | `id`, `status`, `kafka_topic`, `sent_at` | 通知。 |
| `DriftRecord` | `id`, `drift_type`, `evidence`, `status` | drift。 |

### 2.2 关系

| 关系 | 说明 |
| --- | --- |
| `(Table)-[:HAS_FIELD]->(Field)` | 表字段隶属。 |
| `(Field)-[:DERIVES_FROM {transform_expr, transform_type}]->(Field)` | 字段级血缘。 |
| `(Table)-[:UPSTREAM_OF]->(Table)` | 表级聚合血缘，可由字段级边派生。 |
| `(Consumer)-[:DECLARES]->(Subscription)` | 消费方声明订阅。 |
| `(Subscription)-[:SUBSCRIBES_TO]->(Table)` | 订阅目标。 |
| `(QueryRecord)-[:USES]->(Table)` | 查询事实引用。 |
| `(Change)-[:AFFECTS]->(Table/Field)` | 变更影响对象。 |

### 2.3 约束

| 约束 | 说明 |
| --- | --- |
| `Table.id` unique | 内部 ID 唯一。 |
| `Table.name` 或作用域内 `asset_code` unique | 业务编码唯一。 |
| `Field.id` unique | 字段 ID 唯一。 |
| 同表字段名唯一 | 应用层校验或图约束实现。 |
| `DERIVES_FROM` 不允许非法循环 | 写入前做路径检测。 |

## 3. GaussDB 兼容模型

| 表 | 关键字段 |
| --- | --- |
| `metadata` | `metadata_id`, `asset_code`, `asset_name`, `metadata_type`, `domain`, `owner`, `queryable`, `status`, `producer_service_name`, `producer_environment` |
| `metadata_field` | `field_id`, `metadata_id`, `field_name`, `field_type`, `nullable`, `description`, `ordinal` |
| `metadata_binding` | `binding_id`, `metadata_id`, `source_type`, `catalog`, `database_name`, `table_name`, `qualified_name`, `properties` |
| `lineage_edge` | `lineage_id`, `source_metadata_id`, `target_metadata_id`, `source_field_name`, `target_field_name`, `lineage_type`, `transform_type`, `expression` |
| `consumer` | `consumer_id`, `consumer_name`, `consumer_type`, `owner`, `environment` |
| `subscription` | `subscription_id`, `metadata_id`, `consumer_id`, `usage_mode`, `purpose`, `declared_fields`, `notify_on`, `status` |
| `query_record` | `query_record_id`, `consumer_id`, `subscription_id`, `query_mode`, `referenced_asset_codes`, `selected_fields`, `sql_text`, `status` |
| `consumer_job` | `job_id`, `consumer_id`, `job_name`, `engine_type`, `input_asset_codes`, `output_asset_codes`, `status` |
| `metadata_event` | `event_id`, `metadata_id`, `event_type`, `event_payload`, `source`, `created_at` |
| `subscription_notification` | `notification_id`, `subscription_id`, `metadata_id`, `consumer_id`, `event_id`, `status`, `kafka_topic` |
| `drift_record` | `drift_id`, `drift_type`, `metadata_id`, `consumer_id`, `subscription_id`, `evidence`, `status` |

## 4. 图模型与关系模型映射

| 图数据库 | GaussDB |
| --- | --- |
| `Table` | `metadata` + `metadata_binding` |
| `Field` | `metadata_field` |
| `HAS_FIELD` | `metadata_field.metadata_id` |
| `DERIVES_FROM` | `lineage_edge` |
| `Change` | `metadata_event` |
| `Consumer` | `consumer` |
| `Subscription` | `subscription` |
| `QueryRecord` | `query_record` |
| `Notification` | `subscription_notification` |
| `DriftRecord` | `drift_record` |

## 5. Repository 接口

| 接口 | 说明 |
| --- | --- |
| `MetadataRepository` | list/detail/register/patch/delete metadata。 |
| `FieldRepository` | 字段 upsert/remove/query。 |
| `LineageRepository` | 字段级和表级血缘写入、遍历和影响分析。 |
| `EventRepository` | Change/metadata_event 写入和查询。 |
| `SubscriptionRepository` | 订阅声明和取消。 |
| `QueryRecordRepository` | 查询事实写入。 |
| `DriftRepository` | drift upsert 和状态变更。 |

## 6. 写入一致性

1. 所有写入经 governance-server。
2. Agent 只生成 diff，经用户确认后调用正式 API。
3. 图数据库模式下，元数据和事件在同一业务事务边界内提交。
4. GaussDB 模式下，使用数据库事务。
5. 双写不是首期目标；如后续需要双写，必须有一致性校验任务。
