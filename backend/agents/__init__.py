"""Agent scaffolds — importable modules with mocked model/sandbox when GPU/deps absent.

Roles: perception, recon, probe, chain, prove, voice, remediation (+ orchestrator_v2).
All run() methods return simulated:True unless a real backend is configured.
"""
from .perception_agent import PerceptionAgent
from .recon_agent import ReconAgent
from .probe_agent import ProbeAgent
from .chain_agent import ChainAgent
from .prove_agent import ProveAgent
from .voice_agent import VoiceAgent
from .remediation_agent import RemediationAgent
from .orchestrator_v2 import OrchestratorV2

__all__ = [
    "PerceptionAgent", "ReconAgent", "ProbeAgent", "ChainAgent",
    "ProveAgent", "VoiceAgent", "RemediationAgent", "OrchestratorV2",
]
