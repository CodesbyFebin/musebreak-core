"""Recon agent scaffold — read-only, scope.yaml is law."""
from __future__ import annotations
from typing import Any


class ReconAgent:
    role = "recon"
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
            "detail": "Would run read-only recon inside Kali cage; dry-run/mock by default.",
            "context_keys": list(context.keys()),
        }
