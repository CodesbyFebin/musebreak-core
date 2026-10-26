"use client";

/**
 * AGENTIC CLAW HARNESS — Swarm Control.
 * Full-bleed operator console matching the Claw Harness mockup.
 * NOTE: all CPU / MEM / boot-log / VM-state values shown here are DEMO data.
 * They are illustrative, not measured live telemetry. See the banner on screen.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  CLAWS,
  CMD_SUGGESTIONS,
  DEMO_AGENTS,
  DEMO_VMS,
  type Agent,
  type Claw,
  type ClawId,
} from "@/lib/swarm-demo";
import "./swarm.css";

const STATUS_COLOR: Record<Agent["status"], string> = {
  active: "#00ff88",
  idle: "#6b7880",
  waiting: "#ffb020",
  paused: "#ff5c7a",
};

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const w = 120;
  const h = 26;
  const max = Math.max(...values, 1);
  const pts = values
    .map((v, i) => {
      const x = (i / Math.max(values.length - 1, 1)) * w;
      const y = h - (v / max) * (h - 3) - 1.5;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="ch-spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" width="100%" height="26">
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={pts} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function barColor(v: number) {
  if (v >= 70) return "#ff5c7a";
  if (v >= 40) return "#ffb020";
  return "#00ff88";
}

export default function SwarmPage() {
  const [selAgent, setSelAgent] = useState<string>("ag-2");
  const [selVm, setSelVm] = useState<string>("vm-1");
  // enabled claws default = union of claws currently held by any agent
  const [enabled, setEnabled] = useState<Record<ClawId, boolean>>(() => {
    const m: Record<string, boolean> = {};
    for (const c of CLAWS) m[c.id] = DEMO_AGENTS.some((a) => a.claws.includes(c.id));
    return m as Record<ClawId, boolean>;
  });
  const [bootN, setBootN] = useState(0);
  const [cmd, setCmd] = useState("");
  const [cmdLog, setCmdLog] = useState<string[]>([]);

  const agent = useMemo(() => DEMO_AGENTS.find((a) => a.id === selAgent) ?? null, [selAgent]);
  const vm = useMemo(() => DEMO_VMS.find((v) => v.id === selVm) ?? DEMO_VMS[0], [selVm]);

  // stream the selected VM's boot logs
  useEffect(() => {
    setBootN(0);
    const id = setInterval(() => {
      setBootN((n) => (n >= vm.bootLogs.length ? n : n + 1));
    }, 420);
    return () => clearInterval(id);
  }, [vm.id, vm.bootLogs.length]);

  function pickAgent(a: Agent) {
    setSelAgent(a.id);
    setSelVm(a.vmId);
  }

  function runCmd(raw: string) {
    const c = raw.trim();
    if (!c) return;
    let out = `unknown: ${c} (try: select <agent>, inspect <vm>, grant <claw>, revoke <claw>, clear)`;
    const [verb, arg] = [c.split(/\s+/)[0], c.split(/\s+/)[1]];
    if (verb === "select" && arg) {
      const a = DEMO_AGENTS.find((x) => x.id === arg || x.role === arg || x.label.toLowerCase() === arg.toLowerCase());
      if (a) { pickAgent(a); out = `selected ${a.label} (${a.id}) → pinned ${a.vmId}`; }
      else out = `no such agent: ${arg}`;
    } else if ((verb === "inspect" || verb === "logs" || verb === "vsock" || verb === "iptables") && arg) {
      const v = DEMO_VMS.find((x) => x.id === arg || x.name === arg);
      if (v) { setSelVm(v.id); out = `${verb} ${v.name} (${v.id})`; }
      else out = `no such vm: ${arg}`;
    } else if (verb === "grant" && arg) {
      const cl = CLAWS.find((x) => x.id === (arg as ClawId));
      if (cl) { setEnabled((m) => ({ ...m, [cl.id]: true })); out = `granted ${cl.id} (demo — not a live policy change)`; }
      else out = `no such claw: ${arg}`;
    } else if (verb === "revoke" && arg) {
      const cl = CLAWS.find((x) => x.id === (arg as ClawId));
      if (cl) { setEnabled((m) => ({ ...m, [cl.id]: false })); out = `revoked ${cl.id} (demo — not a live policy change)`; }
      else out = `no such claw: ${arg}`;
    } else if (verb === "clear") {
      setCmdLog([]); setCmd(""); return;
    } else if (verb === "help") {
      out = "commands: select, inspect, grant, revoke, clear, help";
    }
    setCmdLog((l) => [...l.slice(-30), `musebreak> ${c}`, out]);
    setCmd("");
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") runCmd(cmd);
    if (e.key === "Tab") {
      e.preventDefault();
      const hit = CMD_SUGGESTIONS.find((s) => s.startsWith(cmd) && s !== cmd);
      if (hit) setCmd(hit);
    }
  }

  const activeCount = DEMO_AGENTS.filter((a) => a.status === "active").length;
  const selAgentLabel = agent?.label ?? "—";

  return (
    <div className="ch-root">
      {/* header */}
      <div className="ch-header">
        <div className="ch-logo">
          <span className="mb">MB</span>
          <div>
            <b>MuseBreak</b> <span className="sub">Agentic Claw Harness</span>
          </div>
        </div>
        <div className="ch-badges">
          <span className="ch-badge green"><span className="dot pulse" />Claw Harness Active</span>
          <span className="ch-badge blue">MetaKeys: Gate1+2 PASS</span>
          <span className="ch-badge green"><span className="dot" />Metabolic: M1 Online</span>
          <span className="ch-badge">FC v1.7.0</span>
          <span className="ch-badge">Kali 2024.3</span>
          <span className="ch-badge">defensive-only</span>
          <span className="ch-badge green"><span className="dot pulse" />STREAMING</span>
        </div>
      </div>

      {/* honesty banner */}
      <div className="ch-simbar">
        Demo / simulated telemetry — CPU, memory, sparklines, boot logs and VM state are illustrative, not measured.
        This computer cannot run Firecracker/KVM; the harness is shown in mock mode.
      </div>

      <div className="ch-grid">
        {/* ---------------- LEFT: SWARM AGENTS ---------------- */}
        <div className="ch-col">
          <div className="ch-section-head">
            <span className="t"><span className="glyph">◈</span>Swarm Agents</span>
            <span className="ch-count">{activeCount} active</span>
          </div>
          <div className="ch-note">Orchestrated via vsock. Isolated per MicroVM. Tap to pin VM + claws.</div>

          {DEMO_AGENTS.map((a) => {
            const vmName = DEMO_VMS.find((v) => v.id === a.vmId)?.name ?? a.vmId;
            return (
              <div key={a.id} className={`ch-agent${a.id === selAgent ? " sel" : ""}`} onClick={() => pickAgent(a)}>
                <div className="top">
                  <span className="rdot" style={{ background: STATUS_COLOR[a.status] }} />
                  <span className="lbl">{a.label}</span>
                  <span className={`ch-stat ${a.status}`}>{a.status}</span>
                  <span className="uptime">{a.uptime}</span>
                </div>
                <div className="ch-kv">
                  <div><div className="k">Model</div><div className="v">{a.model}</div></div>
                  <div><div className="k">VM</div><div className="v vm">{vmName}</div></div>
                </div>
                <div className="ch-meter">
                  <div className="row"><span>CPU</span><span>{a.cpu}%</span></div>
                  <div className="ch-bar"><span style={{ width: `${a.cpu}%`, background: barColor(a.cpu) }} /></div>
                </div>
                <div className="ch-meter">
                  <div className="row"><span>MEM</span><span>{a.mem}%</span></div>
                  <div className="ch-bar"><span style={{ width: `${a.mem}%`, background: barColor(a.mem) }} /></div>
                </div>
                <div className="ch-chips">
                  {a.claws.map((cid) => {
                    const risk = CLAWS.find((c) => c.id === cid)?.risk ?? "low";
                    return <span key={cid} className={`ch-chip ${risk}`}>{cid}</span>;
                  })}
                </div>
              </div>
            );
          })}

          {/* harness policy footer */}
          <div className="ch-hpolicy">
            <div className="t">⚑ Harness Policy</div>
            <div className="r"><span className="ok">✓</span> defensive security only</div>
            <div className="r"><span className="ok">✓</span> no outbound net, proxy allowlist</div>
            <div className="r"><span className="ok">✓</span> audit_log append-only + signed</div>
          </div>
        </div>

        {/* ---------------- CENTER: SANDBOX VIEW ---------------- */}
        <div className="ch-col">
          <div className="ch-section-head">
            <span className="t"><span className="glyph">▣</span>Sandbox View — Firecracker</span>
            <span className="ch-count">3x Kali MicroVMs</span>
          </div>
          <div className="ch-note">isolated netns • vsock mesh</div>

          <div className="ch-panel flush">
            <div className="ch-panel-head"><span className="glyph">⬡</span>Isolated Network Diagram<span className="r">host ↔ vsock ↔ tap</span></div>
            <div className="ch-net">
              <div className="ch-host">
                <span className="ico">⌂</span>
                <div>
                  <b>HOST — CLAW HARNESS</b>
                  <div className="meta">cid=2 • proxy:8443 • audit:1025 • fc-bridge: 10.0.0.1</div>
                </div>
                <span className="gate">MetaKey Gate1+2 PASS</span>
              </div>
              <div className="ch-vmrow">
                {DEMO_VMS.map((v) => (
                  <div key={v.id} className={`ch-vm${v.id === selVm ? " sel" : ""}`} onClick={() => setSelVm(v.id)}>
                    <div className="vt">{v.name}<span className="d" /></div>
                    <div className="vk">
                      <div><span>vsock</span><b>{v.vsock}</b></div>
                      <div><span>cpus/mem</span><b>{v.cpus} / {v.memMb}MB</b></div>
                    </div>
                    <Sparkline values={v.cpuHist} color={v.id === selVm ? "#00ff88" : "#4d9fff"} />
                    <div className="gate">tap {v.tap} • {v.ip}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="ch-two">
            <div className="ch-panel flush">
              <div className="ch-panel-head"><span className="glyph">▤</span>iptables — {vm.name}</div>
              <div className="ch-mono-list">
                {vm.iptables.map((r, i) => (
                  <div key={i} className={`ln ${r.includes("ACCEPT") ? "accept" : r.includes("DROP") ? "drop" : ""}`}># {r}</div>
                ))}
              </div>
            </div>
            <div className="ch-panel flush">
              <div className="ch-panel-head"><span className="glyph">⇄</span>vsock + boot</div>
              <div className="ch-field">
                <div className="lab">vsock</div>
                <div className="val">{vm.vsock}</div>
                <div className="lab">disk</div>
                <div className="val">{vm.disk}</div>
                <div className="lab">mac / ip</div>
                <div className="val">{vm.mac} • {vm.ip}</div>
                <div className="lab">state</div>
                <div className="val">{vm.state} (demo)</div>
              </div>
            </div>
          </div>

          <div className="ch-panel flush">
            <div className="ch-panel-head">
              <span className="glyph">⟩</span>Boot Logs — Streaming {vm.tap}
              <button className="ch-clear" onClick={() => setBootN(0)}>clear</button>
            </div>
            <div className="ch-boot">
              {vm.bootLogs.slice(0, bootN).map((l, i) => (<div key={i} className="ln">{l}</div>))}
              {bootN < vm.bootLogs.length && <div className="ln"><span className="cursor">▋</span></div>}
            </div>
          </div>
        </div>

        {/* ---------------- RIGHT: CLAW HARNESS ---------------- */}
        <div className="ch-col">
          <div className="ch-section-head">
            <span className="t"><span className="glyph">{'{}'}</span>Claw Harness</span>
            <span className="ch-count">6 tools</span>
          </div>
          <div className="ch-note">Grant / revoke per agent. Sandboxed + audited. Selected: <b style={{ color: "#00ff88" }}>{selAgentLabel}</b></div>

          {CLAWS.map((c: Claw) => {
            const holders = DEMO_AGENTS.filter((a) => a.claws.includes(c.id));
            const pinned = agent?.claws.includes(c.id);
            return (
              <div key={c.id} className={`ch-claw${pinned ? " pinned" : ""}`}>
                <div className="top">
                  <span className="cico">◆</span>
                  <div style={{ minWidth: 0 }}>
                    <div className="cl">{c.label}</div>
                    <div className="cd">{c.desc}</div>
                  </div>
                  <div className={`ch-toggle${enabled[c.id] ? " on" : ""}`} onClick={() => setEnabled((m) => ({ ...m, [c.id]: !m[c.id] }))}>
                    <i />
                  </div>
                </div>
                <div className="foot">
                  <span className="holders">holders · {holders.length}</span>
                  {holders.slice(0, 4).map((h) => (
                    <span key={h.id} className={`ch-hchip${h.id === selAgent ? " sel" : ""}`}>{h.label}</span>
                  ))}
                  <span className={`ch-riskpill ${c.risk}`}>{c.risk}</span>
                </div>
              </div>
            );
          })}

          <div className="ch-panel ch-policy">
            <div className="ch-panel-head" style={{ padding: 0, border: "none", marginBottom: 6 }}><span className="glyph">⚙</span>Policy Engine</div>
            <div className="rule"><span className="a">allow file_read</span><span className="allow">if path ^/workspace</span></div>
            <div className="rule"><span className="a">deny shell_kali</span><span className="deny">if net != proxy</span></div>
            <div className="rule"><span className="a">require review_guard</span><span className="req">before code_write</span></div>
          </div>
        </div>
      </div>

      {/* ---------------- CONSOLE ---------------- */}
      <div className="ch-console">
        <div className="ch-panel flush">
          <div className="ch-panel-head"><span className="glyph">❯</span>Console</div>
          <div style={{ padding: "10px 12px" }}>
            <div className="selrow">
              <span>Selected Agent: <b>{agent ? `${agent.label} (${agent.id})` : "— none —"}</b></span>
              <span>Selected VM: <b>{vm ? `${vm.name} (${vm.id})` : "— none —"}</b></span>
            </div>
            <div className="ch-cmdline">
              <span className="prompt">musebreak&gt;</span>
              <input
                value={cmd}
                onChange={(e) => setCmd(e.target.value)}
                onKeyDown={onKey}
                placeholder="select ag-0 · inspect vm-1 · grant file_read · revoke shell_kali"
                spellCheck={false}
                autoComplete="off"
              />
              <span className="hint">Tab autocomplete • Enter to exec</span>
            </div>
            {cmdLog.length > 0 && (
              <div className="ch-cmdout">
                {cmdLog.map((l, i) => (
                  <div key={i} className="ln">{l.startsWith("musebreak>") ? <span className="u">{l}</span> : l}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="ch-footer">vsock 1025 • fc-tap0..2 • seccomp=strict • no-print <span>· demo data, simulated</span></div>
    </div>
  );
}
