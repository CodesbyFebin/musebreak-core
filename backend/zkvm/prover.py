"""Hash-commitment prover MVP — NOT a real ZK prover.

Produces a 256-byte encoding: SHA-256(statement) || 224 zero bytes, base64'd.
``simulated`` is True by default. Future work: swap for SP1 / RISC Zero.
"""
from __future__ import annotations
import base64
import os
import re
import time
from .hash import hash_canonical
from .circuits import CIRCUITS

IMPLEMENTATION = "hash-commitment-mvp"
VERSION = "musebreak-zkvm-0.1"


class GuardBlockedError(Exception):
    """Raised when the pre-prove PII/guard check fails (fail-closed)."""


# Simple offline PII patterns — fail closed before any commitment is issued.
_PII_PATTERNS = [
    re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),  # Aadhaar-like 12 digit groups
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-like
    re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b"),  # crude PAN/card
]


class ZKProver:
    def __init__(self, use_open_source_only: bool | None = None):
        env = os.getenv("USE_OPEN_SOURCE_ONLY", "true").lower() == "true"
        # Real SP1/RISC Zero binary not shipped — always simulated unless overridden later.
        self.use_open_source_only = env if use_open_source_only is None else use_open_source_only
        self.simulated = True  # honesty: no real prover binary in this MVP

    def _guard_check(self, obj) -> None:
        s = str(obj)
        for pat in _PII_PATTERNS:
            if pat.search(s):
                raise GuardBlockedError("PII detected by guard — prove blocked (fail-closed)")

    def prove(self, circuit_name: str, public_inputs: dict, private_witness: dict) -> dict:
        if circuit_name not in CIRCUITS:
            raise ValueError(f"unknown circuit {circuit_name}")
        circ = CIRCUITS[circuit_name]

        # Guard BEFORE prove — fail closed
        self._guard_check(public_inputs)
        self._guard_check(private_witness)

        start = time.perf_counter()
        result = circ.verify(public_inputs, private_witness)
        valid = bool(
            result.get("valid")
            or result.get("intact")
            or result.get("unique")
            or result.get("critical")
            or result.get("isolated")
        )
        statement = circ.get_statement(public_inputs, valid)
        stmt = hash_canonical(statement)
        # Encoding artifact: 32B digest + 224 zero pad = 256B — NOT a ZK proof.
        proof_bytes = stmt["bytes"] + b"\x00" * 224
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return {
            "proof_b64": base64.b64encode(proof_bytes).decode(),
            "statement_hash_hex": stmt["hex"],
            "statement": statement,
            "circuit": circuit_name,
            "public_inputs_hash": hash_canonical(public_inputs)["hex"],
            "result": result,
            "prover_time_ms": elapsed_ms,  # measured wall time only
            "simulated": True,
            "implementation": IMPLEMENTATION,
            "version": VERSION,
            "created_at": time.time(),
            "note": "256-byte payload is hash||padding encoding artifact, not a ZK proof. Future: SP1/RISC Zero.",
        }
