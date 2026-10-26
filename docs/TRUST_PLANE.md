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
| `backend/zkvm/circuits/` | `order_approve`, `audit_chain`, `utr_unique`, `vuln_chain`, `business_isolation`, `fido_binding` |
| `backend/zkvm/router.py` | `GET /zkvm/circuits`, `POST /zkvm/prove`, `POST /zkvm/verify` |
| `backend/metakey/orders.py` | `POST /orders/draft`, `/orders/approve`, `POST /audit/verify` |
| `backend/metakey/fido_auth.py` | `POST /auth/register/options`, `/auth/register/verify`, `/auth/draft`, `/auth/bind`, `/auth/approve`, `/auth/verify` |

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
| WebAuthn assertion verification in `/auth/bind` | **Real** (py_webauthn signature, challenge, origin, RP ID, sign-count checks) for registered credentials |
| Simulated assertion path | **Simulated** — challenge echo, no signature; returns `simulated_assertion: true`; disable with `MUSEBREAK_WEBAUTHN_ALLOW_SIMULATED=false` |
| `/auth` credential/UTR state | **In-memory** demo store (lost on restart) |
| SP1 / RISC Zero proofs | **Not implemented** (future) |
| Voice / learn / most agents | **Scaffolds** (simulated when no GPU/models) |
| meta_clients hosted providers | **Scaffolds** unless keys + HTTP wired |

## MetaKey online plane — FIDO binding (`/auth`)

1. `POST /auth/register/options` → `navigator.credentials.create` → `POST /auth/register/verify` (real WebAuthn registration).
2. `POST /auth/draft {order_id, shop_id, utr(12 digits)}` → `draft_id` + WebAuthn challenge. Rejects a UTR already used.
3. `POST /auth/bind {draft_id, assertion, device_hash}` → verifies the assertion, then proves the `fido_binding` circuit over
   `auth_hash` (order, shop, H(UTR)), `assertion_hash`, `device_hash`, `business_id`, `prev_audit_hash`, `stock_hash`.
   The UTR hash is recorded **only after** verification and a passing circuit; the raw UTR never enters the transcript.
4. `POST /auth/approve {draft_id, muv_approved:true}` — human MuV gate.
5. `POST /auth/verify {proof_b64, statement_hash_hex}` — recheck the commitment. Any edit to the statement fails.

Still a hash-commitment MVP: it binds values for integrity but hides nothing cryptographically — not zero-knowledge.
See [METAKEY_PRODUCT.md](METAKEY_PRODUCT.md) for the dual-plane vision.
