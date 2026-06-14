# 05. API 契约

## 1. 通用前缀

正式 API 前缀统一为：

```text
/rest/oss/inner/modelengineservice/v1
```

旧 `/api/...` 只作为迁移来源或临时兼容入口，不作为目标态新增能力的路径。

## 2. API 总览

| 维度 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| 元数据注册 | POST | `/metadata/register` | 提交微服务或作业完整元数据快照。 |
| 元数据修改 | PATCH | `/metadata/{metadataId}` | 运行时动态修改单个元数据。 |
| 元数据注销 | DELETE | `/metadata/{metadataId}` | 运行时动态取消注册。 |
| 元数据发现 | GET | `/metadata` | 列表检索。 |
| 元数据详情 | GET | `/metadata/{metadataId}` | 查询 schema 和 binding。 |
| 血缘查询 | GET | `/metadata/{metadataId}/lineage` | 查询上游或下游血缘。 |
| 产品查询 | POST | `/apiquery/{metadataId}` | 查询单个数据集内容。 |
| SQL Gateway | POST | `/sqlquery` | 执行已注册数据集只读 SQL。 |
| 创建订阅 | POST | `/subscriptions/{metadataId}` | 创建订阅声明。 |
| 查询订阅 | GET | `/subscriptions/{metadataId}` | 查询指定数据集订阅。 |
| 取消订阅 | DELETE | `/subscriptions/{metadataId}` | 取消消费方订阅。 |
| 事件通知 | POST | `/events` | 写入元数据事件并触发通知匹配。 |
| Drift 分析 | POST | `/drifts/analyze` | 执行 drift 分析。 |
| Drift 查询 | GET | `/drifts` | 查询 drift 记录。 |

路径表中的相对路径均拼接通用前缀。

## 3. 元数据注册语义

`POST /metadata/register` 是启动快照同步入口。请求体包含 producer 和 metadataList。服务端按 `producer.serviceName + producer.environment` 定义同步作用域。

处理规则：

| 场景 | 行为 |
| --- | --- |
| 快照存在、库中不存在 | 新增 metadata、field、binding 和 lineage。 |
| 快照存在、库中存在且声明变化 | 更新声明。 |
| 快照存在、库中存在且声明未变 | 刷新同步时间和实例信息。 |
| 快照缺失、库中存在且属于作用域 | 软下线为 `REMOVED_BY_SNAPSHOT`。 |
| 库中存在但不属于作用域 | 不处理。 |

## 4. 血缘响应

血缘接口返回适合 UI 和 SDK 使用的图结构：

- `nodes`: 元数据节点。
- `edges`: 表级或资产级边。
- `fieldEdges`: 字段级边。

字段级边必须能表达：

- `sourceMetadataId`
- `sourceAssetCode`
- `sourceField`
- `targetMetadataId`
- `targetAssetCode`
- `targetField`
- `lineageType`
- `direction`
- `expression`

## 5. 查询约束

- 产品 API 查询通过 `metadataId` 定位数据集。
- SQL Gateway 只允许只读 `SELECT` 或 `WITH SELECT`。
- SQL Gateway 必须拒绝未注册对象。
- Kafka topic 可进入元数据目录和血缘，但 `queryable=false`，不进入统一查询。
- 成功和失败的查询都写入 `query_record`。

## 6. 订阅约束

- 订阅面向单个 `metadataId`。
- SDK 可以提供批量声明体验，但底层按 metadata 拆分调用正式接口。
- 订阅关注 `notifyOn` 事件类型，不代表真实消费事实。
- 真实消费事实来自 `query_record` 或后续作业运行事实表。

## 7. 错误口径

| 场景 | 建议状态 |
| --- | --- |
| metadataId 不存在 | 404 |
| 请求字段校验失败 | 400 |
| subscription 与请求不匹配 | 403 |
| 已取消订阅继续查询 | 403 |
| 非只读 SQL | 400 |
| 未注册 SQL 对象 | 400 |
| 物理查询失败 | 502 |

错误响应应包含错误码、消息和可定位的请求上下文。
