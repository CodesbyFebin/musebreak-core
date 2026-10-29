# Architecture: proposal, authority, effect, observation

The application separates concepts that an assistant's completion message often conflates.

| Layer | Current implementation | Trust boundary |
| --- | --- | --- |
| Interface | Next.js, experimental WebLLM workspace | A browser result is not proof of a durable effect |
| Gateway | FastAPI, short-lived JWT, HMAC/P-256 challenge protocol | Private keys, configured secrets and server remain trusted |
| Business service | Catalog-derived integer totals and exact-hash approval | Only opt-in /business routes have the new guarantee |
| Commit | SQLite BEGIN IMMEDIATE and stored Ed25519 receipt | Local transaction, no remote payment/message atomicity |
| Observer | Separate Python checker and read-only snapshot | Key must be pinned; snapshot must be independently obtained |

## Data flow

A catalog product supplies prices. The server constructs a draft and canonical hash. An authenticated operator approves that exact hash. At issue time, the service rechecks approval and stock inside the write transaction. Invoice, movements, event and receipt commit together. A repeated issue returns the stored receipt, avoiding duplicate stock movement.

The checker imports no backend business code. It recalculates arithmetic and checks signatures plus actual records, rather than accepting an agent verdict. Valid later movements are allowed when the ledger still reconciles. Missing events, changed stock or substituted signatures fail verification.

## Distinct experimental planes

Legacy OS task routes accept browser completion and are outside the invoice guarantee. The local JSONL audit chain has no external anchor. The hash-commitment MVP is not a real zkVM. A WebLLM model alias does not establish a hosted Muse API call. Read [security](Security.md), [the full contract](../verification/INVOICE-WORKFLOW.md), and [upstream comparison](../verification/UPSTREAM-COMPARISON.md). Return to [wiki home](Home.md).
