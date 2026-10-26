"""Deterministic canonical JSON (RFC 8785-ish) for Trust Plane commitments."""
from __future__ import annotations
import json
from typing import Any


def canonicalize(obj: Any) -> bytes:
    """Return UTF-8 bytes of sorted-key compact JSON. Deterministic across CPython versions."""
    def _sort(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: _sort(o[k]) for k in sorted(o.keys())}
        if isinstance(o, list):
            return [_sort(x) for x in o]
        return o

    sorted_obj = _sort(obj)
    return json.dumps(
        sorted_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_json_str(obj: Any) -> str:
    return canonicalize(obj).decode("utf-8")
