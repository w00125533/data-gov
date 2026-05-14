-- 01_hive_init.sql
-- Creates the Hive database and external table skeletons for the 4 DWD/DWS layer
-- business tables. Idempotent -- uses IF NOT EXISTS everywhere.

CREATE DATABASE IF NOT EXISTS data_gov LOCATION 'hdfs://namenode:8020/user/hive/warehouse/data_gov.db';

USE data_gov;

CREATE EXTERNAL TABLE IF NOT EXISTS dwd_session_qos (
  session_id   STRING,
  imsi         STRING,
  avg_rsrp     DOUBLE,
  avg_rsrq     DOUBLE,
  avg_sinr     DOUBLE,
  packet_loss  DOUBLE,
  latency      DOUBLE,
  throughput   DOUBLE,
  drop_flag    INT
)
STORED AS PARQUET
LOCATION 'hdfs://namenode:8020/user/hive/warehouse/data_gov.db/dwd_session_qos';

CREATE EXTERNAL TABLE IF NOT EXISTS dwd_ho_event (
  imsi          STRING,
  source_cell   STRING,
  target_cell   STRING,
  ho_type       STRING,
  ho_result     STRING,
  ho_cause      STRING,
  ho_latency    DOUBLE
)
STORED AS PARQUET
LOCATION 'hdfs://namenode:8020/user/hive/warehouse/data_gov.db/dwd_ho_event';

CREATE EXTERNAL TABLE IF NOT EXISTS dws_cell_hourly (
  cell_id           STRING,
  hour_bucket       TIMESTAMP,
  avg_rsrp          DOUBLE,
  avg_sinr          DOUBLE,
  total_sessions    BIGINT,
  drop_rate         DOUBLE,
  avg_throughput    DOUBLE,
  ho_success_rate   DOUBLE
)
STORED AS PARQUET
LOCATION 'hdfs://namenode:8020/user/hive/warehouse/data_gov.db/dws_cell_hourly';

CREATE EXTERNAL TABLE IF NOT EXISTS dws_area_traffic (
  area_id          STRING,
  hour_bucket      TIMESTAMP,
  total_throughput DOUBLE,
  active_users     BIGINT,
  avg_latency      DOUBLE,
  peak_throughput  DOUBLE
)
STORED AS PARQUET
LOCATION 'hdfs://namenode:8020/user/hive/warehouse/data_gov.db/dws_area_traffic';
