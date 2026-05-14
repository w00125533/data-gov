"""tests/search/test_searcher_integration.py — 真正连 Neo4j + 真 bge, P2a-acceptance。"""
import pytest

from backend.config import get_settings
from backend.search.docs import build_docs_from_neo4j
from backend.search.embedder import Embedder
from backend.search.searcher import HybridSearcher


pytestmark = pytest.mark.infra


@pytest.fixture(scope="module")
def live_searcher(tmp_path_factory):
    get_settings.cache_clear()
    chroma_dir = str(tmp_path_factory.mktemp("chroma_e2e"))
    s = get_settings()
    emb = Embedder(model_name=s.search_embed_model, chroma_dir=chroma_dir)
    if not emb.available:
        pytest.skip("bge model unavailable in test environment")
    searcher = HybridSearcher(embedder=emb, rerank_threshold=s.search_rerank_threshold)
    searcher.build_index(build_docs_from_neo4j())
    return searcher


def test_p2a_1_search_yields_dws_cell_hourly_for_chinese_query(live_searcher):
    """P2a-1: '小区每小时的平均覆盖强度' Top-3 应含 dws_cell_hourly。"""
    out = live_searcher.search("小区每小时的平均覆盖强度", k=5, use_rerank=False)
    top3_tables = [r["table"] for r in out[:3]]
    assert "dws_cell_hourly" in top3_tables


def test_p2a_2_search_for_field_returns_field_doc(live_searcher):
    """P2a-2: 'avg_sinr 字段含义' 应命中 field 类型 doc。"""
    out = live_searcher.search("avg_sinr 字段含义", k=10, use_rerank=False)
    field_docs = [r for r in out if r["doc"].type == "field"]
    assert any(r["doc"].metadata.get("field_name") == "avg_sinr" for r in field_docs)


def test_p2a_3_index_version_positive_after_build(live_searcher):
    """P2a-3: 构建后 index_version > 0 并稳定。"""
    v = live_searcher.get_index_version()
    assert v > 0
    assert live_searcher.get_index_version() == v


def test_p2a_4_incremental_upsert_visible_in_search(live_searcher):
    """P2a-4: upsert 新 doc 后, 查得到 (模拟 schema_evolve 后)。"""
    from backend.search.docs import SearchDoc
    new_doc = SearchDoc(
        id="table:ods_gnb_load_test",
        type="table",
        text="ods_gnb_load_test 基站负载原始流 cpu_util mem_util",
        metadata={
            "table_name": "ods_gnb_load_test", "layer": "ODS",
            "storage_type": "KAFKA", "version": 1,
        },
    )
    v0 = live_searcher.get_index_version()
    live_searcher.upsert([new_doc])
    v1 = live_searcher.get_index_version()
    assert v1 != v0
    out = live_searcher.search("基站负载", k=5, use_rerank=False)
    assert any(r["table"] == "ods_gnb_load_test" for r in out)
