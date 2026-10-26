"""Prove agent — wraps Trust Plane hash-commitment MVP."""
from __future__ import annotations
from typing import Any
import sys
from pathlib import Path
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from zkvm.prover import ZKProver, GuardBlockedError


class ProveAgent:
    role = "prove"
    scaffold = False  # uses real hash-commitment prover code

    def __init__(self, mock: bool = True):
        self.mock = mock
        self.prover = ZKProver()

    def run(self, context: dict | None = None) -> dict[str, Any]:
        context = context or {}
        circuit = context.get("circuit", "audit_chain")
        public_inputs = context.get("public_inputs") or {
            "prev_hash": "0" * 64,
            "current_hash": "",
            "chain_id": context.get("chain_id", "demo"),
        }
        private_witness = context.get("private_witness") or {
            "prev_data": None,
            "current_data": {"event": "prove_agent", "ok": True},
        }
        if not public_inputs.get("current_hash"):
            from zkvm.hash import hash_canonical
            public_inputs = {
                **public_inputs,
                "current_hash": hash_canonical(private_witness["current_data"])["hex"],
            }
        try:
            proof = self.prover.prove(circuit, public_inputs, private_witness)
            return {"agent": self.role, "simulated": True, "proof": proof, "status": "ok"}
        except GuardBlockedError as e:
            return {"agent": self.role, "simulated": True, "status": "blocked", "error": str(e)}
