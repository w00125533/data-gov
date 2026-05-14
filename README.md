# data-gov

Wireless RNO Data Semantic Service — PoC.

## Quick start (Phase 1, slices 1a + 1b)

```bash
cp .env.example .env
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh                 # runs all 8 init steps + brings up backend
python -m pip install -e ".[dev]"
python -m pytest -m infra -v            # P1-1..P1-8 should all pass
```

> **Windows 注意**：
> - 推荐在 **PowerShell** 中执行上述命令。
> - 如果使用 **Git Bash**，脚本已内置 `MSYS_NO_PATHCONV=1` 防止 MSYS2 路径自动转换。
> - 使用 `python -m pytest` 而非直接 `pytest`，避免 `pytest` 不在 PATH 的问题。
> - 首次冷启动需拉取多个 Docker 镜像（~5GB），请耐心等待。

## Acceptance coverage (Phase 1)

| Case | Verifies | Test |
|------|----------|------|
| P1-1 | All 9 base-compose services healthy + NN/RM UIs reachable | `tests/infra/test_compose_health.py::test_p1_1_all_services_healthy` |
| P1-2 | Hive external table create/insert/select via Spark | `tests/infra/test_hive_external_table.py::test_p1_2_hive_external_table_roundtrip` |
| P1-3 | Kafka produce/consume on `ods_ue_signal` | `tests/infra/test_kafka_pubsub.py::test_p1_3_kafka_produce_consume_ods_ue_signal` |
| P1-4 | StarRocks `ads_cell_profile` rows after seeding | `tests/infra/test_starrocks_query.py::test_p1_4_starrocks_ads_cell_profile_has_rows` |
| P1-5 | Neo4j seeded (10 tables / ~65 fields) + 10 YAML files | `tests/infra/test_neo4j_seed.py` + `tests/infra/test_yaml_export.py` |
| P1-5b | Neo4j constraints + indexes present | `tests/infra/test_neo4j_init.py::test_p1_5b_*` |
| P1-6 | Metadata CRUD API roundtrip | `tests/api/test_metadata_crud.py::test_p1_6_metadata_crud_roundtrip` |
| P1-7 | Lineage `?direction=down` returns dws_* downstream of dwd_session_qos | `tests/api/test_lineage.py::test_p1_7_lineage_downstream_dwd_session_qos` |
| P1-8 | `generate_fake_data(table="dwd_session_qos", rows=5)` writes valid rows | `tests/infra/test_hive_reverse_synth.py::test_p1_8_generate_fake_data_dwd_session_qos` |

Deferred to Phase 2 (slices 2a-c): semantic search, LangGraph Agent, sandbox.

See `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md` for full design.

## Acceptance coverage (Phase 2 — slice 2a)

| Case | Verifies | Test |
|------|----------|------|
| P2a-1 | 中文 NL 查询命中表 (dws_cell_hourly) | `tests/search/test_searcher_integration.py::test_p2a_1_search_yields_dws_cell_hourly_for_chinese_query` |
| P2a-2 | 字段级 doc 可被命中 | `tests/search/test_searcher_integration.py::test_p2a_2_search_for_field_returns_field_doc` |
| P2a-3 | index_version 单调正向 | `tests/search/test_searcher_integration.py::test_p2a_3_index_version_positive_after_build` |
| P2a-4 | 增量 upsert 立即可查 | `tests/search/test_searcher_integration.py::test_p2a_4_incremental_upsert_visible_in_search` |
| P2a-5 | 60 条 benchmark 达到目标 90% | `tests/search/test_benchmark.py::test_benchmark_meets_at_least_90pct_of_targets` |
| P2a-6 | `/api/search?q=&type=&k=` 返回结构 | `tests/search/test_api_search.py::test_get_search_returns_results_for_known_table` |
| P2a-7 | `/api/health` 含 search 组件 | `tests/search/test_api_search.py::test_health_now_includes_search_component` |
| P2a-8 | bge 不可用时降级为纯 BM25 | `tests/search/test_searcher.py::test_searcher_skip_dense_when_embedder_unavailable` |
| P2a-9 | LLM rerank 触发与解析降级 | `tests/search/test_rerank.py::*` |

跑全部 slice 2a 测试：

```bash
pytest tests/search -v
pytest tests/search -v -m infra   # 需 base-compose + Neo4j seeded
python scripts/benchmark_semantic_search.py
```

Deferred to slice 2b: LangGraph Agent (forward_etl / reverse_synth / schema_evolve), `/api/chat/*`, gap_check / gap_proposal.
Deferred to slice 2c: 沙箱 (Spark SQL / Flink SQL / Java Flink dry_run).
