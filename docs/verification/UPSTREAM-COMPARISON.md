# Verification implementation review — October 30, 2026

This review informed an original local-invoice workflow. No upstream implementation or artwork was copied. Review is source inspection, not a reproduction of third-party live-model or sandbox benchmark results.

| Project / pinned revision | Actual inspected behavior | What it does not establish for MuseBreak |
| --- | --- | --- |
| [Witness](https://github.com/yatharthchopra2424/witness-agent-receipts/tree/fe34046a65d3f8bb2f15871b2697234d703ecc3c) | README explicitly says planning/no code. It proposes comparing invoice-entry claims against screen evidence, with verified/mismatch/unverifiable outcomes. It recommends database checks when available. | No running receipt verifier, vision model integration or independently reproducible result was found at this revision. License is undecided; no material imported. |
| [Munix](https://github.com/Dominic-Pi-Sunyer/munix/tree/d808875a679bed191ef7429e08d53305a5e4b83d) | Rust Gate code has signed-plan validation, pinned tool manifests, argument provenance, pending human decisions, typed reader paths and deterministic deny decisions. Core `Signed<T>` uses purpose-separated HMAC-SHA256. The ledger checks canonical lines, hashes and sequence, with one-writer locking. Apache-2.0. | A shared-secret HMAC is not a public-key receipt. Ledger source explicitly documents that truncation/full rewrite requires an external anchor to detect. Its README benchmark numbers were not independently reproduced here; its container runtime was not deployed. |
| [Meta GitHub agent cookbook](https://github.com/meta-models/meta-model-cookbook/tree/0a99b987858ec4e49c04fc3f114bf33851e81deb/03_use_cases/11_github_repo_agent) | Inspected `opencode.json` and PR-review workflow. Muse Spark/OpenCode with role/tool policies, maintainer-gated fixes and human PR merges. Workflow has repository read and review-comment write permissions. | Tool allowlists and prompt instructions are not an independent business-state verifier or universal OS network isolation. Its agent verdict is not an invoice/payment receipt. No workflow installed or secret configured by this change. |
| MuseBreak baseline `ae4d675de3c223c4edf8abcc30747c3e8c5a488e` | `/muse/query` has two-gate authentication. `AuditLog` recomputes a local hash chain. Legacy `/os/tasks/*` stores in-memory tasks, accepts a supplied approver name and browser-reported completion. `/orders` emits explicitly simulated hash commitments. | Those demo paths do not prove business effects or exact-payload authenticated approvals. A hash commitment padded to 256 bytes is not a zkVM proof. The legacy log has no external head anchor or independent observed-outcome check. |

## Resulting design choice

Use deterministic business adapters outside model output. For this bounded slice, an invoice proposal uses integer catalog prices; an authenticated owner approves its exact payload; stock is rechecked inside a SQLite transaction; issuance, movements, event and Ed25519 receipt commit together. A standalone read-only program checks an independently supplied database and pinned public key. It neither asks the drafting model whether it succeeded nor trusts a browser's “done” string.

The differentiated product claim is practical, measurable invoice integrity in the Business OS. Receipts, cryptographic signatures, policy gates and prompt-injection defenses are established techniques. No invention of verification, universal prompt-injection immunity, independent third-party witness deployment or hardware/ZK attestation is claimed.

## Implementation evidence locations

- Munix: `crates/munix-gate/src/gate.rs`, `crates/munix-core/src/crypto.rs`, `crates/munix-ledger/src/lib.rs`, corresponding gate/ledger tests.
- Witness: `README.md`, `docs/`, `data/` planning specifications.
- Meta: cookbook `03_use_cases/11_github_repo_agent/opencode.json`, `workflow/opencode-pr-review.yml`, README.
- New MuseBreak: `backend/business/`, `verification/invoice_receipt.py`, `backend/tests/test_business_receipts.py`, `scripts/verified_invoice_demo.py`.

## Event and comparison context

Meta's [official event page](https://dev.meta.ai/events/global-hackathon), checked October 30, lists submissions due November 4 at 9 PM ET (November 5 at 7:30 AM IST), judging November 4–8, and the closing ceremony November 9. The 20,000 figure is a participant cap, not verified attendance.

The supplied flisk/DeepThink-AIOS/MeetFlow links resolve to public repositories, but their topic tags and stars do not establish acceptance, prize status or technical ranking. In the inspected metadata, DeepThink-AIOS was last pushed September 5 and MeetFlow October 10, before the event build window. This does not determine eligibility or subsequent work elsewhere; they remain comparison leads, not confirmed top hackathon submissions. No winner-monitoring task was created from the pasted offer.
