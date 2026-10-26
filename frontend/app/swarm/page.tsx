"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Shell from "@/components/Shell";
import { fetchAudit, probeGateway, type AuditEntry } from "@/lib/api";
import {
  CLAWS,
  CMD_SUGGESTIONS,
  DEMO_AGENTS,
  DEMO_AUDIT,
  DEMO_VMS,
  type Agent,
  type AuditRow,
  type ClawId,
  type MicroVM,
} from "@/lib/swarm-demo";
import "./swarm.css";

function Sparkline({
  values,
  color,
}: {
  values: number[];
  color: string;
}) {
  const w = 120;
  const h = 28;
  const max = Math.max(...values, 1);
  const pts = values
    .map((v, i) => {
      const x = (i / Math.max(values.length - 1, 1)) * w;
      const y = h - (v / max) * (h - 2) - 1;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg className="spark-svg" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        points={pts}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function clawRisk(id: ClawId) {
  return CLAWS.find((c) => c.id === id)?.risk ?? "low";
}

function nowTs() {
  const d = new Date();
  return d.toTimeString().slice(0, 12);
}

function mapGatewayAudit(entries: AuditEntry[]): AuditRow[] {
  return entries.slice(0, 40).map((e) => {
    const raw = String(
      (e as Record<string, unknown>).decision ??
        (e as Record<string, unknown>).result ??
        e.event ??
        ""
    ).toUpperCase();
    let result: AuditRow["result"] = "INFO";
    if (raw.includes("ALLOW") || raw.includes("PASS") || raw.includes("OK")) result = "ALLOW";
    else if (raw.includes("DENY") || raw.includes("BLOCK") || raw.includes("FAIL")) result = "DENY";
    const tsNum = typeof e.ts === "number" ? e.ts : Number(e.ts);
    const ts =
      Number.isFinite(tsNum) && tsNum > 1e11
        ? new Date(tsNum).toTimeString().slice(0, 12)
        : Number.isFinite(tsNum) && tsNum > 0
          ? new Date(tsNum * 1000).toTimeString().slice(0, 12)
          : nowTs();
    return {
      ts,
      agent: String(e.sub || e.key_id || (e as Record<string, unknown>).agent || "gateway"),
      action: String(e.event || (e as Record<string, unknown>).action || e.model || "audit"),
      target: String(
        e.hash ||
          (e as Record<string, unknown>).target ||
          (e as Record<string, unknown>).resource ||
          "—"
      ).slice(0, 48),
      result,
      source: "gateway" as const,
    };
  });
}

export default function SwarmPage() {
  const [agents, setAgents] = useState<Agent[]>(() =>
    DEMO_AGENTS.map((a) => ({ ...a, claws: [...a.claws] }))
  );
  const [vms, setVms] = useState<MicroVM[]>(() =>
    DEMO_VMS.map((v) => ({
      ...v,
      cpuHist: [...v.cpuHist],
      memHist: [...v.memHist],
      bootLogs: [...v.bootLogs],
      iptables: [...v.iptables],
    }))
  );
  const [audit, setAudit] = useState<AuditRow[]>(DEMO_AUDIT);
  const [gatewayLive, setGatewayLive] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<string | null>("ag-0");
  const [selectedVm, setSelectedVm] = useState<string | null>("vm-1");
  const [expand, setExpand] = useState<{
    vmId: string;
    kind: "logs" | "iptables" | "vsock";
  } | null>(null);
  const [cmd, setCmd] = useState("");
  const [cmdOut, setCmdOut] = useState("");
  const [showSuggest, setShowSuggest] = useState(false);
  const [suggestIdx, setSuggestIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Probe gateway + pull real audit when reachable
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ok = await probeGateway();
      if (cancelled) return;
      setGatewayLive(ok);
      if (!ok) return;
      try {
        const payload = await fetchAudit(40);
        if (cancelled || !payload?.entries?.length) return;
        const mapped = mapGatewayAudit(payload.entries);
        setAudit((prev) => {
          const demo = prev.filter((r) => r.source !== "gateway");
          return [...mapped, ...demo].slice(0, 80);
        });
      } catch {
        /* keep demo audit */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Illustrative telemetry drift (labeled demo)
  useEffect(() => {
    const t = setInterval(() => {
      setAgents((prev) =>
        prev.map((a) => {
          if (a.status !== "active") return a;
          const jitter = () => Math.max(1, Math.min(99, a.cpu + (Math.random() * 6 - 3)));
          const jitterM = () => Math.max(1, Math.min(99, a.mem + (Math.random() * 4 - 2)));
          return { ...a, cpu: Math.round(jitter()), mem: Math.round(jitterM()) };
        })
      );
      setVms((prev) =>
        prev.map((v) => {
          if (v.state !== "running") return v;
          const nextCpu = Math.max(
            1,
            Math.min(100, (v.cpuHist[v.cpuHist.length - 1] ?? 20) + (Math.random() * 8 - 4))
          );
          const nextMem = Math.max(
            1,
            Math.min(100, (v.memHist[v.memHist.length - 1] ?? 40) + (Math.random() * 4 - 2))
          );
          return {
            ...v,
            cpuHist: [...v.cpuHist.slice(1), Math.round(nextCpu)],
            memHist: [...v.memHist.slice(1), Math.round(nextMem)],
          };
        })
      );
    }, 2500);
    return () => clearInterval(t);
  }, []);

  const suggestions = useMemo(() => {
    const q = cmd.trim().toLowerCase();
    if (!q) return CMD_SUGGESTIONS.slice(0, 8);
    return CMD_SUGGESTIONS.filter((s) => s.toLowerCase().includes(q)).slice(0, 8);
  }, [cmd]);

  const pushAudit = useCallback((row: Omit<AuditRow, "ts" | "source"> & { ts?: string }) => {
    setAudit((prev) => [
      { ...row, ts: row.ts ?? nowTs(), source: "cmd" as const },
      ...prev,
    ].slice(0, 80));
  }, []);

  const runCommand = useCallback(
    (raw: string) => {
      const line = raw.trim();
      if (!line) return;
      setShowSuggest(false);
      setCmd("");

      const parts = line.split(/\s+/);
      const verb = parts[0]?.toLowerCase();

      // grant <claw> to <agent>
      if (verb === "grant" && parts.length >= 4 && parts[2]?.toLowerCase() === "to") {
        const claw = parts[1] as ClawId;
        const agentId = parts[3];
        if (!CLAWS.some((c) => c.id === claw)) {
          setCmdOut(`[simulator] unknown claw: ${claw}`);
          return;
        }
        setAgents((prev) =>
          prev.map((a) =>
            a.id === agentId && !a.claws.includes(claw)
              ? { ...a, claws: [...a.claws, claw] }
              : a
          )
        );
        pushAudit({
          agent: "operator",
          action: `grant:${claw}`,
          target: agentId,
          result: "ALLOW",
        });
        setCmdOut(`[simulator] granted ${claw} → ${agentId} (local demo state; no gateway CLI)`);
        return;
      }

      // revoke <claw> from <agent>
      if (verb === "revoke" && parts.length >= 4 && parts[2]?.toLowerCase() === "from") {
        const claw = parts[1] as ClawId;
        const agentId = parts[3];
        setAgents((prev) =>
          prev.map((a) =>
            a.id === agentId ? { ...a, claws: a.claws.filter((c) => c !== claw) } : a
          )
        );
        pushAudit({
          agent: "operator",
          action: `revoke:${claw}`,
          target: agentId,
          result: "ALLOW",
        });
        setCmdOut(`[simulator] revoked ${claw} ← ${agentId} (local demo state)`);
        return;
      }

      // logs <vm> [--tail N]
      if (verb === "logs" && parts[1]) {
        const vmId = parts[1];
        const vm = vms.find((v) => v.id === vmId || v.name === vmId);
        if (!vm) {
          setCmdOut(`[simulator] unknown vm: ${vmId}`);
          return;
        }
        let n = 20;
        const ti = parts.indexOf("--tail");
        if (ti >= 0 && parts[ti + 1]) n = parseInt(parts[ti + 1], 10) || 20;
        setSelectedVm(vm.id);
        setExpand({ vmId: vm.id, kind: "logs" });
        setCmdOut(
          `[simulator / illustrative] ${vm.name} boot logs (tail ${n}):\n` +
            vm.bootLogs.slice(-n).join("\n")
        );
        return;
      }

      // iptables <vm>
      if (verb === "iptables" && parts[1]) {
        const vm = vms.find((v) => v.id === parts[1] || v.name === parts[1]);
        if (!vm) {
          setCmdOut(`[simulator] unknown vm: ${parts[1]}`);
          return;
        }
        setSelectedVm(vm.id);
        setExpand({ vmId: vm.id, kind: "iptables" });
        setCmdOut(`[simulator / illustrative] iptables ${vm.name}:\n` + vm.iptables.join("\n"));
        return;
      }

      // vsock <vm>
      if (verb === "vsock" && parts[1]) {
        const vm = vms.find((v) => v.id === parts[1] || v.name === parts[1]);
        if (!vm) {
          setCmdOut(`[simulator] unknown vm: ${parts[1]}`);
          return;
        }
        setSelectedVm(vm.id);
        setExpand({ vmId: vm.id, kind: "vsock" });
        setCmdOut(
          `[simulator / illustrative] ${vm.name} vsock=${vm.vsock} audit port 1025 append-only`
        );
        return;
      }

      // pause / resume <vm>
      if ((verb === "pause" || verb === "resume") && parts[1]) {
        const vmId = parts[1];
        const next = verb === "pause" ? "paused" : "running";
        setVms((prev) =>
          prev.map((v) =>
            v.id === vmId || v.name === vmId ? { ...v, state: next } : v
          )
        );
        pushAudit({
          agent: "operator",
          action: `${verb}:${vmId}`,
          target: vmId,
          result: "ALLOW",
        });
        setCmdOut(`[simulator] ${verb} ${vmId} → state=${next} (local demo; no Firecracker RPC)`);
        return;
      }

      // clear audit
      if (verb === "clear" && parts[1]?.toLowerCase() === "audit") {
        setAudit([]);
        setCmdOut("[simulator] cleared local audit stream (gateway log unchanged)");
        return;
      }

      // select / inspect helpers
      if (verb === "select" && parts[1]) {
        if (parts[1].startsWith("ag-")) {
          setSelectedAgent(parts[1]);
          setCmdOut(`[simulator] selected agent ${parts[1]}`);
        } else {
          setSelectedVm(parts[1]);
          setCmdOut(`[simulator] selected ${parts[1]}`);
        }
        return;
      }
      if (verb === "inspect" && parts[1]) {
        const vm = vms.find((v) => v.id === parts[1] || v.name === parts[1]);
        if (vm) {
          setSelectedVm(vm.id);
          setExpand({ vmId: vm.id, kind: "logs" });
          setCmdOut(
            `[simulator] ${vm.name} ${vm.ip} ${vm.tap} cpus=${vm.cpus} mem=${vm.memMb}MB state=${vm.state}`
          );
        } else {
          setCmdOut(`[simulator] unknown target: ${parts[1]}`);
        }
        return;
      }

      setCmdOut(
        `[simulator] unknown command. Try: grant | revoke | logs | iptables | vsock | pause | resume | clear audit`
      );
    },
    [vms, pushAudit]
  );

  return (
    <Shell mode={gatewayLive ? "live" : "simulator"} crumb="MUSEBREAK / SWARM CONTROL">
      <div className="swarm-page">
        <header className="swarm-hdr">
          <div className="swarm-brand">
            <div className="swarm-brand-mark">MB</div>
            <div>
              <div className="swarm-brand-name">MuseBreak</div>
              <div className="swarm-brand-sub">Swarm Control</div>
            </div>
          </div>
          <div className="swarm-pills">
            <span className="swarm-pill pass">MetaKeys: Gate1+2 PASS</span>
            <span className="swarm-pill">FC v1.7.0</span>
            <span className="swarm-pill">Kali 2024.3</span>
            <span className="swarm-pill defensive">defensive-only</span>
            <span className="swarm-pill">
              audit: {gatewayLive ? "gateway LIVE" : "demo + local"}
            </span>
          </div>
        </header>

        <div className="swarm-demo-banner">
          DEMO / ILLUSTRATIVE — Agent CPU·mem, VM sparklines, boot logs, and iptables below are
          simulated for the command-center UI. Real audit rows are pulled from{" "}
          <code>GET /audit</code> when the gateway is reachable; grant/revoke/pause/resume mutate
          local simulator state only (no Firecracker RPC from this page).
        </div>

        <div className="swarm-body">
          <div className="swarm-col-left">
            {/* SWARM AGENTS */}
            <section className="swarm-panel">
              <div className="swarm-panel-h">
                <span>Swarm Agents</span>
                <span className="hint">demo telemetry · DENY by default</span>
              </div>
              <div className="swarm-panel-b">
                <div className="swarm-agents">
                  {agents.map((a) => (
                    <button
                      type="button"
                      key={a.id}
                      className={`agent-card${selectedAgent === a.id ? " selected" : ""}`}
                      onClick={() => setSelectedAgent(a.id)}
                      style={{ textAlign: "left", cursor: "pointer", width: "100%" }}
                    >
                      <div className="agent-top">
                        <div>
                          <div className="agent-role">{a.label}</div>
                          <div className="agent-model">{a.model}</div>
                          <div className="agent-open">open ≈ {a.openEquivalent}</div>
                        </div>
                        <span className={`agent-status ${a.status}`}>{a.status}</span>
                      </div>
                      <div className="agent-meta">
                        <span>
                          vm <b>{a.vmId}</b>
                        </span>
                        <span>
                          pid <b>{a.pid}</b>
                        </span>
                        <span>
                          cpu <b>{a.cpu}%</b>
                        </span>
                        <span>
                          mem <b>{a.mem}%</b>
                        </span>
                        <span>
                          up <b>{a.uptime}</b>
                        </span>
                        <span>
                          id <b>{a.id}</b>
                        </span>
                      </div>
                      <div className="agent-claws">
                        {a.claws.map((c) => (
                          <span key={c} className={`claw-chip ${clawRisk(c)}`}>
                            {c}
                          </span>
                        ))}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </section>

            {/* CLAWS legend */}
            <section className="swarm-panel">
              <div className="swarm-panel-h">
                <span>Claws / Capabilities</span>
                <span className="hint">risk · sandbox note</span>
              </div>
              <div className="swarm-panel-b">
                <div className="claws-grid">
                  {CLAWS.map((c) => (
                    <div key={c.id} className="claw-card">
                      <div className="claw-card-h">
                        <span className="claw-id">{c.label}</span>
                        <span className={`risk-badge ${c.risk}`}>{c.risk}</span>
                      </div>
                      <div className="claw-desc">{c.desc}</div>
                      <div className="claw-sandbox">sandbox: {c.sandbox}</div>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </div>

          <div className="swarm-col-right">
            {/* KALI MICROVMS */}
            <section className="swarm-panel">
              <div className="swarm-panel-h">
                <span>Kali MicroVMs</span>
                <span className="hint">illustrative CPU/mem · not live FC</span>
              </div>
              <div className="swarm-panel-b">
                <div className="vms-list">
                  {vms.map((vm) => {
                    const open =
                      expand?.vmId === vm.id
                        ? expand.kind
                        : null;
                    return (
                      <div
                        key={vm.id}
                        className={`vm-card${selectedVm === vm.id ? " selected" : ""}`}
                      >
                        <div className="vm-top">
                          <span className="vm-name">{vm.name}</span>
                          <span className="vm-id">{vm.id}</span>
                          <span className={`vm-state ${vm.state}`}>{vm.state}</span>
                        </div>
                        <div className="vm-grid">
                          <span>
                            tap <b>{vm.tap}</b>
                          </span>
                          <span>
                            ip <b>{vm.ip}</b>
                          </span>
                          <span>
                            mac <b>{vm.mac}</b>
                          </span>
                          <span>
                            vsock <b>{vm.vsock}</b>
                          </span>
                          <span>
                            cpus <b>{vm.cpus}</b>
                          </span>
                          <span>
                            mem <b>{vm.memMb} MB</b>
                          </span>
                          <span>
                            disk <b>{vm.disk}</b>
                          </span>
                        </div>
                        <div className="sparks">
                          <div className="spark">
                            <div className="spark-label">
                              <span>cpu % (demo)</span>
                              <span>{vm.cpuHist[vm.cpuHist.length - 1]}%</span>
                            </div>
                            <Sparkline values={vm.cpuHist} color="#1bff6b" />
                          </div>
                          <div className="spark">
                            <div className="spark-label">
                              <span>mem % (demo)</span>
                              <span>{vm.memHist[vm.memHist.length - 1]}%</span>
                            </div>
                            <Sparkline values={vm.memHist} color="#00d1ff" />
                          </div>
                        </div>
                        <div className="vm-actions">
                          {(
                            [
                              ["logs", "boot logs"],
                              ["iptables", "iptables"],
                              ["vsock", "vsock"],
                            ] as const
                          ).map(([kind, label]) => (
                            <button
                              key={kind}
                              type="button"
                              className={`vm-btn${open === kind ? " open" : ""}`}
                              onClick={() => {
                                setSelectedVm(vm.id);
                                setExpand(
                                  open === kind ? null : { vmId: vm.id, kind }
                                );
                              }}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                        {open === "logs" && (
                          <div className="vm-expand">
                            <div style={{ color: "var(--sw-yellow)", marginBottom: 4 }}>
                              // illustrative boot log — not live
                            </div>
                            {vm.bootLogs.map((l, i) => (
                              <div key={i}>{l}</div>
                            ))}
                          </div>
                        )}
                        {open === "iptables" && (
                          <div className="vm-expand">
                            <div style={{ color: "var(--sw-yellow)", marginBottom: 4 }}>
                              // illustrative iptables — DENY by default
                            </div>
                            {vm.iptables.map((l, i) => (
                              <div key={i}>{l}</div>
                            ))}
                          </div>
                        )}
                        {open === "vsock" && (
                          <div className="vm-expand">
                            <div>vsock endpoint: {vm.vsock}</div>
                            <div>audit_log: append-only on vsock 1025</div>
                            <div>signed audit via vsock · review_guard on vm-2</div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>

            {/* AUDIT */}
            <section className="swarm-panel">
              <div className="swarm-panel-h">
                <span>Audit Stream</span>
                <span className="hint">
                  {gatewayLive ? "gateway + local" : "demo (gateway offline)"}
                </span>
              </div>
              <div className="swarm-panel-b" style={{ paddingTop: 4, maxHeight: 320, overflow: "auto" }}>
                <table className="audit-table">
                  <thead>
                    <tr>
                      <th>ts</th>
                      <th>agent</th>
                      <th>action</th>
                      <th>target</th>
                      <th>result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {audit.length === 0 && (
                      <tr>
                        <td colSpan={5} style={{ color: "var(--sw-text-faint)" }}>
                          (empty — clear audit or wait for gateway events)
                        </td>
                      </tr>
                    )}
                    {audit.map((r, i) => (
                      <tr key={`${r.ts}-${i}`}>
                        <td>{r.ts}</td>
                        <td>{r.agent}</td>
                        <td>{r.action}</td>
                        <td>{r.target}</td>
                        <td>
                          <span
                            className={
                              r.result === "ALLOW"
                                ? "badge-allow"
                                : r.result === "DENY"
                                  ? "badge-deny"
                                  : "badge-info"
                            }
                          >
                            {r.result}
                          </span>
                          {r.source === "demo" && (
                            <span
                              style={{
                                marginLeft: 6,
                                fontSize: 8,
                                color: "var(--sw-text-faint)",
                              }}
                            >
                              demo
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </div>

        {/* Command bar */}
        <div className="cmd-bar">
          {showSuggest && suggestions.length > 0 && (
            <div className="cmd-suggest">
              {suggestions.map((s, i) => (
                <button
                  key={s}
                  type="button"
                  className={i === suggestIdx ? "active" : ""}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    setCmd(s);
                    setShowSuggest(false);
                    inputRef.current?.focus();
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          )}
          <div className="cmd-row">
            <span className="cmd-prompt">musebreak&gt;</span>
            <input
              ref={inputRef}
              className="cmd-input"
              value={cmd}
              placeholder="grant file_read to ag-4 · revoke shell_kali from ag-2 · logs vm-1 --tail 20 · pause vm-2"
              onChange={(e) => {
                setCmd(e.target.value);
                setShowSuggest(true);
                setSuggestIdx(0);
              }}
              onFocus={() => setShowSuggest(true)}
              onBlur={() => setTimeout(() => setShowSuggest(false), 120)}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setSuggestIdx((i) => Math.min(i + 1, suggestions.length - 1));
                } else if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setSuggestIdx((i) => Math.max(i - 1, 0));
                } else if (e.key === "Tab" && suggestions[suggestIdx]) {
                  e.preventDefault();
                  setCmd(suggestions[suggestIdx]);
                  setShowSuggest(false);
                } else if (e.key === "Enter") {
                  e.preventDefault();
                  if (showSuggest && suggestions[suggestIdx] && !cmd.includes(" ")) {
                    runCommand(suggestions[suggestIdx]);
                  } else {
                    runCommand(cmd);
                  }
                } else if (e.key === "Escape") {
                  setShowSuggest(false);
                }
              }}
              spellCheck={false}
              autoComplete="off"
            />
            <span className="cmd-sim">simulator</span>
          </div>
          {cmdOut && <div className="cmd-out">{cmdOut}</div>}
        </div>

        <footer className="swarm-footer">
          <strong>DEFENSIVE MODE</strong> — All exec is jailed in Firecracker. No outbound
          internet. Proxy allowlist: api.github.com, registry.kali.org. Review guard blocks
          secret exfiltration. Audit log signed via vsock. DENY-by-default; claws must be
          explicitly granted.
        </footer>
      </div>
    </Shell>
  );
}
