# Invoice receipt qualification — October 30, 2026

Base: `ae4d675de3c223c4edf8abcc30747c3e8c5a488e`, `CodesbyFebin/musebreak-core`.

## Executed

```sh
ZKVM_HEARTBEAT_DISABLE=1 USE_OPEN_SOURCE_ONLY=false \
  .venv/bin/python -m pytest backend/tests tests -q
python scripts/verified_invoice_demo.py --out /tmp/a-new-synthetic-demo-directory
```

- **89 backend/CLI tests passed**, including **21 new invoice tests**. Python 3.12.14. One existing Starlette/httpx deprecation warning; no test skipped or timeout extended.
- The full HTTP request-handler sequence used the existing login/challenge/HMAC/P-256 authorization, then the new product/draft/approve/issue endpoints. Unauthenticated and Gate-1-only requests fail; a wrong fingerprint fails; an unauthorized subject fails; public demo authentication fails unless the explicit synthetic-test override is enabled. Extra caller-supplied approver fields and boolean quantities are rejected.
- Reopening a service preserves receipts and idempotent issue behavior. Two concurrently issued approved drafts compete for the last stock: one commits, one is refused, stock ends at zero, one movement exists.
- An injected exception after inventory, event and receipt writes rolls the whole transaction back. No inventory decrement, event or issued receipt survives that fault.
- Seven negative receipt/state cases are rejected: changed total, bad signature, wrong trusted public key, changed movement, missing event, changed stock and missing invoice. This is a finite test set, not an estimate of real-world attack resistance.
- Approval failures cover absent approval, wrong payload hash, another owner, expired window, edited stored payload and modified decision signature. Customer-label injection text remains data and cannot change prices/quantity or invoke another operation; no model, command executor or external tool consumes it in this workflow.
- Separate-process verifier succeeded against an actual SQLite snapshot exported by the synthetic demo. The invoice total was **47,198 paise / INR 471.98**. Repeated issue returned the identical receipt without another stock change.
- Python module compilation and `git diff --check` passed. No frontend change, browser UI verification, physical MetaKey test, live model call, payment settlement, external messaging/publishing or deployed service is claimed.

## Test isolation

The first combined run exposed that the new API test's very large software-key counter contaminated legacy gate tests sharing a process. The new test now substitutes and restores its own in-memory challenge/counter store. A forced open-source mode also configured an unreachable guard endpoint for a legacy regex-only test; the final repeatable fixture command above uses the repository's disconnected, non-network mode. Production guard behavior was not weakened. Final combined runs passed all 89 tests.

The demo uses a fresh temporary database, private signing key and JWT secret; its public software MetaKey is explicitly labeled simulated hardware. A follow-up public receipt/database export contains only synthetic records, not production customer data or private signing keys.

## Independent-verification boundary

The verifier is separate source and a separate Python process with only `cryptography` plus standard-library dependencies. It imports no backend business producer, accepts no agent verdict and opens the database read-only. Its result is consistency of the selected local invoice against the supplied trusted public key and independently obtained snapshot. It does not establish that the snapshot is latest or externally anchored, that the operator is physically present, or that the issuer's host/key was uncompromised.

## Remaining product work

- Production security qualification and remediation of legacy unauthenticated/demo OS routes.
- Payload-bound physical/passkey human authorization, staff roles and multi-tenant policy.
- Encrypted storage, key rotation/revocation and off-host receipt/head anchoring.
- UI integration and business corrections/credit-note flows.
- Real, separately authorized Meta model evidence if required by the submission.

The new route remains opt-in and this change is prepared as a draft pull request. No main-branch merge, production deployment, hackathon submission or universal verification novelty claim is made.
