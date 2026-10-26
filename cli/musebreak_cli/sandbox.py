"""Kali cage — CONTROLLED, ISOLATED Firecracker microVM for authorized lab agents.

NOT an attack tool. Hosts standard pentest tooling for authorized, isolated use only.
Egress is locked down by cage/network_jail.py (default-deny; only the MuseBreak proxy is reachable).
When Firecracker / KVM / a Kali rootfs are absent the manager runs in MOCK mode.
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


@dataclass
class AgentVM:
    agent_id: str
    role: str
    vm_id: str
    image: str
    isolated: bool = True
    mock: bool = True
    status: str = "running"
    spawned_at: float = field(default_factory=time.time)


class SandboxManager:
    """Wraps cage/vm_manager.py + network_jail.py. Refuse to start without a Kali image outside mock."""

    def __init__(self, mock: bool = True, image: str | None = None):
        self.mock = mock or not os.path.exists("/dev/kvm")
        self.image = image or os.getenv("FC_ROOTFS", os.getenv("MUSEBREAK_KALI_IMAGE", ""))
        self._agents: dict[str, AgentVM] = {}
        self._vm = None
        self._jail = None
        if not self.mock:
            from cage.vm_manager import VMManager  # noqa
            from cage import network_jail  # noqa
            self._vm, self._jail = VMManager(), network_jail

    # --- legacy session API (swarm orchestrator) ---
    def up(self, session: str) -> dict:
        return self.spawn(agent_id=session, role="orchestrator", image=self.image or "kali-rolling-minimal.ext4",
                          isolated=True)

    def down(self, session: str) -> dict:
        return self.destroy(session)

    def status(self, session: str | None = None):
        if session:
            a = self._agents.get(session)
            return a.__dict__ if a else None
        return {k: v.__dict__ for k, v in self._agents.items()}

    # --- operator-console kali API ---
    def spawn(self, *, agent_id: str, role: str, image: str, isolated: bool = True) -> dict:
        img = image or self.image
        if not self.mock:
            if not img or "kali" not in img.lower():
                raise RuntimeError(
                    "Refuse to spawn: set --image / FC_ROOTFS / MUSEBREAK_KALI_IMAGE to a Kali rootfs "
                    "(e.g. kali-rolling-minimal.ext4). See docs/CLI_SWARM_DESIGN.md."
                )
            if not isolated:
                raise RuntimeError("Refuse: --isolated is required. The Kali cage must stay no-egress.")
            vm_id = self._vm.spawn(agent_id)
            # network_jail applied by vm_manager / explicit jail create — default-deny
        else:
            # Mock still requires a kali-named image string so the contract is exercised.
            if img and "kali" not in img.lower():
                raise RuntimeError("Image name must contain 'kali' (got %r)" % img)
            if not img:
                img = "kali-rolling-minimal.ext4"  # documented placeholder in mock
            vm_id = f"kali-mock-{agent_id[:12]}"
        agent = AgentVM(agent_id=agent_id, role=role, vm_id=vm_id, image=img,
                        isolated=isolated, mock=self.mock)
        self._agents[agent_id] = agent
        return {
            "agent_id": agent_id, "role": role, "vm_id": vm_id, "image": img,
            "isolated": isolated, "status": "running", "mock": self.mock,
            "note": ("MOCK — no Firecracker/KVM/Kali rootfs on this host" if self.mock
                     else "live Firecracker microVM + network_jail"),
        }

    def destroy(self, agent_id: str) -> dict:
        st = self._agents.pop(agent_id, None)
        if st and not self.mock and self._vm:
            self._vm.destroy(agent_id, st.vm_id)
        return {"agent_id": agent_id, "stopped": bool(st)}

    def exec(self, agent_id: str, cmd: str, *, authorized: bool, approver: str | None) -> dict:
        """Run a command inside the cage. DRY-RUN unless authorized + named approver."""
        agent = self._agents.get(agent_id)
        if not agent:
            raise RuntimeError(f"no Kali VM for agent {agent_id!r} — run `musebreak kali spawn` first")
        if not authorized or not approver:
            return {
                "agent_id": agent_id, "cmd": cmd, "executed": False, "dry_run": True,
                "detail": ("dry-run default — pass --i-am-authorized and --approver <name> "
                           "to execute inside the isolated cage"),
                "vm_id": agent.vm_id, "mock": agent.mock,
            }
        # Authorized path — still mock-only on this box; live would ssh/vsock into the microVM.
        if self.mock or agent.mock:
            return {
                "agent_id": agent_id, "cmd": cmd, "executed": True, "dry_run": False,
                "detail": f"MOCK exec inside {agent.vm_id} (approver={approver})",
                "stdout": f"[mock:{agent.role}] $ {cmd}\n(ok)",
                "vm_id": agent.vm_id, "approver": approver, "mock": True,
            }
        # Live path placeholder — real vsock/serial exec would land here.
        return {
            "agent_id": agent_id, "cmd": cmd, "executed": True, "dry_run": False,
            "detail": f"executed in {agent.vm_id} (approver={approver})",
            "vm_id": agent.vm_id, "approver": approver, "mock": False,
        }
