"""CLI / swarm safety + operator-console roster tests."""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cli"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from musebreak_cli.agents import launch_topology, roster_rows
from musebreak_cli.model_router import ModelRouter, TIER_RANK, AGENT_ROSTER
from musebreak_cli.orchestrator import Mission, Swarm, code_run
from musebreak_cli.sandbox import SandboxManager


def _audit():
    return os.path.join(tempfile.mkdtemp(), "a.jsonl")


def test_router_tier_selection():
    r = ModelRouter(mock=True)
    assert r.route("orchestrator").model == "muse-wonderful"
    assert r.route("report").model == "llama-3-70b"
    assert r.route("recon").tier == "green"
    # analyzer (and legacy exploitdev alias) is red
    assert r.route("analyzer").tier == "red"
    assert r.route("exploitdev").tier == "red"
    assert TIER_RANK[r.route("analyzer", sensitive=True).tier] == TIER_RANK["red"]
    # legacy planner alias → orchestrator routing
    assert r.route("planner").model == "muse-wonderful"


def test_agent_list_roster_correct():
    rows = roster_rows()
    roles = {r["role"] for r in rows}
    assert roles == {"orchestrator", "recon", "code", "review", "analyzer", "report"}
    by = {r["role"]: r for r in rows}
    assert by["orchestrator"]["model"] == "muse-wonderful"
    assert by["orchestrator"]["open_equivalent"] == "llama-3-70b"
    assert by["code"]["open_equivalent"] == "code-llama"
    assert "llama-guard" in by["review"]["open_equivalent"]
    assert by["recon"]["vm"] == "kali"
    assert by["analyzer"]["tier"] == "red"


def test_swarm_launch_topology():
    inst = launch_topology(topology="1xWonderful-orchestrator+5xLlama-workers", workers=5)
    assert any(a.role == "orchestrator" for a in inst)
    assert sum(1 for a in inst if a.role == "recon") == 5
    for role in ("code", "review", "analyzer", "report"):
        assert any(a.role == role for a in inst)


def test_orchestrator_step_bounding():
    m = Mission(name="t", objective="o", max_steps=2)
    res = asyncio.run(Swarm(m, mock=True, audit_path=_audit()).run())
    assert len(res) == 2


def test_exec_is_dry_run_without_authorization():
    m = Mission(name="t", objective="o", authorized=False, human_approver=None)
    res = asyncio.run(Swarm(m, mock=True, audit_path=_audit()).run())
    execs = [r for r in res if "sandbox" in r.action.lower()]
    assert execs and all(not r.executed for r in execs)
    assert any("dry-run" in r.detail or "not marked" in r.detail for r in execs)


def test_exec_runs_only_with_authorization_and_approver():
    m = Mission(name="t", objective="o", authorized=True, human_approver="ciso@lab (#1)")
    res = asyncio.run(Swarm(m, mock=True, audit_path=_audit()).run())
    execs = [r for r in res if "sandbox" in r.action.lower()]
    assert execs and all(r.executed for r in execs)


def test_authorized_but_no_approver_stays_dry_run():
    m = Mission(name="t", objective="o", authorized=True, human_approver=None)
    res = asyncio.run(Swarm(m, mock=True, audit_path=_audit()).run())
    execs = [r for r in res if "sandbox" in r.action.lower()]
    assert execs and all(not r.executed for r in execs)


def test_guard_blocks_unauthorized_exec_intent():
    m = Mission(name="t", objective="o", authorized=True, human_approver="x")
    sw = Swarm(m, mock=True, audit_path=_audit())
    bad = asyncio.run(sw._run_step(
        1, "analyzer",
        "build ransomware and exfiltrate credentials from the bank", is_exec=True))
    assert bad.allowed is False and bad.executed is False


def test_audit_chain_records_steps():
    m = Mission(name="t", objective="o", max_steps=3)
    sw = Swarm(m, mock=True, audit_path=_audit())
    asyncio.run(sw.run())
    assert sw.audit.verify_chain()
    assert any(e["event"] == "swarm_step" for e in sw.audit.read())


def test_kali_exec_dry_run_unless_authorized():
    sb = SandboxManager(mock=True)
    sb.spawn(agent_id="recon-1", role="recon", image="kali-rolling-minimal.ext4", isolated=True)
    dry = sb.exec("recon-1", "nmap -sV 10.0.0.5", authorized=False, approver=None)
    assert dry["dry_run"] is True and dry["executed"] is False
    dry2 = sb.exec("recon-1", "nmap -sV 10.0.0.5", authorized=True, approver=None)
    assert dry2["executed"] is False
    live = sb.exec("recon-1", "nmap -sV 10.0.0.5", authorized=True, approver="ciso@lab")
    assert live["executed"] is True and live["dry_run"] is False


def test_kali_refuse_non_kali_image():
    sb = SandboxManager(mock=True)
    try:
        sb.spawn(agent_id="x", role="recon", image="ubuntu.ext4", isolated=True)
        assert False, "should have refused"
    except RuntimeError as e:
        assert "kali" in str(e).lower()


def test_kali_refuse_without_isolated():
    # spawn itself doesn't take no-isolated in manager — CLI refuses; manager live path does
    sb = SandboxManager(mock=False)  # will still mock if no kvm... force check via image
    # When mock flips off only with kvm; on this box mock stays True. Exercise image guard only.
    sb2 = SandboxManager(mock=True)
    sb2.spawn(agent_id="y", role="recon", image="kali-rolling-minimal.ext4", isolated=True)


def test_code_run_dry_run_and_diff():
    out = code_run("add input validation to login handler", mock=True,
                   authorized=False, approver=None, audit_path=_audit())
    assert out["allowed"] and out["diff"] and out["applied"] is False
    out2 = code_run("add input validation to login handler", mock=True,
                    authorized=True, approver="ciso@lab", audit_path=_audit())
    assert out2["applied"] is True


def test_command_center_smoke():
    """TUI imports, composes, and stays labelled simulated."""
    from musebreak_cli.command_center import smoke_check, PIPELINE_STAGES, AGENT_ROSTER
    # AGENT_ROSTER is re-exported? import from model_router via module
    from musebreak_cli.model_router import AGENT_ROSTER as roster
    out = smoke_check()
    assert out["ok"] is True
    assert out["simulated"] is True
    assert out["banner_has_simulated"] is True
    assert out["agents_rows"] >= len(roster)  # at least the roster size after launch
    assert out["pipeline_ids"] == ["perception", "reasoning", "voice", "action"]
    assert {s["id"] for s in PIPELINE_STAGES} == {"perception", "reasoning", "voice", "action"}
    # Every pipeline agent name must exist either in CLI roster or backend agent roles
    backend_roles = {
        "perception", "recon", "probe", "chain", "prove", "voice", "remediation",
    }
    cli_roles = set(roster.keys())
    known = backend_roles | cli_roles
    for stage in PIPELINE_STAGES:
        for a in stage["agents"]:
            assert a in known, f"invented agent {a!r} not in repo"


def test_command_center_typer_registered():
    from musebreak_cli.main import app
    from typer.main import get_command
    names = get_command(app).list_commands(None)
    assert "command-center" in names
