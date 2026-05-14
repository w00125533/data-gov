"""GET /api/search — 混合语义检索 (spec §6.7 + §4.6)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

router = APIRouter()


class SearchHit(BaseModel):
    table: str | None
    score: float
    doc: dict


class SearchResponse(BaseModel):
    query: str
    type: str
    k: int
    results: list[SearchHit]


@router.get("/api/search", response_model=SearchResponse)
def search(
    request: Request,
    q: str = Query(..., min_length=1, description="自然语言查询"),
    type: Literal["any", "table", "field"] = Query("any"),
    k: int = Query(10, ge=1, le=50),
):
    searcher = getattr(request.app.state, "searcher", None)
    if searcher is None:
        raise HTTPException(status_code=503, detail="Search index not initialized")

    raw = searcher.search(q, k=k * 2, use_rerank=False)
    filtered = [
        r for r in raw
        if type == "any" or r["doc"].type == type
    ][:k]
    return SearchResponse(
        query=q,
        type=type,
        k=k,
        results=[
            SearchHit(
                table=r["table"],
                score=r["score"],
                doc=r["doc"].to_dict(),
            )
            for r in filtered
        ],
    )
