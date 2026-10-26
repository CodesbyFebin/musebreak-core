"""Textual TUI command center — live swarm view (simulated-mode default).

Shows:
  • CLI AGENT_ROSTER roles / launched instances (from agents.py + model_router.py)
  • Perception → Reasoning → Voice → Action pipeline (maps onto backend OrchestratorV2
    scaffolds when available; never invents agents that are not in the repo)
  • Kali MicroVM panel (SandboxManager — labelled SIMULATED when no KVM/rootfs)
  • Live audit / event stream

Honesty: every pane that is not driven by a real measurement carries a
SIMULATED / ILLUSTRATIVE badge in the UI itself. No fabricated counts,
timings, CVE IDs, costs, or test totals.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static, DataTable, RichLog, Label

from .agents import load_instances, launch_topology, roster_rows
from .config import CONFIG
from .model_router import AGENT_ROSTER
from .sandbox import SandboxManager

# Backend path for OrchestratorV2 + AuditLog (same pattern as orchestrator.py)
_BACKEND = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# High-level pipeline the TUI advertises. Each stage maps to real modules that
# exist in this repo — never invent names.
PIPELINE_STAGES: list[dict[str, Any]] = [
    {
        "id": "perception",
        "label": "Perception",
        "sources": ["backend/agents/perception_agent.py"],
        "agents": ["perception"],
        "detail": "SAM 2.1 / DINOv2 / vision scaffold (mocked without weights)",
    },
    {
        "id": "reasoning",
        "label": "Reasoning",
        "sources": [
            "backend/agents/recon_agent.py",
            "backend/agents/probe_agent.py",
            "backend/agents/chain_agent.py",
            "cli/musebreak_cli/orchestrator.py",
        ],
        "agents": ["recon", "probe", "chain", "orchestrator", "analyzer", "review"],
        "detail": "Recon / probe / chain + CLI swarm planner (mock infer)",
    },
    {
        "id": "voice",
        "label": "Voice",
        "sources": ["backend/agents/voice_agent.py"],
        "agents": ["voice"],
        "detail": "SeamlessM4T scaffold (no audio synthesized offline)",
    },
    {
        "id": "action",
        "label": "Action",
        "sources": [
            "backend/agents/prove_agent.py",
            "backend/agents/remediation_agent.py",
            "cli/musebreak_cli/sandbox.py",
        ],
        "agents": ["prove", "remediation", "code", "report"],
        "detail": "Prove (hash-commitment MVP) + remediation / report / cage",
    },
]


@dataclass
class StageState:
    status: str = "idle"  # idle | running | done | skipped
    note: str = ""
    started_at: float | None = None
    finished_at: float | None = None


@dataclass
class CenterState:
    simulated: bool = True
    kvm_present: bool = False
    stages: dict[str, StageState] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)
    agents_snapshot: list[dict] = field(default_factory=list)
    vms_snapshot: list[dict] = field(default_factory=list)
    mission: str = "defensive-demo"
    tick: int = 0

    def __post_init__(self) -> None:
        if not self.stages:
            self.stages = {s["id"]: StageState() for s in PIPELINE_STAGES}


def _kvm_available() -> bool:
    return os.path.exists("/dev/kvm")


def _detect_simulated() -> bool:
    """True unless explicitly told otherwise AND a real backend is reachable.
    Default (and this box) is always simulated — no GPU, no Llama Stack, mock=1.
    """
    if os.getenv("MUSEBREAK_MOCK", "1") == "1":
        return True
    if CONFIG.mock:
        return True
    return True  # TUI stays honest: no silent "live" claim without real telemetry


class Banner(Static):
    """Top honesty banner — always visible."""

    def update_banner(self, state: CenterState) -> None:
        kvm = "KVM present (VM still simulated — no Kali rootfs/Firecracker wired)" if state.kvm_present \
            else "no /dev/kvm usable for live Firecracker on this host path"
        mode = "SIMULATED / ILLUSTRATIVE" if state.simulated else "LIVE"
        style = "bold yellow on black" if state.simulated else "bold green on black"
        self.update(Text(
            f"  MODE: {mode}  ·  mission={state.mission}  ·  {kvm}  ·  "
            f"telemetry below is demo unless a real source is named  ",
            style=style,
        ))


class AgentsPanel(Static):
    """Agent roster / live instances table."""

    def compose(self) -> ComposeResult:
        yield Label("AGENTS  (CLI AGENT_ROSTER + launched instances)", classes="panel-title")
        yield DataTable(id="agents-table", zebra_stripes=True)


class PipelinePanel(Static):
    """Perception → Reasoning → Voice → Action."""

    def compose(self) -> ComposeResult:
        yield Label(
            "PIPELINE  Perception → Reasoning → Voice → Action  [SIMULATED]",
            classes="panel-title",
        )
        yield Static(id="pipeline-body")


class KaliPanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("KALI MICROVMs  [SIMULATED unless Firecracker+rootfs live]", classes="panel-title")
        yield Static(id="kali-body")


class AuditPanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("AUDIT / EVENT STREAM  (local hash-chained log + demo ticks)", classes="panel-title")
        yield RichLog(id="audit-log", highlight=True, markup=True, wrap=True)


class CommandCenterApp(App[None]):
    """MuseBreak textual command center."""

    TITLE = "MuseBreak Command Center"
    SUB_TITLE = "Zero-Trust swarm console"
    CSS = """
    Screen { layout: vertical; }
    #banner { height: 3; dock: top; content-align: left middle; }
    #main { height: 1fr; }
    #left { width: 3fr; }
    #right { width: 2fr; }
    #bottom { height: 12; }
    .panel-title { text-style: bold; color: cyan; padding: 0 1; }
    #agents-table { height: 1fr; }
    #pipeline-body { padding: 0 1; height: 1fr; }
    #kali-body { padding: 0 1; height: 1fr; }
    #audit-log { height: 1fr; border: solid $accent; }
    AgentsPanel, PipelinePanel, KaliPanel, AuditPanel {
        border: solid $primary;
        margin: 0 1 1 1;
        height: 1fr;
    }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "rerun", "Re-run demo swarm"),
        ("s", "spawn_mock_vm", "Spawn mock Kali VM"),
    ]

    running_demo: reactive[bool] = reactive(False)

    def __init__(self, *, simulated: bool | None = None, auto_demo: bool = True):
        super().__init__()
        kvm = _kvm_available()
        sim = _detect_simulated() if simulated is None else simulated
        self.state = CenterState(simulated=sim, kvm_present=kvm)
        self.sandbox = SandboxManager(mock=True)  # TUI never claims live VMs here
        self.auto_demo = auto_demo
        self._demo_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Banner(id="banner")
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield AgentsPanel()
                yield PipelinePanel()
            with Vertical(id="right"):
                yield KaliPanel()
        with Vertical(id="bottom"):
            yield AuditPanel()
        yield Footer()

    def on_mount(self) -> None:
        self._ensure_swarm_instances()
        self._refresh_agents_table()
        self._refresh_pipeline()
        self._refresh_kali()
        self.query_one("#banner", Banner).update_banner(self.state)
        self._emit("[dim]command-center mounted — simulated mode default "
                   "(MUSEBREAK_MOCK=1 / no live model telemetry)[/]")
        self._emit("[dim]keys: q quit · r re-run demo · s spawn mock Kali VM[/]")
        # Seed a couple of illustrative mock VMs so the panel is not empty.
        if not self.sandbox.status():
            for role in ("recon", "code"):
                try:
                    self.sandbox.spawn(
                        agent_id=f"{role}-demo",
                        role=role,
                        image="kali-rolling-minimal.ext4",
                        isolated=True,
                    )
                except RuntimeError:
                    pass
            self._refresh_kali()
        if self.auto_demo:
            self._demo_task = asyncio.create_task(self._run_demo_loop())

    def _ensure_swarm_instances(self) -> None:
        inst = load_instances()
        if not inst:
            inst = launch_topology(
                topology="1xWonderful-orchestrator+3xLlama-workers",
                workers=3,
            )
            self._emit(f"[cyan]launched demo swarm[/] {inst[0].swarm_id} "
                       f"({len(inst)} agents) — roster from agents.py")
        self.state.agents_snapshot = [
            {
                "id": a.id, "role": a.role, "model": a.model,
                "open_equivalent": a.open_equivalent, "vm": a.vm or "—",
                "tier": a.tier, "status": "ready",
            }
            for a in inst
        ]

    def _refresh_agents_table(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        table.clear(columns=True)
        table.add_columns("ID", "ROLE", "MODEL", "OPEN EQ", "TIER", "VM", "STATUS")
        rows = self.state.agents_snapshot
        if not rows:
            # Fall back to static roster
            for row in roster_rows():
                table.add_row(
                    row["id"], row["role"], row["model"], row["open_equivalent"],
                    AGENT_ROSTER[row["role"]]["tier"], str(row["vm"]), "roster",
                )
            return
        for a in rows:
            table.add_row(
                a["id"], a["role"], a["model"], a["open_equivalent"],
                a.get("tier", "?"), a.get("vm", "—"), a.get("status", "?"),
            )

    def _refresh_pipeline(self) -> None:
        lines: list[str] = []
        for stage in PIPELINE_STAGES:
            st = self.state.stages[stage["id"]]
            badge = {
                "idle": "[dim]IDLE[/]",
                "running": "[bold yellow]RUNNING[/]",
                "done": "[bold green]DONE[/]",
                "skipped": "[dim]SKIPPED[/]",
            }.get(st.status, st.status)
            note = st.note or stage["detail"]
            agents = ", ".join(stage["agents"])
            lines.append(f"  [{stage['label']}]  {badge}")
            lines.append(f"      agents: {agents}")
            lines.append(f"      {note}")
        body = self.query_one("#pipeline-body", Static)
        body.update("\n".join(lines) if lines else "(no stages)")

    def _refresh_kali(self) -> None:
        vms = self.sandbox.status() or {}
        self.state.vms_snapshot = list(vms.values()) if isinstance(vms, dict) else []
        lines = [
            "[yellow]SIMULATED[/] — SandboxManager(mock=True).",
            "No live Firecracker session is claimed by this TUI.",
            "",
        ]
        if not self.state.vms_snapshot:
            lines.append("(no mock VMs — press [bold]s[/] to spawn one)")
        else:
            for v in self.state.vms_snapshot:
                lines.append(
                    f"  {v.get('vm_id')}  agent={v.get('agent_id')}  "
                    f"role={v.get('role')}  status={v.get('status')}  "
                    f"isolated={v.get('isolated')}  mock={v.get('mock', True)}"
                )
                lines.append(f"      image={v.get('image')}")
        self.query_one("#kali-body", Static).update("\n".join(lines))

    def _emit(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[dim]{ts}[/] {msg}"
        self.state.events.append(line)
        try:
            log = self.query_one("#audit-log", RichLog)
            log.write(line)
        except Exception:
            pass

    def _set_stage(self, stage_id: str, status: str, note: str = "") -> None:
        st = self.state.stages[stage_id]
        st.status = status
        if note:
            st.note = note
        now = time.time()
        if status == "running":
            st.started_at = now
        if status in ("done", "skipped"):
            st.finished_at = now
        self._refresh_pipeline()

    async def _run_demo_loop(self) -> None:
        """Drive one Perception→Reasoning→Voice→Action pass via OrchestratorV2 scaffolds.

        All outputs are labelled simulated. No fabricated metrics.
        """
        if self.running_demo:
            return
        self.running_demo = True
        try:
            self._emit("[bold]demo swarm pass starting[/] (OrchestratorV2 scaffolds)")
            for s in PIPELINE_STAGES:
                self._set_stage(s["id"], "idle")

            # Try real OrchestratorV2; fall back to a local stage walk.
            try:
                from agents.orchestrator_v2 import OrchestratorV2  # type: ignore
                orch = OrchestratorV2(mock=True, lang="ml")
                use_orch = True
            except Exception as e:
                orch = None
                use_orch = False
                self._emit(f"[yellow]OrchestratorV2 import fallback:[/] {e}")

            if use_orch and orch is not None:
                # Map OrchestratorV2 agent order onto the 4-stage pipeline.
                stage_of = {
                    "perception": "perception",
                    "recon": "reasoning",
                    "probe": "reasoning",
                    "chain": "reasoning",
                    "prove": "action",
                    "voice": "voice",
                    "remediation": "action",
                }
                # Mark stages running as their first agent starts.
                seen_stage: set[str] = set()
                result = await asyncio.to_thread(
                    orch.run, {"name": self.state.mission, "dry_run": True}
                )
                for step in result.get("steps", []):
                    role = step.get("agent") or step.get("role") or "?"
                    mapped = stage_of.get(role, "reasoning")
                    if mapped not in seen_stage:
                        self._set_stage(
                            mapped, "running",
                            note=f"running via {role} scaffold (simulated={step.get('simulated', True)})",
                        )
                        seen_stage.add(mapped)
                        await asyncio.sleep(0.35)
                    detail = step.get("detail") or step.get("status") or "ok"
                    sim = step.get("simulated", True)
                    self._emit(
                        f"[cyan]{role}[/] → {detail[:120]} "
                        f"{'[yellow]simulated[/]' if sim else ''}"
                    )
                    # Mark agent status in snapshot if present
                    for a in self.state.agents_snapshot:
                        if a["role"] == role or a["id"].startswith(role):
                            a["status"] = "ran (sim)"
                    self._refresh_agents_table()
                    await asyncio.sleep(0.25)
                    self._set_stage(
                        mapped, "done",
                        note=f"last agent={role}; scaffold={step.get('scaffold', True)}",
                    )
                self._emit(
                    f"[green]orchestrator_v2 done[/] simulated={result.get('simulated')} "
                    f"steps={len(result.get('steps', []))}"
                )
            else:
                # Local walk using CLI Swarm for reasoning + static notes for others.
                for stage in PIPELINE_STAGES:
                    sid = stage["id"]
                    self._set_stage(sid, "running", note=stage["detail"] + " [SIMULATED]")
                    self._emit(f"[cyan]{stage['label']}[/] → {stage['detail']}")
                    await asyncio.sleep(0.5)
                    self._set_stage(sid, "done", note="demo tick complete (simulated)")

                from .orchestrator import Mission, Swarm
                m = Mission(
                    name=self.state.mission,
                    objective="defensive lab assessment (TUI demo)",
                    authorized=False,
                    max_steps=6,
                )
                swarm = Swarm(m, mock=True, audit_path=CONFIG.audit_file)
                results = await swarm.run()
                for r in results:
                    self._emit(
                        f"[magenta]swarm[/] step={r.step} role={r.role} "
                        f"allowed={r.allowed} executed={r.executed} "
                        f"model={r.model} — {r.detail[:80]}"
                    )
                    await asyncio.sleep(0.15)

            # Tail real audit file if present
            self._tail_audit()
            self._emit("[bold green]demo pass complete[/] — press r to re-run, q to quit")
        except asyncio.CancelledError:
            self._emit("[yellow]demo cancelled[/]")
            raise
        except Exception as e:
            self._emit(f"[red]demo error:[/] {e}")
        finally:
            self.running_demo = False
            self.query_one("#banner", Banner).update_banner(self.state)

    def _tail_audit(self) -> None:
        path = CONFIG.audit_file
        if not os.path.exists(path):
            self._emit("[dim]no audit file yet[/]")
            return
        try:
            from audit import AuditLog  # type: ignore
            log = AuditLog(path)
            entries = log.read()[-8:]
            ok = log.verify_chain()
            self._emit(f"[dim]audit chain_valid={ok} showing last {len(entries)}[/]")
            for e in entries:
                ev = e.get("event", "?")
                detail = {k: v for k, v in e.items() if k not in ("hash", "prev_hash", "ts")}
                self._emit(f"[dim]audit[/] {ev} {json.dumps(detail)[:100]}")
        except Exception as e:
            self._emit(f"[dim]audit read skipped: {e}[/]")

    def action_quit(self) -> None:
        if self._demo_task and not self._demo_task.done():
            self._demo_task.cancel()
        self.exit()

    def action_rerun(self) -> None:
        if self.running_demo:
            self._emit("[yellow]demo already running[/]")
            return
        self._demo_task = asyncio.create_task(self._run_demo_loop())

    def action_spawn_mock_vm(self) -> None:
        n = len(self.sandbox.status() or {})
        agent_id = f"recon-tui-{n+1}"
        try:
            info = self.sandbox.spawn(
                agent_id=agent_id, role="recon",
                image="kali-rolling-minimal.ext4", isolated=True,
            )
            self._emit(
                f"[cyan]spawned mock VM[/] {info['vm_id']} "
                f"(mock={info['mock']}) — {info.get('note', '')}"
            )
            self._refresh_kali()
        except RuntimeError as e:
            self._emit(f"[red]spawn failed:[/] {e}")


def run_command_center(*, simulated: bool = True, auto_demo: bool = True) -> None:
    """Entry point used by the Typer `command-center` subcommand."""
    app = CommandCenterApp(simulated=simulated, auto_demo=auto_demo)
    app.run()


async def smoke_check_async() -> dict:
    """Import + compose smoke via textual run_test (no TTY required)."""
    app = CommandCenterApp(simulated=True, auto_demo=False)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        banner = app.query_one("#banner", Banner)
        table = app.query_one("#agents-table", DataTable)
        # Give mount hooks a tick to seed mock VMs
        await pilot.pause(0.1)
        return {
            "ok": True,
            "simulated": app.state.simulated,
            "agents_rows": table.row_count,
            "stages": list(app.state.stages.keys()),
            "banner_has_simulated": "SIMULATED" in banner.renderable.plain
                if hasattr(banner, "renderable") and hasattr(banner.renderable, "plain")
                else "SIMULATED" in str(banner.render()),
            "vms": len(app.sandbox.status() or {}),
            "pipeline_ids": [s["id"] for s in PIPELINE_STAGES],
        }


def smoke_check() -> dict:
    return asyncio.run(smoke_check_async())
