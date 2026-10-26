"""Agent registry — operator-console roster + per-swarm instance table."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, asdict, field

from .config import CONFIG
from .model_router import AGENT_ROSTER


@dataclass
class AgentInstance:
    id: str
    role: str
    model: str
    open_equivalent: str
    vm: str | None
    tier: str
    swarm_id: str | None = None
    spawned_at: float = field(default_factory=time.time)


def roster_rows() -> list[dict]:
    """Static role table for `musebreak agent list` when no swarm is active."""
    rows = []
    for role, info in AGENT_ROSTER.items():
        rows.append({
            "id": f"role:{role}",
            "role": role,
            "model": info["model"],
            "open_equivalent": info["open_equivalent"],
            "tier": info["tier"],
            "vm": info["vm"] or "—",
            "why": info["why"],
        })
    return rows


def save_instances(instances: list[AgentInstance]) -> None:
    CONFIG.ensure_state()
    with open(CONFIG.agents_file, "w") as f:
        json.dump([asdict(a) for a in instances], f, indent=2)


def load_instances() -> list[AgentInstance]:
    if not os.path.exists(CONFIG.agents_file):
        return []
    with open(CONFIG.agents_file) as f:
        return [AgentInstance(**row) for row in json.load(f)]


def launch_topology(topology: str | None = None, workers: int | None = None) -> list[AgentInstance]:
    """Parse '1xWonderful-orchestrator+5xLlama-workers' or --workers N into AgentInstances."""
    instances: list[AgentInstance] = []
    swarm_id = "sw_" + uuid.uuid4().hex[:8]

    n_workers = workers
    if topology:
        # very small parser: NxRole tokens joined by +
        parts = topology.replace(" ", "").split("+")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            n, _, rest = part.partition("x")
            try:
                count = int(n)
            except ValueError:
                count, rest = 1, part
            rest_l = rest.lower()
            if "orchestrator" in rest_l or "wonderful" in rest_l:
                role = "orchestrator"
            elif "worker" in rest_l or "llama" in rest_l or "recon" in rest_l:
                role = "recon"
                if n_workers is None:
                    n_workers = count
                    # workers expand below; skip adding here if we'll expand
                    if "worker" in rest_l:
                        continue
            elif "code" in rest_l:
                role = "code"
            elif "review" in rest_l or "guard" in rest_l:
                role = "review"
            elif "analy" in rest_l:
                role = "analyzer"
            elif "report" in rest_l:
                role = "report"
            else:
                role = "recon"
            info = AGENT_ROSTER[role]
            for i in range(count):
                instances.append(AgentInstance(
                    id=f"{role}-{i+1}-{swarm_id[-4:]}",
                    role=role, model=info["model"], open_equivalent=info["open_equivalent"],
                    vm=info["vm"], tier=info["tier"], swarm_id=swarm_id,
                ))

    # Always ensure one orchestrator
    if not any(a.role == "orchestrator" for a in instances):
        info = AGENT_ROSTER["orchestrator"]
        instances.insert(0, AgentInstance(
            id=f"orchestrator-1-{swarm_id[-4:]}", role="orchestrator",
            model=info["model"], open_equivalent=info["open_equivalent"],
            vm=info["vm"], tier=info["tier"], swarm_id=swarm_id,
        ))

    # Expand Llama workers
    n_workers = n_workers if n_workers is not None else 5
    info = AGENT_ROSTER["recon"]
    existing_workers = sum(1 for a in instances if a.role == "recon")
    for i in range(existing_workers, n_workers):
        instances.append(AgentInstance(
            id=f"recon-{i+1}-{swarm_id[-4:]}", role="recon",
            model=info["model"], open_equivalent=info["open_equivalent"],
            vm=info["vm"], tier=info["tier"], swarm_id=swarm_id,
        ))

    # Attach the rest of the roster once each (code/review/analyzer/report) if missing
    for role in ("code", "review", "analyzer", "report"):
        if not any(a.role == role for a in instances):
            info = AGENT_ROSTER[role]
            instances.append(AgentInstance(
                id=f"{role}-1-{swarm_id[-4:]}", role=role,
                model=info["model"], open_equivalent=info["open_equivalent"],
                vm=info["vm"], tier=info["tier"], swarm_id=swarm_id,
            ))

    save_instances(instances)
    return instances
