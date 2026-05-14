#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[1/8] Waiting for base infrastructure healthy ..."
./scripts/wait-for-healthy.sh 300

echo "[2/8] Applying 01_hive_init.sql ..."
docker compose -f base-compose.yml --profile tools run --rm \
  -v "$REPO_ROOT/init-scripts:/work:ro" \
  spark \
    --conf spark.sql.catalogImplementation=hive \
    --conf spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083 \
    --conf spark.hadoop.fs.defaultFS=hdfs://namenode:8020 \
    -f /work/01_hive_init.sql

echo "[3/8] Creating Kafka topics ..."
./init-scripts/02_kafka_init.sh

echo "[4/8] Applying 03_starrocks_init.sql ..."
docker exec -i starrocks mysql -h 127.0.0.1 -P 9030 -u root < init-scripts/03_starrocks_init.sql

echo "[5/8] Initializing Neo4j schema (constraints + indexes) ..."
python init-scripts/05_neo4j_init.py

echo "[6/8] Seeding Neo4j (10 tables + ~65 fields + lineage) ..."
python init-scripts/06_neo4j_seed.py

echo "[7/8] Exporting YAML ..."
python init-scripts/07_export_yaml.py

echo "[8/8] Seeding sample data (StarRocks + Hive) ..."
python init-scripts/04_sample_data.py

echo "Bringing up FastAPI backend ..."
docker compose -f app-compose.yml up -d --build

echo "Waiting for backend healthy ..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "Backend healthy."
    echo "Init complete."
    exit 0
  fi
  sleep 2
done

echo "Backend did not become healthy in 60s." >&2
docker compose -f app-compose.yml logs --tail=100 backend >&2
exit 1
