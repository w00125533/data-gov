"""P1-7: GET /api/lineage?table=dwd_session_qos&direction=down returns at least 2
field-level edges pointing to dws_cell_hourly and dws_area_traffic."""
import httpx
import pytest


BASE = "http://localhost:8000"


@pytest.mark.infra
def test_p1_7_lineage_downstream_dwd_session_qos():
    with httpx.Client(base_url=BASE, timeout=10) as c:
        r = c.get("/api/lineage", params={"table": "dwd_session_qos", "direction": "down", "depth": 1})
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["root_table"] == "dwd_session_qos"
        assert payload["direction"] == "down"
        edges = payload["edges"]
        downstream_tables = {e["to_table"] for e in edges}
        assert {"dws_cell_hourly", "dws_area_traffic"}.issubset(downstream_tables), \
            f"expected dws_cell_hourly and dws_area_traffic in downstream, got {downstream_tables}"
        target_edges = [e for e in edges if e["to_table"] in {"dws_cell_hourly", "dws_area_traffic"}]
        assert len(target_edges) >= 2, f"expected >=2 edges to dws_*; got {len(target_edges)}"


@pytest.mark.infra
def test_lineage_upstream_dws_cell_hourly():
    with httpx.Client(base_url=BASE, timeout=10) as c:
        r = c.get("/api/lineage", params={"table": "dws_cell_hourly", "direction": "up", "depth": 1})
        assert r.status_code == 200
        upstream_tables = {e["from_table"] for e in r.json()["edges"]}
        assert "dwd_session_qos" in upstream_tables


@pytest.mark.infra
def test_lineage_rejects_invalid_direction():
    with httpx.Client(base_url=BASE, timeout=10) as c:
        r = c.get("/api/lineage", params={"table": "ods_ue_signal", "direction": "sideways"})
        assert r.status_code == 422
