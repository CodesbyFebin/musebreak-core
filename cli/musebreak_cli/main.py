"""`musebreak` CLI — command center for the sandboxed agent swarm."""
from __future__ import annotations

import asyncio
import json
import os

import typer

from . import __version__
from .config import CONFIG
from .model_router import ROUTING_TABLE
from .orchestrator import Swarm, load_mission
from .sandbox import SandboxManager

app = typer.Typer(add_completion=False, help="MuseBreak — Zero-Trust command center + sandboxed agent swarm.")
swarm_app = typer.Typer(help="Run and inspect agent swarms.")
agents_app = typer.Typer(help="Inspect agent roles.")
sandbox_app = typer.Typer(help="Manage the isolated Kali microVM.")
audit_app = typer.Typer(help="Audit log.")
app.add_typer(swarm_app, name="swarm")
app.add_typer(agents_app, name="agents")
app.add_typer(sandbox_app, name="sandbox")
app.add_typer(audit_app, name="audit")

STATE = os.path.expanduser("~/.musebreak")
SANDBOX = SandboxManager(mock=CONFIG.mock)


def _echo(obj):
    typer.echo(json.dumps(obj, indent=2, default=str))


@app.callback(invoke_without_command=True)
def _root(version: bool = typer.Option(False, "--version")):
    if version:
        typer.echo(f"musebreak {__version__}")
        raise typer.Exit()


@app.command()
def login(user: str = "judge", password: str = typer.Option("musebreak", prompt=False)):
    """Gate 1 login against the FastAPI gateway (mock-aware)."""
    if CONFIG.mock:
        os.makedirs(STATE, exist_ok=True)
        open(CONFIG.token_file, "w").write(json.dumps({"mock": True, "user": user}))
        _echo({"gate1": "mock-ok", "user": user, "note": "MUSEBREAK_MOCK=1; no live gateway"})
        return
    from .gateway_client import GatewayClient
    gc = GatewayClient(CONFIG.gateway, CONFIG.key_file)
    gc.login(user, password)
    _echo({"gate1": "ok", "gateway": CONFIG.gateway})


@swarm_app.command("run")
def swarm_run(mission_file: str,
              i_am_authorized: bool = typer.Option(False, "--i-am-authorized",
                                                   help="Attest you are authorized to run exec steps in-lab."),
              approver: str = typer.Option(None, "--approver", help="Named human approver (required for exec)."),
              max_steps: int = typer.Option(None, help="Override mission max_steps.")):
    """Run a mission. Exec steps are DRY-RUN unless --i-am-authorized and --approver are both set."""
    m = load_mission(mission_file)
    if i_am_authorized:
        m.authorized = True
    if approver:
        m.human_approver = approver
    if max_steps:
        m.max_steps = max_steps
    swarm = Swarm(m, mock=CONFIG.mock, audit_path=os.path.join(STATE, "swarm_audit.jsonl"))
    results = asyncio.run(swarm.run())
    _echo({"mission": m.name, "authorized": m.authorized, "approver": m.human_approver,
           "steps": [r.__dict__ for r in results],
           "executed": sum(r.executed for r in results), "dry_run": sum(not r.executed and r.allowed for r in results)})


@swarm_app.command("status")
def swarm_status():
    """Show sandbox sessions backing recent swarm runs."""
    _echo({"sandbox_sessions": SANDBOX.status() or {}, "mock": SANDBOX.mock})


@agents_app.command("list")
def agents_list():
    """List agent roles and their model-tier routing."""
    _echo({role: {"model": m, "tier": t, "why": why} for role, (m, t, why) in ROUTING_TABLE.items()})


@sandbox_app.command("up")
def sandbox_up(session: str = "default"):
    _echo(SANDBOX.up(session))


@sandbox_app.command("down")
def sandbox_down(session: str = "default"):
    _echo(SANDBOX.down(session))


@sandbox_app.command("status")
def sandbox_status(session: str = typer.Argument(None)):
    _echo(SANDBOX.status(session) or {})


@audit_app.command("tail")
def audit_tail(limit: int = 20):
    """Tail the local swarm audit log (hash-chained)."""
    path = os.path.join(STATE, "swarm_audit.jsonl")
    if not os.path.exists(path):
        _echo({"entries": [], "note": "no swarm runs yet"})
        return
    lines = [json.loads(l) for l in open(path) if l.strip()]
    _echo({"count": len(lines), "entries": lines[-limit:]})


@app.command("models")
def models_cmd(action: str = typer.Argument("list")):
    """models list — show the model tier ladder."""
    _echo({role: {"model": m, "tier": t} for role, (m, t, _) in ROUTING_TABLE.items()})


def run():  # console_scripts entry
    app()


if __name__ == "__main__":
    run()
