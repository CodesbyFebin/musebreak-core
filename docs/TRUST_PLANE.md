# Trust Plane — Hash-Commitment MVP

> **Honesty first:** This is **not** a real zero-knowledge proof system.
> The “zkVM” package is a **hash-commitment MVP**: deterministic canonical JSON + SHA-256 +
> fixed-size encoding (`SHA-256(statement) ‖ 224 zero bytes` = 256 bytes) with prove/verify
> helpers and five Python constraint checkers (“circuits”).
>
> The 256-byte payload size is an **encoding artifact**, not a ZK proof size claim.
> API responses always include `simulated: true` and `implementation: "hash-commitment-mvp"`.
>
> **Future work:** swap the prover/verifier for real **SP1** or **RISC Zero** while keeping the
> same circuit statement shapes.

## Layout

| Path | Role |
|------|------|
| `backend/zkvm/canonical.py` | Deterministic JSON (`sort_keys`, compact separators) |
| `backend/zkvm/hash.py` | `hash_canonical`, `hash_chain` |
| `backend/zkvm/prover.py` | Guard (PII fail-closed) → circuit check → commitment |
| `backend/zkvm/verifier.py` | Check proof prefix == statement hash |
| `backend/zkvm/circuits/` | `order_approve`, `audit_chain`, `utr_unique`, `vuln_chain`, `business_isolation` |
| `backend/zkvm/router.py` | `GET /zkvm/circuits`, `POST /zkvm/prove`, `POST /zkvm/verify` |
| `backend/metakey/orders.py` | `POST /orders/draft`, `/orders/approve`, `POST /audit/verify` |

## Guard

Before `prove`, a regex PII guard runs (Aadhaar-like / SSN-like / crude PAN). On match it raises
`GuardBlockedError` and the API returns HTTP 400. Fail-closed.

## CLI

```bash
musebreak zkvm prove --demo
musebreak zkvm verify --proof '...' --hash '...'
musebreak voice --lang ml   # scaffold
musebreak learn             # scaffold
```

## Frontend

- `frontend/components/zkvm/VerifyButton.tsx`
- `frontend/app/verify/page.tsx` — demo draft → verify UI

## What is real vs scaffold

| Piece | Status |
|-------|--------|
| Canonical JSON + SHA-256 + hash chain | **Real** |
| Circuit constraint checks | **Real** (Python) |
| Prove → verify roundtrip | **Real** (hash commitment) |
| PII guard before prove | **Real** (regex fail-closed) |
| SP1 / RISC Zero proofs | **Not implemented** (future) |
| Voice / learn / most agents | **Scaffolds** (simulated when no GPU/models) |
| meta_clients hosted providers | **Scaffolds** unless keys + HTTP wired |
