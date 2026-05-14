"""GET /api/health — slice 2a: FastAPI + Neo4j + Search."""
import time

from fastapi import APIRouter, Request

from backend.metadata.graph import run_query


router = APIRouter()
_BOOT_TS = time.monotonic()


@router.get("/api/health")
def health(request: Request) -> dict:
    components: dict = {}
    overall = "healthy"

    # Neo4j
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
    except Exception as e:
        components["neo4j"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # Search
    searcher = getattr(request.app.state, "searcher", None)
    if searcher is None:
        components["search"] = {"status": "error", "error": "not initialized"}
        overall = "degraded"
    else:
        try:
            version = searcher.get_index_version()
            available = searcher._embedder.available
            components["search"] = {
                "status": "ok" if available else "degraded",
                "index_version": version,
                "dense_available": available,
            }
            if not available and overall == "healthy":
                overall = "degraded"
        except Exception as e:
            components["search"] = {"status": "error", "error": str(e)}
            overall = "degraded"

    return {
        "status": overall,
        "uptime_seconds": int(time.monotonic() - _BOOT_TS),
        "components": components,
    }
