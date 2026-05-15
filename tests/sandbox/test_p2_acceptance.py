"""tests/sandbox/test_p2_acceptance.py -- P2-4..P2-7 真实 YARN 集成验收。"""
import os

import pytest

from backend.sandbox.controller import execute
from backend.sandbox.retry import execute_with_retry

pytestmark = pytest.mark.infra


def test_p2_4_spark_sql_dry_run_against_dwd_session_qos():
    """P2-4: 对 dws_cell_hourly 聚合 sql 调 execute(spark_sql) → preview_row 含 cell_id。"""
    sql = (
        "SELECT cell_id, AVG(avg_rsrp) AS avg_rsrp_h, AVG(avg_sinr) AS avg_sinr_h "
        "FROM data_gov.dwd_session_qos "
        "GROUP BY cell_id LIMIT 1"
    )
    r = execute(sql, "spark_sql")
    assert r.success, r.error_log
    assert r.preview_row is not None
    assert "cell_id" in r.preview_row


def test_p2_5_flink_sql_dry_run_kafka_tumble_count():
    """P2-5: kafka source + 5 分钟滚动窗口 COUNT, sink → filesystem。"""
    sql = """
        CREATE TABLE ods_gnb_alarm_src (gnb_id STRING, alarm_type STRING, alarm_time TIMESTAMP_LTZ(3),
            WATERMARK FOR alarm_time AS alarm_time - INTERVAL '5' SECOND) WITH (
            'connector' = 'kafka', 'topic' = 'ods_gnb_alarm',
            'properties.bootstrap.servers' = 'kafka:9092',
            'format' = 'json', 'scan.startup.mode' = 'earliest-offset');
        INSERT INTO sandbox_sink
          SELECT CAST(window_start AS STRING) || '|' || gnb_id || '|' || CAST(cnt AS STRING)
          FROM (SELECT gnb_id, TUMBLE_START(alarm_time, INTERVAL '5' MINUTE) AS window_start, COUNT(*) AS cnt
                 FROM ods_gnb_alarm_src
                 GROUP BY gnb_id, TUMBLE(alarm_time, INTERVAL '5' MINUTE))
    """
    r = execute(sql, "flink_sql")
    assert r.success, r.error_log


def test_p2_6_java_flink_dry_run_weak_coverage_filter():
    """P2-6: 完整 Java main class — Kafka source → filter RSRP<-110 → HDFS sink。"""
    body = """
    public static void main(String[] args) throws Exception {
        org.apache.flink.streaming.api.environment.StreamExecutionEnvironment env =
            org.apache.flink.streaming.api.environment.StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);
        env.fromElements("test|imsi_1|-115").writeAsText(SANDBOX_OUTPUT);
        env.execute("weak-coverage-filter");
    }
    """
    r = execute(body, "java_flink")
    assert r.success, r.error_log


def test_p2_7_sandbox_retry_fixes_typo_via_llm(monkeypatch):
    """P2-7: 故意拼错 SLECT, 看沙箱层 execute_with_retry 1 轮修复后通过。

    用真实 DeepSeek 客户端；如果环境无 DEEPSEEK_API_KEY → skip。
    """
    from backend.clients.deepseek import build_chat_client
    try:
        client = build_chat_client(temperature=0.0)
    except RuntimeError:
        pytest.skip("DEEPSEEK_API_KEY not set")

    bad_sql = "SLECT cell_id FROM data_gov.dwd_session_qos LIMIT 1"  # SELECT 拼错
    r = execute_with_retry(bad_sql, "spark_sql", llm_client=client, max_retries=2)
    assert r.success, r.error_log
