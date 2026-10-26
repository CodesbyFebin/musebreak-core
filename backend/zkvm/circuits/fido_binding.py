"""fido_binding circuit — binds a verified WebAuthn assertion to a payment auth (constraint checker, not ZK).

Checks (hash-commitment MVP):
  * auth_hash == H(canonical auth {order_id, shop_id, utr_hash})
  * assertion_hash == H(assertion bytes), and the assertion was verified upstream
  * utr_hash not in the seen-UTR set (replay rejection)
  * business_id matches the auth shop_id (isolation)
  * every requested item fits in stock
"""
from __future__ import annotations
from ..hash import hash_canonical


class FidoBindingCircuit:
    name = "fido_binding"

    @staticmethod
    def verify(public_inputs: dict, private_witness: dict) -> dict:
        auth = private_witness.get("auth", {})
        if hash_canonical(auth)["hex"] != public_inputs.get("auth_hash"):
            return {"valid": False, "reason": "auth_hash mismatch"}
        if not private_witness.get("assertion_verified"):
            return {"valid": False, "reason": "assertion not verified"}
        if hash_canonical(private_witness.get("assertion", {}))["hex"] != public_inputs.get("assertion_hash"):
            return {"valid": False, "reason": "assertion_hash mismatch"}
        if auth.get("utr_hash") in set(private_witness.get("utr_seen", [])):
            return {"valid": False, "reason": "utr replay"}
        if public_inputs.get("business_id") != auth.get("shop_id"):
            return {"valid": False, "reason": "business isolation violated"}
        stock = private_witness.get("stock", {})
        for it in private_witness.get("items", []):
            if it.get("qty", 0) > stock.get(it.get("sku"), 0):
                return {"valid": False, "reason": f"oversell {it.get('sku')}"}
        return {"valid": True, "reason": "ok"}

    @staticmethod
    def get_statement(public_inputs: dict, valid: bool) -> dict:
        keys = ("auth_hash", "assertion_hash", "device_hash", "business_id", "prev_audit_hash", "stock_hash")
        return {**{k: public_inputs.get(k) for k in keys}, "valid": valid}
