"""Async, role-based swarm orchestrator.

Every step is bounded (max_steps) and every tool call is wrapped by:
  1. guard review (backend/guard/review_engine.review) — fail-closed, blocks injection/offensive intent,
  2. authorization check — any step that EXECUTES inside the Kali sandbox is dry-run unless the mission is
     explicitly authorized (--i-am-authorized) AND a named human approver is set; red-tier steps always
     require the approver,
  3. audit — an append-only, hash-chained record (backend/audit.AuditLog).

Roles: Planner, Recon-Analyst, ExploitDev (defensive/lab-only), Reviewer/Guard, Reporter.
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

from .model_router import ModelRouter  # noqa: E402
from .sandbox import SandboxManager  # noqa: E402

ROLES = ["planner", "recon-analyst", "exploitdev", "reviewer", "reporter"]


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
        self.audit = AuditLog(audit_path or os.path.expanduser("~/.musebreak/swarm_audit.jsonl"))
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
        route = self.router.route(role, sensitive=(role == "exploitdev"))
        # Guard wraps EVERY step. Guard's LLM stage is fail-closed; offline/mock has no guard LLM, so we run
        # the regex prefilter (tier "blue") to stay runnable while still blocking offensive/injection intent.
        # Authorization for red-tier EXEC is enforced separately below and in audit, so safety is not weakened.
        guard_tier = "blue" if (self.router.mock and not os.getenv("GUARD_LLM_URL")) else route.tier
        verdict = review(f"[{role}] {action}", guard_tier)
        allowed = verdict["allow"]
        executed = False
        detail = verdict.get("reason", "")
        if allowed and is_exec:
            ok, why = self._authorized_for_exec(route.tier)
            detail = why
            executed = ok  # when not ok -> dry-run only, never executed
        elif allowed:
            self.router.infer(role, action, sensitive=(role == "exploitdev"))  # model/plan call (mockable)
        self.audit.append("swarm_step", mission=self.m.name, step=step, role=role, action=action[:200],
                          model=route.model, tier=route.tier, guard_allow=allowed,
                          is_exec=is_exec, executed=executed, approver=self.m.human_approver)
        res = StepResult(step, role, action, route.model, route.tier, allowed, executed, detail)
        self.results.append(res)
        return res

    async def run(self) -> list[StepResult]:
        session = self.m.name.replace(" ", "-")[:24]
        self.sandbox.up(session)
        try:
            plan = [
                ("planner", f"Decompose objective: {self.m.objective}", False),
                ("recon-analyst", "Analyze provided lab scope data (read-only)", False),
                ("exploitdev", "Draft defensive/lab-only validation plan", False),
                ("exploitdev", "Execute validation step inside Kali sandbox", True),
                ("reviewer", "Guard review of findings and plan", False),
                ("reporter", "Write authorized lab report", False),
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
    return Mission(name=d["name"], objective=d["objective"], scope=d.get("scope", "lab-only"),
                   authorized=bool(d.get("authorized", False)), human_approver=d.get("human_approver"),
                   max_steps=int(d.get("max_steps", 12)),
                   roles=d.get("roles", list(ROLES)))
