# Benchmark harness — open-weight models as defensive agents

The benchmark harness measures **how well each configured open-weight model drives the
MuseBreak agent loop** on a suite of scored, sandboxed, synthetic tasks. It benchmarks the
*harness + model*; it does **not** attack real hosts.

## Safety posture (unchanged from the rest of the repo)
- **Defensive-only.** Tasks are local/synthetic fixtures — no live targets, no real CVEs.
- **No egress.** No live port scanning, no network calls to external hosts, no real exploit code.
- **Dry-run default.** Any exec step would still need Jev/human approval (`--i-am-authorized --approver`).
- **Monitor fail-closed.** A monitor agent reviews every step via the guard; offensive intent is blocked.
- **Red tier = defensive research only.**

## Role weighting (as requested)
| Bench role | Muse model | Open equivalent | Canonical swarm role | Weight |
|---|---|---|---|---|
| discovery (lead) | Muse Wonder Full | Llama-3.3-70B-Instruct | `analyzer` | 0.40 |
| exploit-writer | Muse Spark | Llama-3.1-8B-Instruct | `code` | 0.25 |
| monitor | Llama | Llama-3.1-8B-Instruct | `review` | 0.20 |
| tooling | Muse Code | CodeLlama-13b-Instruct | `code` | 0.15 |

Discovery (Muse Wonder Full) carries the most weight. The monitor (Llama) reviews/guards the
other agents' steps. These bench roles reconcile onto the existing operator-console roster
(`cli/musebreak_cli/model_router.py`) rather than inventing a parallel one.

## What it measures
For every (model × task) pair the harness records:
- **success** — did the answer cover all required tokens for the task (deterministic token-coverage scorer)?
- **steps** — number of loop steps taken.
- **score** — fraction of required tokens matched (1.0 on success).
- **composite** — weighted average across tasks using the role weights above.
- **success_rate** — fraction of tasks solved.

No latency/token-count fabrication: timing is only the wall-clock `elapsed_s` of the run.

## Honesty: what actually runs here
On a headless box with no model API/GPU configured, **no real model executes**. Those models
are reported `UNAVAILABLE` and the run is labelled `simulated: true` — scores come from a fixed
oracle over our own fixtures that exercises the scoring/guard loop. **Simulated scores are never
presented as a real model's capability.**

A model tier becomes `available` only when its execution backend is reachable:
- `api` models: set `META_MODEL_API_URL` (or `LLAMA_STACK_URL`) and run with `MUSEBREAK_MOCK=0`.
- `browser-webllm` models run in a WebGPU browser (the `/os` page), not in the CLI, so they are
  always `UNAVAILABLE` from the harness.

## How to run
```bash
pip install -e cli
export MUSEBREAK_MOCK=1
musebreak benchmark roles      # show the role → model → canonical-role mapping
musebreak benchmark models     # show which models can actually run here
musebreak benchmark run        # run the suite; writes ~/.musebreak/benchmark.json
musebreak benchmark run --json # raw JSON to stdout
```
To benchmark real models:
```bash
export MUSEBREAK_MOCK=0
export META_MODEL_API_URL=http://localhost:8321/v1/chat/completions   # Llama Stack / OpenAI-compatible
musebreak benchmark run
```

## Add a model
Add an entry to `BENCH_ROLES` (or extend `model_set()`) in `cli/musebreak_cli/benchmark.py` with
its `open_equivalent`, `backend` (`api` or `browser-webllm`), and weight. Open-weight ids live in
`backend/open_source.py::OPEN_MODEL_MAP`.

## Add a task
Append a `BenchTask` to `TASK_SUITE` in `cli/musebreak_cli/benchmark.py`: give it a `task_id`,
a `bench_role`, a `prompt` over a **synthetic/local fixture**, and the `required` tokens the
answer must contain. Keep it defensive — no live targets.

## Tests
`tests/test_benchmark.py` covers the scorer (determinism, case-insensitivity, partial/zero scores),
the role→canonical reconciliation and weighting, availability honesty, and the end-to-end run
(nothing may claim `available` in mock mode; the monitor must block offensive intent).
