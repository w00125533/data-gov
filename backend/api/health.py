"""GET /api/health — Phase 1 slice 1b scope: only FastAPI + Neo4j.
Other components join in later slices as their subsystems land."""
import time

from fastapi import APIRouter

from backend.metadata.graph import run_query


router = APIRouter()
_BOOT_TS = time.monotonic()


@router.get("/api/health")
def health() -> dict:
    components: dict = {}
    try:
        start = time.perf_counter()
        run_query("RETURN 1")
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        node_count_rows = run_query("MATCH (n) RETURN count(n) AS n")
        components["neo4j"] = {
            "status": "ok",
            "latency_ms": latency_ms,
            "node_count": node_count_rows[0]["n"],
        }
        overall = "healthy"
    except Exception as e:
        components["neo4j"] = {"status": "error", "error": str(e)}
        overall = "degraded"
    return {
        "status": overall,
        "uptime_seconds": int(time.monotonic() - _BOOT_TS),
        "components": components,
    }
