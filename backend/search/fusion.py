"""Reciprocal Rank Fusion — 纯函数。"""
from __future__ import annotations


def rrf_fuse(
    bm25_ranked: list[tuple[str, float]],
    dense_ids: list[str],
    k: int = 60,
    top_k: int = 10,
) -> list[tuple[str, float]]:
    """合并 BM25 和 Dense 两路排序。

    score(doc) = Σ 1 / (k + rank_i + 1)    # rank 从 0 起，所以 +1
    """
    scores: dict[str, float] = {}
    for rank, (doc_id, _) in enumerate(bm25_ranked):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    for rank, doc_id in enumerate(dense_ids):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return ranked[:top_k]
