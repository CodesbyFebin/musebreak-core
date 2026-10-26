"""audit_chain circuit — verifies hash_chain linkage between prev and current."""
from __future__ import annotations
from ..hash import hash_canonical, hash_chain
from ..canonical import canonicalize


class AuditChainCircuit:
    name = "audit_chain"

    @staticmethod
    def verify(public_inputs: dict, private_witness: dict) -> dict:
        prev_hash = public_inputs.get("prev_hash") or "0" * 64
        current_hash = public_inputs.get("current_hash", "")
        prev_data = private_witness.get("prev_data")
        current_data = private_witness.get("current_data")

        if current_data is None:
            return {"intact": False, "reason": "missing current_data"}

        # current_hash must match hash of current_data
        calc_current = hash_canonical(current_data)["hex"]
        if current_hash and current_hash != calc_current:
            # also accept hash_chain form: H(prev || canon(current))
            chained = hash_chain(prev_hash, canonicalize(current_data))
            if current_hash != chained:
                return {"intact": False, "reason": "current_hash mismatch"}

        if prev_data is not None:
            calc_prev = hash_canonical(prev_data)["hex"]
            if prev_hash not in ("0" * 64, calc_prev):
                return {"intact": False, "reason": "prev_hash mismatch"}

        # Prefer chain form when public current_hash is the chained value
        chained = hash_chain(prev_hash, canonicalize(current_data))
        intact = (current_hash in (calc_current, chained)) if current_hash else True
        return {"intact": intact, "reason": "ok" if intact else "chain break", "chained_hash": chained}

    @staticmethod
    def get_statement(public_inputs: dict, intact: bool) -> dict:
        return {
            "chain_id": public_inputs.get("chain_id"),
            "prev_hash": public_inputs.get("prev_hash"),
            "current_hash": public_inputs.get("current_hash"),
            "intact": intact,
        }
