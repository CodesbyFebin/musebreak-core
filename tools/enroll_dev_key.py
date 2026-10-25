#!/usr/bin/env python3
"""Generate a fresh dev MetaKey (P-256 keypair + 32-byte HMAC secret), enrol it with the gateway,
and export it to a JSON file the simulators/tests use (METAKEY_FILE).
Usage: ENROLL_TOKEN=... python tools/enroll_dev_key.py [--api http://localhost:8000] [--out dev_key.json]"""
import argparse, json, os, secrets, sys
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def make_key(owner: str, key_id: str | None = None) -> dict:
    priv = ec.generate_private_key(ec.SECP256R1())
    return {
        "key_id": key_id or "metakey-dev-" + secrets.token_hex(4), "owner": owner,
        "secret_hex": secrets.token_bytes(32).hex(),
        "priv_pem": priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()).decode(),
        "pub_pem": priv.public_key().public_bytes(serialization.Encoding.PEM,
                                                  serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
    }


def enroll(api: str, token: str, k: dict, client=httpx) -> None:
    r = client.post(api + "/keys/enroll", headers={"X-Enroll-Token": token}, json={
        "key_id": k["key_id"], "owner": k["owner"], "hmac_secret_hex": k["secret_hex"], "pubkey_pem": k["pub_pem"]})
    if r.status_code != 200:
        raise SystemExit(f"enrolment failed: {r.status_code} {r.text}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=os.getenv("API", "http://localhost:8000"))
    ap.add_argument("--owner", default=os.getenv("DEMO_USER", "judge"))
    ap.add_argument("--out", default="dev_key.json")
    a = ap.parse_args()
    tok = os.getenv("ENROLL_TOKEN") or sys.exit("set ENROLL_TOKEN")
    k = make_key(a.owner)
    enroll(a.api, tok, k)
    with open(a.out, "w") as f:
        json.dump(k, f, indent=2)
    os.chmod(a.out, 0o600)
    print(f"enrolled {k['key_id']} -> {a.out}")
