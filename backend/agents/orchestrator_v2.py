"""Orchestrator v2 — runs agent pipeline as scaffolds when models/GPU absent."""
from __future__ import annotations
from typing import Any
from .perception_agent import PerceptionAgent
from .recon_agent import ReconAgent
from .probe_agent import ProbeAgent
from .chain_agent import ChainAgent
from .prove_agent import ProveAgent
from .voice_agent import VoiceAgent
from .remediation_agent import RemediationAgent


class OrchestratorV2:
    """Perception → Recon → Probe → Chain → Prove → Voice → Remediation.

    Each step is a scaffold unless the step itself has real local logic (prove).
    """

    def __init__(self, mock: bool = True, lang: str = "ml"):
        self.mock = mock
        self.agents = [
            PerceptionAgent(mock=mock),
            ReconAgent(mock=mock),
            ProbeAgent(mock=mock),
            ChainAgent(mock=mock),
            ProveAgent(mock=mock),
            VoiceAgent(mock=mock, lang=lang),
            RemediationAgent(mock=mock),
        ]

    def run(self, mission: dict | None = None) -> dict[str, Any]:
        mission = mission or {"name": "defensive-demo", "dry_run": True}
        steps = []
        ctx: dict[str, Any] = {"mission": mission}
        for agent in self.agents:
            out = agent.run(ctx)
            steps.append(out)
            ctx[agent.role] = out
        return {
            "orchestrator": "v2",
            "simulated": True,
            "scaffold": True,
            "mission": mission,
            "steps": steps,
            "note": "Agent models/sandbox mocked when deps/GPU absent. Prove step uses hash-commitment-mvp.",
        }
