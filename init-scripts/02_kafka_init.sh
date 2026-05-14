#!/usr/bin/env bash
# 02_kafka_init.sh — idempotent Kafka topic creation for ODS layer.
set -euo pipefail

BOOTSTRAP="${KAFKA_BOOTSTRAP:-kafka:9092}"

create_topic() {
  local name="$1"
  local partitions="${2:-3}"
  local rf="${3:-1}"
  if docker exec kafka /opt/kafka/bin/kafka-topics.sh \
      --bootstrap-server "$BOOTSTRAP" \
      --list 2>/dev/null | grep -qx "$name"; then
    echo "topic $name exists"
    return 0
  fi
  docker exec kafka /opt/kafka/bin/kafka-topics.sh \
      --bootstrap-server "$BOOTSTRAP" \
      --create \
      --topic "$name" \
      --partitions "$partitions" \
      --replication-factor "$rf"
}

create_topic ods_ue_signal 3 1
create_topic ods_gnb_alarm 3 1

echo "Kafka topics ready."
