"""zkVM 24/7 heartbeat — periodically commits the audit tip via hash-commitment MVP.

NOT a real zero-knowledge proof. Labels every commit as hash-commitment-mvp.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

from zkvm.hash import hash_canonical, hash_chain


class ZkvmHeartbeat:
    """Background loop that appends a hash-commitment of the audit tip."""

    def __init__(self, audit, interval_s: float | None = None):
        self.audit = audit
        self.interval_s = float(
            interval_s
            if interval_s is not None
            else os.getenv("ZKVM_HEARTBEAT_INTERVAL_S", "15")
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last: dict[str, Any] | None = None
        self._commits = 0
        self._started_at: float | None = None
        self._errors: list[str] = []

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._started_at = time.time()
        self._thread = threading.Thread(target=self._loop, name="zkvm-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        self._commit_once()
        while not self._stop.wait(self.interval_s):
            self._commit_once()

    def _commit_once(self) -> None:
        try:
            tip = self.audit._last  # noqa: SLF001 — tip of append-only chain
            entries = self.audit.read()
            n = len(entries)
            payload = {
                "heartbeat": True,
                "audit_tip": tip,
                "entry_count": n,
                "ts": time.time(),
                "implementation": "hash-commitment-mvp",
            }
            h = hash_canonical(payload)
            chain = hash_chain(tip if tip else "0" * 64, h["canonical_bytes"])
            with self._lock:
                self._last = {
                    "ok": True,
                    "circuit": "heartbeat",
                    "implementation": "hash-commitment-mvp",
                    "is_zk": False,
                    "simulated": True,  # commitment MVP, not ZK
                    "statement_hash_hex": h["hex"],
                    "chain_hash": chain,
                    "audit_tip": tip,
                    "entry_count": n,
                    "committed_at": time.time(),
                    "note": "Continuous hash-commitment of the audit tip. NOT a real ZK proof.",
                }
                self._commits += 1
                self._errors = self._errors[-5:]
        except Exception as e:  # pragma: no cover
            with self._lock:
                self._errors.append(f"{time.time():.0f}: {e}")
                self._errors = self._errors[-5:]

    def status(self) -> dict[str, Any]:
        with self._lock:
            running = bool(self._thread and self._thread.is_alive())
            return {
                "running": running,
                "implementation": "hash-commitment-mvp",
                "is_zk": False,
                "interval_s": self.interval_s,
                "commits": self._commits,
                "started_at": self._started_at,
                "uptime_s": (time.time() - self._started_at) if self._started_at else 0,
                "last": self._last,
                "recent_errors": list(self._errors),
                "note": "Continuous hash-commitment of the audit tip. NOT a real ZK proof system.",
            }

    def commit_now(self) -> dict[str, Any]:
        self._commit_once()
        return self.status()
