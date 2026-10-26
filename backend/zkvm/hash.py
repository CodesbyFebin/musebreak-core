"""SHA-256 helpers over canonical bytes + audit hash chain."""
from __future__ import annotations
import hashlib
from .canonical import canonicalize


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_canonical(obj) -> dict:
    canon = canonicalize(obj)
    digest = sha256_bytes(canon)
    return {
        "hex": digest.hex(),
        "bytes": digest,
        "canonical_bytes": canon,
        "canonical_str": canon.decode("utf-8"),
    }


def hash_chain(prev_hash_hex: str, current_canonical_bytes: bytes) -> str:
    """H(prev || current_canonical). Genesis prev is 64 zero hex digits."""
    if not prev_hash_hex:
        prev_hash_hex = "0" * 64
    prev_b = bytes.fromhex(prev_hash_hex)
    return sha256_hex(prev_b + current_canonical_bytes)


def hash_chain_bytes(prev_hash_hex: str, current_obj) -> dict:
    canon = canonicalize(current_obj)
    return {"prev": prev_hash_hex or "0" * 64, "new_hex": hash_chain(prev_hash_hex, canon), "canonical": canon}
