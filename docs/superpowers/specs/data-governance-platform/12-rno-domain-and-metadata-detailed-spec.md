# 12. RNO 样例域与元数据详细规格

本文恢复 2026-05-13 版本中关于无线 RNO 样例域、分层表、字段、血缘、YAML 和元数据演进的大量细节，并按目标态技术口径重写。旧版本使用 Neo4j 作为主元数据图；目标态改为 GaussDB 主库，血缘查询由 Spring Boot 服务基于关系表构造图响应。

## 1. RNO 样例域目标

无线网络感知场景用于验证平台能同时处理流式原始数据、离线明细、汇总宽表、指标画像和评估结果。样例域必须覆盖以下治理需求：

- 从 Kafka topic 接入原始 UE 信号和基站告警。
- 用 Hive 或 Iceberg 保存 DWD 明细和 DWS 汇总。
- 用 StarRocks 保存 ADS 宽表和 EVAL 评估结果。
- 在字段级表达从原始采集、会话质量、切换事件到小区画像和用户体验评分的派生关系。
- 在 UI 中通过 X6 展示字段级端口、跨层血缘、表达式、作业来源和影响范围。
- 在 Chat 中通过自然语言生成正向 ETL、反向合成测试数据和元数据演进变更。

RNO 是默认样例域，不是平台边界。后续其他业务域应复用相同 metadata、binding、lineage、subscription 和 query_record 模型。

## 2. 分层结构

| 层级 | 中文名称 | 责任 | 典型存储 | 数据特征 |
| --- | --- | --- | --- | --- |
| L1 ODS | 接入层 | 保存原始采集、原始告警、原始事件。 | Kafka | 流式、近实时、字段原始、质量不稳定。 |
| L2 DWD | 明细层 | 清洗、标准化、会话化和事件化。 | Hive / Iceberg | 可追溯、字段标准化、适合离线加工。 |
| L3 DWS | 汇总层 | 按小区、区域、时间窗口聚合。 | Hive / Iceberg | 粒度稳定、指标可复用。 |
| L4 ADS | 宽表层 | 面向应用和查询的画像、邻区、质量宽表。 | StarRocks | 高查询性能、适合产品 API 和 SQL Gateway。 |
| L5 EVAL | 评估层 | 面向算法、评估和仿真的体验评分和网络健康结果。 | StarRocks | 结果性指标、需要反向合成数据验证。 |

层级流向：

```text
ODS Kafka
  -> DWD Hive/Iceberg
  -> DWS Hive/Iceberg
  -> ADS StarRocks
  -> EVAL StarRocks
```

目标态中的 `metadata.layer` 可以作为扩展属性保存，也可以放入 `metadata.properties`。如果实现需要独立字段，应在 GaussDB migration 中增加 `layer` 和 `layer_priority`，并保证 API 返回给 UI。

## 3. 样例表总览

| # | assetCode | assetName | layer | sourceType | queryable | 核心职责 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `ods_ue_signal` | UE 信号原始流 | ODS | KAFKA | false | UE 上报的 RSRP、RSRQ、SINR、吞吐、时间戳。 |
| 2 | `ods_gnb_alarm` | 基站告警原始流 | ODS | KAFKA | false | gNodeB 告警类型、级别、持续时间。 |
| 3 | `dwd_session_qos` | 会话 QoS 明细 | DWD | HIVE / ICEBERG | true | 按会话清洗后的质量指标。 |
| 4 | `dwd_ho_event` | 切换事件明细 | DWD | HIVE / ICEBERG | true | 源小区、目标小区、切换结果和原因。 |
| 5 | `dws_cell_hourly` | 小区小时汇总 | DWS | HIVE / ICEBERG | true | 小区小时级覆盖、吞吐和切换成功率。 |
| 6 | `dws_area_traffic` | 区域流量汇总 | DWS | HIVE / ICEBERG | true | 区域小时级吞吐、活跃用户和时延。 |
| 7 | `ads_cell_profile` | 小区画像指标 | ADS | STARROCKS | true | 面向应用查询的小区覆盖、容量、稳定性评分。 |
| 8 | `ads_neighbor_pair` | 邻区对指标 | ADS | STARROCKS | true | 邻区切换次数、成功率和推荐优先级。 |
| 9 | `eval_user_score` | 用户体验评分 | EVAL | STARROCKS | true | 用户级 QoE、信号质量、移动性和连续性。 |
| 10 | `eval_net_health` | 网络健康评分 | EVAL | STARROCKS | true | 区域级健康指数、告警权重和退化趋势。 |

## 4. 字段级详细定义

### 4.1 `ods_ue_signal`

| fieldName | fieldType | nullable | description | lineage |
| --- | --- | --- | --- | --- |
| `imsi` | string | false | 用户 IMSI。 | 原始采集字段。 |
| `cell_id` | string | false | 服务小区标识。 | 原始采集字段。 |
| `gnb_id` | string | true | 基站标识。 | 原始采集字段。 |
| `rsrp` | double | true | 参考信号接收功率。 | 原始采集字段。 |
| `rsrq` | double | true | 参考信号接收质量。 | 原始采集字段。 |
| `sinr` | double | true | 信干噪比。 | 原始采集字段。 |
| `throughput` | double | true | 采样时刻吞吐。 | 原始采集字段。 |
| `latency` | double | true | 采样时刻时延。 | 原始采集字段。 |
| `event_time` | timestamp | false | 采集时间。 | 原始采集字段。 |

绑定示例：

```json
{
  "sourceType": "KAFKA",
  "table": "ods_ue_signal",
  "properties": {
    "topic": "ods_ue_signal",
    "bootstrap.servers": "shared-kafka:9092",
    "format": "json"
  }
}
```

### 4.2 `ods_gnb_alarm`

| fieldName | fieldType | nullable | description |
| --- | --- | --- | --- |
| `gnb_id` | string | false | 基站标识。 |
| `cell_id` | string | true | 受影响小区。 |
| `alarm_type` | string | false | 告警类型。 |
| `severity` | string | false | 告警级别。 |
| `alarm_time` | timestamp | false | 告警发生时间。 |
| `duration` | bigint | true | 告警持续秒数。 |

### 4.3 `dwd_session_qos`

| fieldName | fieldType | nullable | expression | upstream |
| --- | --- | --- | --- | --- |
| `session_id` | string | false | `concat(imsi, '_', window_start)` | `ods_ue_signal.imsi`, `ods_ue_signal.event_time` |
| `imsi` | string | false | `imsi` | `ods_ue_signal.imsi` |
| `cell_id` | string | false | `cell_id` | `ods_ue_signal.cell_id` |
| `avg_rsrp` | double | true | `avg(rsrp)` | `ods_ue_signal.rsrp` |
| `avg_rsrq` | double | true | `avg(rsrq)` | `ods_ue_signal.rsrq` |
| `avg_sinr` | double | true | `avg(sinr)` | `ods_ue_signal.sinr` |
| `packet_loss` | double | true | `estimate_packet_loss(throughput, latency)` | `ods_ue_signal.throughput`, `ods_ue_signal.latency` |
| `latency` | double | true | `avg(latency)` | `ods_ue_signal.latency` |
| `throughput` | double | true | `avg(throughput)` | `ods_ue_signal.throughput` |
| `event_hour` | timestamp | false | `date_trunc('hour', event_time)` | `ods_ue_signal.event_time` |

### 4.4 `dwd_ho_event`

| fieldName | fieldType | nullable | expression | upstream |
| --- | --- | --- | --- | --- |
| `imsi` | string | false | `imsi` | `ods_ue_signal.imsi` |
| `source_cell` | string | false | `lag(cell_id) over(partition by imsi order by event_time)` | `ods_ue_signal.cell_id` |
| `target_cell` | string | false | `cell_id` | `ods_ue_signal.cell_id` |
| `ho_type` | string | true | `case when source_cell <> target_cell then 'INTER_CELL' end` | `ods_ue_signal.cell_id` |
| `ho_result` | string | true | `infer_ho_result(rsrp, sinr)` | `ods_ue_signal.rsrp`, `ods_ue_signal.sinr` |
| `ho_cause` | string | true | `infer_ho_cause(rsrp, rsrq, sinr)` | `ods_ue_signal.rsrp`, `ods_ue_signal.rsrq`, `ods_ue_signal.sinr` |
| `ho_latency` | double | true | `latency` | `ods_ue_signal.latency` |

### 4.5 `dws_cell_hourly`

| fieldName | fieldType | nullable | expression | upstream |
| --- | --- | --- | --- | --- |
| `cell_id` | string | false | `cell_id` | `dwd_session_qos.cell_id` |
| `hour_bucket` | timestamp | false | `date_trunc('hour', event_hour)` | `dwd_session_qos.event_hour` |
| `avg_rsrp` | double | true | `avg(avg_rsrp)` | `dwd_session_qos.avg_rsrp` |
| `avg_sinr` | double | true | `avg(avg_sinr)` | `dwd_session_qos.avg_sinr` |
| `total_sessions` | bigint | true | `count(distinct session_id)` | `dwd_session_qos.session_id` |
| `drop_rate` | double | true | `sum(case when packet_loss > 0.2 then 1 else 0 end) / count(*)` | `dwd_session_qos.packet_loss` |
| `avg_throughput` | double | true | `avg(throughput)` | `dwd_session_qos.throughput` |
| `ho_success_rate` | double | true | `sum(success) / count(*)` | `dwd_ho_event.ho_result` |

### 4.6 `dws_area_traffic`

| fieldName | fieldType | nullable | expression | upstream |
| --- | --- | --- | --- | --- |
| `area_id` | string | false | `lookup_area(cell_id)` | `dwd_session_qos.cell_id` |
| `hour_bucket` | timestamp | false | `date_trunc('hour', event_hour)` | `dwd_session_qos.event_hour` |
| `total_throughput` | double | true | `sum(throughput)` | `dwd_session_qos.throughput` |
| `active_users` | bigint | true | `count(distinct imsi)` | `dwd_session_qos.imsi` |
| `avg_latency` | double | true | `avg(latency)` | `dwd_session_qos.latency` |
| `peak_throughput` | double | true | `max(throughput)` | `dwd_session_qos.throughput` |

### 4.7 `ads_cell_profile`

| fieldName | fieldType | nullable | expression | upstream |
| --- | --- | --- | --- | --- |
| `cell_id` | string | false | `cell_id` | `dws_cell_hourly.cell_id` |
| `date` | date | false | `date(hour_bucket)` | `dws_cell_hourly.hour_bucket` |
| `coverage_score` | double | true | `case when avg_rsrp >= -95 then 100 when avg_rsrp >= -110 then 70 else 40 end` | `dws_cell_hourly.avg_rsrp` |
| `capacity_score` | double | true | `normalize(avg_throughput, total_sessions)` | `dws_cell_hourly.avg_throughput`, `dws_cell_hourly.total_sessions` |
| `stability_score` | double | true | `100 - drop_rate * 100` | `dws_cell_hourly.drop_rate` |
| `composite_kpi` | double | true | `0.4 * coverage_score + 0.3 * capacity_score + 0.3 * stability_score` | `coverage_score`, `capacity_score`, `stability_score` |

### 4.8 `ads_neighbor_pair`

| fieldName | fieldType | nullable | expression | upstream |
| --- | --- | --- | --- | --- |
| `source_cell` | string | false | `source_cell` | `dwd_ho_event.source_cell` |
| `target_cell` | string | false | `target_cell` | `dwd_ho_event.target_cell` |
| `ho_count` | bigint | true | `count(*)` | `dwd_ho_event.imsi` |
| `ho_success_rate` | double | true | `sum(success) / count(*)` | `dwd_ho_event.ho_result` |
| `avg_ho_latency` | double | true | `avg(ho_latency)` | `dwd_ho_event.ho_latency` |
| `recommend_priority` | int | true | `rank() over(order by ho_success_rate desc, avg_ho_latency asc)` | `ho_success_rate`, `avg_ho_latency` |

### 4.9 `eval_user_score`

| fieldName | fieldType | nullable | expression | upstream |
| --- | --- | --- | --- | --- |
| `imsi` | string | false | `imsi` | `dwd_session_qos.imsi` |
| `date` | date | false | `date(event_hour)` | `dwd_session_qos.event_hour` |
| `qoe_score` | double | true | `0.5 * signal_quality + 0.3 * mobility_score + 0.2 * service_continuity` | `signal_quality`, `mobility_score`, `service_continuity` |
| `signal_quality` | double | true | `normalize(avg_rsrp, avg_sinr)` | `dwd_session_qos.avg_rsrp`, `dwd_session_qos.avg_sinr` |
| `mobility_score` | double | true | `score_by_ho_success(ho_result)` | `dwd_ho_event.ho_result` |
| `service_continuity` | double | true | `100 - packet_loss * 100` | `dwd_session_qos.packet_loss` |

### 4.10 `eval_net_health`

| fieldName | fieldType | nullable | expression | upstream |
| --- | --- | --- | --- | --- |
| `area_id` | string | false | `area_id` | `dws_area_traffic.area_id` |
| `date` | date | false | `date(hour_bucket)` | `dws_area_traffic.hour_bucket` |
| `health_index` | double | true | `0.4 * traffic_score + 0.3 * alarm_score + 0.3 * user_qoe_score` | traffic, alarm, qoe upstreams |
| `alarm_severity_weighted` | double | true | `sum(severity_weight * duration)` | `ods_gnb_alarm.severity`, `ods_gnb_alarm.duration` |
| `user_complaint_ratio` | double | true | `estimate_complaint_ratio(avg_latency, qoe_score)` | `dws_area_traffic.avg_latency`, `eval_user_score.qoe_score` |
| `degradation_trend` | string | true | `trend(health_index over 7 days)` | `health_index` |

## 5. 目标态 GaussDB 元数据映射

RNO 样例表进入目标态时，按以下规则注册：

```json
{
  "producer": {
    "serviceName": "rno-sample-domain",
    "serviceType": "MANUAL",
    "owner": "network-team",
    "environment": "local"
  },
  "syncMode": "FULL",
  "metadataList": [
    {
      "assetCode": "ads_cell_profile",
      "assetName": "小区画像指标",
      "metadataType": "TABLE",
      "domain": "wireless-rno",
      "owner": "network-team",
      "description": "面向无线网络优化的小区画像指标数据集",
      "queryable": true,
      "fields": [
        {"fieldName": "cell_id", "fieldType": "string", "nullable": false, "description": "小区标识"},
        {"fieldName": "coverage_score", "fieldType": "double", "nullable": true, "description": "覆盖评分"}
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
            "assetCode": "dws_cell_hourly",
            "lineageType": "FIELD",
            "transformType": "JOB",
            "expression": "job:rno-profile-etl",
            "fieldMappings": [
              {
                "sourceField": "avg_rsrp",
                "targetField": "coverage_score",
                "expression": "case when avg_rsrp >= -95 then 100 when avg_rsrp >= -110 then 70 else 40 end"
              }
            ]
          }
        ]
      }
    }
  ]
}
```

注册后应形成：

- `metadata`: 一行 `ads_cell_profile`。
- `metadata_field`: 每个字段一行。
- `metadata_binding`: 一行 StarRocks 绑定。
- `lineage_edge`: 表级边或字段级边，字段级边必须保存 `source_field_name` 和 `target_field_name`。

## 6. YAML 元数据副本

YAML 在目标态仍保留，用于人工审阅、版本 diff 和离线审计，但不作为主存储。主存储为 GaussDB。YAML 由 Spring Boot 或受控导出任务生成。

目录结构：

```text
metadata-yaml/
  L1-ODS/
    ods_ue_signal.yaml
    ods_gnb_alarm.yaml
  L2-DWD/
    dwd_session_qos.yaml
    dwd_ho_event.yaml
  L3-DWS/
    dws_cell_hourly.yaml
    dws_area_traffic.yaml
  L4-ADS/
    ads_cell_profile.yaml
    ads_neighbor_pair.yaml
  L5-EVAL/
    eval_user_score.yaml
    eval_net_health.yaml
```

`dws_cell_hourly.yaml` 示例：

```yaml
assetCode: dws_cell_hourly
assetName: 小区小时汇总
metadataType: TABLE
domain: wireless-rno
owner: network-team
layer: DWS
sourceType: HIVE
binding:
  database: data_gov
  table: dws_cell_hourly
fields:
  - fieldName: cell_id
    fieldType: string
    nullable: false
    description: 小区标识
    upstream:
      - assetCode: dwd_session_qos
        fieldName: cell_id
        expression: direct
  - fieldName: avg_rsrp
    fieldType: double
    nullable: true
    description: 小区小时平均 RSRP
    expression: avg(avg_rsrp)
    upstream:
      - assetCode: dwd_session_qos
        fieldName: avg_rsrp
        expression: avg(avg_rsrp)
```

YAML 生成规则：

- 按 `layer` 分目录。
- 文件名使用 `assetCode.yaml`。
- 字段顺序使用 `metadata_field.ordinal`。
- `upstream` 从 `lineage_edge` 反查。
- Git diff 用于 UI 展示，不替代 `metadata_event`。

## 7. 元数据演进策略

元数据演进由 Chat、UI 表单或管理端触发，但最终必须通过 Spring Boot API 写入。

典型流程：

1. 用户在 Chat 中提出变更，例如“给 `dwd_session_qos` 增加 `jitter` 字段，用相邻采样 latency 标准差计算”。
2. Python Agent 执行 schema lookup，定位目标表和相关字段。
3. Agent 生成变更草案，包含字段定义、表达式、上游字段和影响范围。
4. Spring Boot 执行一致性校验：重名、类型、断链、循环依赖、下游影响。
5. UI 展示 diff 和影响警告。
6. 用户确认后，调用 `PATCH /metadata/{metadataId}`。
7. Spring Boot 更新 GaussDB，写入 `metadata_event`，匹配订阅通知。
8. YAML 导出任务刷新对应文件。

一致性校验：

- 同一 `metadataId` 下字段名唯一。
- 字段级 lineage 的 `targetField` 必须存在于目标 metadata。
- `sourceField` 必须存在于已注册上游 metadata，或在同一快照批次中可解析。
- 删除字段前必须检查所有下游 `lineage_edge`。
- 新增字段表达式引用的字段必须可解析。
- 血缘不能形成无意义循环；允许同表内中间字段依赖，但必须明确顺序和表达式。

## 8. 样例域验收数据

用于 E2E 的最小样例可以只注册两张表：

- `dwd_ui_e2e_lineage`
- `ads_ui_e2e_lineage`

字段级映射：

| source | target | expression |
| --- | --- | --- |
| `dwd_ui_e2e_lineage.rsrp_avg` | `ads_ui_e2e_lineage.coverage_score` | `case when rsrp_avg >= -95 then 100 else 60 end` |

完整样例域验收则必须注册 10 张表，且至少覆盖：

- ODS 到 DWD 的字段直接映射。
- DWD 到 DWS 的聚合表达式。
- DWS 到 ADS 的评分表达式。
- ADS/DWS/ODS 到 EVAL 的综合评分表达式。
- 至少一个多上游字段。
- 至少一个下游影响阻断用例。
