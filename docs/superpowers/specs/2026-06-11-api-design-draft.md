# API 设计临时稿

> 临时稿，仅用于多轮修正。确认后再合入 `2026-06-10-data-product-governance-design.md` 的第 7 章。

通用接口前缀：`/oss/inner/modelengineservice/v1`

订阅接口路径：`/oss/inner/modelengineservice/v1/subscriptions/{assetId}`

术语约定：

- 数据集和数据资产在本章表达同一类治理对象，接口路径暂沿用 `assets`。
- SDK 不单独暴露一套注册接口，而是封装并调用数据注册、数据订阅的正式接口，降低调用方构造请求的成本。
- 数据变化通知由 SDK 在底层异步发送或监听 Kafka 完成，本章不提供服务端事件发布、通知拉取或通知确认类接口。

## 7.1 API 分类总览

| 维度 | 目标 | 核心能力 | 主要使用方 |
| --- | --- | --- | --- |
| 数据注册 | 将散落在不同微服务、作业和数据平台中的数据集统一注册到治理平台。 | 注册、修改、取消注册数据集元数据、字段、物理绑定和血缘关系；SDK 负责简化请求构造。 | 数据生产方、平台作业、SDK |
| 数据发现 | 对应 asset 的一组查询能力，面向元数据和血缘关系发现。 | 元数据检索、详情查询、血缘查询；详情响应包含字段 schema 和物理绑定。 | 数据消费者、治理后台、研发工具 |
| 数据查询 | 查询业务数据内容。 | API 查询单个数据集内容；SQL Gateway 查询已注册数据集内容。 | 上层应用、微服务、分析服务 |
| 数据订阅 | 保持声明态订阅逻辑，并围绕数据变化通知驱动消费策略调整。 | 按数据集订阅、查询订阅、取消订阅；SDK 基于通知定义消费策略变化。 | 数据消费者、SDK |

## 7.2 接口概览表

| 维度 | 方法 | 接口 | 功能描述 |
| --- | --- | --- | --- |
| 数据注册 | POST | `/oss/inner/modelengineservice/v1/assets/register` | 注册数据集元数据、字段、物理绑定和血缘关系。 |
| 数据注册 | PATCH | `/oss/inner/modelengineservice/v1/assets/{assetId}` | 修改已注册数据集的元数据、字段、物理绑定和血缘关系。 |
| 数据注册 | DELETE | `/oss/inner/modelengineservice/v1/assets/{assetId}` | 取消注册数据集。 |
| 数据发现 | GET | `/oss/inner/modelengineservice/v1/assets` | 检索数据集列表。 |
| 数据发现 | GET | `/oss/inner/modelengineservice/v1/assets/{assetId}` | 查询数据集详情，包含字段 schema 和物理绑定。 |
| 数据发现 | GET | `/oss/inner/modelengineservice/v1/assets/{assetId}/lineage` | 查询数据集血缘关系。 |
| 数据查询 | POST | `/oss/inner/modelengineservice/v1/apiquery/{assetId}` | API 查询单个数据集内容。 |
| 数据查询 | POST | `/oss/inner/modelengineservice/v1/sqlquery` | SQL Gateway 查询入口，支持已注册数据集的只读 SQL 查询。 |
| 数据订阅 | POST | `/oss/inner/modelengineservice/v1/subscriptions/{assetId}` | 对指定数据集创建订阅声明。 |
| 数据订阅 | GET | `/oss/inner/modelengineservice/v1/subscriptions/{assetId}` | 查询指定数据集的订阅声明，可按消费方过滤。 |
| 数据订阅 | DELETE | `/oss/inner/modelengineservice/v1/subscriptions/{assetId}` | 取消指定数据集的订阅。 |

## 7.3 数据注册接口定义

### POST `/oss/inner/modelengineservice/v1/assets/register`

注册数据集元数据、字段、物理绑定和血缘关系。请求体包含注册方信息和数据集定义。

```json
{
  "request": {
    "body": {
      "producer": {
        "serviceName": "rno-profile-service",
        "serviceType": {"enum": ["MICROSERVICE", "FLINK", "SPARK", "MANUAL"]},
        "owner": "network-team",
        "environment": "prod",
        "instanceId": "pod-rno-profile-7d8f"
      },
      "declarationHash": "sha256:metadata-lineage-declaration",
      "asset": {
        "assetCode": "ads_cell_profile",
        "assetName": "小区画像指标",
        "assetType": {"enum": ["TABLE", "VIEW", "TOPIC"]},
        "domain": "wireless-rno",
        "owner": "network-team",
        "description": "面向无线网络优化的小区画像指标数据集",
        "queryable": true,
        "fields": [
          {
            "fieldName": "cell_id",
            "fieldType": "string",
            "nullable": false,
            "description": "小区标识"
          }
        ],
        "binding": {
          "sourceType": {"enum": ["HIVE", "STARROCKS", "GAUSSDB", "ICEBERG", "KAFKA"]},
          "catalog": "default_catalog",
          "database": "data_gov",
          "table": "ads_cell_profile",
          "properties": {}
        },
        "lineage": {
          "upstreams": [
            {
              "assetCode": "dwd_cell_profile",
              "lineageType": {"enum": ["TABLE", "FIELD"]},
              "transformType": {"enum": ["DIRECT", "SQL", "JOB", "MANUAL"]},
              "expression": "job:rno-profile-etl",
              "fieldMappings": [
                {
                  "sourceField": "cell_id",
                  "targetField": "cell_id",
                  "expression": "direct"
                }
              ]
            }
          ],
          "downstreams": []
        }
      }
    }
  },
  "response": {
    "assetId": "asset_001",
    "assetCode": "ads_cell_profile",
    "status": {"enum": ["REGISTERED", "UPDATED"]},
    "lineageEdgeCount": 1,
    "registeredAt": "2026-06-11T00:00:00Z"
  }
}
```

### PATCH `/oss/inner/modelengineservice/v1/assets/{assetId}`

修改已注册数据集。可修改元数据、字段、物理绑定和血缘关系；未传字段保持不变。

```json
{
  "request": {
    "path": {
      "assetId": "asset_001"
    },
    "body": {
      "assetName": "小区画像指标 V2",
      "description": "更新后的数据集说明",
      "queryable": true,
      "fields": [
        {
          "fieldName": "coverage_score",
          "fieldType": "double",
          "nullable": true,
          "description": "覆盖评分"
        }
      ],
      "binding": {
        "catalog": "default_catalog",
        "database": "data_gov",
        "table": "ads_cell_profile_v2"
      },
      "lineage": {
        "upstreams": [
          {
            "assetCode": "dwd_cell_profile",
            "lineageType": "TABLE",
            "expression": "job:rno-profile-etl-v2"
          }
        ]
      }
    }
  },
  "response": {
    "assetId": "asset_001",
    "assetCode": "ads_cell_profile",
    "status": "UPDATED",
    "updatedAt": "2026-06-11T00:00:00Z"
  }
}
```

### DELETE `/oss/inner/modelengineservice/v1/assets/{assetId}`

取消注册数据集。请求体包含取消注册原因和操作人。

```json
{
  "request": {
    "path": {
      "assetId": "asset_001"
    },
    "body": {
      "reason": "数据集下线",
      "operator": "network-team"
    }
  },
  "response": {
    "assetId": "asset_001",
    "assetCode": "ads_cell_profile",
    "status": "UNREGISTERED",
    "unregisteredAt": "2026-06-11T00:00:00Z"
  }
}
```

数据注册共用参数：

`POST` 使用完整注册模型；`PATCH` 复用同一模型的可选子集，未传字段表示不修改；`DELETE` 只使用路径参数和取消注册原因。

| 参数名称 | 参数类型 | POST 必选 | PATCH 必选 | DELETE 必选 | 说明 | 校验范围 |
| --- | --- | --- | --- | --- | --- | --- |
| `path.assetId` | `string` | 否 | 是 | 是 | 数据集 ID，路径参数。 | 长度 1-64；必须已存在。 |
| `producer` | `object` | 是 | 否 | 否 | 数据集注册来源，表示由哪个服务、作业或人工流程提交注册。 | 非空对象。 |
| `producer.serviceName` | `string` | 是 | 否 | 否 | 注册方服务或作业名称。 | 长度 1-128；建议使用服务名、作业名或应用名。 |
| `producer.serviceType` | `string` | 是 | 否 | 否 | 注册方类型。 | 枚举：`MICROSERVICE`、`FLINK`、`SPARK`、`MANUAL`。 |
| `producer.owner` | `string` | 是 | 否 | 否 | 注册方归属团队或负责人。 | 长度 1-128。 |
| `producer.environment` | `string` | 是 | 否 | 否 | 注册发生的环境。 | 建议枚举：`dev`、`test`、`staging`、`prod`。 |
| `producer.instanceId` | `string` | 否 | 否 | 否 | 注册方运行实例标识。 | 长度 1-256；可为空。 |
| `declarationHash` | `string` | 否 | 否 | 否 | SDK 或注册方计算的声明哈希，用于识别声明是否变化。 | 建议格式：`sha256:<hex>`；可为空。 |
| `asset` | `object` | 是 | 否 | 否 | 数据集注册主体。 | POST 非空；PATCH 可传局部字段。 |
| `asset.assetCode` | `string` | 是 | 否 | 否 | 数据集唯一编码，业务侧稳定引用该编码。 | 长度 1-128；建议小写字母、数字、下划线；全局唯一。 |
| `asset.assetName` | `string` | 是 | 否 | 否 | 数据集展示名称。 | 长度 1-256。 |
| `asset.assetType` | `string` | 是 | 否 | 否 | 数据集逻辑类型。 | 枚举：`TABLE`、`VIEW`、`TOPIC`。 |
| `asset.domain` | `string` | 是 | 否 | 否 | 数据集所属业务域。 | 长度 1-128；例如 `wireless-rno`。 |
| `asset.owner` | `string` | 是 | 否 | 否 | 数据集责任团队或负责人。 | 长度 1-128。 |
| `asset.description` | `string` | 否 | 否 | 否 | 数据集说明。 | 长度 0-1024。 |
| `asset.queryable` | `boolean` | 是 | 否 | 否 | 是否允许通过治理平台查询数据内容。 | `true` 或 `false`；Kafka/TOPIC 类通常为 `false`。 |
| `asset.fields` | `array<object>` | 是 | 否 | 否 | 数据集字段列表。PATCH 传入时按服务端策略整体替换或按字段名 upsert。 | POST 至少 1 个字段；字段名在同一数据集内唯一。 |
| `asset.fields[].fieldName` | `string` | 是 | 否 | 否 | 字段名称。 | 长度 1-128；建议与物理表字段一致。 |
| `asset.fields[].fieldType` | `string` | 是 | 否 | 否 | 字段类型。 | 使用源系统类型或治理平台标准类型；不能为空。 |
| `asset.fields[].nullable` | `boolean` | 是 | 否 | 否 | 字段是否允许为空。 | `true` 或 `false`。 |
| `asset.fields[].description` | `string` | 否 | 否 | 否 | 字段说明。 | 长度 0-512。 |
| `asset.binding` | `object` | 是 | 否 | 否 | 数据集物理绑定信息。 | POST 非空；PATCH 可传局部字段。 |
| `asset.binding.sourceType` | `string` | 是 | 否 | 否 | 物理来源类型。 | 枚举：`HIVE`、`STARROCKS`、`GAUSSDB`、`ICEBERG`、`KAFKA`。 |
| `asset.binding.catalog` | `string` | 否 | 否 | 否 | StarRocks catalog 或等价逻辑目录。 | 长度 0-128；Kafka 可为空。 |
| `asset.binding.database` | `string` | 否 | 否 | 否 | 数据库或 schema 名称。 | 长度 0-128；Kafka 可为空。 |
| `asset.binding.table` | `string` | 是 | 否 | 否 | 物理表、视图或 topic 名称。 | 长度 1-256。 |
| `asset.binding.properties` | `object` | 否 | 否 | 否 | 扩展物理属性。 | JSON 对象；用于 Kafka topic 配置、Iceberg namespace 等扩展信息。 |
| `asset.lineage` | `object` | 否 | 否 | 否 | 数据集血缘声明。 | 可为空；包含 `upstreams` 和 `downstreams`。 |
| `asset.lineage.upstreams` | `array<object>` | 否 | 否 | 否 | 当前数据集的上游数据集列表。 | 可为空数组。 |
| `asset.lineage.downstreams` | `array<object>` | 否 | 否 | 否 | 当前数据集的下游数据集列表。 | 可为空数组。 |
| `asset.lineage.upstreams[].assetCode` | `string` | 条件必选 | 否 | 否 | 上游数据集编码。 | 当传入 `upstreams[]` 时必填；长度 1-128；应能解析到已注册或本次批次注册的数据集。 |
| `asset.lineage.upstreams[].lineageType` | `string` | 条件必选 | 否 | 否 | 血缘粒度。 | 当传入 `upstreams[]` 时必填；枚举：`TABLE`、`FIELD`。 |
| `asset.lineage.upstreams[].transformType` | `string` | 否 | 否 | 否 | 血缘转换来源或表达方式。 | 枚举：`DIRECT`、`SQL`、`JOB`、`MANUAL`。 |
| `asset.lineage.upstreams[].expression` | `string` | 否 | 否 | 否 | 血缘转换表达式或作业标识。 | 长度 0-4096。 |
| `asset.lineage.upstreams[].fieldMappings` | `array<object>` | 否 | 否 | 否 | 字段级映射关系。 | `lineageType=FIELD` 时建议必填。 |
| `asset.lineage.upstreams[].fieldMappings[].sourceField` | `string` | 条件必选 | 否 | 否 | 上游字段名。 | 当传入 `fieldMappings[]` 时必填；长度 1-128。 |
| `asset.lineage.upstreams[].fieldMappings[].targetField` | `string` | 条件必选 | 否 | 否 | 当前数据集字段名。 | 当传入 `fieldMappings[]` 时必填；长度 1-128；应存在于 `asset.fields`。 |
| `asset.lineage.upstreams[].fieldMappings[].expression` | `string` | 否 | 否 | 否 | 字段转换表达式。 | 长度 0-1024。 |
| `reason` | `string` | 否 | 否 | 是 | 取消注册原因。 | 长度 1-512。 |
| `operator` | `string` | 否 | 否 | 是 | 取消注册操作人。 | 长度 1-128。 |

## 7.4 数据发现接口定义

数据发现提供 asset 资源下的查询能力。列表接口返回数据集摘要；详情接口返回元数据、字段 schema 和物理绑定；血缘接口返回表级和字段级血缘关系。

### GET `/oss/inner/modelengineservice/v1/assets`

检索数据集列表。支持按关键字、业务域、数据集类型和负责人过滤。

```json
{
  "request": {
    "query": {
      "keyword": "cell",
      "domain": "wireless-rno",
      "assetType": "TABLE",
      "owner": "network-team",
      "page": 1,
      "size": 20
    }
  },
  "response": {
    "items": [
      {
        "assetId": "asset_001",
        "assetCode": "ads_cell_profile",
        "assetName": "小区画像指标",
        "assetType": "TABLE",
        "domain": "wireless-rno",
        "owner": "network-team",
        "queryable": true
      }
    ],
    "page": 1,
    "size": 20,
    "total": 1
  }
}
```

### GET `/oss/inner/modelengineservice/v1/assets/{assetId}`

查询数据集详情，包含基础元数据、字段 schema 和物理绑定。

```json
{
  "request": {
    "path": {
      "assetId": "asset_001"
    }
  },
  "response": {
    "assetId": "asset_001",
    "assetCode": "ads_cell_profile",
    "assetName": "小区画像指标",
    "assetType": "TABLE",
    "domain": "wireless-rno",
    "owner": "network-team",
    "description": "面向无线网络优化的小区画像指标数据集",
    "queryable": true,
    "schema": [
      {
        "fieldName": "cell_id",
        "fieldType": "string",
        "nullable": false,
        "description": "小区标识",
        "ordinal": 1
      }
    ],
    "binding": {
      "sourceType": {"enum": ["HIVE", "STARROCKS", "GAUSSDB", "ICEBERG", "KAFKA"]},
      "catalog": "default_catalog",
      "database": "data_gov",
      "table": "ads_cell_profile",
      "qualifiedName": "default_catalog.data_gov.ads_cell_profile",
      "properties": {}
    },
    "createdAt": "2026-06-11T00:00:00Z",
    "updatedAt": "2026-06-11T00:00:00Z"
  }
}
```

### GET `/oss/inner/modelengineservice/v1/assets/{assetId}/lineage`

查询数据集血缘关系。`direction=up` 表示查询当前数据集的上游依赖；`direction=down` 表示查询当前数据集影响到的下游对象。响应中的每条边都显式返回 `direction`，字段级血缘通过 `fieldEdges` 表达。

```json
{
  "request": {
    "path": {
      "assetId": "asset_001"
    },
    "query": {
      "direction": {"enum": ["up", "down"]},
      "depth": 5
    }
  },
  "response": {
    "assetId": "asset_001",
    "direction": "up",
    "depth": 5,
    "nodes": [
      {"assetId": "asset_000", "assetCode": "dwd_cell_profile", "assetName": "小区画像明细"},
      {"assetId": "asset_001", "assetCode": "ads_cell_profile", "assetName": "小区画像指标"}
    ],
    "edges": [
      {
        "sourceAssetId": "asset_000",
        "sourceAssetCode": "dwd_cell_profile",
        "targetAssetId": "asset_001",
        "targetAssetCode": "ads_cell_profile",
        "lineageType": "TABLE",
        "direction": "up",
        "expression": "job:rno-profile-etl"
      }
    ],
    "fieldEdges": [
      {
        "sourceAssetId": "asset_000",
        "sourceAssetCode": "dwd_cell_profile",
        "sourceField": "cell_id",
        "targetAssetId": "asset_001",
        "targetAssetCode": "ads_cell_profile",
        "targetField": "cell_id",
        "lineageType": "FIELD",
        "direction": "up",
        "expression": "direct"
      },
      {
        "sourceAssetId": "asset_000",
        "sourceAssetCode": "dwd_cell_profile",
        "sourceField": "rsrp_avg",
        "targetAssetId": "asset_001",
        "targetAssetCode": "ads_cell_profile",
        "targetField": "coverage_score",
        "lineageType": "FIELD",
        "direction": "up",
        "expression": "case when rsrp_avg >= -95 then 100 else 60 end"
      }
    ]
  }
}
```

数据发现共用参数：

| 参数名称 | 参数类型 | 列表必选 | 详情必选 | 血缘必选 | 说明 | 校验范围 |
| --- | --- | --- | --- | --- | --- | --- |
| `path.assetId` | `string` | 否 | 是 | 是 | 数据集 ID，路径参数。 | 长度 1-64；必须已注册。 |
| `keyword` | `string` | 否 | 否 | 否 | 按数据集编码、名称或描述搜索。 | 长度 0-128。 |
| `domain` | `string` | 否 | 否 | 否 | 按业务域过滤。 | 长度 0-128。 |
| `assetType` | `string` | 否 | 否 | 否 | 按数据集逻辑类型过滤。 | 枚举：`TABLE`、`VIEW`、`TOPIC`。 |
| `owner` | `string` | 否 | 否 | 否 | 按负责人或责任团队过滤。 | 长度 0-128。 |
| `page` | `integer` | 否 | 否 | 否 | 分页页码。 | 大于等于 1；默认 1。 |
| `size` | `integer` | 否 | 否 | 否 | 分页大小。 | 1-100；默认 20。 |
| `direction` | `string` | 否 | 否 | 是 | 血缘查询方向。 | 枚举：`up`、`down`。 |
| `depth` | `integer` | 否 | 否 | 否 | 血缘递归深度。 | 1-10；默认 3。 |
| `response.items[].asset` | `object` | 是 | 否 | 否 | 列表中的数据集摘要。 | 列表响应必返。 |
| `response.schema` | `array<object>` | 否 | 是 | 否 | 数据集字段 schema。 | 详情响应必返；字段名在数据集内唯一。 |
| `response.binding` | `object` | 否 | 是 | 否 | 数据集物理绑定。 | 详情响应必返。 |
| `response.nodes` | `array<object>` | 否 | 否 | 是 | 血缘图节点集合。 | 血缘响应必返；可为空数组。 |
| `response.edges` | `array<object>` | 否 | 否 | 是 | 表级血缘边集合。 | 血缘响应必返；可为空数组。 |
| `response.fieldEdges` | `array<object>` | 否 | 否 | 否 | 字段级血缘边集合。 | 有字段级血缘时返回。 |

## 7.5 数据查询接口定义

### POST `/oss/inner/modelengineservice/v1/apiquery/{assetId}`

API 查询单个数据集内容。请求体包含返回字段、过滤条件、排序条件和返回行数上限。

```json
{
  "request": {
    "path": {
      "assetId": "asset_001"
    },
    "headers": {
      "X-DataGov-Subscription-Id": "sub_001"
    },
    "body": {
      "select": ["cell_id", "coverage_score"],
      "filters": [
        {
          "field": "date",
          "op": {"enum": ["=", "!=", ">", ">=", "<", "<=", "IN", "LIKE"]},
          "value": {"types": ["string", "number", "boolean", "array"]}
        }
      ],
      "orderBy": [
        {"field": "coverage_score", "direction": {"enum": ["ASC", "DESC"]}}
      ],
      "limit": 100
    }
  },
  "response": {
    "columns": [
      {"name": "cell_id", "type": "string"},
      {"name": "coverage_score", "type": "double"}
    ],
    "rows": [
      {"cell_id": "cell_001", "coverage_score": 92.5}
    ],
    "rowCount": 1,
    "queryRecordId": "query_001"
  }
}
```

### POST `/oss/inner/modelengineservice/v1/sqlquery`

SQL Gateway 查询入口。请求体包含 SQL 语句、参数、返回行数上限和消费方标识。

```json
{
  "request": {
    "body": {
      "sql": "select cell_id, coverage_score from ads_cell_profile where date = :date limit 100",
      "parameters": {
        "date": "2026-06-11"
      },
      "limit": 100,
      "consumerId": "consumer_001",
      "subscriptionId": "sub_001"
    }
  },
  "response": {
    "columns": [
      {"name": "cell_id", "type": "string"},
      {"name": "coverage_score", "type": "double"}
    ],
    "rows": [
      {"cell_id": "cell_001", "coverage_score": 92.5}
    ],
    "rowCount": 1,
    "queryRecordId": "query_002",
    "rewrittenSql": "select cell_id, coverage_score from default_catalog.data_gov.ads_cell_profile where date = ? limit 100"
  }
}
```

数据查询共用参数：

| 参数名称 | 参数类型 | API 查询必选 | SQL 查询必选 | 说明 | 校验范围 |
| --- | --- | --- | --- | --- | --- |
| `path.assetId` | `string` | 是 | 否 | API 查询目标数据集 ID。 | 长度 1-64；必须已注册且可 API 查询。 |
| `headers.X-DataGov-Subscription-Id` | `string` | 否 | 否 | 订阅声明 ID，用于治理审计和声明态校验。 | 长度 0-64；建议已注册订阅。 |
| `select` | `array<string>` | 是 | 否 | API 查询返回字段列表。 | 至少 1 个字段；字段必须存在于数据集 schema。 |
| `filters` | `array<object>` | 否 | 否 | API 查询过滤条件。 | 字段必须存在于数据集 schema。 |
| `filters[].field` | `string` | 条件必选 | 否 | 过滤字段。 | 传入 `filters[]` 时必填。 |
| `filters[].op` | `string` | 条件必选 | 否 | 过滤操作符。 | 枚举：`=`、`!=`、`>`、`>=`、`<`、`<=`、`IN`、`LIKE`。 |
| `filters[].value` | `string number boolean array` | 条件必选 | 否 | 过滤值。 | 类型需与字段类型兼容。 |
| `orderBy` | `array<object>` | 否 | 否 | 排序条件。 | 字段必须存在于数据集 schema。 |
| `orderBy[].field` | `string` | 条件必选 | 否 | 排序字段。 | 传入 `orderBy[]` 时必填。 |
| `orderBy[].direction` | `string` | 条件必选 | 否 | 排序方向。 | 枚举：`ASC`、`DESC`。 |
| `limit` | `integer` | 否 | 否 | 返回行数上限。 | 1-5000；默认 100。 |
| `sql` | `string` | 否 | 是 | SQL Gateway 查询语句。 | 只允许只读 `SELECT` 或 `WITH SELECT`。 |
| `parameters` | `object` | 否 | 否 | SQL 参数。 | JSON 对象；参数名需与 SQL 占位符匹配。 |
| `consumerId` | `string` | 否 | 否 | 消费方 ID。 | 长度 0-64；建议已注册消费方。 |
| `subscriptionId` | `string` | 否 | 否 | 订阅声明 ID。 | 长度 0-64；建议已注册订阅。 |
| `response.columns` | `array<object>` | 是 | 是 | 返回列定义。 | 查询成功时必返。 |
| `response.rows` | `array<object>` | 是 | 是 | 查询结果行。 | 查询成功时必返；受 `limit` 限制。 |
| `response.queryRecordId` | `string` | 是 | 是 | 查询记录 ID。 | 查询成功后写入运行态记录。 |

## 7.6 数据订阅接口定义

订阅接口统一使用 `/oss/inner/modelengineservice/v1/subscriptions/{assetId}`。订阅面向单个数据集；SDK 一次声明多个数据集订阅时，按 `assetId` 拆分并逐个调用该接口。

### POST `/oss/inner/modelengineservice/v1/subscriptions/{assetId}`

对指定数据集创建订阅声明。请求体包含消费方、使用模式、字段范围和关注的数据变化类型。

```json
{
  "request": {
    "path": {
      "assetId": "asset_001"
    },
    "body": {
      "consumer": {
        "consumerName": "rno-dashboard",
        "consumerType": {"enum": ["MICROSERVICE", "FLINK", "SPARK"]},
        "owner": "network-team",
        "environment": "prod"
      },
      "usageMode": {"enum": ["API_QUERY", "SQL_QUERY", "FLINK_JOB", "SPARK_JOB", "MICROSERVICE_READ"]},
      "purpose": "展示小区画像指标",
      "fields": ["cell_id", "coverage_score"],
      "notifyOn": ["SCHEMA_CHANGE", "DATA_QUALITY_ALERT", "DEPRECATION"],
      "notificationStrategy": {
        "delivery": "KAFKA",
        "sdkCallback": true,
        "consumerGroup": "rno-dashboard"
      }
    }
  },
  "response": {
    "subscriptionId": "sub_001",
    "assetId": "asset_001",
    "assetCode": "ads_cell_profile",
    "consumerId": "consumer_001",
    "status": "ACTIVE",
    "createdAt": "2026-06-11T00:00:00Z"
  }
}
```

数据订阅共用参数：

| 参数名称 | 参数类型 | 订阅必选 | 查询必选 | 取消必选 | 说明 | 校验范围 |
| --- | --- | --- | --- | --- | --- | --- |
| `path.assetId` | `string` | 是 | 是 | 是 | 被订阅数据集 ID，路径参数。 | 长度 1-64；必须已注册。 |
| `consumer` | `object` | 是 | 否 | 否 | 消费方声明。 | 非空对象。 |
| `consumer.consumerName` | `string` | 是 | 否 | 否 | 消费方名称。 | 长度 1-128；建议使用服务名或作业名。 |
| `consumer.consumerType` | `string` | 是 | 否 | 否 | 消费方类型。 | 枚举：`MICROSERVICE`、`FLINK`、`SPARK`。 |
| `consumer.owner` | `string` | 是 | 否 | 否 | 消费方责任团队或负责人。 | 长度 1-128。 |
| `consumer.environment` | `string` | 是 | 否 | 否 | 消费方环境。 | 建议枚举：`dev`、`test`、`staging`、`prod`。 |
| `usageMode` | `string` | 是 | 否 | 否 | 订阅使用模式。 | 枚举：`API_QUERY`、`SQL_QUERY`、`FLINK_JOB`、`SPARK_JOB`、`MICROSERVICE_READ`。 |
| `purpose` | `string` | 是 | 否 | 否 | 订阅用途说明。 | 长度 1-512。 |
| `fields` | `array<string>` | 否 | 否 | 否 | 订阅字段范围。 | 字段需存在于数据集 schema；空数组表示订阅全字段。 |
| `notifyOn` | `array<string>` | 否 | 否 | 否 | 关注的数据变化事件。 | 枚举项包括 `SCHEMA_CHANGE`、`DATA_QUALITY_ALERT`、`DEPRECATION`。 |
| `notificationStrategy` | `object` | 否 | 否 | 否 | 通知消费策略。 | 不传时使用平台默认策略。 |
| `notificationStrategy.delivery` | `string` | 否 | 否 | 否 | 通知投递方式。 | 当前固定为 `KAFKA`。 |
| `notificationStrategy.sdkCallback` | `boolean` | 否 | 否 | 否 | 是否由 SDK 回调业务处理器。 | `true` 或 `false`；默认 `true`。 |
| `notificationStrategy.consumerGroup` | `string` | 否 | 否 | 否 | Kafka consumer group。 | 长度 0-128；建议与消费方名称一致。 |
| `consumerId` | `string` | 否 | 否 | 是 | 消费方 ID；查询时可作为过滤条件，取消时用于定位消费方订阅。 | 长度 1-64；取消订阅时必须已存在。 |
| `status` | `string` | 否 | 否 | 否 | 查询时按订阅状态过滤。 | 枚举：`ACTIVE`、`INACTIVE`、`CANCELLED`。 |
| `page` | `integer` | 否 | 否 | 否 | 分页页码。 | 大于等于 1；默认 1。 |
| `size` | `integer` | 否 | 否 | 否 | 分页大小。 | 1-100；默认 20。 |
| `reason` | `string` | 否 | 否 | 是 | 取消订阅原因。 | 长度 1-512。 |
| `operator` | `string` | 否 | 否 | 是 | 取消订阅操作人。 | 长度 1-128。 |

### GET `/oss/inner/modelengineservice/v1/subscriptions/{assetId}`

查询指定数据集的订阅声明。可通过 `consumerId` 查询某个消费方对该数据集的订阅，也可查询该数据集下全部订阅。

```json
{
  "request": {
    "path": {
      "assetId": "asset_001"
    },
    "query": {
      "consumerId": "consumer_001",
      "status": {"enum": ["ACTIVE", "INACTIVE", "CANCELLED"]},
      "page": 1,
      "size": 20
    }
  },
  "response": {
    "assetId": "asset_001",
    "items": [
      {
        "subscriptionId": "sub_001",
        "assetId": "asset_001",
        "assetCode": "ads_cell_profile",
        "consumerId": "consumer_001",
        "usageMode": "API_QUERY",
        "status": "ACTIVE",
        "fields": ["cell_id", "coverage_score"],
        "notifyOn": ["SCHEMA_CHANGE", "DATA_QUALITY_ALERT", "DEPRECATION"],
        "createdAt": "2026-06-11T00:00:00Z"
      }
    ],
    "page": 1,
    "size": 20,
    "total": 1
  }
}
```

### DELETE `/oss/inner/modelengineservice/v1/subscriptions/{assetId}`

取消指定消费方对指定数据集的订阅。请求体包含消费方 ID、取消原因和操作人。

```json
{
  "request": {
    "path": {
      "assetId": "asset_001"
    },
    "body": {
      "consumerId": "consumer_001",
      "reason": "业务下线",
      "operator": "network-team"
    }
  },
  "response": {
    "assetId": "asset_001",
    "consumerId": "consumer_001",
    "cancelledSubscriptions": [
      {"subscriptionId": "sub_001", "status": "CANCELLED"}
    ],
    "cancelledAt": "2026-06-11T00:00:00Z"
  }
}
```

## 7.7 SDK 快速组装与消费策略回调

SDK 要支持数据注册和数据订阅的快速数据组装。SDK 不新增独立服务端接口，而是封装前文定义的正式 API：

- 数据注册：组装后调用 `POST /oss/inner/modelengineservice/v1/assets/register`。
- 数据订阅：组装后按数据集调用 `POST /oss/inner/modelengineservice/v1/subscriptions/{assetId}`。
- 数据变化通知：生产方 SDK 或治理 SDK 底层异步发送 Kafka；消费方 SDK 监听 Kafka 后回调业务处理器。

数据注册快速组装示例：

```java
dataGovRegistrar.asset("ads_cell_profile")
    .name("小区画像指标")
    .type(AssetType.TABLE)
    .domain("wireless-rno")
    .owner("network-team")
    .queryable(true)
    .field("cell_id", "string", false, "小区标识")
    .field("coverage_score", "double", true, "覆盖评分")
    .binding(binding -> binding
        .sourceType(SourceType.STARROCKS)
        .catalog("default_catalog")
        .database("data_gov")
        .table("ads_cell_profile"))
    .upstream(lineage -> lineage
        .assetCode("dwd_cell_profile")
        .lineageType(LineageType.FIELD)
        .transformType(TransformType.JOB)
        .expression("job:rno-profile-etl")
        .field("rsrp_avg", "coverage_score", "case when rsrp_avg >= -95 then 100 else 60 end"))
    .register();
```

上面 SDK 调用等价于组装数据注册 JSON 中的：

```json
{
  "asset": {
    "assetCode": "ads_cell_profile",
    "assetType": "TABLE",
    "fields": [
      {"fieldName": "cell_id", "fieldType": "string", "nullable": false},
      {"fieldName": "coverage_score", "fieldType": "double", "nullable": true}
    ],
    "binding": {
      "sourceType": "STARROCKS",
      "catalog": "default_catalog",
      "database": "data_gov",
      "table": "ads_cell_profile"
    },
    "lineage": {
      "upstreams": [
        {
          "assetCode": "dwd_cell_profile",
          "lineageType": "FIELD",
          "transformType": "JOB",
          "expression": "job:rno-profile-etl",
          "fieldMappings": [
            {
              "sourceField": "rsrp_avg",
              "targetField": "coverage_score",
              "expression": "case when rsrp_avg >= -95 then 100 else 60 end"
            }
          ]
        }
      ]
    }
  }
}
```

数据订阅快速组装示例。SDK 可以让业务方一次声明多个数据集订阅，但底层会拆分为多次 `POST /oss/inner/modelengineservice/v1/subscriptions/{assetId}` 调用：

```java
dataGovSubscriptions.consumer("rno-dashboard")
    .type(ConsumerType.MICROSERVICE)
    .owner("network-team")
    .environment("prod")
    .subscribe("ads_cell_profile", sub -> sub
        .usageMode(UsageMode.API_QUERY)
        .purpose("展示小区画像指标")
        .fields("cell_id", "coverage_score")
        .notifyOn(AssetEventType.SCHEMA_CHANGE, AssetEventType.DATA_QUALITY_ALERT))
    .subscribe("ads_cell_quality", sub -> sub
        .usageMode(UsageMode.API_QUERY)
        .purpose("展示小区质量指标")
        .fields("cell_id", "quality_score")
        .notifyOn(AssetEventType.DATA_QUALITY_ALERT))
    .notification(strategy -> strategy
        .delivery(NotificationDelivery.KAFKA)
        .sdkCallback(true)
        .consumerGroup("rno-dashboard"))
    .register();
```

消费策略回调示例：

数据订阅的变化通知不通过服务端同步事件接口触发。数据集变化由生产方 SDK 或治理 SDK 在底层异步发送到 Kafka；消费方 SDK 监听 Kafka 后回调业务定义的消费策略调整逻辑，例如暂停使用某字段、切换兼容查询、触发本地缓存刷新。

```java
@Component
class CellProfileNotificationHandler implements DataGovNotificationHandler {
    @Override
    public void handle(NotificationMessage message) {
        if (message.eventType() == AssetEventType.SCHEMA_CHANGE) {
            // 业务方在这里调整消费策略
        }
    }
}
```

SDK 配置示例：

```yaml
data-gov:
  notifications:
    enabled: true
    topic: data-gov.subscription-notifications
    group-id: rno-dashboard
```
