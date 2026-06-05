#!/usr/bin/env bash
set -euo pipefail
export MSYS_NO_PATHCONV=1

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
SHARED_INFRA_DIR="${SHARED_INFRA_DIR:-$REPO_ROOT/../shared-data-infra}"

if [ ! -f "$SHARED_INFRA_DIR/compose.yaml" ]; then
  echo "Shared infrastructure repo not found: $SHARED_INFRA_DIR" >&2
  exit 1
fi

echo "[0/10] Starting shared lakehouse, streaming and StarRocks infrastructure ..."
docker compose \
  -f "$SHARED_INFRA_DIR/compose.yaml" \
  -f "$SHARED_INFRA_DIR/compose.lakehouse.yaml" \
  -f "$SHARED_INFRA_DIR/compose.streaming.yaml" \
  -f "$SHARED_INFRA_DIR/compose.starrocks.yaml" \
  --profile lakehouse \
  --profile yarn \
  --profile spark-tools \
  --profile streaming \
  --profile starrocks \
  up -d

echo "[0/10] Starting data-gov local services ..."
docker compose -f base-compose.yml up -d

echo "[1/10] Waiting for base infrastructure healthy ..."
./scripts/wait-for-healthy.sh 300

echo "[2/10] Applying 01_hive_init.sql ..."
docker compose \
  -f "$SHARED_INFRA_DIR/compose.yaml" \
  -f "$SHARED_INFRA_DIR/compose.lakehouse.yaml" \
  --profile spark-tools \
  run --rm \
  -v "$REPO_ROOT/init-scripts:/work:ro" \
  spark \
    --conf spark.sql.catalogImplementation=hive \
    --conf spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083 \
    --conf spark.hadoop.fs.defaultFS=hdfs://namenode:8020 \
    -f /work/01_hive_init.sql

echo "[3/10] Creating Kafka topics ..."
./init-scripts/02_kafka_init.sh

echo "[4/10] Applying 03_starrocks_init.sql ..."
docker compose \
  -f "$SHARED_INFRA_DIR/compose.yaml" \
  -f "$SHARED_INFRA_DIR/compose.starrocks.yaml" \
  exec -T starrocks mysql -h 127.0.0.1 -P 9030 -u root < init-scripts/03_starrocks_init.sql

echo "[5/10] Initializing Neo4j schema (constraints + indexes) ..."
python init-scripts/05_neo4j_init.py

echo "[6/10] Seeding Neo4j (10 tables + ~65 fields + lineage) ..."
python init-scripts/06_neo4j_seed.py

echo "[7/10] Exporting YAML ..."
python init-scripts/07_export_yaml.py

echo "[8/10] Seeding sample data (StarRocks + Hive) ..."
python init-scripts/04_sample_data.py

echo "[9/10] Building search index offline ..."
python init-scripts/08_build_search_index.py

echo "[10/10] Bringing up FastAPI backend ..."
docker compose -f app-compose.yml up -d --build

echo "Waiting for backend healthy ..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/api/health > /dev/null 2>&1; then
    if curl -fsS http://localhost:8000/api/health | grep -q '"search"'; then
      if curl -fsS http://localhost:8000/api/health | grep -q '"status":"healthy"'; then
        echo "Backend healthy."
        echo "Init complete."
        exit 0
      fi
    fi
  fi
  sleep 3
done

echo "Backend did not become healthy in 90s." >&2
docker compose -f app-compose.yml logs --tail=100 backend >&2
exit 1
