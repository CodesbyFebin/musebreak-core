"""Thin HTTP client toward Llama Stack / local gateway — scaffold when unreachable."""
from __future__ import annotations
import os
from typing import Any


class MetaGatewayClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("LLAMA_STACK_URL") or "").rstrip("/")
        self.simulated = not bool(self.base_url)

    def health(self) -> dict[str, Any]:
        if not self.base_url:
            return {"ok": False, "simulated": True, "reason": "LLAMA_STACK_URL unset"}
        try:
            import httpx
            r = httpx.get(self.base_url + "/health", timeout=2.0)
            return {"ok": r.is_success, "simulated": False, "status": r.status_code}
        except Exception as e:
            return {"ok": False, "simulated": True, "reason": str(e)}

    def chat(self, model: str, prompt: str) -> dict[str, Any]:
        if self.simulated:
            return {"simulated": True, "model": model, "text": f"[SIMULATED] {prompt[:100]}"}
        try:
            import httpx
            # OpenAI-compatible shape used by Llama Stack / OGX
            r = httpx.post(
                self.base_url + "/v1/chat/completions",
                timeout=60,
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            )
            r.raise_for_status()
            return {"simulated": False, "model": model, "raw": r.json()}
        except Exception as e:
            return {"simulated": True, "model": model, "text": f"[SIMULATED unreachable] {e}"}
