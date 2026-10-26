"""Probe agent scaffold — guarded safe probes."""
from __future__ import annotations
from typing import Any


class ProbeAgent:
    role = "probe"
    scaffold = True

    def __init__(self, mock: bool = True):
        self.mock = mock

    def run(self, context: dict | None = None) -> dict[str, Any]:
        context = context or {}
        return {
            "agent": self.role,
            "scaffold": True,
            "simulated": True,
            "mock": self.mock,
            "status": "ok",
            "detail": "Would generate defensive probes via Code Llama when available; Llama Guard fail-closed.",
            "context_keys": list(context.keys()),
        }
