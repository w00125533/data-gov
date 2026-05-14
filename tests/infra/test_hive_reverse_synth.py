"""P1-8: generate_fake_data(table='dwd_session_qos', rows=5) writes 5 rows into Hive.
Spark SELECT shows fields are in valid ranges (rsrp in [-140,-44], sinr in [-20,30])."""
import subprocess
from pathlib import Path

import pytest

from backend.seed.fake_data import generate_fake_data


REPO_ROOT = Path(__file__).resolve().parents[2]


def _spark_sql(sql: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "docker", "run", "--rm",
            "--network", "data-gov_default",
            "-v", f"{REPO_ROOT}/docker/hadoop-conf:/etc/hadoop/conf:ro",
            "apache/spark:3.5.4",
            "/opt/spark/bin/spark-sql",
            "--conf", "spark.sql.catalogImplementation=hive",
            "--conf", "spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083",
            "--conf", "spark.hadoop.fs.defaultFS=hdfs://namenode:8020",
            "-e", sql,
        ],
        capture_output=True, text=True, check=False, timeout=300,
    )


@pytest.mark.infra
def test_p1_8_generate_fake_data_dwd_session_qos():
    result = generate_fake_data(table="dwd_session_qos", rows=5)
    assert result["rows_written"] == 5

    sql = "SELECT COUNT(*) AS c, MIN(avg_rsrp) AS min_rsrp, MAX(avg_rsrp) AS max_rsrp, " \
          "MIN(avg_sinr) AS min_sinr, MAX(avg_sinr) AS max_sinr FROM data_gov.dwd_session_qos"
    output = _spark_sql(sql)
    assert output.returncode == 0, output.stderr
    data_lines = [l for l in output.stdout.splitlines() if "\t" in l and not l.startswith("Time")]
    assert data_lines, f"no result row in stdout: {output.stdout!r}"
    parts = data_lines[-1].split("\t")
    count, min_rsrp, max_rsrp, min_sinr, max_sinr = (
        int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
    )
    assert count >= 5
    assert -140 <= min_rsrp <= max_rsrp <= -44
    assert -20 <= min_sinr <= max_sinr <= 30
