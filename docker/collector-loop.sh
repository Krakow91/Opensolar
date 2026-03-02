#!/usr/bin/env sh
set -eu

INTERVAL_SECONDS="${COLLECT_INTERVAL_SECONDS:-3600}"

echo "[collector] Starting loop with interval ${INTERVAL_SECONDS}s"

while true; do
  echo "[collector] Running collect.py at $(date -Iseconds)"
  if python /app/collect.py; then
    echo "[collector] Success"
  else
    echo "[collector] collect.py failed - retrying after interval" >&2
  fi
  sleep "${INTERVAL_SECONDS}"
done
