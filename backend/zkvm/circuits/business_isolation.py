"""business_isolation circuit — no shared PII hash overlap between shops."""
from __future__ import annotations


class BusinessIsolationCircuit:
    name = "business_isolation"

    @staticmethod
    def verify(public_inputs: dict, private_witness: dict) -> dict:
        a_data = private_witness.get("shop_a_data", {})
        b_data = private_witness.get("shop_b_data", {})
        a_hashes = set(a_data.get("pii_hashes", []))
        b_hashes = set(b_data.get("pii_hashes", []))
        if a_hashes & b_hashes:
            return {"isolated": False, "reason": "pii overlap"}
        return {"isolated": True, "reason": "ok"}

    @staticmethod
    def get_statement(public_inputs: dict, isolated: bool) -> dict:
        return {
            "shop_a_id": public_inputs.get("shop_a_id"),
            "shop_b_id": public_inputs.get("shop_b_id"),
            "isolated": isolated,
        }
