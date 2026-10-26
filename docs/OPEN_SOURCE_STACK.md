# MuseBreak open-source Meta stack

Goal: let judges run MuseBreak **offline** with **open-weight Meta models only** — no closed APIs.
Builds on the existing Zero-Trust gateway, Go proxy, in-process guard, and CLI. Nothing here
claims a proprietary Meta Muse endpoint exists.

```
                    ┌─────────────────────────────────────────┐
  MetaKey / CLI ──► │ musebreak-gateway :8000                 │
                    │  Gate1 JWT + Gate2 NFC/QR → Wonder tok  │
                    │  guard (regex + optional Llama-Guard)   │
                    │  /muse/query ──OpenAI chat───────────┐  │
                    └──────────────────────────────────────┼──┘
                                                           ▼
                    ┌─────────────────────────────────────────┐
                    │ llama-stack / OGX :8321                 │
                    │  ogxai/distribution-starter:1.5.0       │
                    │  POST /v1/chat/completions              │
                    └──────────────────┬──────────────────────┘
                                       │ OLLAMA_URL
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │ ollama :11434   (local weights)          │
                    │  llama3.3:70b / llama-guard3:8b / …     │
                    └─────────────────────────────────────────┘

  musebreak-proxy :8443 ──► same stack (JWT check) ──► upstream
  redis ── sessions / counters
  [profile vision-extras] sam / dinov2 / seamlessm4t  (local Dockerfiles → HF ids)
```

## Model mapping (proprietary label → open HF id → where used)

| Product / label | Open HF id (verified HTTP 200) | Ollama tag (local pull) | Used by |
|---|---|---|---|
| Muse Wonderful / Wonder | `meta-llama/Llama-3.3-70B-Instruct` | `llama3.3:70b` | orchestrator, `/muse/query`, INFERENCE_MODEL |
| Muse Code | `meta-llama/CodeLlama-13b-Instruct-hf` | `codellama:13b-instruct` | CLI code agent |
| Muse Spark / Glimmer / recon workers | `meta-llama/Llama-3.1-8B-Instruct` | `llama3.1:8b` | green-tier / workers |
| Guard prefilter | `meta-llama/Llama-Guard-3-8B` | `llama-guard3:8b` | SAFETY_MODEL, `GUARD_LLM_MODEL` |
| Vision | `meta-llama/Llama-3.2-11B-Vision-Instruct` | `llama3.2-vision` | VISION_MODEL (declared) |
| Vision (base, non-Instruct) | `meta-llama/Llama-3.2-11B-Vision` | — | alternate HF id |
| SAM (segmentation) | `facebook/sam2.1-hiera-large` | — | `services/sam` (profile) |
| DINOv2 | `facebook/dinov2-giant` | — | `services/dinov2` (profile) |
| SeamlessM4T | `facebook/seamless-m4t-v2-large` | — | `services/seamlessm4t` (profile) |

**SAM note:** `facebook/sam3` and `facebook/sam3.1` also exist on Hugging Face (gated, verified 2026-10-26).
We default to **ungated** SAM 2.1 (`facebook/sam2.1-hiera-large`). There is **no** official
`facebook/sam2.1` Docker Hub image — we ship a local Dockerfile under `services/sam/`.

**zkVM:** design / future work only. Not implemented in this repo. Do not treat as shipped.

## Exact run steps

```bash
cp .env.example .env
# set JWT_SECRET, REDIS_PASSWORD (required by compose)

# 1) Start the light open stack (does NOT download 70B weights by itself)
docker compose -f docker-compose.open.yml up --build

# 2) Pull open models into the ollama service (host needs disk + preferably GPU)
docker compose -f docker-compose.open.yml exec ollama ollama pull llama3.3:70b
docker compose -f docker-compose.open.yml exec ollama ollama pull llama-guard3:8b
# optional vision:
docker compose -f docker-compose.open.yml exec ollama ollama pull llama3.2-vision

# CPU / small-box smoke (do NOT claim 70B fits):
#   INFERENCE_MODEL=llama3.1:8b SAFETY_MODEL=llama-guard3:1b \
#   OPEN_SOURCE_MODEL_STYLE=ollama \
#   docker compose -f docker-compose.open.yml up --build

# 3) Gateway is in open-source mode:
#    USE_OPEN_SOURCE_ONLY=true
#    LLAMA_STACK_URL=http://llama-stack:8321
#    META_MODEL_API_URL=http://llama-stack:8321/v1/chat/completions
#    GUARD_LLM_URL=http://llama-stack:8321/v1

# 4) Optional heavy helpers (build local Dockerfiles; weights NOT bundled):
docker compose -f docker-compose.open.yml --profile vision-extras up --build
```

Gateway without Docker (same adapter):

```bash
export USE_OPEN_SOURCE_ONLY=true
export LLAMA_STACK_URL=http://localhost:8321
cd backend && uvicorn main:app --port 8000
# If Llama Stack is down, /muse/query returns a clearly labelled SIMULATED response.
```

## Images verified vs flagged

| Image / artifact | Status |
|---|---|
| `ogxai/distribution-starter:1.5.0` | **Verified** on Docker Hub (manifest 200, digest `sha256:7f24b91f…`, tags updated 2026-10) — current official Llama Stack → OGX starter |
| `ollama/ollama:latest` | **Verified** (Docker Hub `ollama/ollama`) |
| `redis:7-alpine` | **Verified** (same as main compose) |
| `llamastack/distribution-ollama` | **Archived** on Docker Hub — do not prefer; kept only as historical name in comments |
| `llamastack/distribution-starter` | Named in OGX docs table; Hub search did **not** resolve a live `llamastack/*` starter — use `ogxai/…` |
| Any `facebook/sam*` / `dinov2` / `seamless` **Docker Hub** image | **Not verified / not used** — local `services/*/Dockerfile` instead |

## What's real vs placeholder / hardware

| Piece | Reality on this box / typical judge laptop |
|---|---|
| Compose file + YAML + gateway adapter | **Real** (lint/import tested). |
| Llama Stack OpenAI `/v1/chat/completions` | **Real API shape** (OGX docs). Not exercised here without Docker+GPU. |
| 70B / 11B-Vision weights | **Not run in CI.** Need multi-GPU or a hosted open endpoint. |
| Simulated fallback | **Real** — when upstream is unset or unreachable, responses are labelled `SIMULATED`. |
| `services/sam|dinov2|seamlessm4t` | **Scaffold only** — declare HF ids, `/load` does not download weights at build. |
| zkVM | **Future work** — not implemented. |
| Fireworks / Together / Baseten / Modal | Optional remote OpenAI-compatible backends: set `META_MODEL_API_URL` / `VLLM_URL` / provider API keys on the starter image (`FIREWORKS_API_KEY`, `TOGETHER_API_KEY`, …). Still open-weight models; you are not required to use Meta-closed APIs. |

### Hardware notes

- **Llama-3.3-70B-Instruct**: typically ≥2×80GB or heavy quantization via Ollama; not a laptop default.
- **Llama-Guard-3-8B**: fits a single mid-range GPU; `llama-guard3:1b` exists for tiny boxes.
- **Llama-3.2-11B-Vision**: needs a multimodal backend (Ollama `llama3.2-vision` or vLLM).
- **SAM / DINOv2 / SeamlessM4T**: GPU strongly recommended; CPU torch wheels are for smoke only.

## Adapter knobs

| Env | Meaning |
|---|---|
| `USE_OPEN_SOURCE_ONLY=true` | Gateway fills `META_MODEL_API_*` + `GUARD_LLM_*` from `LLAMA_STACK_URL` if unset |
| `LLAMA_STACK_URL` | e.g. `http://localhost:8321` |
| `LLAMA_STACK_OPENAI_BASE` | Override OpenAI root (default `$LLAMA_STACK_URL/v1`; older stacks used `/v1/openai/v1`) |
| `OPEN_SOURCE_MODEL_STYLE=ollama` | Prefer Ollama tags in chat payloads instead of HF ids |
| `INFERENCE_MODEL` / `SAFETY_MODEL` / `VISION_MODEL` | Defaults to the HF ids in the table above |

See also: [`cli/`](../cli/) operator console (Part 1) which already labels open equivalents for agent roles.
