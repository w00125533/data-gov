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


def main() -> int:
    inserted = seed_ads_cell_profile()
    print(f"Inserted {inserted} rows into ads_cell_profile.")
    return 0 if inserted > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
