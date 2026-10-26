"""Async, role-based swarm orchestrator (defensive lab use only).

Every step is bounded (max_steps) and every tool call is wrapped by:
  1. guard review (backend/guard/review_engine.review) — fail-closed,
  2. authorization check — EXEC inside Kali is dry-run unless --i-am-authorized AND a named human approver,
  3. audit — append-only hash-chained JSONL (backend/audit.AuditLog).

Roles (operator console): orchestrator, recon, code, review, analyzer, report.
The swarm orchestrates PLANNING and ANALYSIS. It does not ship exploit/attack tooling.
"""
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
from audit import AuditLog  # noqa: E402
from guard.review_engine import review  # noqa: E402

from .config import CONFIG  # noqa: E402
from .model_router import ModelRouter, AGENT_ROSTER  # noqa: E402
from .sandbox import SandboxManager  # noqa: E402

ROLES = list(AGENT_ROSTER.keys())


@dataclass
class Mission:
    name: str
    objective: str
    scope: str = "lab-only"
    authorized: bool = False
    human_approver: str | None = None
    max_steps: int = 12
    roles: list[str] = field(default_factory=lambda: list(ROLES))


@dataclass
class StepResult:
    step: int
    role: str
    action: str
    model: str
    tier: str
    allowed: bool
    executed: bool
    detail: str


class Swarm:
    def __init__(self, mission: Mission, *, gateway=None, mock: bool = True, audit_path: str | None = None):
        self.m = mission
        self.router = ModelRouter(gateway, mock=mock)
        self.sandbox = SandboxManager(mock=mock)
        self.audit = AuditLog(audit_path or CONFIG.audit_file)
        self.results: list[StepResult] = []

    def _authorized_for_exec(self, tier: str) -> tuple[bool, str]:
        if not self.m.authorized:
            return False, "mission not marked authorized (dry-run default)"
        if not self.m.human_approver:
            return False, "no human approver set"
        if tier == "red" and not self.m.human_approver:
            return False, "red tier requires a named human approver"
        return True, "authorized + approver present"

    async def _run_step(self, step: int, role: str, action: str, *, is_exec: bool) -> StepResult:
        sensitive = role in ("analyzer", "exploitdev")
        route = self.router.route(role, sensitive=sensitive)
        # Guard wraps EVERY step. Offline/mock: regex prefilter (tier blue) so we stay runnable
        # while still blocking offensive/injection intent. Auth for red EXEC is separate.
        guard_tier = "blue" if (self.router.mock and not os.getenv("GUARD_LLM_URL")) else route.tier
        verdict = review(f"[{role}] {action}", guard_tier)
        allowed = verdict["allow"]
        executed = False
        detail = verdict.get("reason", "")
        if allowed and is_exec:
            ok, why = self._authorized_for_exec(route.tier)
            detail = why
            executed = ok
        elif allowed:
            self.router.infer(role, action, sensitive=sensitive)
        self.audit.append(
            "swarm_step", mission=self.m.name, step=step, role=role, action=action[:200],
            model=route.model, tier=route.tier, guard_allow=allowed,
            is_exec=is_exec, executed=executed, approver=self.m.human_approver,
        )
        res = StepResult(step, role, action, route.model, route.tier, allowed, executed, detail)
        self.results.append(res)
        return res

    async def run(self) -> list[StepResult]:
        session = self.m.name.replace(" ", "-")[:24]
        self.sandbox.up(session)
        try:
            plan = [
                ("orchestrator", f"Decompose objective: {self.m.objective}", False),
                ("recon", "Defensive asset inventory of provided lab scope (read-only)", False),
                ("analyzer", "Map findings to mitigations (no exploit generation)", False),
                ("analyzer", "Execute validation step inside Kali sandbox", True),
                ("review", "Guard review of findings and plan", False),
                ("report", "Write authorized lab report", False),
            ]
            for i, (role, action, is_exec) in enumerate(plan[: self.m.max_steps], start=1):
                await self._run_step(i, role, action, is_exec=is_exec)
                await asyncio.sleep(0)
        finally:
            self.sandbox.down(session)
        return self.results


def load_mission(path: str) -> Mission:
    import yaml
    with open(path) as f:
        d = yaml.safe_load(f)
    return Mission(
        name=d["name"], objective=d["objective"], scope=d.get("scope", "lab-only"),
        authorized=bool(d.get("authorized", False)), human_approver=d.get("human_approver"),
        max_steps=int(d.get("max_steps", 12)),
        roles=d.get("roles", list(ROLES)),
    )


def code_run(prompt: str, *, mock: bool = True, authorized: bool = False,
             approver: str | None = None, audit_path: str | None = None) -> dict:
    """Wonderful plans → Code Llama writes patch → review (guard) checks → apply inside cage only.

    Always returns a diff. Apply is dry-run unless authorized + approver.
    """
    router = ModelRouter(mock=mock)
    audit = AuditLog(audit_path or CONFIG.audit_file)
    sandbox = SandboxManager(mock=mock)

    plan = router.infer("orchestrator", f"Plan a defensive patch for: {prompt}")
    guard_tier = "blue" if (mock and not os.getenv("GUARD_LLM_URL")) else "green"
    v1 = review(f"[code-plan] {prompt}", guard_tier)
    audit.append("code_plan", prompt=prompt[:200], allow=v1["allow"], model=plan["model"])
    if not v1["allow"]:
        return {"allowed": False, "reason": v1.get("reason"), "diff": None, "applied": False}

    patch = router.infer("code", f"Write a minimal defensive patch for: {prompt}")
    v2 = review(f"[code-patch] {patch.get('text', '')[:500]}", guard_tier)
    audit.append("code_patch", allow=v2["allow"], model=patch["model"])
    if not v2["allow"]:
        return {"allowed": False, "reason": v2.get("reason"), "diff": None, "applied": False}

    # Deep review agent
    review_out = router.infer("review", f"Review patch safety: {patch.get('text', '')[:300]}")
    diff = (
        f"--- a/lab/target\n+++ b/lab/target\n"
        f"@@ defensive patch (Muse Code ≡ Code Llama) @@\n"
        f"+# planned by {plan['model']} (≡ {plan.get('open_equivalent')})\n"
        f"+# reviewed by {review_out['model']}\n"
        f"+# prompt: {prompt[:80]}\n"
        f"+harden()\n"
    )
    applied = False
    detail = "dry-run — pass --i-am-authorized --approver to apply inside Kali cage"
    if authorized and approver:
        sandbox.spawn(agent_id="code-1", role="code", image="kali-rolling-minimal.ext4", isolated=True)
        ex = sandbox.exec("code-1", "apply-patch", authorized=True, approver=approver)
        applied = bool(ex.get("executed"))
        detail = ex.get("detail", "applied")
        sandbox.destroy("code-1")
    audit.append("code_apply", applied=applied, approver=approver, authorized=authorized)
    return {
        "allowed": True, "plan": plan, "patch": patch, "review": review_out,
        "diff": diff, "applied": applied, "detail": detail,
        "note": "Open equivalents: Muse Wonderful→Llama-3-70B, Muse Code→Code Llama, guard→Llama-Guard-3-8B",
    }
