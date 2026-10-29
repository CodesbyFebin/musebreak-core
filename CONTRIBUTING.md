# Welcome to the MeTaBoss community

We welcome reproducible bug reports, clear documentation, accessible interfaces, security analysis, and focused code improvements. Start with the [wiki](docs/wiki/Home.md) and [workflow contract](docs/verification/INVOICE-WORKFLOW.md).

## Choose a useful first contribution

1. Run the synthetic invoice demo and report your revision and environment.
2. Improve a confusing instruction without changing the documented guarantee.
3. Add a meaningful negative case to a boundary you are changing.
4. Propose an adapter with a precise effect, permission, observation source, and failure state.

Use synthetic data. Never attach private keys, bearer tokens, customer records, or a real business database. Keep public demo credentials labeled public. A screenshot alone does not establish transaction correctness.

## Development and review

Read AGENTS.md. Keep changes focused and explain the concrete problem, resulting behavior, and validation. Business changes must preserve owner checks, integer money, exact-payload approvals, transactions, and independent verification. Run the focused tests; broaden only when the change requires it. Documentation changes use `python scripts/check_docs.py` after installing `docs/requirements.txt`.

For a code change, describe any migration or compatibility impact. For new dependencies, provide the exact source, license and reason. Do not copy restricted artwork or imply an unexecuted integration is verified. Live API calls, publishing, or financial actions require explicit authorization and separately controlled credentials.

## Community conduct

Be respectful, specific, and patient. Critique the behavior and evidence, not the person. No harassment, unsolicited promotion, fake review/star campaigns, or sharing personal data. Maintainers review as capacity permits; there is no promised support SLA or guaranteed merge. Security issues should follow [SECURITY.md](SECURITY.md).

## Recognition and licensing

The project is MIT licensed under LICENSE. Contributions should be compatible with that license and preserve relevant attribution. Models, third-party services and imported material can have separate terms. Contributions do not create employment or compensation obligations. Thank you for helping make the boundaries easier to understand and reproduce.
