# MuseBreak Command Center (Textual TUI)

Launch:

```bash
pip install -e cli          # pulls textual + rich
export MUSEBREAK_MOCK=1     # default
musebreak command-center
```

## What you see

| Pane | Source of truth | Real vs simulated |
|---|---|---|
| Agents | `cli/musebreak_cli/agents.py` + `model_router.AGENT_ROSTER` | Roster is real; status during demo is illustrative |
| Pipeline | Perception → Reasoning → Voice → Action mapped to `backend/agents/` scaffolds + CLI `Swarm` | Stage walk is simulated without GPU / Llama Stack |
| Kali MicroVMs | `cli/musebreak_cli/sandbox.SandboxManager` | **Simulated** on this host (mock=True). Panel says so. |
| Audit stream | `backend/audit.AuditLog` + demo event ticks | Chain verification is real when a log exists; demo lines are labelled |

## Keys

- `q` — quit
- `r` — re-run one demo swarm pass
- `s` — spawn another mock Kali VM row

## What this is not

- Not a live Firecracker console (no rootfs / vsock claimed here)
- Not real ZK proof telemetry (Trust Plane is hash-commitment-mvp — see `docs/TRUST_PLANE.md`)
- Not a claim of proprietary Meta endpoints — open equivalents only (Llama-3-70B, Code Llama, Llama-Guard-3-8B)

## Smoke

```bash
python3 -c "from musebreak_cli.command_center import smoke_check; print(smoke_check())"
```
