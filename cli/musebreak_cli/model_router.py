"""Model router: maps agent roles + task sensitivity to a Muse model tier, then calls the gateway.

Tier ladder (most → least capable): wonderful-cyber > wonderful > wonder > spark > glimmer/llama (open-weight).
Routing is policy, not hard-coded per call: see ROUTING_TABLE. Open-weight models (Glimmer/Llama) are the
default for cheap/bulk work and for anything that can run fully inside the sandbox without a frontier call.
"""
from __future__ import annotations

from dataclasses import dataclass

# role -> (model, tier, why)
ROUTING_TABLE: dict[str, tuple[str, str, str]] = {
    "planner": ("muse-wonderful", "blue", "long-horizon mission planning / decomposition"),
    "recon-analyst": ("muse-wonder", "blue", "frontier reasoning over collected lab data"),
    "exploitdev": ("muse-wonderful-cyber", "red", "defensive/lab-only analysis; red tier => human approver"),
    "reviewer": ("muse-spark-1.1", "green", "fast guard/second-opinion safety review"),
    "reporter": ("glimmer", "green", "open-weight summarization/write-up, cheap + local-capable"),
    "default": ("llama-3.1-8b", "green", "open-weight workhorse for bulk/offline steps"),
}

TIER_RANK = {"green": 0, "blue": 1, "red": 2}


@dataclass
class Route:
    role: str
    model: str
    tier: str
    reason: str


class ModelRouter:
    def __init__(self, gateway_client=None, mock: bool = True):
        self.client = gateway_client
        self.mock = mock

    def route(self, role: str, sensitive: bool = False) -> Route:
        model, tier, why = ROUTING_TABLE.get(role, ROUTING_TABLE["default"])
        # A sensitive step may only ESCALATE a tier, never silently downgrade.
        if sensitive and TIER_RANK[tier] < TIER_RANK["red"] and role in ("exploitdev",):
            tier = "red"
        return Route(role=role, model=model, tier=tier, reason=why)

    def infer(self, role: str, prompt: str, *, sensitive: bool = False) -> dict:
        r = self.route(role, sensitive=sensitive)
        if self.mock or self.client is None:
            return {"model": r.model, "tier": r.tier, "simulated": True,
                    "text": f"[MOCK {r.model}/{r.tier}] {role} -> {prompt[:140]}"}
        out = self.client.query(prompt)  # goes through gateway /muse/query (guard + metabolic + upstream)
        out["model"], out["tier"] = out.get("model", r.model), out.get("tier", r.tier)
        return out
