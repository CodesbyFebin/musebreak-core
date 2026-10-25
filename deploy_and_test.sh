#!/usr/bin/env bash
# Bring the stack up and run the real end-to-end check with a freshly ENROLLED key.
# Fails on ANY non-200 Gate2 (403 is a failure, not "secure"), and requires replay -> 401.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { cp .env.example .env
  sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$(openssl rand -hex 32)/; s/^REDIS_PASSWORD=.*/REDIS_PASSWORD=$(openssl rand -hex 16)/; s/^ENROLL_TOKEN=.*/ENROLL_TOKEN=$(openssl rand -hex 16)/" .env; }
set -a; . ./.env; set +a
docker compose up -d --build redis backend proxy mock-upstream
for i in $(seq 30); do curl -fs http://localhost:8000/health >/dev/null && break; sleep 1; done
python3 tools/enroll_dev_key.py --api http://localhost:8000 --out /tmp/musebreak_dev_key.json
METAKEY_FILE=/tmp/musebreak_dev_key.json PROXY_URL=http://localhost:8443 node hardware/metakey_sim.js http://localhost:8000
echo "ALL CHECKS PASSED"
