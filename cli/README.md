# MuseBreak CLI

Install (editable): `pip install -e cli`  → provides the `musebreak` command.

Offline/mock mode is on by default (`MUSEBREAK_MOCK=1`) so it runs without a live gateway, Firecracker, or Kali
rootfs. Point it at a real stack with `MUSEBREAK_MOCK=0 MUSEBREAK_GATEWAY=... METAKEY_FILE=dev_key.json`.

```
musebreak --help
musebreak models list
musebreak agents list
musebreak sandbox up --session demo && musebreak sandbox status
musebreak swarm run cli/missions/example_mission.yaml                       # all exec steps DRY-RUN
musebreak swarm run cli/missions/example_mission.yaml --i-am-authorized --approver "ciso@lab (#1234)"
musebreak audit tail
```
See `docs/CLI_SWARM_DESIGN.md` for architecture and the safety/authorization model.
