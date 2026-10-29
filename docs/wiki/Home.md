# MeTaBoss documentation wiki

**Meta AI Business Operations Sovereign System** — formerly MuseBreak. The repository and existing modules retain historical names. Independent project, not an official Meta product.

MeTaBoss is a public, MIT-licensed experimental AI gateway and Business OS by CodesbyFebin. The core research question is whether an operator can approve an exact business action and independently verify the resulting local records.

This source-controlled wiki is built into the static documentation site. It is not a claim that the separate GitHub Wiki repository has been published. The invoice implementation is in [PR #1](https://github.com/CodesbyFebin/musebreak-core/pull/1); check merge state before using a default-branch checkout.

## Read by task

- [Quick start](Quickstart.md): run a synthetic INR 471.98 invoice and separate verifier.
- [Architecture](Architecture.md): gateway, deterministic service, receipt and observer boundaries.
- [Security](Security.md): assumptions, durable data and excluded legacy paths.
- [Questions](FAQ.md): public repository, models, robotics, and what verification means.
- [Community](Community.md): practical ways to contribute and reproduce results.
- [Publishing](Publishing.md): GitHub Pages setup, crawlability, and measurement.
- [Full project guide](../../README.md): story, technical detail and roadmap.
- [Invoice contract](../verification/INVOICE-WORKFLOW.md): exact operational details.
- [Qualification](../verification/QUALIFICATION.md): recorded commands and test evidence.

## A bounded result

The new workflow commits invoice issuance, stock changes, an event, and an Ed25519 receipt in one local SQLite transaction. A separate checker verifies the receipt against a pinned trusted public key and supplied read-only snapshot. This is not payment settlement, physical delivery, a real zkVM, a robot controller, or proof that every legacy route is protected.
