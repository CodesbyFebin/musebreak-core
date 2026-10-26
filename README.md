# MuseBreak 🔑 — Zero-Trust gateway for Muse models

Zero-Trust gateway + **Business OS** (`/os`, WebLLM). See [`docs/README_MASTER.md`](docs/README_MASTER.md) and [`docs/BUSINESS_OS.md`](docs/BUSINESS_OS.md).

> **No password alone can reach Muse Wonder.** You need a physical **MetaKey**: NFC tap + QR intent.
> Both gates pass → forward. MIT licensed.

📘 **Full release briefing, architecture, Real-vs-Simulated table and run guide: [`docs/README_MASTER.md`](docs/README_MASTER.md)**

```
Browser/Phone ──Gate1: /login (JWT 5 min, bound to sha256(device fingerprint))──► FastAPI gateway ──► Redis
      │        ──/challenge──► 32-byte secrets.token_bytes challenge + QR nonce (30 s TTL, single-use)
      ▼
  MetaKey  ── NFC: HMAC-SHA256(secret, challenge|fp|key_id|counter)   (counter must strictly increase)
           ── QR : ECDSA P-256 over "MUSEBREAK-INTENT|cid|nonce|model" after button press
      │
      └──/authorize──► GETDEL challenge (atomic) → compare_digest HMAC → P-256 verify → counter CAS
                       → red tier needs human approver → Wonder token (60 s, typ=wonder, gate1&&gate2)
                                   │
           /muse/query (guard → Metabolic sim → Meta Model API*)   or   Go proxy :8443 → vLLM / upstream
```
\* `META_MODEL_API_URL` / `META_MODEL_API_KEY` are **your** configuration. This repo does not assume or
hard-code any real Meta endpoint; when unset, `/muse/query` returns a response clearly labelled `SIMULATED`.

## Repo layout
| Path | What |
|---|---|
| `backend/main.py` | FastAPI: `/login` `/challenge` `/authorize` `/muse/query` `/audit` `/keys/enroll` `/health` |
| `backend/crypto.py` | challenges, HMAC (`hmac.compare_digest`), P-256 verify (raw r‖s or DER) |
| `backend/store.py` | Redis (`SET EX`, atomic `GETDEL`, Lua counter CAS) or in-memory TTL fallback |
| `backend/audit.py` | append-only JSONL, SHA-256 hash chain, `verify_chain()` |
| `backend/metabolic_sim.py` | Metabolic M1 latency/cost **simulator** |
| `backend/guard/review_engine.py` | regex prefilter + OpenAI-compatible LLM review (vLLM), **fail-closed** |
| `backend/tests/test_gates.py` | pytest: happy path, replay, expiry, bad HMAC, bad QR sig, no Gate1, counter, guard… |
| `proxy/` | Go reverse proxy: verifies HS256 Wonder token + fingerprint binding (stdlib only) + tests |
| `frontend/` | Next.js 14: Access Control, **Business OS `/os` (WebLLM)**, Swarm `/swarm`, `/auth`, `/verify` |
| `backend/os_plane/` | Task router, Jev gate, zkVM heartbeat (`docs/BUSINESS_OS.md`) |
| `cli/musebreak_cli/benchmark.py` | Benchmark open-weight models as defensive agents (`docs/BENCHMARK_HARNESS.md`) |
| `hardware/metakey_sim.js` | Node phone sim — same HMAC + P-256 as firmware; runs the full E2E flow |
| `hardware/metakey_esp32.ino` | ESP32 + PN532 + e-ink prototype (NVS counter) |
| `hardware/WIRING.md` | STM32 + SE050 (I²C 0x48) + PN532 (SPI) + e-ink (SPI) reference wiring |
| `firmware/metakey_auth.c` | SE050 NFC-response core with non-volatile counter; host-testable (`-DHOST_SIM`) |
| `cage/vm_manager.py`, `cage/network_jail.py`, `cage/fetch_firecracker.sh` | Firecracker microVM per agent + nftables jail |
| `loadtest/` | Locust (master/workers) full-flow load test through the Go proxy + mock upstream |
| `tools/enroll_dev_key.py` | generate + enrol a dev MetaKey, export `dev_key.json` |
| `deploy_and_test.sh` | docker compose up + enrolled-key E2E (403 = failure, replay must be 401) |
| `docker-compose.open.yml` | Open-weight Meta stack: OGX/Llama Stack + Ollama + gateway/proxy |
| `llama-stack-run.yaml` | Reference Llama Stack run config (HF ids for inference/safety/vision) |
| `backend/open_source.py` | `USE_OPEN_SOURCE_ONLY` adapter → OpenAI-compat Llama Stack |
| `docs/OPEN_SOURCE_STACK.md` | Model map, verified ids, hardware honesty, run steps |
| `services/{sam,dinov2,seamlessm4t}/` | Optional HF helpers (local Dockerfiles, profile `vision-extras`) |

## Run locally (no Docker)
```bash
# backend
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
pytest -q tests
export JWT_SECRET=$(openssl rand -hex 32) ENROLL_TOKEN=$(openssl rand -hex 16)   # optional: REDIS_URL=redis://:pw@localhost:6379/0
uvicorn main:app --port 8000

# phone simulator E2E (demo key)
node hardware/metakey_sim.js http://localhost:8000

# Go proxy (same JWT_SECRET) + mock upstream, then E2E with a freshly enrolled key
(cd loadtest && uvicorn mock_upstream:app --port 9000 &)
(cd proxy && go test ./... && UPSTREAM_URL=http://localhost:9000 go run .) &
python3 tools/enroll_dev_key.py --out dev_key.json
METAKEY_FILE=dev_key.json PROXY_URL=http://localhost:8443 node hardware/metakey_sim.js

# frontend
cd frontend && npm install && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```
Demo login: `judge` / `musebreak` (change via `DEMO_USER` / `DEMO_PASSWORD`).

## Trust Plane (hash-commitment MVP)

> **Not a real ZK proof.** `backend/zkvm/` commits statements with SHA-256 over canonical JSON.
> Proof encoding is 32-byte digest + 224 zero bytes (256 bytes total) — an encoding artifact.
> Responses include `simulated: true` and `implementation: "hash-commitment-mvp"`.
> Future work: SP1 / RISC Zero. Details: [`docs/TRUST_PLANE.md`](docs/TRUST_PLANE.md).

```bash
# from backend/
pytest -q tests/test_zkvm.py
# CLI
musebreak zkvm prove --demo
musebreak voice --lang ml   # scaffold
musebreak learn             # scaffold
# UI
# http://localhost:3000/verify
# http://localhost:3000/auth   (MetaKey UTR + WebAuthn binding)
```

**MetaKey online plane:** `/auth/draft` → `/auth/bind` (real WebAuthn assertion verification via `webauthn`, with a labelled simulated fallback) → `/auth/approve` → `/auth/verify`, committed by the `fido_binding` circuit. The physical MetaKey (FIDO2 certification, IP68, secure element, wallet) is a product concept only — see [`docs/METAKEY_PRODUCT.md`](docs/METAKEY_PRODUCT.md).

## Run with Docker
```bash
cp .env.example .env   # set JWT_SECRET, REDIS_PASSWORD, ENROLL_TOKEN (deploy_and_test.sh can generate them)
./deploy_and_test.sh                    # redis + backend + proxy + mock upstream, then E2E
docker compose up --build frontend      # UI on :3000
docker compose --profile gpu up vllm    # optional open-weight model via vLLM (set UPSTREAM_URL/GUARD_LLM_URL)
```

## 60-second demo script
1. **0–10 s** — Open `localhost:3000`. "Password alone gets you nothing." Log in → **Gate 1 green** (JWT + device fingerprint).
2. **10–25 s** — Click the MetaKey: NFC rings pulse → HMAC-SHA256 over the 32-byte challenge + counter.
3. **25–40 s** — QR panel shows the rotating intent (model + tier, 30 s countdown). *Scan & approve* → P-256 signature verified → **Gateway OPEN**.
4. **40–50 s** — Query "Explain Metabolic vs Jalapeño" → routed through the Metabolic M1 simulator (TTFT, decode, cost) → Muse Wonder (or a labelled simulated reply).
5. **50–60 s** — Audit panel: `gate1_pass`, `gate2_pass` with HMAC, signature, counter, device fingerprint, key id; **chain valid**. Bonus: re-send the same authorize → 401 (replay).

## Security model
- Challenges: `secrets.token_bytes(32)`, 30 s TTL, consumed with atomic `GETDEL` — replay/expiry → 401.
- Gate 1 and Wonder tokens are real HS256 JWTs (PyJWT); the Go proxy re-verifies signature, `alg`, `typ`, gates, `exp`, and fingerprint binding. Gate-1 tokens cannot query.
- Monotonic counter is checked **after** the crypto passes (forged taps can't burn counters) and must strictly increase per key (Redis Lua CAS) — defeats cloned keys / recorded taps.
- Red tier: requires `human_approver` at Gate 2 and an LLM guard verdict; guard unreachable ⇒ blocked.
- `/keys/enroll` is disabled unless `ENROLL_TOKEN` is set.

## ⚠️ Demo key material
`hardware/demo_metakey_private.pem` and the demo HMAC secret are **public** so the demo works out of the box.
Anyone can impersonate the demo key. For any real use, enrol your own keys (`tools/enroll_dev_key.py`), override
`METAKEY_ID/METAKEY_SECRET/METAKEY_PUBKEY_PEM`, and keep secrets in a secure element.



## Access Control web command center
The Next.js frontend (`frontend/`) ships a dark neon **ACCESS CONTROL** dashboard that mirrors the two-gate flow:

```bash
# terminal A — gateway
uvicorn backend.main:app --reload --port 8000
# terminal B — UI
cd frontend && npm install && npm run dev
# open http://localhost:3000
```

- Sidebar: Overview · Sessions · MetaKeys · Model routing · Audit log · Settings (`⌘1`–`⌘6`).
- Overview runs Gate1 on load (when the gateway is reachable), shows live session/challenge countdowns, and the **SIMULATE TAP & APPROVE** button executes the real Gate2 flow via `lib/metakey.ts` (NFC HMAC + P-256 QR) → `/authorize`.
- When the gateway is unreachable the UI falls back to a clearly-labeled **LOCAL DEMO / SIMULATOR** mode — never presents fake data as live.
- Classic step-by-step demo remains at `/legacy`. Audit table at `/audit` reads `GET /audit`.

## Command center CLI + agent swarm
A `musebreak` CLI drives a **sandboxed, role-based agent swarm** on top of the gateway. It runs offline in mock
mode by default, and every step is wrapped by the 2-gate auth + guard + audit model. Exec steps inside the
**isolated Kali Firecracker microVM** are **dry-run unless** you pass `--i-am-authorized` and a named `--approver`
(red tier always needs the approver). This is a **defensive, authorized-lab** tool — no attack tooling ships here.
```bash
pip install -e cli            # provides `musebreak`
musebreak agents list         # roles -> model tier routing
musebreak sandbox up --session demo
musebreak swarm run cli/missions/example_mission.yaml                 # exec steps DRY-RUN
musebreak swarm run cli/missions/example_mission.yaml --i-am-authorized --approver "ciso@lab (#1234)"
musebreak audit tail
```
Design + safety model: [`docs/CLI_SWARM_DESIGN.md`](docs/CLI_SWARM_DESIGN.md). Roles: Planner, Recon-Analyst,
ExploitDev (defensive/lab-only), Reviewer/Guard, Reporter. Tiers: Muse Spark → Wonder → Wonderful/Wonderful-Cyber
→ Glimmer/Llama (open-weight). Muse Code is the agent runtime / tool-calling layer; all model calls route through
the gateway.


## Open-source stack
Run MuseBreak offline with **open-weight Meta models only** (Llama Stack / OGX + Ollama) — no closed APIs.
Compose file: [`docker-compose.open.yml`](docker-compose.open.yml). Full mapping, verified image/HF ids,
hardware caveats, and run steps: [`docs/OPEN_SOURCE_STACK.md`](docs/OPEN_SOURCE_STACK.md).

```bash
cp .env.example .env   # set JWT_SECRET, REDIS_PASSWORD
docker compose -f docker-compose.open.yml up --build
# then pull models into the ollama service (see the doc — 70B needs serious GPU/quantization)
```

When `USE_OPEN_SOURCE_ONLY=true`, the gateway routes `/muse/query` and the guard at an OpenAI-compatible
Llama Stack endpoint (`LLAMA_STACK_URL`, default port **8321**). If nothing is reachable, responses stay
clearly labelled `SIMULATED`. Optional SAM / DINOv2 / SeamlessM4T helpers live under `services/` behind
compose profile `vision-extras` (local Dockerfiles — we do not invent registry images).

## Master prompt
See [`MASTER_PROMPT.md`](MASTER_PROMPT.md).

## Load test (local, 40 users, 2 Locust workers, 30 s, mock upstream 20 ms)
See `loadtest/results/REPORT.md`. Run: `cd loadtest && ./run_local.sh`.

MIT © MuseBreak contributors. "Meta", "Muse", "Metabolic" are referenced descriptively; this is an independent hackathon project.
