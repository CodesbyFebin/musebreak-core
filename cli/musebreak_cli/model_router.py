"""Model router — role → model/tier, with open-weight equivalents labeled clearly.

Operator-console roster (open equivalents; we do NOT assert a proprietary Meta endpoint exists):
  Muse Wonderful  → Llama-3-70B   (labeled as such)
  Muse Code       → Code Llama
  guard prefilter → Llama-Guard-3-8B
  deep review     → Llama-3-70B
  recon/workers   → Llama-3-8B

Tier ladder (most → least capable): wonderful-cyber / wonderful > wonder > spark > glimmer/llama.
Routing is escalate-only for sensitive steps. Red tier always requires a named human approver for exec.
"""
from __future__ import annotations

from dataclasses import dataclass

# Canonical operator-console roles → (display_model, open_equivalent, tier, why)
AGENT_ROSTER: dict[str, dict] = {
    "orchestrator": {
        "model": "muse-wonderful",
        "open_equivalent": "llama-3-70b",
        "tier": "blue",
        "why": "1× Wonderful orchestrator — long-horizon mission planning (open eq: Llama-3-70B)",
        "vm": None,
    },
    "recon": {
        "model": "llama-3-8b",
        "open_equivalent": "llama-3-8b",
        "tier": "green",
        "why": "defensive asset inventory on OWN lab only (e.g. nmap -sV against in-scope targets)",
        "vm": "kali",
    },
    "code": {
        "model": "muse-code",
        "open_equivalent": "code-llama",
        "tier": "blue",
        "why": "Muse Code runtime — plans/patches (open eq: Code Llama)",
        "vm": "kali",
    },
    "review": {
        "model": "llama-guard-3-8b+llama-3-70b",
        "open_equivalent": "llama-guard-3-8b + llama-3-70b",
        "tier": "green",
        "why": "Llama-Guard-3-8B prefilter + Llama-3-70B deep review (fail-closed)",
        "vm": None,
    },
    "analyzer": {
        "model": "muse-wonderful-cyber",
        "open_equivalent": "llama-3-70b",
        "tier": "red",
        "why": "defensive vuln→mitigation mapping ONLY — no exploit generation; red ⇒ human approver",
        "vm": "kali",
    },
    "report": {
        "model": "llama-3-70b",
        "open_equivalent": "llama-3-70b",
        "tier": "green",
        "why": "authorized lab report authoring",
        "vm": None,
    },
}

# Backward-compat aliases used by the earlier swarm scaffold / mission files
_ALIASES = {
    "planner": "orchestrator",
    "recon-analyst": "recon",
    "exploitdev": "analyzer",
    "reviewer": "review",
    "reporter": "report",
    "default": "recon",
}

# Flat routing table for ModelRouter.route()
ROUTING_TABLE: dict[str, tuple[str, str, str]] = {
    role: (info["model"], info["tier"], info["why"]) for role, info in AGENT_ROSTER.items()
}
# aliases share the same routing
for alias, canon in _ALIASES.items():
    if alias not in ROUTING_TABLE and canon in AGENT_ROSTER:
        info = AGENT_ROSTER[canon]
        ROUTING_TABLE[alias] = (info["model"], info["tier"], info["why"] + f" [alias→{canon}]")

TIER_RANK = {"green": 0, "blue": 1, "red": 2}


@dataclass
class Route:
    role: str
    model: str
    tier: str
    reason: str
    open_equivalent: str = ""


class ModelRouter:
    def __init__(self, gateway_client=None, mock: bool = True):
        self.client = gateway_client
        self.mock = mock

    def _canon(self, role: str) -> str:
        return _ALIASES.get(role, role)

    def route(self, role: str, sensitive: bool = False) -> Route:
        canon = self._canon(role)
        info = AGENT_ROSTER.get(canon) or AGENT_ROSTER["recon"]
        model, tier, why = info["model"], info["tier"], info["why"]
        # A sensitive step may only ESCALATE a tier, never silently downgrade.
        if sensitive and TIER_RANK[tier] < TIER_RANK["red"] and canon in ("analyzer",):
            tier = "red"
        # legacy: exploitdev alias is always red
        if role == "exploitdev" or canon == "analyzer":
            if sensitive or role == "exploitdev":
                tier = "red" if TIER_RANK[tier] < TIER_RANK["red"] else tier
        return Route(role=role, model=model, tier=tier, reason=why,
                     open_equivalent=info.get("open_equivalent", ""))

    def infer(self, role: str, prompt: str, *, sensitive: bool = False) -> dict:
        r = self.route(role, sensitive=sensitive)
        if self.mock or self.client is None:
            return {
                "model": r.model,
                "open_equivalent": r.open_equivalent,
                "tier": r.tier,
                "simulated": True,
                "text": f"[MOCK {r.model}/{r.tier} ≡ {r.open_equivalent}] {role} → {prompt[:140]}",
            }
        out = self.client.query(prompt)
        out["model"] = out.get("model", r.model)
        out["tier"] = out.get("tier", r.tier)
        out["open_equivalent"] = r.open_equivalent
        return out
