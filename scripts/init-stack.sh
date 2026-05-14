#!/usr/bin/env bash
# init-stack.sh — wait for healthy, then run init scripts 01..04 in order.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[1/5] Waiting for all services healthy ..."
./scripts/wait-for-healthy.sh 300

echo "[2/5] Applying 01_hive_init.sql via ephemeral Spark client ..."
docker run --rm \
  --network data-gov_default \
  -v "$REPO_ROOT/init-scripts:/work:ro" \
  -v "$REPO_ROOT/docker/hadoop-conf:/etc/hadoop:ro" \
  -v "$REPO_ROOT/docker/hive-conf:/opt/spark/conf/hive-site.xml.d:ro" \
  apache/spark:3.5.4 \
  /opt/spark/bin/spark-sql \
    --conf spark.sql.catalogImplementation=hive \
    --conf spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083 \
    --conf spark.hadoop.fs.defaultFS=hdfs://namenode:8020 \
    -f /work/01_hive_init.sql

echo "[3/5] Creating Kafka topics ..."
./init-scripts/02_kafka_init.sh

echo "[4/5] Applying 03_starrocks_init.sql ..."
docker exec -i starrocks mysql -h 127.0.0.1 -P 9030 -u root < init-scripts/03_starrocks_init.sql

echo "[5/5] Seeding StarRocks sample data ..."
python init-scripts/04_sample_data.py

echo "Init complete."
