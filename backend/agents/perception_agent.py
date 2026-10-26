"""Perception agent scaffold (SAM 2.1 / DINOv2 / vision)."""
from __future__ import annotations
from typing import Any


class PerceptionAgent:
    role = "perception"
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
            "detail": "Would run SAM 2.1 segmentation + DINOv2 fingerprint + vision read when models available.",
            "context_keys": list(context.keys()),
        }
