"""Deterministic fake-data generator. Slice 1b: dwd_session_qos only.

Later slices will add reverse-synth flows for other tables driven by the Agent's
reverse_synth path. The signature is kept stable.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import tempfile
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_INFRA_DIR = Path(os.environ.get("SHARED_INFRA_DIR", REPO_ROOT.parent / "shared-data-infra"))
SHARED_COMPOSE = [
    "docker", "compose",
    "-f", str(SHARED_INFRA_DIR / "compose.yaml"),
    "-f", str(SHARED_INFRA_DIR / "compose.lakehouse.yaml"),
]


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
                *SHARED_COMPOSE,
                "--profile", "spark-tools", "run", "--rm",
                "-v", f"{sql_path}:/work/insert.sql:ro",
                "spark",
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


def _generate_eval_user_score_rows(rows: int, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    bands = [
        ("excellent", 86.0, 96.0),
        ("good", 58.0, 78.0),
        ("poor", 18.0, 45.0),
    ]
    out: list[dict] = []
    for i in range(rows):
        band, low, high = bands[i % len(bands)]
        qoe = round(rng.uniform(low, high), 2)
        signal_quality = round(min(100.0, max(0.0, qoe + rng.uniform(-6, 6))), 2)
        mobility_score = round(min(100.0, max(0.0, qoe + rng.uniform(-10, 8))), 2)
        continuity = round(min(100.0, max(0.0, qoe + rng.uniform(-8, 10))), 2)
        out.append(
            {
                "imsi": f"460{rng.randrange(10**12):012d}",
                "date": "2026-05-01",
                "qoe_score": qoe,
                "signal_quality": signal_quality,
                "mobility_score": mobility_score,
                "service_continuity": continuity,
                "quality_band": band,
            }
        )
    return out


def _bucket_counts(rows: list[dict]) -> dict[str, int]:
    return {
        "excellent": sum(1 for r in rows if r["qoe_score"] > 80),
        "good": sum(1 for r in rows if 50 <= r["qoe_score"] <= 80),
        "poor": sum(1 for r in rows if r["qoe_score"] < 50),
    }


def _write_json_rows_to_hdfs(table: str, rows: list[dict]) -> str:
    hdfs_dir = "/tmp/sandbox/fake-data"
    hdfs_path = f"{hdfs_dir}/{table}.json"
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        local_path = Path(f.name)
    remote_tmp = f"/tmp/{local_path.name}"
    try:
        commands = [
            [*SHARED_COMPOSE, "exec", "-T", "namenode", "hdfs", "dfs", "-mkdir", "-p", hdfs_dir],
            [*SHARED_COMPOSE, "cp", str(local_path), f"namenode:{remote_tmp}"],
            [*SHARED_COMPOSE, "exec", "-T", "namenode", "hdfs", "dfs", "-put", "-f", remote_tmp, hdfs_path],
            [*SHARED_COMPOSE, "exec", "-T", "namenode", "rm", "-f", remote_tmp],
        ]
        for cmd in commands:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
            if result.returncode != 0:
                raise RuntimeError(f"HDFS write failed: {' '.join(cmd)}\n{result.stderr}")
    finally:
        local_path.unlink(missing_ok=True)
    return hdfs_path


def generate_fake_data(table: str, rows: int) -> dict:
    """Generate `rows` deterministic rows into `table` via Spark.

    Returns: {"rows_written": int, "table": str}.
    Raises NotImplementedError for unsupported tables.
    """
    if table == "eval_user_score":
        data = _generate_eval_user_score_rows(rows)
        hdfs_path = _write_json_rows_to_hdfs(table, data)
        return {
            "rows_written": len(data),
            "table": table,
            "hdfs_path": hdfs_path,
            "buckets": _bucket_counts(data),
        }
    if table != "dwd_session_qos":
        raise NotImplementedError(f"fake data generation does not support {table!r}")
    data = _generate_dwd_session_qos_rows(rows)
    _write_rows_via_spark(data)
    return {"rows_written": len(data), "table": table}
