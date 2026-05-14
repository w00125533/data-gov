# Semantic Search Benchmark Queries

60 条 NL 查询，覆盖类型 A (规则生成 30 条) / 类型 B (人工 LLM 生成 20 条) / 类型 C (对抗 10 条)。

源文件: `benchmark_queries.yaml`
生成脚本: `scripts/generate_benchmark_queries.py` (类型 A 自动重生成；B/C 锁定)
评估脚本: `scripts/benchmark_semantic_search.py`

CI 门禁：核心指标不得低于 spec §4.7.3 目标值的 90%。
