# Security and privacy boundaries

The invoice slice is a bounded development implementation. Its tests do not qualify the whole repository for public production use.

## Trusted components

The current model trusts the gateway JWT secret, allowed private MetaKey, server process/code, signing key, filesystem and database. A compromised administrator can fabricate local history. A trusted public key and independently acquired snapshot are required by the separate checker; neither proves snapshot freshness or complete history without an external anchor.

## Operator approval

A signed server decision records an authenticated owner approval. It is not a separate physical human signature over invoice bytes. Do not give approval-capable bearer credentials to a drafting worker. The public demo MetaKey is rejected by the business API unless an explicit synthetic override is set. Keep that override off for valuable records.

## Durable data

Invoices, customer labels, approvals, movements and receipts persist. This is not zero retention. Encryption at rest, key rotation/revocation, legal retention administration and off-host anchoring remain work. Never publish a live database, private key, token or customer receipt in public docs. Only synthetic evidence belongs in a shareable demo.

## Excluded guarantees

Legacy /os task routes and demo order approvals are not hardened by the new service. No universal prompt-injection immunity, real zkVM, physical delivery, bank settlement, robot safety, always-on worker fleet, or third-party witness is established. The guard does not replace authentication or deterministic policy.

Follow [SECURITY.md](../../SECURITY.md) for cautious reporting. Read [the full workflow contract](../verification/INVOICE-WORKFLOW.md), [qualification](../verification/QUALIFICATION.md), or return to [wiki home](Home.md).
