"""tests/search/test_embedder.py — 不下载真实模型时跳过 dense；仅验证降级路径与 ChromaDB 操作。"""
import pytest

from backend.search.embedder import Embedder


def test_embedder_degraded_when_model_load_fails(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("offline")

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer", boom
    )
    emb = Embedder(model_name="boom-model", chroma_dir=":memory:")
    assert emb.available is False
    # encode 在 degraded 模式下抛 RuntimeError
    with pytest.raises(RuntimeError):
        emb.encode(["x"])


def test_embedder_chroma_upsert_and_count(tmp_path, monkeypatch):
    """用一个 stub encoder 跑通 upsert/query 链路。"""
    import numpy as np

    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            # 把字符串长度作为唯一维度，简化但确定。
            return np.array([[len(t) / 100.0] * 16 for t in texts])

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer",
        lambda name: StubEncoder(),
    )
    emb = Embedder(model_name="stub", chroma_dir=str(tmp_path / "chroma"))
    assert emb.available is True

    emb.upsert(
        ids=["a", "b"],
        documents=["aaaaa", "bbbbbbb"],
        metadatas=[{"k": 1}, {"k": 2}],
    )
    assert emb.count() == 2

    out = emb.query("aaaaa", n_results=2)
    assert "a" in out["ids"][0]


def test_embedder_index_version_roundtrip(tmp_path, monkeypatch):
    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            return [[0.0] * 16 for _ in texts]

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer",
        lambda name: StubEncoder(),
    )
    emb = Embedder(model_name="stub", chroma_dir=str(tmp_path / "chroma"))
    assert emb.get_index_version() == 0
    emb.set_index_version(7)
    assert emb.get_index_version() == 7
