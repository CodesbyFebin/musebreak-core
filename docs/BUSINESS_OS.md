# MuseBreak Business OS (WebLLM)

Interactive web/mobile console at **`/os`**: in-browser inference, open model routing,
agent swarm with Claw grants, Jev human approval gate, and a continuous zkVM
hash-commitment heartbeat.

## What is real

| Piece | Reality |
|---|---|
| Small tier **Muse Spark ≡ Llama-3.2-1B-Instruct** via `@mlc-ai/web-llm` | **Real** in-browser inference when WebGPU is available. Streams tokens. |
| WebGPU detection | **Real** — page shows a clear message if unavailable (no fake completions). |
| Task classifier (small / medium / large) | **Real** heuristic (shared backend + CLI + frontend). Unit-tested. |
| Jev approval gate | **Real** UI + `/os/tasks/{id}/jev` — default-deny for medium/large and action-like prompts. Does **not** execute shell/Kali in-browser. |
| zkVM 24/7 heartbeat `/os/zkvm/status` | **Real** background hash-commitment of the audit tip. Labelled `hash-commitment-mvp`, `is_zk: false`. **Not** zero-knowledge. |
| Medium / Large API call | **Real** only when an OpenAI-compatible base URL is set (localStorage or `MUSEBREAK_MEDIUM_API_URL` / `MUSEBREAK_LARGE_API_URL`). Otherwise **UNAVAILABLE**. |
| Agent assignment + Claw toggles | **Real** routing/assignment logic; claws are UI capability grants. |
| Mobile | **Responsive** CSS — no native app. |

## Model map (Open Routing)

| Size | Muse label | Open equivalent | Runtime |
|---|---|---|---|
| small | Muse Spark | Llama-3.2-1B-Instruct (WebLLM q4f32_1) | browser-webllm |
| medium | Muse Code | CodeLlama-13b-Instruct / Llama-3.1-8B | API (optional) |
| large | Muse Wonder Full | Llama-3.3-70B-Instruct | API (optional) |

`USE_OPEN_SOURCE_ONLY` (default true) keeps the gateway on the open Meta/Llama stack.

## APIs

- `GET /os/models` — tiers, agents, API configured flags
- `POST /os/route` — preview classification
- `POST /os/tasks` — enqueue (sorted + assigned)
- `GET /os/tasks` / `GET /os/tasks/{id}`
- `POST /os/tasks/{id}/jev` — Jev approve
- `POST /os/tasks/{id}/complete` — record WebLLM/API result (browser posts real text)
- `GET /os/zkvm/status` · `POST /os/zkvm/commit`

## Run

```bash
# Gateway (starts zkVM heartbeat)
cd backend && pip install -r requirements.txt && uvicorn main:app --port 8000

# Web (needs a WebGPU browser for local inference)
cd frontend && npm install && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
# open http://localhost:3000/os
```

Optional medium/large: point the Settings fields on `/os` at Llama Stack / Ollama
OpenAI-compatible base (e.g. `http://localhost:8321`).

## Honesty notes

- Live WebGPU inference is **not** executed in CI or on headless build boxes.
  Confirm with a Chrome/Edge WebGPU browser.
- No fabricated GPU hardware, parameter counts, latency, or cost figures.
- Mockup cosmetics (layout) only — fake logs / ∞ params / 4× A100 were **not** copied.
