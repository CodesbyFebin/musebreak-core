"""MetaKey online plane tests: real WebAuthn signature path via a software authenticator."""
# Named test_zz_* so it collects after test_gates.py (which sets CHALLENGE_TTL before importing main).
from __future__ import annotations
import base64, hashlib, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.pop("REDIS_URL", None)
os.environ.setdefault("AUDIT_PATH", os.path.join(tempfile.mkdtemp(), "audit.jsonl"))

import cbor2, pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
import main
from metakey import fido_auth
from zkvm.prover import ZKProver
from zkvm.verifier import ZKVerifier
from zkvm.circuits.business_isolation import BusinessIsolationCircuit

ORIGIN, RP = fido_auth.ORIGIN, fido_auth.RP_ID
b64u = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
client = TestClient(main.app)


class SoftKey:
    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cid = os.urandom(16)
        self.count = 0

    def register(self):
        n = self.key.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, "big"), -3: n.y.to_bytes(32, "big")})
        fido_auth.STATE["credentials"][b64u(self.cid)] = {"public_key": cose, "sign_count": 0, "user_id": "t"}

    def assert_(self, challenge_b64u, origin=ORIGIN):
        self.count += 1
        auth_data = hashlib.sha256(RP.encode()).digest() + b"\x05" + self.count.to_bytes(4, "big")
        cdj = json.dumps({"type": "webauthn.get", "challenge": challenge_b64u, "origin": origin}).encode()
        sig = self.key.sign(auth_data + hashlib.sha256(cdj).digest(), ec.ECDSA(hashes.SHA256()))
        return {"id": b64u(self.cid), "rawId": b64u(self.cid), "type": "public-key",
                "response": {"authenticatorData": b64u(auth_data), "clientDataJSON": b64u(cdj),
                             "signature": b64u(sig)}}


@pytest.fixture(autouse=True)
def fresh():
    fido_auth.reset_state()


def _draft(utr="123456789012", shop="shop-a"):
    r = client.post("/auth/draft", json={"order_id": "o1", "shop_id": shop, "utr": utr,
                                         "items": [{"sku": "laptop-dell-1", "qty": 1, "price": 1000}]})
    assert r.status_code == 200, r.text
    return r.json()


def test_valid_real_webauthn_bind_and_verify():
    k = SoftKey(); k.register()
    d = _draft()
    r = client.post("/auth/bind", json={"draft_id": d["draft_id"], "assertion": k.assert_(d["challenge"]),
                                        "device_hash": "dev01"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["simulated_assertion"] is False and body["proof"]["circuit"] == "fido_binding"
    p = body["proof"]
    v = client.post("/auth/verify", json={"proof_b64": p["proof_b64"], "statement_hash_hex": p["statement_hash_hex"]})
    assert v.json()["verified"] is True
    a = client.post("/auth/approve", json={"draft_id": d["draft_id"], "muv_approved": True})
    assert a.status_code == 200


def test_bad_signature_rejected_and_utr_not_recorded():
    k = SoftKey(); k.register()
    d = _draft()
    r = client.post("/auth/bind", json={"draft_id": d["draft_id"], "assertion": k.assert_(d["challenge"], origin="https://evil.example"),
                                        "device_hash": "dev01"})
    assert r.status_code == 401
    assert not fido_auth.STATE["utr_seen"]


def test_utr_replay_rejected():
    k = SoftKey(); k.register()
    d = _draft()
    assert client.post("/auth/bind", json={"draft_id": d["draft_id"], "assertion": k.assert_(d["challenge"]),
                                           "device_hash": "dev01"}).status_code == 200
    r = client.post("/auth/draft", json={"order_id": "o2", "shop_id": "shop-a", "utr": "123456789012"})
    assert r.status_code == 409


def test_utr_replay_rejected_between_two_open_drafts():
    k = SoftKey(); k.register()
    d1, d2 = _draft(), _draft()
    assert client.post("/auth/bind", json={"draft_id": d1["draft_id"], "assertion": k.assert_(d1["challenge"]),
                                           "device_hash": "x"}).status_code == 200
    r = client.post("/auth/bind", json={"draft_id": d2["draft_id"], "assertion": k.assert_(d2["challenge"]),
                                        "device_hash": "x"})
    assert r.status_code == 409


def test_tampered_transcript_fails_verify():
    k = SoftKey(); k.register()
    d = _draft()
    p = client.post("/auth/bind", json={"draft_id": d["draft_id"], "assertion": k.assert_(d["challenge"]),
                                        "device_hash": "dev01"}).json()["proof"]
    tampered = dict(p["statement"], device_hash="attacker")
    from zkvm.hash import hash_canonical
    assert ZKVerifier().verify(p["proof_b64"], hash_canonical(tampered)["hex"])["verified"] is False
    raw = bytearray(base64.b64decode(p["proof_b64"])); raw[0] ^= 1
    assert ZKVerifier().verify(base64.b64encode(raw).decode(), p["statement_hash_hex"])["verified"] is False


def test_simulated_assertion_is_labelled_and_can_be_disabled(monkeypatch):
    d = _draft()
    r = client.post("/auth/bind", json={"draft_id": d["draft_id"], "assertion": {"simulated": True, "challenge": d["challenge"]},
                                        "device_hash": "sim"})
    assert r.status_code == 200 and r.json()["simulated_assertion"] is True
    monkeypatch.setenv("MUSEBREAK_WEBAUTHN_ALLOW_SIMULATED", "false")
    d2 = _draft(utr="999999999999")
    r2 = client.post("/auth/bind", json={"draft_id": d2["draft_id"], "assertion": {"simulated": True, "challenge": d2["challenge"]},
                                         "device_hash": "sim"})
    assert r2.status_code == 401


def test_business_isolation_in_binding_and_circuit():
    from zkvm.hash import hash_canonical
    auth = {"order_id": "o", "shop_id": "shop-a", "utr_hash": "u"}
    pub = {"auth_hash": hash_canonical(auth)["hex"], "assertion_hash": hash_canonical({})["hex"],
           "business_id": "shop-b"}
    res = ZKProver().prove("fido_binding", pub, {"auth": auth, "assertion": {}, "assertion_verified": True})
    assert res["result"] == {"valid": False, "reason": "business isolation violated"}
    assert BusinessIsolationCircuit.verify({}, {"shop_a_data": {"pii_hashes": ["h1"]},
                                                "shop_b_data": {"pii_hashes": ["h1"]}})["isolated"] is False
