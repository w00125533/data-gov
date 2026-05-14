-- 03_starrocks_init.sql
-- Creates the StarRocks database and ADS/EVAL tables (4 total).
-- Run via `mysql -h 127.0.0.1 -P 9030 -u root < 03_starrocks_init.sql`.

CREATE DATABASE IF NOT EXISTS data_gov;

USE data_gov;

CREATE TABLE IF NOT EXISTS ads_cell_profile (
  cell_id           VARCHAR(64)  NOT NULL,
  `date`            DATE         NOT NULL,
  coverage_score    DOUBLE,
  capacity_score    DOUBLE,
  stability_score   DOUBLE,
  composite_kpi     DOUBLE
)
ENGINE = OLAP
DUPLICATE KEY(cell_id, `date`)
DISTRIBUTED BY HASH(cell_id) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS ads_neighbor_pair (
  source_cell        VARCHAR(64) NOT NULL,
  target_cell        VARCHAR(64) NOT NULL,
  ho_count           BIGINT,
  ho_success_rate    DOUBLE,
  avg_ho_latency     DOUBLE,
  recommend_priority INT
)
ENGINE = OLAP
DUPLICATE KEY(source_cell, target_cell)
DISTRIBUTED BY HASH(source_cell) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS eval_user_score (
  imsi                  VARCHAR(64) NOT NULL,
  `date`                DATE        NOT NULL,
  qoe_score             DOUBLE,
  signal_quality        DOUBLE,
  mobility_score        DOUBLE,
  service_continuity    DOUBLE
)
ENGINE = OLAP
DUPLICATE KEY(imsi, `date`)
DISTRIBUTED BY HASH(imsi) BUCKETS 4
PROPERTIES ("replication_num" = "1");

CREATE TABLE IF NOT EXISTS eval_net_health (
  area_id                   VARCHAR(64) NOT NULL,
  `date`                    DATE        NOT NULL,
  health_index              DOUBLE,
  alarm_severity_weighted   DOUBLE,
  user_complaint_ratio      DOUBLE,
  degradation_trend         DOUBLE
)
ENGINE = OLAP
DUPLICATE KEY(area_id, `date`)
DISTRIBUTED BY HASH(area_id) BUCKETS 4
PROPERTIES ("replication_num" = "1");
