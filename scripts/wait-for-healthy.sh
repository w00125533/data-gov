#!/usr/bin/env bash
set -euo pipefail

SERVICES=(hms-db namenode datanode resourcemanager nodemanager hive-metastore kafka starrocks neo4j)
TIMEOUT_SECONDS="${1:-240}"
DEADLINE=$(( $(date +%s) + TIMEOUT_SECONDS ))

while (( $(date +%s) < DEADLINE )); do
  all_ok=true
  for svc in "${SERVICES[@]}"; do
    state=$(docker compose -f base-compose.yml ps --format json "$svc" 2>/dev/null | head -n1 || echo '')
    if [[ -z "$state" ]]; then
      all_ok=false
      break
    fi
    running=$(echo "$state" | grep -oE '"State":"[^"]*"' | head -n1 | cut -d'"' -f4)
    health=$(echo "$state" | grep -oE '"Health":"[^"]*"' | head -n1 | cut -d'"' -f4)
    if [[ "$running" != "running" ]] || { [[ -n "$health" ]] && [[ "$health" != "healthy" ]]; }; then
      all_ok=false
      break
    fi
  done
  if $all_ok; then
    echo "All ${#SERVICES[@]} services healthy."
    exit 0
  fi
  sleep 3
done

echo "Timed out waiting for services after ${TIMEOUT_SECONDS}s." >&2
docker compose -f base-compose.yml ps >&2
exit 1
