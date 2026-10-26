"""Open-weights router — reuses Part-2 open_source mapping; hosted fallbacks are scaffolds."""
from __future__ import annotations
import os
import sys
from pathlib import Path

# Ensure backend root on path when imported as package sibling
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import open_source  # noqa: E402


class OpenWeightsRouter:
    """Route generation to Llama Stack / Ollama via open_source, or labelled scaffold providers."""

    def __init__(self):
        self.baseten_key = os.getenv("BASETEN_API_KEY")
        self.modal_key = os.getenv("MODAL_API_KEY")
        self.fireworks_key = os.getenv("FIREWORKS_API_KEY")
        self.use_open = open_source.use_open_source_only()

    def get_provider(self) -> str:
        if self.baseten_key:
            return "baseten"
        if self.modal_key:
            return "modal"
        if self.fireworks_key:
            return "fireworks"
        if self.use_open:
            return "llama-stack" if os.getenv("LLAMA_STACK_URL") else "ollama-simulated"
        return "unset"

    def resolve(self, muse_model: str = "muse-wonder") -> dict:
        mid, label = open_source.resolve_model_id(muse_model)
        return {
            "provider": self.get_provider(),
            "muse_model": muse_model,
            "open_model_id": mid,
            "open_label": label,
            "use_open_source_only": self.use_open,
        }

    async def generate(self, prompt: str, model: str = "meta-llama/Llama-3.3-70B-Instruct") -> dict:
        provider = self.get_provider()
        if provider in ("baseten", "modal", "fireworks"):
            # Keys present but HTTP not wired in this MVP — honest scaffold.
            return {
                "provider": provider,
                "model": model,
                "response": f"[SCAFFOLD {provider}] would call {model}: {prompt[:80]}",
                "simulated": True,
                "scaffold": True,
            }
        return {
            "provider": provider,
            "model": model,
            "response": f"[SIMULATED {model}] {prompt[:80]}",
            "simulated": True,
            "scaffold": True,
            "note": "No GPU/hosted backend in this environment; use LLAMA_STACK_URL when available.",
        }
