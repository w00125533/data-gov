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

    # HDFS / YARN — slice 2c
    from backend.config import get_settings as _gs
    settings = _gs()
    try:
        import requests as _r
        r = _r.get(f"{settings.yarn_rm_url}/ws/v1/cluster/info", timeout=2)
        info = r.json().get("clusterInfo", {})
        components["yarn"] = {"status": "ok", "state": info.get("state", "UNKNOWN")}
    except Exception as e:
        components["yarn"] = {"status": "error", "error": str(e)[:200]}
        overall = "degraded"

    try:
        nn_url = settings.hdfs_defaultfs.replace("hdfs://", "http://").replace(":8020", ":9870")
        import requests as _r
        r = _r.get(f"{nn_url}/jmx?qry=Hadoop:service=NameNode,name=NameNodeStatus", timeout=2)
        beans = r.json().get("beans", [])
        nn_state = beans[0].get("State", "UNKNOWN") if beans else "UNKNOWN"
        components["hdfs"] = {"status": "ok", "namenode_state": nn_state}
    except Exception as e:
        components["hdfs"] = {"status": "error", "error": str(e)[:200]}
        overall = "degraded"

    components["sandbox"] = {"status": "ok", "base_dir": settings.sandbox_base_dir}

    return {
        "status": overall,
        "uptime_seconds": int(time.monotonic() - _BOOT_TS),
        "components": components,
    }
