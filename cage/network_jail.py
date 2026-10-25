"""Network jail for agent microVMs: per-VM tap device + nftables default-deny egress,
allowing only the MuseBreak proxy. Requires root (CAP_NET_ADMIN). DRY_RUN=1 prints commands."""
import ipaddress
import os
import subprocess

DRY = os.getenv("DRY_RUN") == "1"


def _run(cmd: list[str]) -> None:
    if DRY:
        print("+", " ".join(cmd))
        return
    subprocess.run(cmd, check=True)


def create_jail(vm_id: str, host_ip: str, proxy_ip: str, proxy_port: int = 8443) -> str:
    ipaddress.ip_address(proxy_ip)
    ipaddress.ip_interface(host_ip)
    if not vm_id.replace("-", "").isalnum():
        raise ValueError("bad vm id")
    tap = ("tap" + vm_id.replace("-", ""))[:15]
    _run(["ip", "tuntap", "add", tap, "mode", "tap"])
    _run(["ip", "addr", "add", host_ip, "dev", tap])
    _run(["ip", "link", "set", tap, "up"])
    table = f"mb_{vm_id.replace('-', '_')}"
    _run(["nft", "add", "table", "inet", table])
    _run(["nft", "add", "chain", "inet", table, "fwd",
          "{ type filter hook forward priority 0 ; policy accept ; }"])
    _run(["nft", "add", "rule", "inet", table, "fwd", "iifname", tap, "ip", "daddr", proxy_ip,
          "tcp", "dport", str(proxy_port), "accept"])
    _run(["nft", "add", "rule", "inet", table, "fwd", "iifname", tap, "drop"])  # default deny
    return tap


def destroy_jail(vm_id: str) -> None:
    tap = ("tap" + vm_id.replace("-", ""))[:15]
    _run(["nft", "delete", "table", "inet", f"mb_{vm_id.replace('-', '_')}"])
    _run(["ip", "link", "del", tap])


if __name__ == "__main__":
    os.environ["DRY_RUN"] = "1"; DRY = True
    create_jail("mb-abc123", "172.16.0.1/30", "10.0.0.5")
