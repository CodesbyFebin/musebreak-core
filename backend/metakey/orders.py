"""MetaKey order draft/approve + audit verify endpoints (hash-commitment MVP)."""
from __future__ import annotations
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from zkvm.prover import ZKProver, GuardBlockedError
from zkvm.verifier import ZKVerifier
from zkvm.hash import hash_canonical

orders_router = APIRouter(prefix="/orders", tags=["metakey"])
audit_verify_router = APIRouter(prefix="/audit", tags=["metakey"])


class DraftReq(BaseModel):
    order_id: str
    shop_id: str
    items: list
    total: float
    utr: str | None = None
    prev_audit_hash: str = "0" * 64


class ApproveReq(BaseModel):
    order_id: str
    shop_id: str
    muv_approved: bool = False
    muv_hash: str | None = None


class AuditVerifyReq(BaseModel):
    proof_b64: str
    statement_hash_hex: str


@orders_router.post("/draft")
def draft_order(req: DraftReq):
    prover = ZKProver(use_open_source_only=os.getenv("USE_OPEN_SOURCE_ONLY", "true").lower() == "true")
    items_hash = hash_canonical(req.items)["hex"]
    public_inputs = {
        "order_id": req.order_id,
        "shop_id": req.shop_id,
        "items_hash": items_hash,
        "total": req.total,
        "prev_audit_hash": req.prev_audit_hash,
        "utr": req.utr,
    }
    private_witness = {
        "stock_available": {"laptop-dell-1": 100, "laptop-hp-1": 50},
        "items": req.items,
    }
    try:
        proof = prover.prove("order_approve", public_inputs, private_witness)
        return {
            "order_id": req.order_id,
            "proof": proof,
            "items_hash": items_hash,
            "status": "draft",
            "implementation": "hash-commitment-mvp",
            "simulated": True,
        }
    except GuardBlockedError as e:
        raise HTTPException(400, detail=str(e))


@orders_router.post("/approve")
def approve_order(req: ApproveReq):
    if not req.muv_approved:
        raise HTTPException(400, detail="MuV gate required — human/policy approval needed")
    prover = ZKProver()
    current = {"order_id": req.order_id, "approved": True, "muv_hash": req.muv_hash}
    current_hash = hash_canonical(current)["hex"]
    public_inputs = {
        "prev_hash": "0" * 64,
        "current_hash": req.muv_hash or current_hash,
        "chain_id": req.order_id,
    }
    private_witness = {"prev_data": None, "current_data": current}
    # If muv_hash provided and differs from current_hash, use chained form for circuit
    if req.muv_hash and req.muv_hash != current_hash:
        public_inputs["current_hash"] = current_hash
    proof = prover.prove("audit_chain", public_inputs, private_witness)
    return {
        "order_id": req.order_id,
        "status": "approved",
        "audit_proof": proof,
        "muv": True,
        "implementation": "hash-commitment-mvp",
        "simulated": True,
    }


@audit_verify_router.post("/verify")
def verify_audit(req: AuditVerifyReq):
    res = ZKVerifier().verify(req.proof_b64, req.statement_hash_hex)
    explanation = (
        "Proof verified (hash-commitment MVP)."
        if res["verified"]
        else f"Verification failed: {res.get('reason')} (hash-commitment MVP — not a ZK proof)."
    )
    return {**res, "explanation": explanation}
