"""order_approve circuit — stock + total + items_hash checks (constraint checker, not ZK)."""
from __future__ import annotations
from ..hash import hash_canonical


class OrderApproveCircuit:
    name = "order_approve"

    @staticmethod
    def verify(public_inputs: dict, private_witness: dict) -> dict:
        items = private_witness.get("items", [])
        stock = private_witness.get("stock_available", {})
        total_claimed = public_inputs.get("total", 0)

        for it in items:
            sku = it["sku"]
            qty = it["qty"]
            avail = stock.get(sku, 0)
            if qty > avail:
                return {"valid": False, "reason": f"oversell {sku} {qty}>{avail}"}

        calc_total = sum(it["qty"] * it["price"] for it in items)
        if calc_total != total_claimed:
            return {"valid": False, "reason": f"total mismatch {calc_total}!={total_claimed}"}

        calc_hash = hash_canonical(items)["hex"]
        if calc_hash != public_inputs.get("items_hash"):
            return {"valid": False, "reason": "items_hash mismatch"}

        return {"valid": True, "reason": "ok"}

    @staticmethod
    def get_statement(public_inputs: dict, valid: bool) -> dict:
        return {
            "order_id": public_inputs.get("order_id"),
            "shop_id": public_inputs.get("shop_id"),
            "items_hash": public_inputs.get("items_hash"),
            "valid": valid,
        }
