"""FastAPI router for Trust Plane hash-commitment prove/verify (mounted at /zkvm)."""
from __future__ import annotations
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .prover import ZKProver, GuardBlockedError
from .verifier import ZKVerifier
from .circuits import CIRCUITS

router = APIRouter(prefix="/zkvm", tags=["zkvm"])


class ProveReq(BaseModel):
    circuit: str
    public_inputs: dict
    private_witness: dict


class VerifyReq(BaseModel):
    proof_b64: str
    statement_hash_hex: str


@router.get("/circuits")
def list_circuits():
    return {
        "circuits": list(CIRCUITS.keys()),
        "implementation": "hash-commitment-mvp",
        "note": "Not a real ZK proof system. Future: SP1/RISC Zero.",
    }


@router.post("/prove")
def prove(req: ProveReq):
    prover = ZKProver(use_open_source_only=os.getenv("USE_OPEN_SOURCE_ONLY", "true").lower() == "true")
    try:
        return prover.prove(req.circuit, req.public_inputs, req.private_witness)
    except GuardBlockedError as e:
        raise HTTPException(status_code=400, detail=f"Guard blocked: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify")
def verify(req: VerifyReq):
    return ZKVerifier().verify(req.proof_b64, req.statement_hash_hex)
