"""CLI helpers for Trust Plane hash-commitment prove/verify."""
from __future__ import annotations
import json
import sys
from pathlib import Path


def _backend_path() -> Path:
    return Path(__file__).resolve().parents[2] / "backend"


def _ensure_backend():
    bp = str(_backend_path())
    if bp not in sys.path:
        sys.path.insert(0, bp)


def prove(circuit: str, public_inputs: dict, private_witness: dict) -> dict:
    _ensure_backend()
    from zkvm.prover import ZKProver
    return ZKProver().prove(circuit, public_inputs, private_witness)


def verify(proof_b64: str, statement_hash_hex: str) -> dict:
    _ensure_backend()
    from zkvm.verifier import ZKVerifier
    return ZKVerifier().verify(proof_b64, statement_hash_hex)


def demo_order_payload():
    _ensure_backend()
    from zkvm.hash import hash_canonical
    items = [{"sku": "laptop-dell-1", "qty": 1, "price": 1000}]
    return {
        "circuit": "order_approve",
        "public_inputs": {
            "order_id": "ord-demo-1",
            "shop_id": "shop-1",
            "items_hash": hash_canonical(items)["hex"],
            "total": 1000,
            "prev_audit_hash": "0" * 64,
        },
        "private_witness": {
            "stock_available": {"laptop-dell-1": 100},
            "items": items,
        },
    }
