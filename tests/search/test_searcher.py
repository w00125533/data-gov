"""tests/search/test_searcher.py — 用 seed_only=True 构建 docs，stub embedder。"""
import numpy as np
import pytest

from backend.search.docs import build_docs_from_neo4j
from backend.search.embedder import Embedder
from backend.search.searcher import HybridSearcher


@pytest.fixture
def stub_searcher(tmp_path, monkeypatch):
    """构造一个用 stub bge 的搜索器, 跑通索引流程。"""
    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            return np.array([[hash(t) % 100 / 100.0] * 16 for t in texts])

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer",
        lambda name: StubEncoder(),
    )
    emb = Embedder(model_name="stub", chroma_dir=str(tmp_path / "chroma"))
    docs = build_docs_from_neo4j(seed_only=True)
    s = HybridSearcher(embedder=emb, rerank_threshold=0.15)
    s.build_index(docs)
    return s


def test_searcher_returns_results_for_known_table(stub_searcher):
    """搜 'dws_cell_hourly' 应命中 (BM25 强匹配)。"""
    out = stub_searcher.search("dws_cell_hourly", k=5, use_rerank=False)
    assert len(out) > 0
    table_names = {r["doc"].metadata.get("table_name") for r in out}
    assert "dws_cell_hourly" in table_names


def test_searcher_returns_results_for_chinese_query(stub_searcher):
    out = stub_searcher.search("掉话率", k=5, use_rerank=False)
    table_names = [r["doc"].metadata.get("table_name") for r in out]
    assert "dws_cell_hourly" in table_names


def test_searcher_skip_dense_when_embedder_unavailable(tmp_path, monkeypatch):
    """bge 不可用 → 自动跳过 Dense, 只走 BM25。"""
    def boom(*a, **kw):
        raise RuntimeError("offline")

    monkeypatch.setattr("backend.search.embedder.SentenceTransformer", boom)
    emb = Embedder(model_name="boom", chroma_dir=str(tmp_path / "chroma"))
    assert emb.available is False
    docs = build_docs_from_neo4j(seed_only=True)
    s = HybridSearcher(embedder=emb, rerank_threshold=0.15)
    s.build_index(docs)
    out = s.search("ods_ue_signal", k=3, use_rerank=False)
    assert len(out) > 0
    assert any(r["doc"].metadata.get("table_name") == "ods_ue_signal" for r in out)


def test_searcher_upsert_adds_new_doc(stub_searcher):
    from backend.search.docs import SearchDoc

    new_doc = SearchDoc(
        id="table:ods_gnb_load",
        type="table",
        text="ods_gnb_load 基站负载原始流 cpu_util mem_util",
        metadata={"table_name": "ods_gnb_load", "layer": "ODS",
                  "storage_type": "KAFKA", "version": 1},
    )
    stub_searcher.upsert([new_doc])
    out = stub_searcher.search("基站负载", k=5, use_rerank=False)
    table_names = [r["doc"].metadata.get("table_name") for r in out]
    assert "ods_gnb_load" in table_names


def test_searcher_get_index_version(stub_searcher):
    assert stub_searcher.get_index_version() >= 1
