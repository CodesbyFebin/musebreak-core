"""Distributed load test of the FULL MuseBreak flow:
   login (Gate1) -> /challenge -> MetaKey NFC HMAC + P-256 QR -> /authorize (Gate2) -> Go proxy -> upstream.
Each simulated user enrols its OWN dev MetaKey so per-key monotonic counters never collide.

Single box:   locust -f locustfile.py --headless -u 50 -r 10 -t 30s --host http://localhost:8000
Distributed:  locust -f locustfile.py --master --expect-workers 4 ...
              locust -f locustfile.py --worker --master-host <master-ip>     (x N machines)
Env: PROXY_URL (default http://localhost:8443), ENROLL_TOKEN, DEMO_PASSWORD
"""
import os, secrets, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from locust import HttpUser, between, task
import crypto
from enroll_dev_key import make_key

PROXY = os.getenv("PROXY_URL", "http://localhost:8443")
TOKEN = os.getenv("ENROLL_TOKEN", "")
PASSWORD = os.getenv("DEMO_PASSWORD", "musebreak")
USER = os.getenv("DEMO_USER", "judge")


class MuseBreakUser(HttpUser):
    wait_time = between(0, 0.05)

    def on_start(self):
        self.k = make_key(USER, "lt-" + secrets.token_hex(6))
        r = self.client.post("/keys/enroll", headers={"X-Enroll-Token": TOKEN}, name="/keys/enroll", json={
            "key_id": self.k["key_id"], "owner": USER, "hmac_secret_hex": self.k["secret_hex"],
            "pubkey_pem": self.k["pub_pem"]})
        if r.status_code != 200:
            raise RuntimeError(f"enrol failed {r.status_code}")
        self.priv = serialization.load_pem_private_key(self.k["priv_pem"].encode(), None)
        self.secret = bytes.fromhex(self.k["secret_hex"])
        self.fp = "lt-device-" + secrets.token_hex(4)
        self.counter = 0
        self.g1_at = 0

    def _gate1(self):
        if time.time() - self.g1_at > 240:
            r = self.client.post("/login", json={"username": USER, "password": PASSWORD,
                                                 "device_fingerprint": self.fp})
            self.h = {"Authorization": "Bearer " + r.json()["gate1_token"], "X-Device-Fingerprint": self.fp}
            self.g1_at = time.time()

    @task
    def full_flow(self):
        self._gate1()
        ch = self.client.post("/challenge", json={"key_id": self.k["key_id"], "model": "muse-wonder"},
                              headers=self.h).json()
        self.counter += 1
        mac = crypto.compute_hmac(self.secret, crypto.nfc_message(
            bytes.fromhex(ch["challenge"]), crypto.fingerprint_hash(self.fp), self.k["key_id"], self.counter))
        q = ch["qr_payload"]
        sig = self.priv.sign(crypto.qr_message(q["cid"], q["nonce"], q["model"]), ec.ECDSA(hashes.SHA256()))
        with self.client.post("/authorize", headers=self.h, catch_response=True, json={
                "challenge_id": ch["challenge_id"], "key_id": self.k["key_id"], "nfc_hmac": mac,
                "qr_signature": sig.hex(), "counter": self.counter}) as r:
            if r.status_code != 200:  # 401/403 are failures, not "secure rejections"
                r.failure(f"gate2 {r.status_code}"); return
            wonder = r.json()["wonder_token"]
        with self.client.post(PROXY + "/v1/chat/completions", name="proxy /v1/chat/completions",
                              catch_response=True, headers={"Authorization": "Bearer " + wonder,
                                                            "X-Device-Fingerprint": self.fp},
                              json={"model": "muse-wonder", "messages": [{"role": "user", "content": "ping"}]}) as r:
            if r.status_code != 200:
                r.failure(f"proxy {r.status_code}")
