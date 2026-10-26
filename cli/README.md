# MuseBreak CLI — operator console

Zero-Trust command center for the sandboxed agent swarm. **Defensive / authorized-lab use only.**

Safety (enforced in code):
- dry-run default for any Kali exec
- `--i-am-authorized` **and** a named `--approver` required to actually execute
- every step wrapped by guard review + hash-chained audit
- Kali cage is isolated / no-egress (`--isolated` required)
- red tier never unfilters; analyzer does vuln→mitigation mapping, **not** exploit generation

```bash
pip install -e cli          # provides `musebreak`
export MUSEBREAK_MOCK=1     # default — offline mock of gateway + Firecracker
```

## Commands

```bash
musebreak auth login --user judge
musebreak key tap --interface nfc          # Gate2 → stores MUSE_ROUTING_KEY_… in ~/.musebreak/token

musebreak swarm launch --topology '1xWonderful-orchestrator+5xLlama-workers'
musebreak swarm launch --workers 3
musebreak swarm status
musebreak agent list                       # ID · ROLE · MODEL · VM

musebreak kali spawn --agent recon --image kali-rolling-minimal.ext4 --isolated
musebreak kali exec recon-1 -- "nmap -sV 10.0.0.5"                                   # DRY-RUN
musebreak kali exec recon-1 --i-am-authorized --approver "ciso@lab (#1234)" -- "nmap -sV 10.0.0.5"

musebreak code run --agent code --prompt "harden login input validation"
musebreak audit tail
musebreak audit log --tail 50
musebreak models list
musebreak config show
```

## Agent roster / open equivalents

| Role | Model (label) | Open equivalent | VM |
|---|---|---|---|
| orchestrator | Muse Wonderful | Llama-3-70B | — |
| recon | Llama-3-8B | Llama-3-8B | kali |
| code | Muse Code | Code Llama | kali |
| review | Llama-Guard-3-8B + Llama-3-70B | same | — |
| analyzer | Muse Wonderful-Cyber (red) | Llama-3-70B | kali |
| report | Llama-3-70B | Llama-3-70B | — |

These are **labeled open equivalents** — we do not assert a proprietary Meta Muse endpoint. All model calls go through the existing gateway (2-gate auth + guard + audit) when `MUSEBREAK_MOCK=0`.

See `docs/CLI_SWARM_DESIGN.md` for architecture and the safety model.
