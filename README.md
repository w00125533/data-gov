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
| P2a-5 | benchmark pipeline 完整运行 (60 queries, 合法指标, CI 门禁脚本) | `tests/search/test_benchmark.py::test_benchmark_pipeline_runs_and_produces_expected_structure` ；CI 门禁 `scripts/benchmark_semantic_search.py --bootstrap-from-seed` |
| P2a-6 | `/api/search?q=&type=&k=` 返回结构 | `tests/search/test_api_search.py::TestSearchEndpoint::test_get_search_returns_results_for_known_table` |
| P2a-7 | `/api/health` 含 search 组件 | `tests/search/test_api_search.py::TestHealthIntegration::test_health_now_includes_search_component` |
| P2a-8 | bge 不可用时降级为纯 BM25 | `tests/search/test_searcher.py::test_searcher_skip_dense_when_embedder_unavailable` |
| P2a-9 | LLM rerank 触发与解析降级 | `tests/search/test_rerank.py::*` |

跑全部 slice 2a 测试：

```bash
# 单元测试 (无需外部依赖)
python -m pytest tests/search -v

# 集成测试 (需 base-compose + Neo4j seeded)
python -m pytest tests/search -v -m infra

# Benchmark CI 门禁 (基础模式: BM25 + Dense RRF)
python scripts/benchmark_semantic_search.py

# Benchmark CI 门禁 (LLM 增强: 低置信度查询触发 DeepSeek rerank)
python scripts/benchmark_semantic_search.py --use-rerank

# 使用 seed data 离线跑 (不需要 Neo4j)
python scripts/benchmark_semantic_search.py --bootstrap-from-seed
```


## Acceptance coverage (Phase 2 — slice 2b)

| Case | Verifies | Test |
|------|----------|------|
| P2b-1 | classifier 三意图分类 + 关键词降级 | `tests/agent/nodes/test_classifier.py` |
| P2b-2 | forward_etl / reverse_synth 抽取与表搜索 | `tests/agent/nodes/test_forward_etl.py` + `test_reverse_synth.py` |
| P2b-3 | pipeline_parse 上溯链路 | `tests/agent/nodes/test_pipeline_parse.py` |
| P2b-4 | gap_check + gap_proposal 子流程 | `tests/agent/nodes/test_gap_check.py` + `test_gap_proposal.py` |
| P2b-5 | code_generate + dry_run + Agent 层 3 轮重试 | `tests/agent/nodes/test_code_generate.py` + `test_dry_run.py` + `tests/agent/test_graph_routing.py` |
| P2b-6 | schema_evolve → validate → apply 全链 | `tests/agent/nodes/test_schema_evolve.py` / `test_schema_validate.py` / `test_schema_apply.py` |
| P2b-7 | YAML 同步 + git commit + Change.commit_hash | `tests/agent/test_yaml_sync.py` + `test_schema_apply.py` |
| P2-1 | forward_etl → spark_sql 路径 (mock LLM/sandbox) | `tests/agent/test_graph_e2e.py::test_p2_1_*` |
| P2-8 | NL→新增字段 → Neo4j + YAML (mock) | `tests/agent/test_graph_e2e.py::test_p2_8_*` |
| P2-9 | 删除有下游引用的字段被拒绝 | `tests/agent/test_graph_e2e.py::test_p2_9_*` |
| P2-11 | gap_check missing_table | `tests/agent/test_graph_e2e.py::test_p2_11_*` |
| Chat | SSE 流式对话 `/api/chat/*` | `tests/agent/test_api_chat.py` |
| Schema | `/api/schema/apply` + evolution timeline | `tests/agent/test_api_schema.py` |

跑 slice 2b 全部测试：

```bash
python -m pytest tests/agent -v
```

**Status in slice 2c**：沙箱真实执行、execute_with_retry、sandbox_stub 替换均已落地 — 见下方 slice 2c 验收表。

## Acceptance coverage (Phase 2 — slice 2c)

| Case | Verifies | Test |
|------|----------|------|
| P2c-1 | 模板加载与占位符注入 | `tests/sandbox/test_templates.py` |
| P2c-2 | Maven 编译成功 / 失败错误解析 | `tests/sandbox/test_compile.py` + `test_compile_real.py` (infra) |
| P2c-3 | HDFS CLI 包装 (put/cat/mkdir/rm/ls) | `tests/sandbox/test_hdfs.py` |
| P2c-4 | YARN RM REST 轮询 + 终态判定 | `tests/sandbox/test_yarn.py` |
| P2c-5 | spark-submit / flink run app_id 解析 | `tests/sandbox/test_submit.py` |
| P2c-6 | SandboxController 全链路单元 (mock) | `tests/sandbox/test_controller.py` |
| P2c-7 | sandbox 层 execute_with_retry (mock LLM) | `tests/sandbox/test_retry.py` |
| P2c-8 | sandbox_stub 重新导出真实 controller | `tests/agent/test_sandbox_stub.py` |
| P2-4 | Spark SQL dry-run (真实 YARN) | `tests/sandbox/test_p2_acceptance.py::test_p2_4_*` |
| P2-5 | Flink SQL dry-run (Kafka source + TUMBLE) | `tests/sandbox/test_p2_acceptance.py::test_p2_5_*` |
| P2-6 | Java Flink dry-run | `tests/sandbox/test_p2_acceptance.py::test_p2_6_*` |
| P2-7 | 沙箱层编译失败自动重试 (真实 LLM) | `tests/sandbox/test_p2_acceptance.py::test_p2_7_*` |

跑 slice 2c 全部测试：

```bash
# 单元 (不需要外部依赖)
pytest tests/sandbox -v -m "not infra"

# 集成 (需要 backend 容器内, base-compose + Neo4j seeded)
docker compose -f app-compose.yml exec backend pytest tests/sandbox -v -m infra
```

**Phase 2 收尾确认（同时跑 2a + 2b + 2c）**：

```bash
docker compose -f app-compose.yml exec backend pytest -v -m "not infra"
docker compose -f app-compose.yml exec backend pytest -v -m infra
```
