"""MetaKey online plane: UTR + FIDO2/WebAuthn assertion bound into the hash-commitment transcript.

Flow: /auth/register/options -> /auth/register/verify (real WebAuthn registration)
      /auth/draft  (order_id, shop_id, 12-digit UTR) -> draft_id + WebAuthn challenge
      /auth/bind   (draft_id, assertion, device_hash) -> verifies assertion, proves fido_binding
      /auth/approve (MuV human gate) and /auth/verify (re-check the commitment).

Assertion verification is REAL (py_webauthn verify_authentication_response) when a
credential was registered. A clearly-labelled SIMULATED path exists for demos without an
authenticator; it is enabled only while MUSEBREAK_WEBAUTHN_ALLOW_SIMULATED is not "false",
and every response from it carries simulated_assertion=True.

The proof is a hash-commitment MVP, NOT a zero-knowledge proof. State is in-memory.
"""
from __future__ import annotations
import base64
import os
import secrets
import time
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from zkvm.hash import hash_canonical
from zkvm.prover import ZKProver
from zkvm.verifier import ZKVerifier

try:
    import webauthn
    from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json
    from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement
    HAVE_WEBAUTHN = True
except Exception:  # pragma: no cover
    HAVE_WEBAUTHN = False

auth_router = APIRouter(prefix="/auth", tags=["metakey-fido"])

RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")
RP_NAME = "MuseBreak MetaKey"
ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:3000")
DEFAULT_STOCK = {"laptop-dell-1": 100, "laptop-hp-1": 50}

STATE: dict = {"credentials": {}, "reg_challenges": {}, "drafts": {}, "utr_seen": set(), "bound": {},
               "prev_audit_hash": "0" * 64}


def reset_state() -> None:
    STATE.update(credentials={}, reg_challenges={}, drafts={}, utr_seen=set(), bound={}, prev_audit_hash="0" * 64)


def _allow_sim() -> bool:
    return os.getenv("MUSEBREAK_WEBAUTHN_ALLOW_SIMULATED", "true").lower() != "false"


def _utr_hash(utr: str) -> str:
    # Raw 12-digit UTR never enters the transcript (it also trips the PII guard).
    return hash_canonical({"utr": utr})["hex"]


class RegOptReq(BaseModel):
    user_id: str = "demo-user"


class RegVerifyReq(BaseModel):
    user_id: str = "demo-user"
    credential: dict


class DraftReq(BaseModel):
    order_id: str
    shop_id: str
    utr: str
    items: list = []


class BindReq(BaseModel):
    draft_id: str
    assertion: dict
    device_hash: str


class ApproveReq(BaseModel):
    draft_id: str
    muv_approved: bool = False


class VerifyReq(BaseModel):
    proof_b64: str
    statement_hash_hex: str


@auth_router.post("/register/options")
def register_options(req: RegOptReq):
    if not HAVE_WEBAUTHN:
        raise HTTPException(501, "webauthn library not installed")
    opts = webauthn.generate_registration_options(rp_id=RP_ID, rp_name=RP_NAME, user_name=req.user_id,
                                                  user_id=req.user_id.encode())
    STATE["reg_challenges"][req.user_id] = opts.challenge
    return {"options": options_to_json(opts)}


@auth_router.post("/register/verify")
def register_verify(req: RegVerifyReq):
    challenge = STATE["reg_challenges"].pop(req.user_id, None)
    if not challenge:
        raise HTTPException(400, "no pending registration")
    try:
        v = webauthn.verify_registration_response(credential=req.credential, expected_challenge=challenge,
                                                  expected_rp_id=RP_ID, expected_origin=ORIGIN)
    except Exception as e:
        raise HTTPException(400, f"registration failed: {e}")
    cid = bytes_to_base64url(v.credential_id)
    STATE["credentials"][cid] = {"public_key": v.credential_public_key, "sign_count": v.sign_count,
                                 "user_id": req.user_id}
    return {"credential_id": cid, "registered": True, "webauthn": "real"}


@auth_router.post("/draft")
def draft(req: DraftReq):
    if not (req.utr.isdigit() and len(req.utr) == 12):
        raise HTTPException(400, "UTR must be exactly 12 digits")
    uh = _utr_hash(req.utr)
    if uh in STATE["utr_seen"]:
        raise HTTPException(409, "UTR already used (replay rejected)")
    challenge = secrets.token_bytes(32)
    draft_id = uuid.uuid4().hex
    STATE["drafts"][draft_id] = {"order_id": req.order_id, "shop_id": req.shop_id, "utr_hash": uh,
                                 "items": req.items, "challenge": challenge, "created": time.time()}
    allow = [{"type": "public-key", "id": cid} for cid in STATE["credentials"]]
    return {"draft_id": draft_id, "utr_hash": uh,
            "challenge": base64.urlsafe_b64encode(challenge).rstrip(b"=").decode(),
            "rp_id": RP_ID, "allow_credentials": allow, "simulated_allowed": _allow_sim()}


def _verify_assertion(d: dict, assertion: dict) -> tuple[bool, bool, str]:
    """Returns (ok, simulated, reason)."""
    if assertion.get("simulated"):
        if not _allow_sim():
            return False, True, "simulated assertions disabled"
        expected = base64.urlsafe_b64encode(d["challenge"]).rstrip(b"=").decode()
        return (assertion.get("challenge") == expected), True, "simulated (challenge echo only, no signature)"
    if not HAVE_WEBAUTHN:
        return False, False, "webauthn library not installed"
    cred = STATE["credentials"].get(assertion.get("id") or assertion.get("rawId", ""))
    if not cred:
        return False, False, "unknown credential (register first)"
    try:
        v = webauthn.verify_authentication_response(
            credential=assertion, expected_challenge=d["challenge"], expected_rp_id=RP_ID,
            expected_origin=ORIGIN, credential_public_key=cred["public_key"],
            credential_current_sign_count=cred["sign_count"], require_user_verification=False)
    except Exception as e:
        return False, False, f"assertion invalid: {e}"
    cred["sign_count"] = v.new_sign_count
    return True, False, "webauthn signature verified"


@auth_router.post("/bind")
def bind(req: BindReq):
    d = STATE["drafts"].get(req.draft_id)
    if not d:
        raise HTTPException(404, "unknown draft")
    if d["utr_hash"] in STATE["utr_seen"]:
        raise HTTPException(409, "UTR already used (replay rejected)")
    ok, simulated, reason = _verify_assertion(d, req.assertion)
    if not ok:
        raise HTTPException(401, reason)
    auth = {"order_id": d["order_id"], "shop_id": d["shop_id"], "utr_hash": d["utr_hash"]}
    public_inputs = {
        "auth_hash": hash_canonical(auth)["hex"],
        "assertion_hash": hash_canonical(req.assertion)["hex"],
        "device_hash": req.device_hash,
        "business_id": d["shop_id"],
        "prev_audit_hash": STATE["prev_audit_hash"],
        "stock_hash": hash_canonical(DEFAULT_STOCK)["hex"],
    }
    witness = {"auth": auth, "assertion": req.assertion, "assertion_verified": True,
               "utr_seen": sorted(STATE["utr_seen"]), "stock": DEFAULT_STOCK, "items": d["items"]}
    proof = ZKProver().prove("fido_binding", public_inputs, witness)
    if not proof["result"].get("valid"):
        raise HTTPException(400, proof["result"].get("reason"))
    # UTR recorded only after the assertion verified and the binding passed.
    STATE["utr_seen"].add(d["utr_hash"])
    STATE["prev_audit_hash"] = proof["statement_hash_hex"]
    STATE["bound"][req.draft_id] = proof
    d.pop("challenge", None)
    return {"draft_id": req.draft_id, "bound": True, "proof": proof, "assertion_check": reason,
            "simulated_assertion": simulated, "implementation": "hash-commitment-mvp"}


@auth_router.post("/approve")
def approve(req: ApproveReq):
    if req.draft_id not in STATE["bound"]:
        raise HTTPException(400, "bind first")
    if not req.muv_approved:
        raise HTTPException(400, "MuV gate required — human approval needed")
    return {"draft_id": req.draft_id, "status": "approved", "muv": True,
            "statement_hash_hex": STATE["bound"][req.draft_id]["statement_hash_hex"]}


@auth_router.post("/verify")
def verify(req: VerifyReq):
    return {**ZKVerifier().verify(req.proof_b64, req.statement_hash_hex),
            "note": "hash-commitment MVP — not a zero-knowledge proof"}
