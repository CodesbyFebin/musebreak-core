"""Firecracker microVM per agent session (Linux + /dev/kvm only).

Talks to the Firecracker API over its unix socket. Kernel/rootfs paths come from env:
  FC_BIN (default: firecracker), FC_KERNEL, FC_ROOTFS, FC_RUN_DIR (default /run/musebreak)
Get binaries from the official releases: https://github.com/firecracker-microvm/firecracker/releases
and a guest kernel/rootfs per the official guide:
https://github.com/firecracker-microvm/firecracker/blob/main/docs/getting-started.md
"""
import os
import secrets
import subprocess
import time

import httpx

RUN_DIR = os.getenv("FC_RUN_DIR", "/run/musebreak")
OK = (200, 204)  # Firecracker returns 204 No Content on successful PUTs


class FirecrackerError(RuntimeError):
    pass


class VMManager:
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.procs: dict[str, subprocess.Popen] = {}

    def _api(self, sock: str, method: str, path: str, body: dict) -> None:
        transport = httpx.HTTPTransport(uds=sock)
        with httpx.Client(transport=transport, base_url="http://localhost", timeout=5) as c:
            response = c.request(method, path, json=body)
        if response.status_code not in OK:
            raise FirecrackerError(f"{method} {path} -> {response.status_code}: {response.text}")

    def spawn(self, session_id: str, vcpus: int = 1, mem_mib: int = 512, tap: str | None = None) -> str:
        kernel, rootfs = os.getenv("FC_KERNEL"), os.getenv("FC_ROOTFS")
        if not (kernel and rootfs and os.path.exists("/dev/kvm")):
            raise FirecrackerError("FC_KERNEL/FC_ROOTFS unset or /dev/kvm missing")
        vm_id = "mb-" + secrets.token_hex(6)
        os.makedirs(RUN_DIR, exist_ok=True)
        sock = os.path.join(RUN_DIR, vm_id + ".sock")
        self.procs[vm_id] = subprocess.Popen([os.getenv("FC_BIN", "firecracker"), "--api-sock", sock])
        for _ in range(50):
            if os.path.exists(sock):
                break
            time.sleep(0.05)
        else:
            raise FirecrackerError("firecracker API socket did not appear")
        self._api(sock, "PUT", "/boot-source", {"kernel_image_path": kernel,
                                                 "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"})
        self._api(sock, "PUT", "/drives/rootfs", {"drive_id": "rootfs", "path_on_host": rootfs,
                                                   "is_root_device": True, "is_read_only": True})
        self._api(sock, "PUT", "/machine-config", {"vcpu_count": vcpus, "mem_size_mib": mem_mib})
        if tap:
            self._api(sock, "PUT", "/network-interfaces/eth0", {"iface_id": "eth0", "host_dev_name": tap})
        self._api(sock, "PUT", "/actions", {"action_type": "InstanceStart"})
        if self.redis:
            self.redis.setex(f"vm:{session_id}", 3600, vm_id)
        return vm_id

    def destroy(self, session_id: str, vm_id: str | None = None) -> None:
        if self.redis and not vm_id:
            vm_id = self.redis.get(f"vm:{session_id}")
        p = self.procs.pop(vm_id, None) if vm_id else None
        if p:
            p.terminate()
            p.wait(5)
        if self.redis:
            self.redis.delete(f"vm:{session_id}")
