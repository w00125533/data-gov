# data-gov

Wireless RNO Data Semantic Service — PoC.

## Quick start (Phase 1, slices 1a + 1b)

```bash
cp .env.example .env
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh        # runs all 7 init scripts + brings up backend
pip install -e ".[dev]"
pytest -m infra                # P1-1..P1-8 should all pass
```

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
