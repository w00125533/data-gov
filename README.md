# data-gov

Wireless RNO Data Semantic Service — PoC.

## Quick start (slice 1a: base infrastructure)

```bash
cp .env.example .env
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh
pip install -e ".[test]"
pytest -m infra
```

## Layout

- `base-compose.yml` — infrastructure services (HDFS / YARN / Hive / Kafka / StarRocks / Neo4j)
- `init-scripts/` — post-start seed scripts (Hive DDL, Kafka topics, StarRocks data)
- `tests/infra/` — pytest integration tests (P1-1..P1-4)

See `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md` for full design.
