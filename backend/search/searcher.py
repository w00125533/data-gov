"""HybridSearcher — BM25 + Dense + RRF + (optional) LLM rerank."""
from __future__ import annotations

import logging
from threading import RLock
from typing import Any

from rank_bm25 import BM25Okapi

from backend.search.docs import SearchDoc
from backend.search.embedder import Embedder
from backend.search.fusion import rrf_fuse
from backend.search.preprocessing import tokenize
from backend.search.rerank import llm_rerank

logger = logging.getLogger(__name__)


class HybridSearcher:
    """组合 BM25 + Dense + RRF + LLM rerank 兜底。"""

    def __init__(
        self,
        *,
        embedder: Embedder,
        rerank_threshold: float = 0.15,
        rrf_k: int = 60,
    ):
        self._embedder = embedder
        self._rerank_threshold = rerank_threshold
        self._rrf_k = rrf_k

        self._docs: list[SearchDoc] = []
        self._bm25: BM25Okapi | None = None
        self._doc_by_id: dict[str, SearchDoc] = {}
        self._lock = RLock()

    # ---- 构建 / 增量 ----

    def build_index(self, docs: list[SearchDoc]) -> None:
        with self._lock:
            self._docs = list(docs)
            self._doc_by_id = {d.id: d for d in self._docs}
            self._bm25 = BM25Okapi([tokenize(d.text) for d in self._docs])
            if self._embedder.available:
                self._embedder.upsert(
                    ids=[d.id for d in self._docs],
                    documents=[d.text for d in self._docs],
                    metadatas=[d.metadata for d in self._docs],
                )
            self._embedder.set_index_version(self._compute_version())

    def upsert(self, docs: list[SearchDoc]) -> None:
        with self._lock:
            for d in docs:
                self._doc_by_id[d.id] = d
            self._docs = list(self._doc_by_id.values())
            self._bm25 = BM25Okapi([tokenize(d.text) for d in self._docs])
            if self._embedder.available:
                self._embedder.upsert(
                    ids=[d.id for d in docs],
                    documents=[d.text for d in docs],
                    metadatas=[d.metadata for d in docs],
                )
            self._embedder.set_index_version(self._compute_version())

    def _compute_version(self) -> int:
        if not self._docs:
            return 0
        total = sum(int(d.metadata.get("version", 1)) for d in self._docs)
        return len(self._docs) * 1000 + total

    def get_index_version(self) -> int:
        return self._embedder.get_index_version()

    # ---- 检索 ----

    def search(
        self,
        query: str,
        *,
        k: int = 10,
        use_rerank: bool = True,
        rerank_client: Any | None = None,
    ) -> list[dict]:
        if self._bm25 is None or not self._docs:
            return []

        bm25_scores = self._bm25.get_scores(tokenize(query))
        bm25_pairs = sorted(
            zip([d.id for d in self._docs], bm25_scores),
            key=lambda x: -x[1],
        )[:k * 2]

        if self._embedder.available:
            try:
                dense = self._embedder.query(query, n_results=k)
                dense_ids = dense.get("ids", [[]])[0]
            except Exception as e:
                logger.warning("Dense query failed, falling back to BM25 only: %s", e)
                dense_ids = []
        else:
            dense_ids = []

        fused = rrf_fuse(bm25_pairs, dense_ids, k=self._rrf_k, top_k=k)
        result_pairs = [
            (self._doc_by_id[doc_id], score)
            for doc_id, score in fused
            if doc_id in self._doc_by_id
        ]

        if use_rerank and result_pairs and result_pairs[0][1] < self._rerank_threshold:
            if rerank_client is None:
                logger.debug("Rerank skipped — no client provided.")
            else:
                result_pairs = llm_rerank(query, result_pairs, rerank_client)

        return [
            {
                "doc": d,
                "score": s,
                "table": d.metadata.get("table_name"),
            }
            for d, s in result_pairs
        ]
