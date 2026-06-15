# 09 领域模型与样例

## 1. RNO 分层结构

```text
L1 ODS:  ods_ue_signal, ods_gnb_alarm
L2 DWD:  dwd_session_qos, dwd_ho_event
L3 DWS:  dws_cell_hourly, dws_area_traffic
L4 ADS:  ads_cell_profile, ads_neighbor_pair
L5 EVAL: eval_user_score, eval_net_health
```

## 2. 10 张样例表

| # | 表名 | 层 | 存储类型 | 核心字段 | 上游依赖 |
| --- | --- | --- | --- | --- | --- |
| 1 | `ods_ue_signal` | L1-ODS | Kafka/Hive | `imsi`, `cell_id`, `rsrp`, `rsrq`, `sinr`, `timestamp` | 无。 |
| 2 | `ods_gnb_alarm` | L1-ODS | Kafka/Hive | `gnb_id`, `alarm_type`, `severity`, `alarm_time`, `duration` | 无。 |
| 3 | `dwd_session_qos` | L2-DWD | Hive/Iceberg | `session_id`, `imsi`, `avg_rsrp`, `avg_rsrq`, `avg_sinr`, `packet_loss`, `latency`, `throughput` | `ods_ue_signal`。 |
| 4 | `dwd_ho_event` | L2-DWD | Hive/Iceberg | `imsi`, `source_cell`, `target_cell`, `ho_type`, `ho_result`, `ho_cause`, `ho_latency` | `ods_ue_signal`。 |
| 5 | `dws_cell_hourly` | L3-DWS | Hive/StarRocks | `cell_id`, `hour_bucket`, `avg_rsrp`, `avg_sinr`, `total_sessions`, `drop_rate`, `avg_throughput`, `ho_success_rate` | `dwd_session_qos`, `dwd_ho_event`。 |
| 6 | `dws_area_traffic` | L3-DWS | Hive/StarRocks | `area_id`, `hour_bucket`, `total_throughput`, `active_users`, `avg_latency`, `peak_throughput` | `dwd_session_qos`。 |
| 7 | `ads_cell_profile` | L4-ADS | StarRocks | `cell_id`, `date`, `coverage_score`, `capacity_score`, `stability_score`, `composite_kpi` | `dws_cell_hourly`。 |
| 8 | `ads_neighbor_pair` | L4-ADS | StarRocks | `source_cell`, `target_cell`, `ho_count`, `ho_success_rate`, `avg_ho_latency`, `recommend_priority` | `dwd_ho_event`。 |
| 9 | `eval_user_score` | L5-EVAL | StarRocks | `imsi`, `date`, `qoe_score`, `signal_quality`, `mobility_score`, `service_continuity` | `ads_cell_profile`。 |
| 10 | `eval_net_health` | L5-EVAL | StarRocks | `area_id`, `date`, `health_index`, `alarm_severity_weighted`, `user_complaint_ratio`, `degradation_trend` | `dws_area_traffic`, `ods_gnb_alarm`, `eval_user_score`。 |

## 3. 字段级血缘样例

| 下游字段 | 上游字段 | 类型 | 表达式 |
| --- | --- | --- | --- |
| `dwd_session_qos.imsi` | `ods_ue_signal.imsi` | DIRECT | `imsi`。 |
| `dwd_session_qos.avg_rsrp` | `ods_ue_signal.rsrp` | SQL | `AVG(rsrp) OVER session window`。 |
| `dwd_session_qos.avg_sinr` | `ods_ue_signal.sinr` | SQL | `AVG(sinr) OVER session window`。 |
| `dws_cell_hourly.avg_rsrp` | `dwd_session_qos.avg_rsrp` | SQL | `AVG(avg_rsrp)`。 |
| `dws_cell_hourly.avg_sinr` | `dwd_session_qos.avg_sinr` | SQL | `AVG(avg_sinr)`。 |
| `dws_cell_hourly.ho_success_rate` | `dwd_ho_event.ho_result` | SQL | `SUM(success)/COUNT(*)`。 |
| `ads_cell_profile.coverage_score` | `dws_cell_hourly.avg_rsrp` | SQL | RSRP 归一化评分。 |
| `eval_user_score.signal_quality` | `ads_cell_profile.coverage_score` | SQL | 覆盖评分映射。 |
| `eval_net_health.alarm_severity_weighted` | `ods_gnb_alarm.severity` | SQL | 告警级别加权。 |

## 4. YAML 副本格式

```yaml
assetCode: dws_cell_hourly
assetName: 小区小时汇总指标
domain: wireless-rno
layer: DWS
metadataType: TABLE
owner: rno-data-team
queryable: true
binding:
  sourceType: HIVE
  catalog: hive_catalog
  database: rno_dws
  table: dws_cell_hourly
fields:
  - fieldName: cell_id
    fieldType: STRING
    nullable: false
    upstream:
      - assetCode: dwd_session_qos
        fieldName: cell_id
        transformType: DIRECT
        expression: cell_id
  - fieldName: avg_sinr
    fieldType: DOUBLE
    nullable: true
    expression: AVG(avg_sinr)
    upstream:
      - assetCode: dwd_session_qos
        fieldName: avg_sinr
        transformType: SQL
        expression: AVG(avg_sinr)
```

## 5. 语义检索 Benchmark 样例

| 查询 | 期望命中 |
| --- | --- |
| 每个小区每小时的平均信噪比 | `dws_cell_hourly.avg_sinr`。 |
| 弱覆盖用户的 RSRP 从哪里来 | `ods_ue_signal.rsrp`、`dwd_session_qos.avg_rsrp`。 |
| 基站告警对网络健康影响 | `ods_gnb_alarm.severity`、`eval_net_health.alarm_severity_weighted`。 |

目标指标：Recall@5 >= 0.90，MRR >= 0.75，nDCG@10 >= 0.80，非 LLM rerank P95 <= 800ms。
