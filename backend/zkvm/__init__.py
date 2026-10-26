"""MuseBreak Trust Plane — hash-commitment MVP (NOT a real zero-knowledge proof).

This package provides deterministic canonical JSON, SHA-256 hashing, a hash-chain
helper, five Python "circuits" (constraint checkers), and a prove/verify pair that
binds a statement hash into a fixed-size encoding.

Honesty:
  - ``implementation`` is always ``hash-commitment-mvp``.
  - The 256-byte ``proof_b64`` payload is an *encoding artifact* (32-byte SHA-256
    digest + 224 zero bytes), not a ZK proof. Future work: swap for real SP1 / RISC Zero.
  - ``simulated`` is True whenever no real prover binary is configured (the default).
"""
from .prover import ZKProver, GuardBlockedError
from .verifier import ZKVerifier, verify_statement

__all__ = ["ZKProver", "ZKVerifier", "GuardBlockedError", "verify_statement"]
VERSION = "musebreak-zkvm-0.1"
IMPLEMENTATION = "hash-commitment-mvp"
