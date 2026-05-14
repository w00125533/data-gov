"""Deterministic fake-data generator. Slice 1b: dwd_session_qos only.

Later slices will add reverse-synth flows for other tables driven by the Agent's
reverse_synth path. The signature is kept stable.
"""
from __future__ import annotations

import random
import subprocess
import tempfile
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _generate_dwd_session_qos_rows(rows: int, seed: int = 42) -> list[tuple]:
    rng = random.Random(seed)
    out = []
    for i in range(rows):
        rsrp = round(rng.uniform(-140, -44), 2)
        rsrq = round(rng.uniform(-19.5, -3), 2)
        sinr = round(rng.uniform(-20, 30), 2)
        packet_loss = round(rng.uniform(0, 0.05), 4)
        latency = round(rng.uniform(5, 200), 2)
        throughput = round(rng.uniform(0.1, 200), 2)
        drop_flag = 1 if rng.random() < 0.02 else 0
        out.append((
            f"sess_{i:08d}",          # session_id
            f"460{rng.randrange(10**12):012d}",  # imsi
            rsrp, rsrq, sinr,
            packet_loss, latency, throughput, drop_flag,
        ))
    return out


def _write_rows_via_spark(rows: list[tuple]) -> None:
    """Build a VALUES clause and INSERT via spark-sql in an ephemeral Spark container."""
    values_sql = ",".join(
        f"('{r[0]}', '{r[1]}', {r[2]}, {r[3]}, {r[4]}, {r[5]}, {r[6]}, {r[7]}, {r[8]})"
        for r in rows
    )
    sql = textwrap.dedent(f"""
        USE data_gov;
        INSERT INTO dwd_session_qos VALUES {values_sql};
    """).strip()

    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as f:
        f.write(sql)
        sql_path = Path(f.name)

    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--network", "data-gov_default",
                "-v", f"{REPO_ROOT}/docker/hadoop-conf:/etc/hadoop/conf:ro",
                "-v", f"{sql_path}:/work/insert.sql:ro",
                "apache/spark:3.5.4",
                "/opt/spark/bin/spark-sql",
                "--conf", "spark.sql.catalogImplementation=hive",
                "--conf", "spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083",
                "--conf", "spark.hadoop.fs.defaultFS=hdfs://namenode:8020",
                "-f", "/work/insert.sql",
            ],
            capture_output=True, text=True, check=False, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"spark-sql INSERT failed: {result.stderr}")
    finally:
        sql_path.unlink(missing_ok=True)


def generate_fake_data(table: str, rows: int) -> dict:
    """Generate `rows` deterministic rows into `table` via Spark.

    Returns: {"rows_written": int, "table": str}.
    Raises NotImplementedError for unsupported tables (will land in later slices).
    """
    if table != "dwd_session_qos":
        raise NotImplementedError(f"slice 1b only supports dwd_session_qos; got {table!r}")
    data = _generate_dwd_session_qos_rows(rows)
    _write_rows_via_spark(data)
    return {"rows_written": len(data), "table": table}
