"""Thin client for the FastAPI gateway: Gate1 login, full Gate2 flow (via the enrolled MetaKey), and query.
Mirrors hardware/metakey_sim.js. Used by the CLI for real auth when a gateway + key are available."""
from __future__ import annotations

import json
import os
import time

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None


class GatewayClient:
    def __init__(self, base: str, key_file: str, fingerprint: str = "musebreak-cli"):
        self.base, self.key_file, self.fp = base.rstrip("/"), key_file, fingerprint
        self.g1 = None
        self.wonder = None
        self._key = None
        self._counter = int(time.time() * 1000)

    def _load_key(self):
        if self._key is None:
            with open(self.key_file) as f:
                self._key = json.load(f)
        return self._key

    def login(self, user: str, password: str) -> None:
        r = httpx.post(f"{self.base}/login", json={"username": user, "password": password,
                                                   "device_fingerprint": self.fp}, timeout=10)
        r.raise_for_status()
        self.g1 = r.json()["gate1_token"]

    def _headers(self, token):
        return {"Authorization": f"Bearer {token}", "X-Device-Fingerprint": self.fp}

    def authorize(self, model: str = "muse-wonder", human_approver: str | None = None) -> None:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        import hashlib, hmac
        k = self._load_key()
        ch = httpx.post(f"{self.base}/challenge", json={"key_id": k["key_id"], "model": model},
                        headers=self._headers(self.g1), timeout=10).json()
        self._counter += 1
        fp_hash = hashlib.sha256(self.fp.encode()).hexdigest()
        msg = (b"MUSEBREAK-NFC|" + bytes.fromhex(ch["challenge"]) + b"|" + fp_hash.encode()
               + b"|" + k["key_id"].encode() + b"|" + str(self._counter).encode())
        mac = hmac.new(bytes.fromhex(k["secret_hex"]), msg, hashlib.sha256).hexdigest()
        q = ch["qr_payload"]
        priv = load_pem_private_key(k["priv_pem"].encode(), None)
        sig = priv.sign(f"MUSEBREAK-INTENT|{q['cid']}|{q['nonce']}|{q['model']}".encode(),
                        ec.ECDSA(hashes.SHA256())).hex()
        body = {"challenge_id": ch["challenge_id"], "key_id": k["key_id"], "nfc_hmac": mac,
                "qr_signature": sig, "counter": self._counter, "human_approver": human_approver}
        r = httpx.post(f"{self.base}/authorize", json=body, headers=self._headers(self.g1), timeout=10)
        r.raise_for_status()
        self.wonder = r.json()["wonder_token"]

    def query(self, prompt: str, max_tokens: int = 256) -> dict:
        r = httpx.post(f"{self.base}/muse/query", json={"prompt": prompt, "max_tokens": max_tokens},
                       headers=self._headers(self.wonder), timeout=60)
        r.raise_for_status()
        return r.json()

    def audit(self, limit: int = 20) -> dict:
        return httpx.get(f"{self.base}/audit?limit={limit}", timeout=10).json()
