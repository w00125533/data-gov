#!/usr/bin/env bash
set -euo pipefail

LOCAL_CONTAINERS=(neo4j)
SHARED_CONTAINERS=(hms-db namenode datanode resourcemanager nodemanager hive-metastore kafka starrocks)
TIMEOUT_SECONDS="${1:-240}"
DEADLINE=$(( $(date +%s) + TIMEOUT_SECONDS ))

check_all_healthy() {
  local healthy_list missing=0
  healthy_list=$(docker ps --filter health=healthy --format '{{.Names}}' 2>/dev/null)
  for c in "${LOCAL_CONTAINERS[@]}"; do
    if ! echo "$healthy_list" | grep -qxF "$c"; then
      missing=$((missing + 1))
    fi
  done
  for c in "${SHARED_CONTAINERS[@]}"; do
    if ! echo "$healthy_list" | grep -Eq "(^|-)${c}(-|$)"; then
      missing=$((missing + 1))
    fi
  done
  [ "$missing" -eq 0 ]
}

while (( $(date +%s) < DEADLINE )); do
  if check_all_healthy; then
    echo "All local and shared data-gov services healthy."
    exit 0
  fi
  sleep 3
done

echo "Timed out waiting for services after ${TIMEOUT_SECONDS}s." >&2
docker ps -a --format "table {{.Names}}\t{{.Status}}" >&2
exit 1
