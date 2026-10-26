/** Illustrative Swarm Control demo data — CPU/mem/boot logs are DEMO, not live telemetry. */

export type ClawId =
  | "file_read"
  | "code_write"
  | "shell_kali"
  | "http_proxy"
  | "review_guard"
  | "audit_log";

export type Claw = {
  id: ClawId;
  label: string;
  desc: string;
  risk: "low" | "med" | "high";
  sandbox: string;
};

export type Agent = {
  id: string;
  role: string;
  label: string;
  model: string;
  openEquivalent: string;
  vmId: string;
  status: "active" | "idle" | "waiting" | "paused";
  cpu: number;
  mem: number;
  claws: ClawId[];
  pid: string;
  uptime: string;
};

export type MicroVM = {
  id: string;
  name: string;
  tap: string;
  ip: string;
  mac: string;
  vsock: string;
  cpus: number;
  memMb: number;
  disk: string;
  state: "running" | "paused";
  cpuHist: number[];
  memHist: number[];
  bootLogs: string[];
  iptables: string[];
};

export type AuditRow = {
  ts: string;
  agent: string;
  action: string;
  target: string;
  result: "ALLOW" | "DENY" | "INFO";
  source?: "gateway" | "demo" | "cmd";
};

export const CLAWS: Claw[] = [
  {
    id: "file_read",
    label: "file_read",
    desc: "RO mount /workspace, denylist /etc/shadow",
    risk: "low",
    sandbox: "gvisor+seccomp",
  },
  {
    id: "code_write",
    label: "code_write",
    desc: "RW /workspace only, diff guard",
    risk: "med",
    sandbox: "overlay + audit",
  },
  {
    id: "shell_kali",
    label: "shell_kali",
    desc: "Kali toolshed, no outbound net",
    risk: "high",
    sandbox: "fc-jail + no netns",
  },
  {
    id: "http_proxy",
    label: "http_proxy",
    desc: "Allowlist: api.github.com, registry.kali.org",
    risk: "med",
    sandbox: "proxy + mTLS",
  },
  {
    id: "review_guard",
    label: "review_guard",
    desc: "Enforces policy, blocks secrets",
    risk: "low",
    sandbox: "opa + regex",
  },
  {
    id: "audit_log",
    label: "audit_log",
    desc: "Append-only, vsock 1025",
    risk: "low",
    sandbox: "vsock + sig",
  },
];

/** Mockup roster; display names Claw Code 22B / Claw 7B kept; open equivalents labeled. */
export const DEMO_AGENTS: Agent[] = [
  {
    id: "ag-0",
    role: "orchestrator",
    label: "ORCHESTRATOR",
    model: "Wonderful 70B",
    openEquivalent: "Llama-3.3-70B-Instruct",
    vmId: "vm-0",
    status: "active",
    cpu: 34,
    mem: 62,
    claws: ["audit_log", "review_guard", "file_read"],
    pid: "f1a0",
    uptime: "2h 14m",
  },
  {
    id: "ag-1",
    role: "recon",
    label: "RECON",
    model: "Claw 13B",
    openEquivalent: "Llama-3.1-8B-Instruct",
    vmId: "vm-0",
    status: "active",
    cpu: 21,
    mem: 18,
    claws: ["file_read", "http_proxy"],
    pid: "f1a1",
    uptime: "2h 12m",
  },
  {
    id: "ag-2",
    role: "code",
    label: "CODE",
    model: "Claw Code 22B",
    openEquivalent: "CodeLlama-13b-Instruct",
    vmId: "vm-1",
    status: "active",
    cpu: 78,
    mem: 44,
    claws: ["file_read", "code_write", "shell_kali"],
    pid: "f1a2",
    uptime: "2h 11m",
  },
  {
    id: "ag-3",
    role: "review",
    label: "REVIEW",
    model: "Claw 13B",
    openEquivalent: "Llama-Guard-3-8B + Llama-3-70B",
    vmId: "vm-2",
    status: "idle",
    cpu: 12,
    mem: 22,
    claws: ["review_guard", "file_read", "audit_log"],
    pid: "f1a3",
    uptime: "2h 09m",
  },
  {
    id: "ag-4",
    role: "analyzer",
    label: "ANALYZER",
    model: "Claw 13B",
    openEquivalent: "Llama-3.3-70B-Instruct",
    vmId: "vm-1",
    status: "waiting",
    cpu: 5,
    mem: 31,
    claws: ["file_read", "audit_log"],
    pid: "f1a4",
    uptime: "1h 58m",
  },
  {
    id: "ag-5",
    role: "report",
    label: "REPORT",
    model: "Claw 7B",
    openEquivalent: "Llama-3.1-8B-Instruct",
    vmId: "vm-2",
    status: "idle",
    cpu: 8,
    mem: 14,
    claws: ["file_read", "audit_log"],
    pid: "f1a5",
    uptime: "1h 44m",
  },
];

export const DEMO_VMS: MicroVM[] = [
  {
    id: "vm-0",
    name: "kali-control",
    tap: "fc-tap0",
    ip: "10.0.0.2/24",
    mac: "02:fc:00:00:00:02",
    vsock: "vsock://2:1024",
    cpus: 2,
    memMb: 1024,
    disk: "kali-base.ext4:ro",
    state: "running",
    cpuHist: [12, 18, 22, 19, 24, 28, 31, 29, 34, 33, 27, 30],
    memHist: [58, 60, 61, 62, 63, 62, 61, 62, 63, 62, 62, 62],
    bootLogs: [
      "[ 0.000000] Firecracker MicroVM boot: kernel 6.1.62-kali",
      "[ 0.121000] vsock: host cid=2 guest cid=3",
      "[ 0.340000] fc-tap0: link up, mtu 1500",
      "[ 0.401000] iptables: default DROP applied",
      "[ 0.512000] audit: vsock 1025 connected",
      "[ 0.612000] metabolic: M1 gate open",
      "[ 0.811000] orchestrator ready pid f1a0",
      "[ 1.202000] metakey verify: Gate1 PASS Gate2 PASS",
    ],
    iptables: [
      "-P INPUT DROP",
      "-P FORWARD DROP",
      "-P OUTPUT DROP",
      "-A OUTPUT -o fc-tap0 -d 10.0.0.0/24 -j ACCEPT",
      "-A INPUT -i lo -j ACCEPT",
      "-A INPUT -p vsock --dport 1025 -j ACCEPT",
    ],
  },
  {
    id: "vm-1",
    name: "kali-exec",
    tap: "fc-tap1",
    ip: "10.0.1.2/24",
    mac: "02:fc:00:00:01:02",
    vsock: "vsock://2:1026",
    cpus: 4,
    memMb: 2048,
    disk: "kali-tools.ext4:rw",
    state: "running",
    cpuHist: [45, 52, 61, 78, 72, 68, 74, 81, 79, 77, 69, 78],
    memHist: [32, 36, 40, 44, 43, 42, 44, 45, 44, 43, 44, 44],
    bootLogs: [
      "[ 0.000000] Firecracker MicroVM boot: kernel 6.1.62-kali",
      "[ 0.143000] vsock: host cid=2 guest cid=4",
      "[ 0.360000] fc-tap1: link up, isolated ns",
      "[ 0.411000] seccomp: profile=kali-exec loaded",
      "[ 0.523000] overlay: /workspace rw",
      "[ 0.701000] code_write claw mounted",
      "[ 0.812000] shell_kali: nmap, gobuster, ffuf avail",
      "[ 1.104000] no outbound net - proxy only",
    ],
    iptables: [
      "-P INPUT DROP",
      "-P FORWARD DROP",
      "-P OUTPUT DROP",
      "-A OUTPUT -o fc-tap1 -p tcp --dport 443 -d 10.0.0.1 -j ACCEPT",
      "-A OUTPUT -o lo -j ACCEPT",
      "-A INPUT -m state ESTABLISHED -j ACCEPT",
    ],
  },
  {
    id: "vm-2",
    name: "kali-audit",
    tap: "fc-tap2",
    ip: "10.0.2.2/24",
    mac: "02:fc:00:00:02:02",
    vsock: "vsock://2:1028",
    cpus: 2,
    memMb: 1024,
    disk: "kali-audit.ext4:ro",
    state: "running",
    cpuHist: [5, 8, 9, 12, 14, 11, 13, 15, 12, 10, 11, 12],
    memHist: [18, 20, 21, 22, 23, 22, 22, 22, 22, 21, 22, 22],
    bootLogs: [
      "[ 0.000000] Firecracker MicroVM boot: kernel 6.1.62-kali",
      "[ 0.132000] vsock: host cid=2 guest cid=5",
      "[ 0.355000] fc-tap2: link up, audit vlan",
      "[ 0.405000] audit_log: append-only /var/log/claw.audit",
      "[ 0.521000] review_guard: OPA bundle loaded",
      "[ 0.712000] sig: ed25519 verify enabled",
      "[ 0.901000] report agent connected",
    ],
    iptables: [
      "-P INPUT DROP",
      "-P OUTPUT DROP",
      "-A OUTPUT -o fc-tap2 -d 10.0.0.1 -p vsock -j ACCEPT",
      "-A INPUT -i fc-tap2 -j DROP",
    ],
  },
];

export const DEMO_AUDIT: AuditRow[] = [
  { ts: "14:02:11.204", agent: "ag-2", action: "code_write:/workspace/app.py", target: "vm-1", result: "ALLOW", source: "demo" },
  { ts: "14:02:14.891", agent: "ag-1", action: "http_proxy:GET api.github.com", target: "proxy", result: "ALLOW", source: "demo" },
  { ts: "14:02:15.022", agent: "ag-2", action: "shell_kali:nmap 10.0.1.0/24", target: "vm-1", result: "DENY", source: "demo" },
  { ts: "14:02:18.441", agent: "ag-0", action: "orchestrate:assign task #42", target: "ag-2", result: "INFO", source: "demo" },
  { ts: "14:02:22.100", agent: "ag-3", action: "review_guard:scan diff", target: "ag-2", result: "ALLOW", source: "demo" },
  { ts: "14:02:29.773", agent: "ag-4", action: "file_read:/workspace/report.md", target: "vm-1", result: "ALLOW", source: "demo" },
  { ts: "14:02:33.120", agent: "ag-2", action: "shell_kali:ffuf -w common.txt", target: "vm-1", result: "ALLOW", source: "demo" },
];

export const CMD_SUGGESTIONS = [
  "inspect vm-1",
  "inspect vm-2",
  "select ag-0",
  "select ag-2",
  "grant file_read to ag-4",
  "revoke shell_kali from ag-2",
  "logs vm-1 --tail 20",
  "iptables vm-1",
  "vsock vm-0",
  "pause vm-2",
  "resume vm-2",
  "clear audit",
];
