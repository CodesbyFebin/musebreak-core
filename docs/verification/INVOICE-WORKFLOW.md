# Independently checkable local invoice workflow

The opt-in `/business` API implements one bounded workflow: create a catalog product, draft an INR invoice, explicitly approve its exact SHA-256 payload, issue it once, then verify its signed receipt against durable business records. The outcome is local invoice issuance and stock movement. It is not payment settlement or delivery.

## Safety guarantee and assumptions

For requests through this API, an invoice can issue only after an owner-bound, unexpired exact-payload approval. Stock is checked inside `BEGIN IMMEDIATE`; a successful commit includes the issued invoice, exactly one stock movement per line, one issuance event and a signed receipt. Repeating issue with the same invoice/hash returns the stored receipt and makes no additional stock change. Concurrent requests serialize through SQLite; failures roll back the complete transaction.

Assumptions: trusted gateway JWT secret, privately enrolled/allowed MetaKey, server signing key, database filesystem, server code and process. The operator who controls these can forge identity or business history. This is not protection against a compromised server, host administrator or stolen signing key. Existing public demo credentials cannot qualify an operator's identity. The new API rejects public demo HMAC/P-256 material by default, including when renamed; an explicit synthetic-demo override exists for tests only.

The approval signature attests the server's authenticated decision, not a separate human hardware signature over invoice bytes. Possession of an authorized bearer credential can submit an approval; this version does not independently establish physical human presence for each invoice. Never give that credential to a drafting model or untrusted worker. The existing MetaKey QR signature covers gateway model intent, not this invoice payload. A separately trusted issuer public key plus independent observed state is required by the verifier. Receiving a receipt and a replacement public key from the same untrusted source does not establish trust.

## Enable explicitly

Install `backend/requirements.txt`. Provision an Ed25519 private key outside the repository and distribute its public key through an independent trusted channel. Example key generation for an operator-controlled directory:

```python
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
key = Ed25519PrivateKey.generate()
private = Path('/your/private/directory/invoice-signing.pem')
with private.open('xb') as f:
    f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
private.chmod(0o600)
public = private.with_name('invoice-signing-public.pem')
with public.open('xb') as f:
    f.write(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
```

Set `BUSINESS_DB_PATH`, `BUSINESS_SIGNING_KEY_PATH`, `BUSINESS_OPERATOR_SUBJECT` and comma-separated `BUSINESS_ALLOWED_KEY_IDS`. Enroll private MetaKey material using the existing enrollment mechanism; rotate the public demo authentication material and protect the JWT secret. Keep `BUSINESS_ALLOW_DEMO_AUTH` unset in real operation. Missing storage/signing/operator configuration fails closed. This is single-operator business ownership derived from verified JWT subject, not a multi-tenant RBAC implementation.

Each business route requires the existing short-lived Wonder token, both gates, the bound device-fingerprint header, matching business subject and an allowlisted MetaKey. The caller cannot supply an `approver` field. Do not put bearer credentials, private keys or customer invoices into model prompts or source control.

## HTTP sequence

1. `POST /business/products`: `{name, price_minor, tax_bps, stock}`. No fake catalog seed. Minor units and quantities are strict bounded integers; booleans/floats/unknown fields fail validation.
2. `POST /business/invoices`: `{customer, items:[{product_id,quantity}]}`. The server loads catalog price/tax data and returns the immutable payload plus hash. Duplicate products and unsupported totals are rejected. Customer text is a label, not executable instructions.
3. After displaying/reviewing the complete payload, `POST /business/invoices/{id}/approve` with `{payload_hash}`. The server binds the authenticated subject, invoice, one-use scope, nonce and a five-minute approval window, and signs the decision.
4. `POST /business/invoices/{id}/issue` with the same `{payload_hash}`. It rechecks stock and approval inside the transaction and returns the signed decision/result receipt. Insufficient stock or a failed write commits nothing. Reissue is an idempotent receipt read, even after approval expires; it is not a fresh issuance.
5. `GET /business/invoices/{id}` reads the owner-scoped state and receipt. Missing/other-owner records are unavailable. No external publisher, messaging, tax filing or payment API is called.

Tax arithmetic is an explicitly configured per-line half-up calculation: `tax_minor = (quantity * price_minor * tax_bps + 5000) // 10000`. This is not a qualified GST/VAT engine or a government e-invoice integration. Currency is INR in this version. Issued payloads cannot be edited through this API; corrections/refunds are future separately approved flows.

## Run the synthetic demonstration

```sh
python scripts/verified_invoice_demo.py --out /tmp/new-synthetic-invoice-demo
python verification/invoice_receipt.py \
  --receipt /tmp/new-synthetic-invoice-demo/receipt.json \
  --public-key /tmp/new-synthetic-invoice-demo/signing-public.pem \
  --database /tmp/new-synthetic-invoice-demo/business-snapshot.sqlite
```

The output directory must be new. The demo uses temporary JWT/signing secrets, the explicitly public software MetaKey, synthetic customer/stock and FastAPI TestClient. It exercises real request handlers and crypto but does not run physical hardware, a live model or a browser. Its export includes only the public key, synthetic receipt/database and verification verdict. Private signing material remains in a temporary directory. The expected invoice total is 47,198 paise (INR 471.98).

## Independent verifier

`verification/invoice_receipt.py` imports no backend/producer code. In a separate process it loads the pinned Ed25519 public key, checks signature domains/key ID and the nested approval, recalculates invoice arithmetic and approval validity at issue time, and opens the supplied SQLite database with read-only/query-only access. It checks the issued invoice, receipt, one movement per line, stock continuity/current balance, and exactly one matching issuance event. Legitimate later movements do not invalidate an earlier receipt if the ledger still reconciles.

The database must be obtained independently by the operator or witness (for example through read-only administrative access or a consistent SQLite backup). The demonstration supplies a local synthetic snapshot; it does not deploy an independent third-party witness. The verdict proves consistency at the supplied snapshot, not that it is the newest snapshot or that no records were omitted elsewhere. There is no external checkpoint, timestamp authority or whole-history completeness proof. Back up with SQLite's backup API; copying only a live main file can omit journal/WAL contents.

Tampered receipts, another public key, missing invoices, missing events, changed stock and changed movements cause a nonzero verifier exit. A signature alone can verify a statement about a nonexistent result; that is why the independent database read is mandatory. No `verified:true` flag from the issuing agent is accepted as evidence.

## Limits and retention

Receipts, invoices, movements and approvals are durable business records containing customer labels and line data. They are not zero-retention AI context. This slice does not provide encryption at rest, server key rotation/revocation, external anchoring, retention/export/deletion administration, multi-process JSONL audit repair, staff roles or a production security assessment. Failed requests return errors rather than a separate signed denial receipt.

The new guard applies only to `/business`. Legacy `/os/tasks/*`, `/orders` demo approvals and the existing hash-commitment “zkVM” paths remain outside this guarantee. A passing new workflow must not be presented as making every existing MuseBreak route authenticated or independently verifiable. No 24/7 uptime, universal prompt-injection immunity, physical MetaKey attestation or real ZK proof is claimed.
