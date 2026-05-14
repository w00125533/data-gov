"""P1-6: POST new table -> GET /api/tables -> GET /api/fields -> PUT field expression -> GET verifies.
Each step returns 200 (or 201 for create); data is consistent across calls."""
import httpx
import pytest


BASE = "http://localhost:8000"


@pytest.mark.infra
def test_p1_6_metadata_crud_roundtrip():
    with httpx.Client(base_url=BASE, timeout=10) as c:
        # Cleanup from previous test runs
        existing = c.get("/api/tables").json()
        for t in existing:
            if t["name"] == "test_temp_table":
                c.delete(f"/api/tables/{t['id']}")

        # 1. POST new table
        r = c.post("/api/tables", json={
            "name": "test_temp_table",
            "layer": "DWS",
            "storage_type": "HIVE",
            "description": "temporary CRUD acceptance",
        })
        assert r.status_code == 201, r.text
        new_table = r.json()
        assert new_table["name"] == "test_temp_table"
        assert new_table["fields"] == []
        table_id = new_table["id"]

        # 2. GET /api/tables -- list contains new table
        r = c.get("/api/tables")
        assert r.status_code == 200
        names = {t["name"] for t in r.json()}
        assert "test_temp_table" in names

        # 3. POST new field on the table
        r = c.post("/api/fields", json={
            "table_id": table_id,
            "name": "crud_test_field",
            "field_type": "DOUBLE",
            "is_nullable": True,
            "is_partition": False,
            "expression": "AVG(value)",
            "description": "smoke test",
            "upstream": [],
        })
        assert r.status_code == 201, r.text
        field = r.json()
        field_id = field["id"]
        assert field["version"] == 1

        # 4. GET /api/fields/:id -- verify creation
        r = c.get(f"/api/fields/{field_id}")
        assert r.status_code == 200
        assert r.json()["expression"] == "AVG(value)"

        # 5. PUT -- update expression; version bumps
        r = c.put(f"/api/fields/{field_id}", json={"expression": "SUM(value)/COUNT(*)"})
        assert r.status_code == 200, r.text
        assert r.json()["version"] == 2

        # 6. GET -- verify update persisted
        r = c.get(f"/api/fields/{field_id}")
        assert r.status_code == 200
        assert r.json()["expression"] == "SUM(value)/COUNT(*)"
        assert r.json()["version"] == 2

        # Cleanup
        c.delete(f"/api/fields/{field_id}")
        c.delete(f"/api/tables/{table_id}")
