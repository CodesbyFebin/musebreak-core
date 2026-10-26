"""`musebreak` — Zero-Trust operator console for the sandboxed agent swarm.

Safety (non-negotiable): defensive-only · dry-run default · human approver for exec ·
guard+audit on every step · isolated no-egress Kali cage. Red tier never unfilters.
"""
from __future__ import annotations

import json
import os
import time

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from . import __version__
from .agents import launch_topology, load_instances, roster_rows
from .config import CONFIG, load_token, save_token
from .model_router import AGENT_ROSTER, ROUTING_TABLE
from .orchestrator import Swarm, Mission, code_run, load_mission
from .sandbox import SandboxManager

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="MuseBreak operator console — Zero-Trust command center + sandboxed agent swarm.")
auth_app = typer.Typer(help="Two-gate authentication (Gate1 JWT + Gate2 MetaKey).")
key_app = typer.Typer(help="MetaKey tap (Gate2).")
swarm_app = typer.Typer(help="Launch and inspect agent swarms.")
agent_app = typer.Typer(help="Inspect agent roster / live instances.")
# plural alias kept for older scripts
agents_app = typer.Typer(help="Alias of `agent`.")
kali_app = typer.Typer(help="Isolated Kali Firecracker cage (no-egress).")
code_app = typer.Typer(help="Muse Code — plan/patch/review inside the cage.")
audit_app = typer.Typer(help="Hash-chained audit log.")
config_app = typer.Typer(help="Show local CLI config.")
sandbox_app = typer.Typer(help="Alias of `kali` (legacy).")

app.add_typer(auth_app, name="auth")
app.add_typer(key_app, name="key")
app.add_typer(swarm_app, name="swarm")
app.add_typer(agent_app, name="agent")
app.add_typer(agents_app, name="agents")
app.add_typer(kali_app, name="kali")
app.add_typer(sandbox_app, name="sandbox")
app.add_typer(code_app, name="code")
app.add_typer(audit_app, name="audit")
app.add_typer(config_app, name="config")

zkvm_app = typer.Typer(help="Trust Plane hash-commitment prove/verify (NOT real ZK).")
app.add_typer(zkvm_app, name="zkvm")

console = Console()
STATE = os.path.expanduser("~/.musebreak")
# Process-local sandbox so spawn→exec works in one CLI process; persisted agent table for list.
_SANDBOX = SandboxManager(mock=CONFIG.mock)
_VM_STATE = os.path.join(STATE, "kali_vms.json")


def _save_vms():
    CONFIG.ensure_state()
    with open(_VM_STATE, "w") as f:
        json.dump({k: v.__dict__ for k, v in _SANDBOX._agents.items()}, f, indent=2)


def _load_vms():
    if not os.path.exists(_VM_STATE):
        return
    try:
        from .sandbox import AgentVM
        data = json.load(open(_VM_STATE))
        for aid, row in data.items():
            _SANDBOX._agents[aid] = AgentVM(**{k: row[k] for k in
                ("agent_id", "role", "vm_id", "image", "isolated", "mock", "status", "spawned_at")
                if k in row})
    except Exception:
        pass


def _ok(msg: str) -> None:
    console.print(f"[bold green]✓[/] {msg}")


def _warn(msg: str) -> None:
    console.print(f"[bold yellow]![/] {msg}")


def _err(msg: str) -> None:
    console.print(f"[bold red]✗[/] {msg}")


@app.callback(invoke_without_command=True)
def _root(version: bool = typer.Option(False, "--version", help="Print version and exit.")):
    if version:
        console.print(f"musebreak {__version__}")
        raise typer.Exit()


# ─── auth / key ───────────────────────────────────────────────────────────────

@auth_app.command("login")
def auth_login(user: str = typer.Option(..., "--user", "-u", help="Operator username"),
               password: str = typer.Option("musebreak", "--password", "-p", help="Password")):
    """Gate 1: obtain a short-lived JWT bound to the device fingerprint, then prompt for a key tap."""
    CONFIG.ensure_state()
    if CONFIG.mock:
        g1 = f"mock.gate1.{user}.{int(time.time())}"
        save_token({"gate1_token": g1, "user": user, "mock": True, "wonder_token": None,
                    "note": "MUSEBREAK_MOCK=1 — call `musebreak key tap` to mint a simulated Wonder token"})
        _ok(f"Gate1 JWT issued for [cyan]{user}[/] (mock)")
        _warn("Next: musebreak key tap --interface nfc   # completes Gate2, stores MUSE_ROUTING_KEY_…")
        return
    from .gateway_client import GatewayClient
    gc = GatewayClient(CONFIG.gateway, CONFIG.key_file)
    try:
        gc.login(user, password)
    except Exception as e:
        _err(f"Gate1 failed: {e}")
        raise typer.Exit(1)
    save_token({"gate1_token": gc.g1, "user": user, "mock": False, "wonder_token": None,
                "gateway": CONFIG.gateway})
    _ok(f"Gate1 JWT issued for [cyan]{user}[/]")
    _warn("Next: musebreak key tap --interface nfc|qr")


@key_app.command("tap")
def key_tap(interface: str = typer.Option("nfc", "--interface", "-i",
                                          help="nfc | qr  (both required for real Gate2; either accepted in mock)")):
    """Gate 2: MetaKey NFC HMAC + P-256 QR intent → Wonder / MUSE_ROUTING_KEY token."""
    tok = load_token()
    if not tok or not tok.get("gate1_token"):
        _err("No Gate1 session — run `musebreak auth login --user <name>` first")
        raise typer.Exit(1)
    interface = interface.lower()
    if interface not in ("nfc", "qr", "both"):
        _err("--interface must be nfc or qr")
        raise typer.Exit(1)

    if CONFIG.mock or tok.get("mock"):
        routing = f"MUSE_ROUTING_KEY_MOCK_{int(time.time())}"
        tok["wonder_token"] = routing
        tok["routing_key"] = routing
        tok["interface"] = interface
        tok["gate2"] = "mock-ok"
        save_token(tok)
        _ok(f"Gate2 complete via [cyan]{interface}[/] (mock)")
        console.print(Panel(routing, title="MUSE_ROUTING_KEY (stored in ~/.musebreak/token)",
                            border_style="green"))
        return

    from .gateway_client import GatewayClient
    gc = GatewayClient(CONFIG.gateway, CONFIG.key_file)
    gc.g1 = tok["gate1_token"]
    try:
        # Full Gate2 always does NFC HMAC + QR P-256 regardless of which interface flag was used to trigger.
        gc.authorize(model="muse-wonder")
    except Exception as e:
        _err(f"Gate2 failed: {e}")
        raise typer.Exit(1)
    routing = gc.wonder if gc.wonder.startswith("MUSE_ROUTING_KEY_") else f"MUSE_ROUTING_KEY_{gc.wonder[:24]}"
    tok["wonder_token"] = gc.wonder
    tok["routing_key"] = routing
    tok["interface"] = interface
    tok["gate2"] = "ok"
    save_token(tok)
    _ok(f"Gate2 complete via [cyan]{interface}[/] — Wonder token stored")
    console.print(Panel(routing, title="MUSE_ROUTING_KEY", border_style="green"))


# Keep a top-level `login` alias for older docs/scripts
@app.command("login")
def login_alias(user: str = typer.Option("judge", "--user", "-u"),
                password: str = typer.Option("musebreak", "--password", "-p")):
    """Alias of `auth login`."""
    auth_login(user=user, password=password)


# ─── swarm ────────────────────────────────────────────────────────────────────

@swarm_app.command("launch")
def swarm_launch(
    topology: str = typer.Option(
        "1xWonderful-orchestrator+5xLlama-workers", "--topology", "-t",
        help="e.g. '1xWonderful-orchestrator+5xLlama-workers'"),
    workers: int = typer.Option(None, "--workers", "-w", help="Override Llama worker count"),
    run: bool = typer.Option(False, "--run", help="Also execute a bounded defensive mission after launch"),
    i_am_authorized: bool = typer.Option(False, "--i-am-authorized"),
    approver: str = typer.Option(None, "--approver"),
):
    """Launch a swarm with the given topology (1 orchestrator + N Llama workers + roster)."""
    instances = launch_topology(topology=topology, workers=workers)
    table = Table(title=f"Swarm launched · {instances[0].swarm_id}", box=box.SIMPLE_HEAVY)
    table.add_column("ID", style="cyan")
    table.add_column("ROLE")
    table.add_column("MODEL")
    table.add_column("OPEN EQ", style="dim")
    table.add_column("VM")
    for a in instances:
        table.add_row(a.id, a.role, a.model, a.open_equivalent, a.vm or "—")
    console.print(table)
    _ok(f"{len(instances)} agents ready (mock={CONFIG.mock})")
    if run:
        m = Mission(name=instances[0].swarm_id, objective="defensive lab assessment",
                    authorized=i_am_authorized, human_approver=approver, max_steps=6)
        import asyncio
        res = asyncio.run(Swarm(m, mock=CONFIG.mock, audit_path=CONFIG.audit_file).run())
        console.print({"executed": sum(r.executed for r in res),
                       "dry_run": sum(1 for r in res if r.allowed and not r.executed),
                       "steps": len(res)})


@swarm_app.command("status")
def swarm_status():
    """Show the last launched swarm + Kali VM sessions."""
    _load_vms()
    inst = load_instances()
    if not inst:
        _warn("No swarm launched yet — try `musebreak swarm launch`")
    else:
        table = Table(title=f"Active swarm · {inst[0].swarm_id}", box=box.SIMPLE)
        table.add_column("ID"); table.add_column("ROLE"); table.add_column("MODEL"); table.add_column("VM")
        for a in inst:
            table.add_row(a.id, a.role, a.model, a.vm or "—")
        console.print(table)
    vms = _SANDBOX.status() or {}
    console.print(Panel(json.dumps(vms, indent=2) if vms else "(no Kali VMs)",
                        title="Kali cage sessions", border_style="dim"))


@swarm_app.command("run")
def swarm_run(mission_file: str,
              i_am_authorized: bool = typer.Option(False, "--i-am-authorized"),
              approver: str = typer.Option(None, "--approver"),
              max_steps: int = typer.Option(None, "--max-steps")):
    """Run a YAML mission (legacy). Exec steps dry-run unless authorized + approver."""
    import asyncio
    m = load_mission(mission_file)
    if i_am_authorized:
        m.authorized = True
    if approver:
        m.human_approver = approver
    if max_steps:
        m.max_steps = max_steps
    res = asyncio.run(Swarm(m, mock=CONFIG.mock, audit_path=CONFIG.audit_file).run())
    console.print_json(data={"mission": m.name, "authorized": m.authorized, "approver": m.human_approver,
                             "steps": [r.__dict__ for r in res],
                             "executed": sum(r.executed for r in res),
                             "dry_run": sum(1 for r in res if r.allowed and not r.executed)})


# ─── agent(s) ─────────────────────────────────────────────────────────────────

def _agent_list():
    inst = load_instances()
    table = Table(title="MuseBreak agent roster", box=box.SIMPLE_HEAVY)
    table.add_column("ID", style="cyan")
    table.add_column("ROLE")
    table.add_column("MODEL")
    table.add_column("OPEN EQ", style="dim")
    table.add_column("VM")
    if inst:
        for a in inst:
            table.add_row(a.id, a.role, a.model, a.open_equivalent, a.vm or "—")
    else:
        for row in roster_rows():
            table.add_row(row["id"], row["role"], row["model"], row["open_equivalent"], str(row["vm"]))
    console.print(table)
    console.print("[dim]Open equivalents: Muse Wonderful→Llama-3-70B · Muse Code→Code Llama · "
                  "guard→Llama-Guard-3-8B (labeled; no proprietary Meta endpoint asserted).[/]")


@agent_app.command("list")
def agent_list():
    """Table of agents: ID, ROLE, MODEL, VM."""
    _agent_list()


@agents_app.command("list")
def agents_list_alias():
    """Alias of `agent list`."""
    _agent_list()


# ─── kali / sandbox ───────────────────────────────────────────────────────────

@kali_app.command("spawn")
def kali_spawn(
    agent: str = typer.Option(..., "--agent", "-a", help="Role or agent id (orchestrator|recon|code|…)"),
    image: str = typer.Option("kali-rolling-minimal.ext4", "--image",
                              help="Kali rootfs image (must contain 'kali')"),
    isolated: bool = typer.Option(True, "--isolated/--no-isolated",
                                  help="Required no-egress network_jail (default: on)"),
):
    """Spawn an isolated Kali Firecracker microVM for an agent. Mock when no KVM."""
    if not isolated:
        _err("Refuse: --isolated is required. The Kali cage must stay no-egress.")
        raise typer.Exit(2)
    role = agent.split("-")[0] if "-" in agent else agent
    if role not in AGENT_ROSTER and agent not in AGENT_ROSTER:
        # allow free-form agent ids; default role=recon
        role = role if role in AGENT_ROSTER else "recon"
    agent_id = agent if agent not in AGENT_ROSTER else f"{agent}-1"
    try:
        info = _SANDBOX.spawn(agent_id=agent_id, role=role, image=image, isolated=isolated)
    except RuntimeError as e:
        _err(str(e))
        raise typer.Exit(2)
    _save_vms()
    _ok(f"spawned [cyan]{info['vm_id']}[/] for agent [cyan]{agent_id}[/] (role={role}, mock={info['mock']})")
    console.print_json(data=info)


@kali_app.command("exec")
def kali_exec(
    agent: str = typer.Argument(..., help="Agent id (from kali spawn / agent list)"),
    cmd: str = typer.Argument(..., help="Command to run inside the cage"),
    i_am_authorized: bool = typer.Option(False, "--i-am-authorized",
                                         help="Attest authorized lab use"),
    approver: str = typer.Option(None, "--approver", help="Named human approver (required to exec)"),
):
    """Run a command inside the Kali cage. DRY-RUN by default; needs --i-am-authorized + --approver."""
    _load_vms()
    # Guard every command
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
    from audit import AuditLog
    from guard.review_engine import review
    guard_tier = "blue" if (CONFIG.mock and not os.getenv("GUARD_LLM_URL")) else "red"
    verdict = review(f"[kali-exec:{agent}] {cmd}", guard_tier)
    audit = AuditLog(CONFIG.audit_file)
    if not verdict["allow"]:
        audit.append("kali_exec_blocked", agent=agent, cmd=cmd[:200], reason=verdict.get("reason"))
        _err(f"guard blocked: {verdict.get('reason')}")
        raise typer.Exit(3)
    try:
        result = _SANDBOX.exec(agent, cmd, authorized=i_am_authorized, approver=approver)
    except RuntimeError as e:
        _err(str(e))
        raise typer.Exit(2)
    audit.append("kali_exec", agent=agent, cmd=cmd[:200], executed=result.get("executed"),
                 dry_run=result.get("dry_run"), approver=approver)
    if result.get("dry_run"):
        _warn(result["detail"])
    else:
        _ok(result["detail"])
    console.print_json(data=result)


@kali_app.command("status")
def kali_status():
    _load_vms()
    console.print_json(data=_SANDBOX.status() or {})


@kali_app.command("down")
def kali_down(agent: str = typer.Argument(...)):
    _load_vms()
    out = _SANDBOX.destroy(agent)
    _save_vms()
    console.print_json(data=out)


# sandbox aliases
@sandbox_app.command("up")
def sandbox_up(session: str = "default"):
    out = _SANDBOX.up(session); _save_vms(); console.print_json(data=out)


@sandbox_app.command("down")
def sandbox_down(session: str = "default"):
    out = _SANDBOX.down(session); _save_vms(); console.print_json(data=out)


@sandbox_app.command("status")
def sandbox_status(session: str = typer.Argument(None)):
    _load_vms(); console.print_json(data=_SANDBOX.status(session) or {})


# ─── code ─────────────────────────────────────────────────────────────────────

@code_app.command("run")
def code_run_cmd(
    prompt: str = typer.Option(..., "--prompt", "-p", help="What to harden / patch (defensive)"),
    agent: str = typer.Option("code", "--agent", "-a", help="Must be the code agent"),
    i_am_authorized: bool = typer.Option(False, "--i-am-authorized"),
    approver: str = typer.Option(None, "--approver"),
):
    """Wonderful plans → Code Llama writes patch → review (guard) checks → apply in cage only."""
    if agent not in ("code", "muse-code"):
        _warn(f"expected --agent code (got {agent}); continuing with code agent")
    out = code_run(prompt, mock=CONFIG.mock, authorized=i_am_authorized,
                   approver=approver, audit_path=CONFIG.audit_file)
    if not out.get("allowed"):
        _err(f"blocked: {out.get('reason')}")
        raise typer.Exit(3)
    console.print(Panel(out["diff"], title="defensive diff (cage-only apply)", border_style="green"))
    if out["applied"]:
        _ok(out["detail"])
    else:
        _warn(out["detail"])
    console.print(f"[dim]{out.get('note')}[/]")


# ─── audit / models / config ──────────────────────────────────────────────────

@audit_app.command("tail")
def audit_tail(limit: int = typer.Option(20, "--limit", "-n", help="Lines to show")):
    """Tail the local hash-chained audit log."""
    _audit_show(limit)


@audit_app.command("log")
def audit_log(tail: int = typer.Option(20, "--tail", "-n", help="Lines to show")):
    """Alias: `musebreak audit log --tail N`."""
    _audit_show(tail)


def _audit_show(limit: int):
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
    from audit import AuditLog
    path = CONFIG.audit_file
    if not os.path.exists(path):
        console.print_json(data={"entries": [], "note": "no audit events yet"})
        return
    log = AuditLog(path)
    entries = log.read()[-limit:]
    table = Table(title=f"audit · chain_valid={log.verify_chain()}", box=box.SIMPLE)
    table.add_column("#"); table.add_column("EVENT"); table.add_column("DETAIL", overflow="fold")
    for i, e in enumerate(entries, 1):
        detail = {k: v for k, v in e.items() if k not in ("hash", "prev_hash", "ts")}
        table.add_row(str(i), e.get("event", "?"), json.dumps(detail)[:120])
    console.print(table)


@app.command("models")
def models_cmd(action: str = typer.Argument("list")):
    """models list — show the role → model/tier ladder (with open equivalents)."""
    table = Table(title="Model routing", box=box.SIMPLE_HEAVY)
    table.add_column("ROLE"); table.add_column("MODEL"); table.add_column("OPEN EQ", style="dim")
    table.add_column("TIER"); table.add_column("WHY", overflow="fold")
    for role, info in AGENT_ROSTER.items():
        table.add_row(role, info["model"], info["open_equivalent"], info["tier"], info["why"])
    console.print(table)


@config_app.command("show")
def config_show():
    """Show effective CLI config."""
    console.print_json(data=CONFIG.as_dict())



# ─── zkvm / voice / learn (Trust Plane + scaffolds) ───────────────────────────

@zkvm_app.command("prove")
def zkvm_prove(
    circuit: str = typer.Option("order_approve", "--circuit", "-c"),
    demo: bool = typer.Option(True, "--demo/--no-demo", help="Use built-in demo order payload"),
    public_json: str = typer.Option(None, "--public", help="JSON public_inputs"),
    witness_json: str = typer.Option(None, "--witness", help="JSON private_witness"),
):
    """Prove a circuit statement (hash-commitment MVP — simulated:true)."""
    from . import zkvm_cmd
    try:
        if demo and not public_json:
            payload = zkvm_cmd.demo_order_payload()
            circuit = payload["circuit"]
            pub, wit = payload["public_inputs"], payload["private_witness"]
        else:
            pub = json.loads(public_json or "{}")
            wit = json.loads(witness_json or "{}")
        proof = zkvm_cmd.prove(circuit, pub, wit)
        console.print(Panel.fit(
            json.dumps({k: proof[k] for k in
                        ("circuit", "statement_hash_hex", "simulated", "implementation",
                         "prover_time_ms", "version", "note") if k in proof}, indent=2),
            title="zkvm prove (hash-commitment-mvp)",
            border_style="green",
        ))
        console.print(f"proof_b64 length (chars): {len(proof['proof_b64'])}")
        _ok(f"statement={proof['statement_hash_hex'][:16]}… simulated={proof['simulated']}")
    except Exception as e:
        _err(str(e))
        raise typer.Exit(1)


@zkvm_app.command("verify")
def zkvm_verify(
    proof_b64: str = typer.Option(..., "--proof", "-p"),
    statement_hash_hex: str = typer.Option(..., "--hash", "-H"),
):
    """Verify a hash-commitment proof encoding."""
    from . import zkvm_cmd
    res = zkvm_cmd.verify(proof_b64, statement_hash_hex)
    console.print(json.dumps(res, indent=2))
    if res.get("verified"):
        _ok("verified (hash-commitment-mvp)")
    else:
        _err(f"not verified: {res.get('reason')}")
        raise typer.Exit(1)


@app.command("voice")
def voice_cmd(lang: str = typer.Option("ml", "--lang", "-l", help="Language code (default ml=Malayalam)")):
    """Voice stub — SeamlessM4T not loaded in CI; labelled scaffold."""
    _warn(f"voice --lang {lang}: SCAFFOLD — SeamlessM4T weights not present; no audio synthesized.")
    console.print(Panel.fit(
        f"lang={lang}\nsimulated=true\nnote=Install vision-extras / SeamlessM4T for real TTS/ASR",
        title="musebreak voice (stub)",
        border_style="yellow",
    ))


@app.command("learn")
def learn_cmd(
    topic: str = typer.Option("trust-plane", "--topic", "-t"),
):
    """Learn stub — interactive trainer not shipped yet."""
    _warn("learn: SCAFFOLD — curriculum runner not implemented; showing static tip.")
    console.print(Panel.fit(
        f"topic={topic}\n"
        "1. Gate1+Gate2 before any Wonder call\n"
        "2. Trust Plane is hash-commitment-mvp (not ZK yet)\n"
        "3. scope.yaml / dry-run default / human approve for exec\n"
        "Future: mission packs under cli/missions/",
        title="musebreak learn (stub)",
        border_style="cyan",
    ))


@app.command("command-center")
def command_center_cmd(
    no_demo: bool = typer.Option(False, "--no-demo", help="Skip auto demo swarm pass on mount"),
    simulated: bool = typer.Option(True, "--simulated/--live-claim",
                                   help="Honesty default: keep SIMULATED banner (live-claim still shows simulated telemetry unless real sources exist)"),
):
    """Textual TUI — live swarm view (Perception→Reasoning→Voice→Action). Simulated by default."""
    from .command_center import run_command_center
    if not simulated:
        _warn(" --live-claim requested, but this TUI still labels unmeasured panes as SIMULATED.")
    _ok("launching command-center TUI (q quit · r re-run · s spawn mock Kali VM)")
    run_command_center(simulated=True, auto_demo=not no_demo)


def run():
    app()


if __name__ == "__main__":
    run()
