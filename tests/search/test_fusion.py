"""tests/search/test_fusion.py"""
from backend.search.fusion import rrf_fuse


def test_rrf_top1_match_gets_high_score_when_both_agree():
    """两路都把同一个 doc 排到第一位 → RRF 分最大。"""
    bm25 = [("d1", 5.2), ("d2", 4.1), ("d3", 0.9)]
    dense_ids = ["d1", "d3", "d2"]
    fused = rrf_fuse(bm25, dense_ids, k=60, top_k=3)
    assert fused[0][0] == "d1"
    # d1 同列两路 rank1 → 1/61 + 1/61 ≈ 0.0328
    assert abs(fused[0][1] - (1 / 61 + 1 / 61)) < 1e-9


def test_rrf_unique_to_one_source_still_returned():
    """只在 bm25 出现的 doc 也要被返回。"""
    bm25 = [("d1", 5.2)]
    dense_ids = ["d2"]
    fused = rrf_fuse(bm25, dense_ids, k=60, top_k=5)
    ids = [d for d, _ in fused]
    assert "d1" in ids and "d2" in ids


def test_rrf_top_k_caps_output():
    bm25 = [("d1", 1.0), ("d2", 0.9), ("d3", 0.8), ("d4", 0.7)]
    dense_ids = ["d1", "d2", "d3", "d4"]
    fused = rrf_fuse(bm25, dense_ids, k=60, top_k=2)
    assert len(fused) == 2


def test_rrf_empty_inputs_return_empty():
    assert rrf_fuse([], [], k=60, top_k=10) == []
