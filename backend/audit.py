"""Append-only, hash-chained JSONL audit log. Each entry includes prev_hash; tampering breaks the chain."""
import hashlib
import json
import os
import threading
import time

GENESIS = "0" * 64


class AuditLog:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._last = GENESIS
        for e in self.read():
            self._last = e["hash"]

    def read(self) -> list:
        if not os.path.exists(self.path):
            return []
        with open(self.path) as f:
            return [json.loads(l) for l in f if l.strip()]

    def append(self, event: str, **data) -> dict:
        with self._lock:
            entry = {"ts": time.time(), "event": event, **data, "prev_hash": self._last}
            body = json.dumps(entry, sort_keys=True, separators=(",", ":"))
            entry["hash"] = hashlib.sha256(body.encode()).hexdigest()
            with open(self.path, "a") as f:  # append-only
                f.write(json.dumps(entry, sort_keys=True) + "\n")
            self._last = entry["hash"]
            return entry

    def verify_chain(self) -> bool:
        prev = GENESIS
        for e in self.read():
            h = e.pop("hash")
            if e["prev_hash"] != prev:
                return False
            body = json.dumps(e, sort_keys=True, separators=(",", ":"))
            if hashlib.sha256(body.encode()).hexdigest() != h:
                return False
            prev = h
        return True
