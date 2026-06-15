# 11 API 契约

## 1. API 分层

| 类型 | 前缀 | 稳定性 | 说明 |
| --- | --- | --- | --- |
| 正式治理 API | `/rest/oss/inner/modelengineservice/v1` | 对外稳定 | metadata、lineage、query、subscription、event、drift。 |
| Agent 内部 API | `/api/agent` | 平台内部 | Chat、ETL plan、schema diff、reverse synthesis。 |
| Sandbox 内部 API | `/api/sandbox` | 平台内部 | dry-run、status、logs、preview、cleanup。 |

## 2. 正式治理 API 总览

| 维度 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| 数据注册 | POST | `/rest/oss/inner/modelengineservice/v1/metadata/register` | 启动快照或受控注册。 |
| 数据注册 | PATCH | `/rest/oss/inner/modelengineservice/v1/metadata/{metadataId}` | 运行时修改字段、绑定、血缘。 |
| 数据注册 | DELETE | `/rest/oss/inner/modelengineservice/v1/metadata/{metadataId}` | 取消注册。 |
| 数据发现 | GET | `/rest/oss/inner/modelengineservice/v1/metadata` | 列表检索。 |
| 数据发现 | GET | `/rest/oss/inner/modelengineservice/v1/metadata/{metadataId}` | 详情。 |
| 数据发现 | GET | `/rest/oss/inner/modelengineservice/v1/metadata/{metadataId}/lineage` | 血缘。 |
| 查询 | POST | `/rest/oss/inner/modelengineservice/v1/apiquery/{metadataId}` | 单数据集 API query。 |
| 查询 | POST | `/rest/oss/inner/modelengineservice/v1/sqlquery` | SQL Gateway。 |
| 订阅 | POST | `/rest/oss/inner/modelengineservice/v1/subscriptions/{metadataId}` | 创建订阅。 |
| 订阅 | GET | `/rest/oss/inner/modelengineservice/v1/subscriptions/{metadataId}` | 查询订阅。 |
| 订阅 | DELETE | `/rest/oss/inner/modelengineservice/v1/subscriptions/{metadataId}` | 取消订阅。 |
| 事件 | GET | `/rest/oss/inner/modelengineservice/v1/metadata/events` | 查询变更事件。 |
| Drift | GET | `/rest/oss/inner/modelengineservice/v1/drift-records` | 查询 drift。 |

## 3. register 请求核心结构

```json
{
  "producer": {
    "serviceName": "rno-data-service",
    "serviceType": "MICROSERVICE",
    "owner": "rno-data-team",
    "environment": "dev",
    "instanceId": "pod-001"
  },
  "syncMode": "FULL",
  "declarationHash": "sha256:...",
  "metadataList": [
    {
      "assetCode": "dws_cell_hourly",
      "assetName": "小区小时汇总指标",
      "metadataType": "TABLE",
      "domain": "wireless-rno",
      "owner": "rno-data-team",
      "queryable": true,
      "fields": [
        {"fieldName": "cell_id", "fieldType": "STRING", "nullable": false}
      ],
      "binding": {"sourceType": "HIVE", "catalog": "hive_catalog", "database": "rno_dws", "table": "dws_cell_hourly"},
      "lineage": {"upstreams": []}
    }
  ]
}
```

## 4. Agent 内部 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/agent/health` | Agent 健康。 |
| POST | `/api/agent/conversations` | 创建对话。 |
| GET | `/api/agent/conversations` | 对话列表。 |
| POST | `/api/agent/conversations/{conversationId}/messages` | 发送消息，返回 SSE。 |
| POST | `/api/agent/context/resolve` | 解析 metadata/lineage/pipeline 跳转上下文。 |
| POST | `/api/agent/etl/plan` | 正向 ETL 计划和代码卡。 |
| POST | `/api/agent/reverse-synthesis/plan` | 反向合成计划和约束。 |
| POST | `/api/agent/reverse-synthesis/code` | 反向合成代码生成。 |
| POST | `/api/agent/schema-evolution/diff` | 元数据演进 diff。 |
| POST | `/api/agent/schema-evolution/validate` | diff 校验。 |

SSE 消息事件：

| event | data |
| --- | --- |
| `intent` | intent badge 和 confidence。 |
| `token` | 流式文本片段。 |
| `card` | code/diff/gap/constraint 卡片。 |
| `done` | 完成标记。 |
| `error` | 错误信息。 |

## 5. Sandbox 内部 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/sandbox/health` | 沙箱健康。 |
| POST | `/api/sandbox/dry-runs` | 提交 dry-run。 |
| GET | `/api/sandbox/dry-runs/{runId}` | 查询状态。 |
| GET | `/api/sandbox/dry-runs/{runId}/logs` | 查询日志。 |
| GET | `/api/sandbox/dry-runs/{runId}/preview` | 查询预览。 |
| POST | `/api/sandbox/dry-runs/{runId}/retry` | 重试。 |
| POST | `/api/sandbox/dry-runs/{runId}/cancel` | 取消。 |
| POST | `/api/sandbox/cleanup` | 清理临时目录。 |

Dry-run 请求：

```json
{
  "engine": "SPARK_SQL",
  "code": "SELECT ...",
  "context": {
    "sourceAssets": ["ods_ue_signal"],
    "targetAsset": "dws_cell_hourly"
  },
  "resourceLimits": {
    "timeoutSeconds": 300,
    "previewLimit": 10
  }
}
```

Dry-run 响应：

```json
{
  "runId": "run-001",
  "status": "RUNNING",
  "engine": "SPARK_SQL",
  "applicationId": "application_001",
  "attempts": 1
}
```

## 6. 错误结构

```json
{
  "code": "VALIDATION_FAILED",
  "message": "fieldName is required",
  "details": {},
  "traceId": "trace-001"
}
```

| code | 场景 |
| --- | --- |
| `VALIDATION_FAILED` | 参数校验失败。 |
| `METADATA_NOT_FOUND` | metadata 不存在。 |
| `DOWNSTREAM_DEPENDENCY_EXISTS` | 删除或修改会破坏下游。 |
| `QUERY_NOT_ALLOWED` | 查询未注册对象或 Kafka topic。 |
| `SQL_NOT_READONLY` | SQL Gateway 收到非 SELECT。 |
| `SANDBOX_RUN_FAILED` | dry-run 失败。 |
