"""Remediation agent scaffold — PR/SARIF/WAF suggestions."""
from __future__ import annotations
from typing import Any


class RemediationAgent:
    role = "remediation"
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
            "detail": "Would draft defensive patches when Code Llama available.",
            "context_keys": list(context.keys()),
        }
