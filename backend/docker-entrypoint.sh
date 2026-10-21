#!/bin/sh
# With TEMPORAL_EMBEDDED=true the container runs its own Temporal dev server (PoC without
# Temporal Cloud, decision 43): in-process persistence on the instance's disk, lost on restart;
# the dispatcher's reconcile step marks such runs failed. Otherwise the worker connects to
# TEMPORAL_ADDRESS as configured (local dev server or Temporal Cloud).
set -e
if [ "${TEMPORAL_EMBEDDED:-false}" = "true" ]; then
  export TEMPORAL_ADDRESS="${TEMPORAL_ADDRESS:-127.0.0.1:7233}"
  export TEMPORAL_NAMESPACE="${TEMPORAL_NAMESPACE:-default}"
  export TEMPORAL_API_KEY=""
  temporal server start-dev --ip 127.0.0.1 --port 7233 --headless --log-level warn \
    --db-filename /tmp/temporal.db &
  i=0
  until temporal operator cluster health --address 127.0.0.1:7233 >/dev/null 2>&1; do
    i=$((i + 1)); [ "$i" -ge 60 ] && { echo "embedded Temporal did not start" >&2; exit 1; }
    sleep 1
  done
  echo "embedded Temporal dev server ready on 127.0.0.1:7233 (not durable across restarts)"
fi
exec python -m worker.main
