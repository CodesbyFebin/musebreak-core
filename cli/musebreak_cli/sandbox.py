"""Kali sandbox manager — a CONTROLLED, ISOLATED Firecracker microVM for running agents in an authorized lab.

This is NOT an attack tool. The VM hosts standard pentest tooling for authorized, isolated use only; egress is
locked down by cage/network_jail.py (default-deny, only the MuseBreak proxy is reachable). When Firecracker /
KVM / a Kali rootfs are absent (e.g. this box) the manager runs in MOCK mode so the CLI still works.

Build a Kali rootfs: see docs/CLI_SWARM_DESIGN.md "Kali rootfs" (debootstrap/kali-rootfs -> ext4). Point
FC_ROOTFS at it and FC_KERNEL at a Firecracker-compatible kernel (cage/fetch_firecracker.sh + getting-started).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class SandboxManager:
    def __init__(self, mock: bool = True):
        self.mock = mock or not os.path.exists("/dev/kvm")
        self._state: dict[str, dict] = {}
        self._vm = None
        if not self.mock:
            from cage.vm_manager import VMManager  # noqa
            from cage import network_jail  # noqa
            self._vm, self._jail = VMManager(), network_jail

    def up(self, session: str) -> dict:
        if self.mock:
            vm_id = f"kali-mock-{session[:8]}"
            self._state[session] = {"vm_id": vm_id, "status": "running", "mock": True,
                                    "note": "MOCK — no Firecracker/KVM/Kali rootfs on this host"}
            return self._state[session]
        rootfs = os.getenv("FC_ROOTFS", "")
        if "kali" not in rootfs.lower():
            raise RuntimeError("Set FC_ROOTFS to a Kali rootfs image (see design doc 'Kali rootfs')")
        vm_id = self._vm.spawn(session)  # network isolation applied via tap + nftables by the jail
        self._state[session] = {"vm_id": vm_id, "status": "running", "mock": False}
        return self._state[session]

    def status(self, session: str | None = None):
        return self._state.get(session) if session else self._state

    def down(self, session: str) -> dict:
        st = self._state.pop(session, None)
        if st and not self.mock:
            self._vm.destroy(session, st["vm_id"])
        return {"session": session, "stopped": bool(st)}
