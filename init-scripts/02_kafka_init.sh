#!/usr/bin/env bash
# 02_kafka_init.sh — idempotent Kafka topic creation for ODS layer.
# Run from repo root.  MSYS_NO_PATHCONV prevents Git Bash from mangling
# /opt/… paths inside docker exec.
set -euo pipefail
export MSYS_NO_PATHCONV=1

BOOTSTRAP="${KAFKA_BOOTSTRAP:-kafka:9092}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARED_INFRA_DIR="${SHARED_INFRA_DIR:-$REPO_ROOT/../shared-data-infra}"
SHARED_COMPOSE=(
  docker compose
  -f "$SHARED_INFRA_DIR/compose.yaml"
  -f "$SHARED_INFRA_DIR/compose.streaming.yaml"
)

create_topic() {
  local name="$1"
  local partitions="${2:-3}"
  local rf="${3:-1}"
  if "${SHARED_COMPOSE[@]}" exec -T kafka kafka-topics \
      --bootstrap-server "$BOOTSTRAP" \
      --list 2>/dev/null | grep -qx "$name"; then
    echo "topic $name exists"
    return 0
  fi
  "${SHARED_COMPOSE[@]}" exec -T kafka kafka-topics \
      --bootstrap-server "$BOOTSTRAP" \
      --create \
      --topic "$name" \
      --partitions "$partitions" \
      --replication-factor "$rf"
}

create_topic ods_ue_signal 3 1
create_topic ods_gnb_alarm 3 1

echo "Kafka topics ready."
