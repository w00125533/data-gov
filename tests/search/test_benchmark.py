"""tests/search/test_benchmark.py — 在 stub 模式下跑 benchmark, 验证 pipeline 贯通。"""
import numpy as np
import pytest
import yaml
from pathlib import Path

from backend.search.docs import build_docs_from_neo4j
from backend.search.embedder import Embedder
from backend.search.searcher import HybridSearcher
from scripts.benchmark_semantic_search import (
    evaluate,
    check_gate,
    BenchmarkTargets,
    DEFAULT_TARGETS,
    GATE_FACTOR,
)


@pytest.fixture
def searcher(tmp_path, monkeypatch):
    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            return np.array([[hash(t) % 100 / 100.0] * 16 for t in texts])

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer",
        lambda name: StubEncoder(),
    )
    emb = Embedder(model_name="stub", chroma_dir=str(tmp_path / "chroma"))
    s = HybridSearcher(embedder=emb, rerank_threshold=0.15)
    s.build_index(build_docs_from_neo4j(seed_only=True))
    return s


def test_benchmark_pipeline_runs_and_produces_expected_structure(searcher):
    """验证 evaluate pipeline 正确运行、输出结构完整。"""
    queries_path = Path("benchmark/benchmark_queries.yaml")
    queries = yaml.safe_load(queries_path.read_text(encoding="utf-8"))
    metrics = evaluate(searcher, queries)

    # 所有 60 条 query 均被执行
    assert metrics["n"] == len(queries) == 60

    # 所有 metric 是合法概率 [0, 1]
    for key in ("table_recall_at_1", "table_recall_at_3", "table_mrr",
                "field_recall_at_3", "hard_recall_at_1"):
        val = metrics[key]
        assert 0.0 <= val <= 1.0, f"{key}={val} not in [0,1]"

    # latency 是正数
    assert metrics["avg_latency_ms"] > 0
    assert metrics["p99_latency_ms"] > 0

    # 按 difficulty 切分的输出完整
    assert set(metrics["by_difficulty"]) == {"easy", "medium", "hard"}
    assert sum(v["n"] for v in metrics["by_difficulty"].values()) == 60
    for d in ("easy", "medium", "hard"):
        assert 0.0 <= metrics["by_difficulty"][d]["recall_at_1"] <= 1.0
        assert metrics["by_difficulty"][d]["n"] > 0

    # 总 recall 正值: 在 60 条 query 中至少命中 1 条表 (因为表名精确出现在文本里)
    assert metrics["table_recall_at_1"] > 0.0

    # field recall: 使用宽 k 召回 + type=field 过滤后应 > 0
    assert metrics["field_recall_at_3"] > 0.0


def test_benchmark_targets_defaults_match_spec():
    """spec §4.7.3 目标值落到代码里。"""
    assert DEFAULT_TARGETS.table_recall_at_1 == 0.85
    assert DEFAULT_TARGETS.table_recall_at_3 == 0.95
    assert DEFAULT_TARGETS.table_mrr == 0.90
    assert DEFAULT_TARGETS.field_recall_at_3 == 0.80
    assert DEFAULT_TARGETS.hard_recall_at_1 == 0.65


def test_check_gate_passes_when_all_metrics_above_threshold():
    """全满分应通过 CI gate。"""
    perfect = {
        "n": 60, "table_recall_at_1": 1.0, "table_recall_at_3": 1.0,
        "table_mrr": 1.0, "field_recall_at_3": 1.0, "hard_recall_at_1": 1.0,
        "avg_latency_ms": 5.0, "p99_latency_ms": 10.0,
        "by_difficulty": {},
    }
    assert check_gate(perfect, DEFAULT_TARGETS) == []


def test_check_gate_detects_failure():
    """全 0 分应该检测到所有失败。"""
    zero = {
        "n": 60, "table_recall_at_1": 0.0, "table_recall_at_3": 0.0,
        "table_mrr": 0.0, "field_recall_at_3": 0.0, "hard_recall_at_1": 0.0,
        "avg_latency_ms": 500.0, "p99_latency_ms": 1000.0,
        "by_difficulty": {},
    }
    failures = check_gate(zero, DEFAULT_TARGETS)
    assert len(failures) >= 3  # 至少 table/mrr/field 三个指标不达标
    assert any("table_recall_at_1" in f for f in failures)
