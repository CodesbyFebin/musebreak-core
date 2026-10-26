"""Hash-commitment verifier MVP — checks proof prefix equals statement hash."""
from __future__ import annotations
import base64
import time

IMPLEMENTATION = "hash-commitment-mvp"


class ZKVerifier:
    def verify(self, proof_b64: str, statement_hash_hex: str) -> dict:
        start = time.perf_counter()
        try:
            proof_bytes = base64.b64decode(proof_b64)
            if len(proof_bytes) != 256:
                return {
                    "verified": False,
                    "reason": f"proof len {len(proof_bytes)} != 256 (encoding size)",
                    "verify_time_ms": int((time.perf_counter() - start) * 1000),
                    "simulated": True,
                    "implementation": IMPLEMENTATION,
                }
            if proof_bytes[:32].hex() != statement_hash_hex:
                return {
                    "verified": False,
                    "reason": "hash mismatch",
                    "verify_time_ms": int((time.perf_counter() - start) * 1000),
                    "simulated": True,
                    "implementation": IMPLEMENTATION,
                }
            return {
                "verified": True,
                "reason": "ok",
                "verify_time_ms": int((time.perf_counter() - start) * 1000),
                "simulated": True,
                "implementation": IMPLEMENTATION,
            }
        except Exception as e:
            return {
                "verified": False,
                "reason": str(e),
                "verify_time_ms": int((time.perf_counter() - start) * 1000),
                "simulated": True,
                "implementation": IMPLEMENTATION,
            }


def verify_statement(proof: dict) -> dict:
    return ZKVerifier().verify(proof["proof_b64"], proof["statement_hash_hex"])
