#!/usr/bin/env bash
# Short local run: mock upstream + gateway + Go proxy + locust (1 master + 2 workers). Writes results/.
set -euo pipefail
cd "$(dirname "$0")"
export JWT_SECRET="${JWT_SECRET:-$(openssl rand -hex 32)}" ENROLL_TOKEN="${ENROLL_TOKEN:-$(openssl rand -hex 16)}"
USERS="${USERS:-40}" DURATION="${DURATION:-30s}" WORKERS="${WORKERS:-2}"
mkdir -p results; pids=()
trap 'kill ${pids[@]} 2>/dev/null || true' EXIT
uvicorn mock_upstream:app --port 9000 --log-level warning & pids+=($!)
(cd ../backend && AUDIT_PATH=/tmp/mb_lt_audit.jsonl uvicorn main:app --port 8000 --workers 1 --log-level warning) & pids+=($!)
(cd ../proxy && go build -o /tmp/mb-proxy . && UPSTREAM_URL=http://localhost:9000 LISTEN=:8443 /tmp/mb-proxy) & pids+=($!)
sleep 4
for i in $(seq "$WORKERS"); do locust -f locustfile.py --worker --master-host 127.0.0.1 >/dev/null 2>&1 & pids+=($!); done
locust -f locustfile.py --master --headless --expect-workers "$WORKERS" -u "$USERS" -r 20 -t "$DURATION" \
  --host http://localhost:8000 --csv results/run --only-summary 2>&1 | tee results/summary.txt
python3 report.py results/run_stats.csv | tee results/REPORT.md
