# data-gov

Wireless RNO Data Semantic Service — PoC.

## Quick start (slice 1a: base infrastructure)

```bash
cp .env.example .env
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh           # waits for healthy → runs 01..04
pip install -e ".[test]"
pytest -m infra                    # P1-1..P1-4 should all pass
```

## Acceptance coverage (Phase 1, slice 1a)

| Case | Verifies | Test |
|------|----------|------|
| P1-1 | All 9 compose services healthy + NN/RM UIs reachable | `tests/infra/test_compose_health.py::test_p1_1_all_services_healthy` |
| P1-2 | Hive external table create/insert/select via Spark | `tests/infra/test_hive_external_table.py::test_p1_2_hive_external_table_roundtrip` |
| P1-3 | Kafka produce/consume on `ods_ue_signal` | `tests/infra/test_kafka_pubsub.py::test_p1_3_kafka_produce_consume_ods_ue_signal` |
| P1-4 | StarRocks `ads_cell_profile` rows after seeding | `tests/infra/test_starrocks_query.py::test_p1_4_starrocks_ads_cell_profile_has_rows` |

Deferred to slice 1b: Neo4j seed (`05/06/07`), FastAPI metadata CRUD (P1-6), lineage API (P1-7), Hive reverse-synth seed (P1-8).

See `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md` for full design.
