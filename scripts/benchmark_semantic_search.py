"""60 条 benchmark queries 的离线评估 + CI 门禁。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import yaml

from backend.search.docs import build_docs_from_neo4j
from backend.search.embedder import Embedder
from backend.search.searcher import HybridSearcher
from backend.config import get_settings


@dataclass
class BenchmarkTargets:
    table_recall_at_1: float = 0.85
    table_recall_at_3: float = 0.95
    table_mrr: float = 0.90
    field_recall_at_3: float = 0.80
    avg_latency_no_llm_ms: float = 20.0
    avg_latency_with_llm_ms: float = 1000.0
    hard_recall_at_1: float = 0.65


DEFAULT_TARGETS = BenchmarkTargets()

GATE_FACTOR = 0.9


def _table_rank(results: list[dict], expected_table: str) -> int:
    for idx, r in enumerate(results):
        if r["table"] == expected_table:
            return idx + 1
    return 0


def evaluate(searcher: HybridSearcher, queries: list[dict]) -> dict:
    table_hits_1 = 0
    table_hits_3 = 0
    reciprocal_ranks = []
    field_hits_3 = 0
    field_total = 0
    latencies = []
    hard_hits_1 = 0
    hard_total = 0
    by_diff = {"easy": {"r1": 0, "n": 0}, "medium": {"r1": 0, "n": 0}, "hard": {"r1": 0, "n": 0}}

    for q in queries:
        start = time.perf_counter()
        results = searcher.search(q["query"], k=10, use_rerank=False)
        latencies.append((time.perf_counter() - start) * 1000)

        rank = _table_rank(results, q["expected_table"])
        diff = q.get("difficulty", "medium")
        by_diff[diff]["n"] += 1
        if rank == 1:
            table_hits_1 += 1
            by_diff[diff]["r1"] += 1
            if diff == "hard":
                hard_hits_1 += 1
        if 0 < rank <= 3:
            table_hits_3 += 1
        reciprocal_ranks.append(1.0 / rank if rank > 0 else 0.0)
        if diff == "hard":
            hard_total += 1

        expected_fields = q.get("expected_fields", [])
        if expected_fields:
            field_total += 1
            top3 = results[:3]
            top3_field_names = [
                r["doc"].metadata.get("field_name")
                for r in top3
                if r["doc"].type == "field"
            ]
            if any(f in top3_field_names for f in expected_fields):
                field_hits_3 += 1

    n = len(queries)
    return {
        "n": n,
        "table_recall_at_1": table_hits_1 / n,
        "table_recall_at_3": table_hits_3 / n,
        "table_mrr": sum(reciprocal_ranks) / n,
        "field_recall_at_3": (field_hits_3 / field_total) if field_total else 0.0,
        "avg_latency_ms": sum(latencies) / n,
        "p99_latency_ms": sorted(latencies)[int(0.99 * (n - 1))],
        "hard_recall_at_1": (hard_hits_1 / hard_total) if hard_total else 0.0,
        "by_difficulty": {
            d: {"recall_at_1": (s["r1"] / s["n"]) if s["n"] else 0.0, "n": s["n"]}
            for d, s in by_diff.items()
        },
    }


def check_gate(metrics: dict, targets: BenchmarkTargets, gate_factor: float = 0.9) -> list[str]:
    failures = []
    if metrics["table_recall_at_1"] < targets.table_recall_at_1 * gate_factor:
        failures.append(f"table_recall_at_1 {metrics['table_recall_at_1']:.3f} < {targets.table_recall_at_1 * gate_factor:.3f}")
    if metrics["table_recall_at_3"] < targets.table_recall_at_3 * gate_factor:
        failures.append(f"table_recall_at_3 {metrics['table_recall_at_3']:.3f} < {targets.table_recall_at_3 * gate_factor:.3f}")
    if metrics["table_mrr"] < targets.table_mrr * gate_factor:
        failures.append(f"table_mrr {metrics['table_mrr']:.3f} < {targets.table_mrr * gate_factor:.3f}")
    if metrics["field_recall_at_3"] < targets.field_recall_at_3 * gate_factor:
        failures.append(f"field_recall_at_3 {metrics['field_recall_at_3']:.3f} < {targets.field_recall_at_3 * gate_factor:.3f}")
    if metrics["hard_recall_at_1"] < targets.hard_recall_at_1 * gate_factor:
        failures.append(f"hard_recall_at_1 {metrics['hard_recall_at_1']:.3f} < {targets.hard_recall_at_1 * gate_factor:.3f}")
    return failures


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--queries", default="benchmark/benchmark_queries.yaml")
    p.add_argument("--bootstrap-from-seed", action="store_true")
    p.add_argument("--report", default=None, help="write metrics to JSON file")
    p.add_argument("--gate-factor", type=float, default=0.9,
                   help="CI gate factor (default 0.9 = 90%% of targets)")
    args = p.parse_args()

    queries = yaml.safe_load(Path(args.queries).read_text(encoding="utf-8"))
    settings = get_settings()
    embedder = Embedder(
        model_name=settings.search_embed_model,
        chroma_dir=settings.search_chroma_dir,
    )
    searcher = HybridSearcher(
        embedder=embedder,
        rerank_threshold=settings.search_rerank_threshold,
        rrf_k=settings.search_rrf_k,
    )
    searcher.build_index(build_docs_from_neo4j(seed_only=args.bootstrap_from_seed))

    metrics = evaluate(searcher, queries)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

    if args.report:
        Path(args.report).write_text(
            json.dumps({"metrics": metrics, "targets": asdict(DEFAULT_TARGETS)},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    failures = check_gate(metrics, DEFAULT_TARGETS, gate_factor=args.gate_factor)
    if failures:
        print("CI GATE FAILED:", file=sys.stderr)
        for f in failures:
            print("  -", f, file=sys.stderr)
        return 1
    print("CI GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
