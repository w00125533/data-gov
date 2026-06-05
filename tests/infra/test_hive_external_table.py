"""P1-2: Through a Spark SQL session, create an external table, insert 10 rows,
SELECT COUNT(*) returns 10.

We invoke Spark via an ephemeral ``apache/spark:3.5.4`` container on the compose
network — slice 1a does not run a permanent Spark service.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_INFRA_ROOT = REPO_ROOT.parent / "shared-data-infra"
SHARED_COMPOSE = [
    "docker", "compose",
    "-f", str(SHARED_INFRA_ROOT / "compose.yaml"),
    "-f", str(SHARED_INFRA_ROOT / "compose.lakehouse.yaml"),
]


def _run_spark_sql(sql: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            *SHARED_COMPOSE,
            "--profile", "spark-tools", "run", "--rm",
            "spark",
            "--conf", "spark.sql.catalogImplementation=hive",
            "--conf", "spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083",
            "--conf", "spark.hadoop.fs.defaultFS=hdfs://namenode:8020",
            "-e", sql,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


@pytest.mark.infra
def test_p1_2_hive_external_table_roundtrip():
    sql = textwrap.dedent("""
        CREATE DATABASE IF NOT EXISTS smoke_test;
        DROP TABLE IF EXISTS smoke_test.tmp_p1_2;
        CREATE EXTERNAL TABLE smoke_test.tmp_p1_2 (n INT)
          STORED AS PARQUET
          LOCATION 'hdfs://namenode:8020/user/hive/warehouse/smoke_test.db/tmp_p1_2';
        INSERT INTO smoke_test.tmp_p1_2 VALUES (1),(2),(3),(4),(5),(6),(7),(8),(9),(10);
        SELECT COUNT(*) AS c FROM smoke_test.tmp_p1_2;
    """).strip()

    result = _run_spark_sql(sql)
    assert result.returncode == 0, (
        f"spark-sql failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    # spark-sql prints results line by line; the last numeric token before
    # "Time taken" is the count.
    output_lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    assert "10" in output_lines, (
        f"expected '10' in spark-sql output, got: {output_lines!r}"
    )
