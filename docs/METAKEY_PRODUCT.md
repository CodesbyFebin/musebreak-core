# MetaKey — dual-plane product vision

> Status legend: **Implemented** = in this repo and tested. **Concept / target** = intended product direction,
> not built, not tested, not certified. Nothing here is a certification claim.

MetaKey is pitched as one product with two planes.

## Plane 1 — physical key (concept / target)

| Feature | Status |
|---|---|
| NFC tap + USB-C connector | Concept / target. The repo has an NFC HMAC Gate 2 **simulator** and reference firmware (`firmware/`, `hardware/`) not validated on hardware |
| FIDO2 / WebAuthn authenticator, CTAP 2.1, passkeys | Concept / target for the device. Any off-the-shelf FIDO2 key or platform passkey already works with the `/auth` flow below |
| FIDO2 L2 certification | **Not certified.** Target only |
| IP68 rating | **Not tested.** Target only |
| Secure Element with a certified assurance level | **Not certified.** Target only; the STM32 ↔ NXP SE wiring docs are reference designs |
| Crypto hardware-wallet functions | **Concept only.** Not designed or implemented here |

## Plane 2 — online verifiable auth (implemented as MVP)

| Feature | Status |
|---|---|
| Gate 1 JWT + device fingerprint, Gate 2 HMAC + P-256 QR challenge | Implemented, tested |
| `/auth/draft` → `/auth/bind` → `/auth/approve` → `/auth/verify` | Implemented, tested |
| WebAuthn assertion verification | Implemented with `py_webauthn` (signature, challenge, origin, RP ID, sign count) for registered credentials |
| Simulated assertion fallback | Demo only, labelled `simulated_assertion: true`, can be disabled |
| UTR uniqueness (replay rejected; recorded only after verification) | Implemented, tested |
| `fido_binding` commitment over auth, assertion hash, device hash, business id, prev audit hash, stock | Implemented as **hash-commitment-mvp** — not zero-knowledge |
| Real ZK proofs (SP1 / RISC Zero) | Future work |
| Persistent credential / UTR store | Future work (in-memory today) |

## Not claimed
No proof-size or latency figures, no Rust circuits, no third-party lab/certification results, and no coin/token
support counts are claimed for MuseBreak or MetaKey.
