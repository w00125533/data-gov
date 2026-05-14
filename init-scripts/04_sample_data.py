"""04_sample_data.py — deterministic sample data for slice 1a.

This slice populates StarRocks only. Hive + Kafka seeding lands in later slices.

Run via:
    python init-scripts/04_sample_data.py
"""
from __future__ import annotations

import datetime as dt
import sys

import pymysql


STARROCKS_HOST = "127.0.0.1"
STARROCKS_PORT = 9030
STARROCKS_USER = "root"
STARROCKS_DB = "data_gov"

# 6 deterministic rows across 3 cells × 2 dates so P1-4's SELECT COUNT > 0 is robust.
SAMPLE_CELLS = ["cell_001", "cell_002", "cell_003"]
SAMPLE_DATES = [dt.date(2026, 5, 1), dt.date(2026, 5, 2)]


def seed_ads_cell_profile() -> int:
    conn = pymysql.connect(
        host=STARROCKS_HOST,
        port=STARROCKS_PORT,
        user=STARROCKS_USER,
        password="",
        database=STARROCKS_DB,
        autocommit=True,
    )
    rows_inserted = 0
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE ads_cell_profile")
            for date in SAMPLE_DATES:
                for cell in SAMPLE_CELLS:
                    cur.execute(
                        """
                        INSERT INTO ads_cell_profile
                            (cell_id, `date`, coverage_score, capacity_score, stability_score, composite_kpi)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (cell, date, 85.5, 78.2, 92.1, 85.3),
                    )
                    rows_inserted += 1
    finally:
        conn.close()
    return rows_inserted


def seed_hive_dwd_session_qos(rows: int = 10) -> int:
    """Phase 1 slice 1b extension — Hive seed via Spark."""
    from backend.seed.fake_data import generate_fake_data
    return generate_fake_data(table="dwd_session_qos", rows=rows)["rows_written"]


def main() -> int:
    starrocks_count = seed_ads_cell_profile()
    print(f"Inserted {starrocks_count} rows into ads_cell_profile.")
    hive_count = seed_hive_dwd_session_qos(rows=10)
    print(f"Inserted {hive_count} rows into dwd_session_qos.")
    return 0 if (starrocks_count > 0 and hive_count > 0) else 1


if __name__ == "__main__":
    sys.exit(main())
