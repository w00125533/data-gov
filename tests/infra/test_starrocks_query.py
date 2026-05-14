"""P1-4: After 04_sample_data.py runs, SELECT COUNT(*) FROM ads_cell_profile > 0."""
import pymysql
import pytest


@pytest.mark.infra
def test_p1_4_starrocks_ads_cell_profile_has_rows():
    conn = pymysql.connect(
        host="127.0.0.1",
        port=9030,
        user="root",
        password="",
        database="data_gov",
        connect_timeout=5,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM ads_cell_profile")
            (count,) = cur.fetchone()
    finally:
        conn.close()

    assert count > 0, f"ads_cell_profile is empty; did 04_sample_data.py run?"
