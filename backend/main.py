"""MuseBreak Gateway — Zero-Trust 2-gate auth in front of Muse models.

Gate 1: JWT (5 min) bound to a device fingerprint.
Gate 2: MetaKey — NFC HMAC-SHA256 over a 32-byte one-time challenge + QR intent signed with P-256.
Only Gate1 && Gate2 => short-lived Wonder token. /muse/query requires it. No bypass path exists.
"""
import json
import os
import secrets
import time
import uuid

import httpx
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import crypto
import metabolic_sim
from audit import AuditLog
from store import make_store
from guard.review_engine import review

# ---------------- config ----------------
JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_hex(32)
GATE1_TTL = int(os.getenv("GATE1_TTL", "300"))
CHALLENGE_TTL = int(os.getenv("CHALLENGE_TTL", "30"))
WONDER_TTL = int(os.getenv("WONDER_TTL", "60"))
DEMO_USER = os.getenv("DEMO_USER", "judge")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "musebreak")
META_MODEL_API_URL = os.getenv("META_MODEL_API_URL", "")
META_MODEL_API_KEY = os.getenv("META_MODEL_API_KEY", "")
AUDIT_PATH = os.getenv("AUDIT_PATH", os.path.join(os.path.dirname(__file__), "data", "audit.jsonl"))
# Tiers / models are configurable: JSON {"model": "tier"}
MODELS = json.loads(os.getenv("MUSE_MODELS", json.dumps({
    "muse-spark-1.1": "green", "muse-wonder": "blue", "muse-wonderful": "blue",
    "glimmer": "green", "red-defensive-research": "red",
})))
METABOLIC_MODELS = set(os.getenv("METABOLIC_MODELS", "muse-wonder,muse-wonderful").split(","))

# Registered MetaKeys. DEMO KEY MATERIAL IS PUBLIC — rotate for any real deployment.
DEMO_PUB = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEWsULMaBz1WB4YaafeKYgz9fX1Z4b
mO+vtfiJcLnCOaRVT+mX2ZNRQNl86yHbeFDkj9b1vFEnjcE4jonIRdG8hw==
-----END PUBLIC KEY-----"""
KEYS = {
    os.getenv("METAKEY_ID", "metakey-demo-001"): {
        "hmac_secret": bytes.fromhex(os.getenv(
            "METAKEY_SECRET", "6d757365627265616b2d64656d6f2d6465766963652d7365637265742d303031")),
        "pub": crypto.load_public_key(os.getenv("METAKEY_PUBKEY_PEM", DEMO_PUB)),
        "owner": DEMO_USER,
    }
}
# Admin enrolment token. Unset => /keys/enroll is disabled (no bypass by default).
ENROLL_TOKEN = os.getenv("ENROLL_TOKEN", "")

store = make_store(os.getenv("REDIS_URL"))
audit = AuditLog(AUDIT_PATH)
app = FastAPI(title="MuseBreak Gateway", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


# ---------------- models ----------------
class LoginReq(BaseModel):
    username: str
    password: str
    device_fingerprint: str


class ChallengeReq(BaseModel):
    key_id: str
    model: str = "muse-wonder"


class AuthorizeReq(BaseModel):
    challenge_id: str
    key_id: str
    nfc_hmac: str
    qr_signature: str
    counter: int  # MetaKey hardware monotonic counter, must strictly increase per key
    human_approver: str | None = None  # required for red tier


class EnrollReq(BaseModel):
    key_id: str
    owner: str
    hmac_secret_hex: str
    pubkey_pem: str


class QueryReq(BaseModel):
    prompt: str
    max_tokens: int = 256


# ---------------- helpers ----------------
def _decode(token: str, typ: str) -> dict:
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"invalid token: {e}")
    if claims.get("typ") != typ:
        raise HTTPException(401, "wrong token type")
    return claims


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    return authorization[7:]


def gate1(authorization: str | None = Header(None), x_device_fingerprint: str | None = Header(None)) -> dict:
    claims = _decode(_bearer(authorization), "gate1")
    if not x_device_fingerprint or claims["fp"] != crypto.fingerprint_hash(x_device_fingerprint):
        audit.append("gate1_fail", reason="fingerprint mismatch", sub=claims.get("sub"))
        raise HTTPException(401, "device fingerprint mismatch")
    return claims


def wonder(authorization: str | None = Header(None), x_device_fingerprint: str | None = Header(None)) -> dict:
    claims = _decode(_bearer(authorization), "wonder")
    if not x_device_fingerprint or claims["fp"] != crypto.fingerprint_hash(x_device_fingerprint):
        raise HTTPException(401, "device fingerprint mismatch")
    if not (claims.get("gate1") and claims.get("gate2")):
        raise HTTPException(403, "both gates required")
    return claims


# ---------------- endpoints ----------------
@app.get("/health")
def health():
    return {"ok": True, "store": type(store).__name__, "meta_api_configured": bool(META_MODEL_API_URL)}


@app.post("/login")
def login(req: LoginReq):
    ok = secrets.compare_digest(req.username, DEMO_USER) & secrets.compare_digest(req.password, DEMO_PASSWORD)
    fp = crypto.fingerprint_hash(req.device_fingerprint)
    if not ok:
        audit.append("gate1_fail", sub=req.username, device_fp=fp)
        raise HTTPException(401, "bad credentials")
    now = int(time.time())
    tok = jwt.encode({"sub": req.username, "fp": fp, "typ": "gate1", "iat": now,
                      "exp": now + GATE1_TTL, "jti": uuid.uuid4().hex}, JWT_SECRET, algorithm="HS256")
    audit.append("gate1_pass", sub=req.username, device_fp=fp)
    return {"gate1_token": tok, "expires_in": GATE1_TTL, "device_fp": fp}


@app.post("/challenge")
def challenge(req: ChallengeReq, g1: dict = Depends(gate1)):
    if req.key_id not in KEYS or KEYS[req.key_id]["owner"] != g1["sub"]:
        raise HTTPException(403, "unknown MetaKey for this user")
    if req.model not in MODELS:
        raise HTTPException(400, f"unknown model; choose from {list(MODELS)}")
    cid = uuid.uuid4().hex
    chal = crypto.new_challenge()
    qr_nonce = secrets.token_hex(16)
    store.set(f"chal:{cid}", json.dumps({"c": chal.hex(), "qr": qr_nonce, "sub": g1["sub"], "fp": g1["fp"],
                                          "key_id": req.key_id, "model": req.model}), CHALLENGE_TTL)
    return {"challenge_id": cid, "challenge": chal.hex(), "expires_in": CHALLENGE_TTL,
            "qr_payload": {"v": 1, "cid": cid, "nonce": qr_nonce, "model": req.model,
                           "tier": MODELS[req.model]}}


@app.post("/authorize")
def authorize(req: AuthorizeReq, g1: dict = Depends(gate1)):
    raw = store.getdel(f"chal:{req.challenge_id}")  # atomic single-use
    if raw is None:
        audit.append("gate2_fail", reason="challenge expired/replayed", key_id=req.key_id, device_fp=g1["fp"])
        raise HTTPException(401, "challenge expired or already used")
    st = json.loads(raw)
    if st["sub"] != g1["sub"] or st["fp"] != g1["fp"] or st["key_id"] != req.key_id:
        audit.append("gate2_fail", reason="binding mismatch", key_id=req.key_id, device_fp=g1["fp"])
        raise HTTPException(401, "challenge not bound to this session/key")
    key = KEYS[req.key_id]
    nfc_ok = crypto.verify_hmac(key["hmac_secret"],
                                crypto.nfc_message(bytes.fromhex(st["c"]), st["fp"], req.key_id, req.counter),
                                req.nfc_hmac)
    qr_ok = crypto.verify_p256(key["pub"], crypto.qr_message(req.challenge_id, st["qr"], st["model"]),
                               req.qr_signature)
    tier = MODELS[st["model"]]
    # Counter checked only after crypto passes, so forged taps cannot burn counter values.
    ctr_ok = nfc_ok and qr_ok and store.bump_counter(req.key_id, req.counter)
    hil_ok = tier != "red" or bool(req.human_approver)
    if not (nfc_ok and qr_ok and ctr_ok and hil_ok):
        audit.append("gate2_fail", nfc_ok=nfc_ok, qr_ok=qr_ok, counter_ok=ctr_ok, counter=req.counter, hil_ok=hil_ok, key_id=req.key_id,
                     device_fp=g1["fp"])
        raise HTTPException(401, {"nfc_ok": nfc_ok, "qr_ok": qr_ok, "counter_ok": ctr_ok,
                                 "human_in_loop_ok": hil_ok})
    now = int(time.time())
    tok = jwt.encode({"sub": g1["sub"], "fp": g1["fp"], "typ": "wonder", "gate1": True, "gate2": True,
                      "model": st["model"], "tier": tier, "key_id": req.key_id, "iat": now,
                      "exp": now + WONDER_TTL, "jti": uuid.uuid4().hex}, JWT_SECRET, algorithm="HS256")
    entry = audit.append("gate2_pass", sub=g1["sub"], device_fp=g1["fp"], key_id=req.key_id, model=st["model"],
                         tier=tier, gate1_jti=g1["jti"], counter=req.counter, nfc_hmac=req.nfc_hmac,
                         qr_signature=req.qr_signature[:32] + "…", human_approver=req.human_approver)
    return {"wonder_token": tok, "expires_in": WONDER_TTL, "model": st["model"], "tier": tier,
            "audit_hash": entry["hash"]}


@app.post("/keys/enroll")
def enroll(req: EnrollReq, x_enroll_token: str | None = Header(None)):
    if not ENROLL_TOKEN or not secrets.compare_digest(x_enroll_token or "", ENROLL_TOKEN):
        raise HTTPException(403, "enrolment disabled or bad token")
    secret = bytes.fromhex(req.hmac_secret_hex)
    if len(secret) < 32:
        raise HTTPException(400, "hmac secret must be >= 32 bytes")
    try:
        pub = crypto.load_public_key(req.pubkey_pem)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if req.key_id in KEYS:
        raise HTTPException(409, "key already enrolled")
    KEYS[req.key_id] = {"hmac_secret": secret, "pub": pub, "owner": req.owner}
    audit.append("key_enrolled", key_id=req.key_id, owner=req.owner)
    return {"enrolled": req.key_id}


@app.post("/muse/query")
def muse_query(req: QueryReq, w: dict = Depends(wonder)):
    model = w["model"]
    verdict = review(req.prompt, w["tier"])
    if not verdict["allow"]:
        audit.append("guard_block", sub=w["sub"], key_id=w["key_id"], model=model, verdict=verdict)
        raise HTTPException(403, {"guard": verdict})
    sim = metabolic_sim.infer(model, req.prompt, req.max_tokens) if model in METABOLIC_MODELS else None
    if META_MODEL_API_URL:
        # Generic OpenAI-style chat payload; adapt to whatever endpoint you configure.
        r = httpx.post(META_MODEL_API_URL, timeout=60,
                       headers={"Authorization": f"Bearer {META_MODEL_API_KEY}"},
                       json={"model": model, "max_tokens": req.max_tokens,
                             "messages": [{"role": "user", "content": req.prompt}]})
        r.raise_for_status()
        upstream, simulated = r.json(), False
    else:
        upstream, simulated = {"text": f"[SIMULATED RESPONSE — META_MODEL_API_URL not set] {model} would "
                                       f"answer: '{req.prompt[:120]}'. Configure META_MODEL_API_URL/KEY "
                                       f"to forward to a real endpoint."}, True
    entry = audit.append("muse_query", sub=w["sub"], device_fp=w["fp"], key_id=w["key_id"], model=model,
                         routed_to="metabolic_sim" if sim else "direct", simulated=simulated)
    return {"model": model, "tier": w["tier"], "simulated": simulated, "metabolic": sim,
            "response": upstream, "guard": verdict, "audit_hash": entry["hash"]}


@app.get("/audit")
def get_audit(limit: int = 50):
    return {"chain_valid": audit.verify_chain(), "entries": audit.read()[-limit:]}
