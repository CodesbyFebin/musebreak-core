"""utr_unique circuit — UPI/UTR uniqueness + format check."""
from __future__ import annotations
import re


class UTRUniqueCircuit:
    name = "utr_unique"

    @staticmethod
    def verify(public_inputs: dict, private_witness: dict) -> dict:
        utr = str(public_inputs.get("utr", ""))
        seen = private_witness.get("utr_list", [])
        if not re.match(r"^\d{10,18}$", utr):
            return {"unique": False, "reason": "utr format invalid"}
        if utr in seen:
            return {"unique": False, "reason": "utr replay"}
        return {"unique": True, "reason": "ok"}

    @staticmethod
    def get_statement(public_inputs: dict, unique: bool) -> dict:
        return {
            "utr": public_inputs.get("utr"),
            "shop_id": public_inputs.get("shop_id"),
            "unique": unique,
        }
