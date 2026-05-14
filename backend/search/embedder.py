"""bge-small-zh + ChromaDB persistent collection。

Embedder 故意做成可降级 — bge 模型加载失败时 available=False，
HybridSearcher 检测后跳过 Dense 检索 (spec §4.6.4 异常处理)。
"""
from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

# 惰性导入，让降级路径在 monkeypatch 后仍生效
try:
    from sentence_transformers import SentenceTransformer  # noqa: F401
except Exception:  # pragma: no cover — 仅在 sentence_transformers 安装异常时
    SentenceTransformer = None  # type: ignore[assignment]


_COLLECTION_NAME = "metadata_index"


class Embedder:
    """封装 bge-small-zh 编码 + ChromaDB persistent collection。"""

    def __init__(self, model_name: str, chroma_dir: str):
        self.model_name = model_name
        self.chroma_dir = chroma_dir
        self._encoder: Any | None = None
        try:
            if SentenceTransformer is None:
                raise RuntimeError("sentence_transformers not importable")
            self._encoder = SentenceTransformer(model_name)
        except Exception as e:
            logger.warning("Embedder degraded — bge load failed: %s", e)
            self._encoder = None

        if chroma_dir == ":memory:":
            self._client = chromadb.EphemeralClient(
                settings=ChromaSettings(anonymized_telemetry=False)
            )
        else:
            self._client = chromadb.PersistentClient(
                path=chroma_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def available(self) -> bool:
        return self._encoder is not None

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not self.available:
            raise RuntimeError("Embedder is in degraded mode (bge unavailable)")
        vecs = self._encoder.encode(texts, normalize_embeddings=True)
        return [list(map(float, v)) for v in vecs]

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        embeddings = self.encode(documents) if self.available else None
        kwargs = {
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        }
        if embeddings is not None:
            kwargs["embeddings"] = embeddings
        self._collection.upsert(**kwargs)

    def query(self, text: str, n_results: int = 10) -> dict:
        if not self.available:
            raise RuntimeError("Dense query unavailable in degraded mode")
        vec = self.encode([text])[0]
        return self._collection.query(
            query_embeddings=[vec],
            n_results=n_results,
            include=["metadatas", "documents", "distances"],
        )

    def count(self) -> int:
        return self._collection.count()

    def get_index_version(self) -> int:
        meta = self._collection.metadata or {}
        return int(meta.get("index_version", 0))

    def set_index_version(self, version: int) -> None:
        meta = dict(self._collection.metadata or {})
        meta["index_version"] = int(version)
        # ChromaDB 不允许修改 hnsw:space（创建后不可变）
        meta.pop("hnsw:space", None)
        self._collection.modify(metadata=meta)
