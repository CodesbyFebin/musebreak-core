"""MuseBreak crypto primitives: challenges, HMAC (constant-time), P-256 ECDSA verify."""
import hashlib
import hmac
import secrets

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

CHALLENGE_BYTES = 32


def new_challenge() -> bytes:
    return secrets.token_bytes(CHALLENGE_BYTES)


def fingerprint_hash(fp: str) -> str:
    return hashlib.sha256(fp.encode()).hexdigest()


def nfc_message(challenge: bytes, fp_hash: str, key_id: str, counter: int) -> bytes:
    # Bind the NFC tap to: the one-time challenge, the Gate1 device, the key id and the
    # key's hardware monotonic counter (decimal ASCII). Server requires counter to strictly increase.
    return (b"MUSEBREAK-NFC|" + challenge + b"|" + fp_hash.encode() + b"|" + key_id.encode()
            + b"|" + str(int(counter)).encode())


def qr_message(challenge_id: str, qr_nonce: str, model: str) -> bytes:
    # The QR "intent" the user approves on the key's e-ink screen.
    return f"MUSEBREAK-INTENT|{challenge_id}|{qr_nonce}|{model}".encode()


def compute_hmac(secret: bytes, msg: bytes) -> str:
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def verify_hmac(secret: bytes, msg: bytes, provided_hex: str) -> bool:
    expected = compute_hmac(secret, msg)
    return hmac.compare_digest(expected.encode(), (provided_hex or "").lower().encode())


def load_public_key(pem: str) -> ec.EllipticCurvePublicKey:
    key = serialization.load_pem_public_key(pem.encode())
    if not isinstance(key, ec.EllipticCurvePublicKey) or key.curve.name != "secp256r1":
        raise ValueError("MetaKey public key must be P-256")
    return key


def verify_p256(pub: ec.EllipticCurvePublicKey, msg: bytes, sig_hex: str) -> bool:
    """Accepts raw r||s (64 bytes, WebCrypto/CryptoKit style) or DER signatures."""
    try:
        sig = bytes.fromhex(sig_hex)
    except (ValueError, TypeError):
        return False
    if len(sig) == 64:
        sig = encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big"))
    try:
        pub.verify(sig, msg, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError):
        return False
