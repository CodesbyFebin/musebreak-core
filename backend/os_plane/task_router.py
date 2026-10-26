"""Open model routing: classify tasks small/medium/large and assign models.

Naming is consistent with cli/musebreak_cli/model_router.py and
backend/open_source.py. Muse* labels are product aliases; open_equivalent
is always shown.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any


class TaskSize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# Muse product label → open model + where it runs
MODEL_TIERS: dict[str, dict[str, Any]] = {
    "small": {
        "muse_label": "Muse Spark",
        "open_equivalent": "Llama-3.2-1B-Instruct (WebLLM q4f32_1)",
        "webllm_model_id": "Llama-3.2-1B-Instruct-q4f32_1-MLC",
        "runtime": "browser-webllm",
        "requires_api": False,
        "requires_jev": False,
        "note": "Runs fully in-browser via WebGPU. Real local inference.",
    },
    "medium": {
        "muse_label": "Muse Code",
        "open_equivalent": "CodeLlama-13b-Instruct / Llama-3.1-8B-Instruct",
        "api_env": "MUSEBREAK_MEDIUM_API_URL",
        "runtime": "api",
        "requires_api": True,
        "requires_jev": True,  # code-write / actions need Jev
        "note": "Needs configured API endpoint. UNAVAILABLE when unset.",
    },
    "large": {
        "muse_label": "Muse Wonder Full",
        "open_equivalent": "Llama-3.3-70B-Instruct",
        "api_env": "MUSEBREAK_LARGE_API_URL",
        "runtime": "api",
        "requires_api": True,
        "requires_jev": True,
        "note": "Needs configured API endpoint. UNAVAILABLE when unset.",
    },
}

# Agent roster aligned with CLI + Claw Harness
OS_AGENT_ROSTER: list[dict[str, Any]] = [
    {
        "id": "orchestrator",
        "name": "Orchestrator",
        "role": "planner",
        "default_size": "large",
        "claw": ["plan", "assign"],
        "why": "Long-horizon mission planning",
    },
    {
        "id": "recon",
        "name": "Recon-Analyst",
        "role": "recon",
        "default_size": "small",
        "claw": ["read"],
        "why": "Defensive asset inventory (own lab)",
    },
    {
        "id": "code",
        "name": "Muse Code",
        "role": "code",
        "default_size": "medium",
        "claw": ["code_write"],
        "why": "Plans and patches (open eq: Code Llama)",
    },
    {
        "id": "review",
        "name": "Reviewer/Guard",
        "role": "review",
        "default_size": "small",
        "claw": ["read", "review"],
        "why": "Guard prefilter + review",
    },
    {
        "id": "reporter",
        "name": "Reporter",
        "role": "report",
        "default_size": "medium",
        "claw": ["read", "report"],
        "why": "Authorized lab report authoring",
    },
    {
        "id": "claw-worker",
        "name": "Claw Worker",
        "role": "claw",
        "default_size": "small",
        "claw": ["read"],
        "why": "Capability-scoped helper; grants controlled by Jev",
    },
]

_LARGE_HINTS = re.compile(
    r"\b(architect|refactor\s+(entire|whole|all)|migrate\s+codebase|"
    r"multi[- ]?agent|security\s+audit\s+report|threat\s+model|"
    r"wonder\s*full|muse\s*wonder|70b|large\s+model)\b",
    re.I,
)
_MEDIUM_HINTS = re.compile(
    r"\b(code|patch|fix|implement|write\s+function|unit\s*test|"
    r"docker|kubernetes|sql|api\s+design|muse\s*code|codellama)\b",
    re.I,
)
_ACTION_HINTS = re.compile(
    r"\b(exec|shell|run\s+command|write\s+file|deploy|delete|rm\s+-|"
    r"kali|exploit|payload)\b",
    re.I,
)


def classify_task(prompt: str, *, force_size: str | None = None) -> TaskSize:
    """Heuristic classifier. Prefer explicit force_size when the UI sets one."""
    if force_size:
        try:
            return TaskSize(force_size.lower())
        except ValueError:
            pass
    text = (prompt or "").strip()
    if not text:
        return TaskSize.SMALL
    if _LARGE_HINTS.search(text) or len(text) > 1200:
        return TaskSize.LARGE
    if _MEDIUM_HINTS.search(text) or len(text) > 280:
        return TaskSize.MEDIUM
    return TaskSize.SMALL


def needs_jev(prompt: str, size: TaskSize) -> bool:
    """Large/medium always; any action-looking prompt also needs Jev (default-deny)."""
    if size in (TaskSize.MEDIUM, TaskSize.LARGE):
        return True
    if _ACTION_HINTS.search(prompt or ""):
        return True
    return False


def pick_agent(size: TaskSize, prompt: str) -> dict[str, Any]:
    """Assign an agent by size / keywords. Deterministic, not ML."""
    p = (prompt or "").lower()
    if "recon" in p or "scan" in p or "inventory" in p:
        return next(a for a in OS_AGENT_ROSTER if a["id"] == "recon")
    if size == TaskSize.LARGE or "plan" in p or "orchestr" in p:
        return next(a for a in OS_AGENT_ROSTER if a["id"] == "orchestrator")
    if size == TaskSize.MEDIUM or _MEDIUM_HINTS.search(p):
        if "report" in p or "summar" in p:
            return next(a for a in OS_AGENT_ROSTER if a["id"] == "reporter")
        return next(a for a in OS_AGENT_ROSTER if a["id"] == "code")
    if "review" in p or "guard" in p:
        return next(a for a in OS_AGENT_ROSTER if a["id"] == "review")
    return next(a for a in OS_AGENT_ROSTER if a["id"] == "claw-worker")


@dataclass
class RouteDecision:
    size: str
    muse_label: str
    open_equivalent: str
    runtime: str
    webllm_model_id: str | None
    requires_api: bool
    requires_jev: bool
    agent: dict
    status: str  # ready | awaiting_jev | unavailable
    note: str
    api_configured: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def route_task(
    prompt: str,
    *,
    force_size: str | None = None,
    medium_api_configured: bool = False,
    large_api_configured: bool = False,
    jev_approved: bool = False,
) -> RouteDecision:
    size = classify_task(prompt, force_size=force_size)
    tier = MODEL_TIERS[size.value]
    agent = pick_agent(size, prompt)
    jev = needs_jev(prompt, size) or bool(tier.get("requires_jev"))

    api_ok = True
    if tier["requires_api"]:
        if size == TaskSize.MEDIUM:
            api_ok = medium_api_configured
        elif size == TaskSize.LARGE:
            api_ok = large_api_configured

    if not api_ok:
        status = "unavailable"
    elif jev and not jev_approved:
        status = "awaiting_jev"
    else:
        status = "ready"

    return RouteDecision(
        size=size.value,
        muse_label=tier["muse_label"],
        open_equivalent=tier["open_equivalent"],
        runtime=tier["runtime"],
        webllm_model_id=tier.get("webllm_model_id"),
        requires_api=tier["requires_api"],
        requires_jev=jev,
        agent=agent,
        status=status,
        note=tier["note"],
        api_configured=api_ok if tier["requires_api"] else True,
    )
