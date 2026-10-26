"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { fetchAudit, probeGateway, type AuditEntry, type Mode } from "@/lib/api";

function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleString("en-GB", { hour12: false });
}

export default function AuditPage() {
  const [mode, setMode] = useState<Mode>("simulator");
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [chain, setChain] = useState<boolean | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      const live = await probeGateway();
      setMode(live ? "live" : "simulator");
      if (!live) {
        setErr("Gateway unreachable — showing empty audit. Start the FastAPI backend to load the hash-chained log.");
        return;
      }
      try {
        const a = await fetchAudit(50);
        setEntries(a.entries.slice().reverse());
        setChain(a.chain_valid);
      } catch (e) {
        setErr(String(e));
      }
    })();
  }, []);

  return (
    <Shell mode={mode} crumb="MUSEBREAK / SECURITY / AUDIT LOG">
      <div className="page-head">
        <div>
          <h1>AUDIT LOG</h1>
          <div className="sub">
            Append-only, hash-chained evidence
            {chain === true && " · chain valid ✓"}
            {chain === false && " · chain BROKEN"}
          </div>
        </div>
      </div>
      {err && <div className="err">⚠ {err}</div>}
      <div className="panel">
        <div className="panel-h"><span className="n">08</span> AUDIT EVIDENCE</div>
        <div className="panel-b" style={{ paddingTop: 6 }}>
          <table className="table">
            <thead>
              <tr><th>#</th><th>EVENT</th><th>SUBJECT</th><th>KEY / MODEL</th><th>TIME</th><th>HASH</th></tr>
            </thead>
            <tbody>
              {entries.length === 0 && (
                <tr><td colSpan={6} style={{ color: "var(--muted)" }}>No entries</td></tr>
              )}
              {entries.map((e, i) => (
                <tr key={i}>
                  <td>{String(i + 1).padStart(3, "0")}</td>
                  <td>{e.event}</td>
                  <td>{String(e.sub || "—")}</td>
                  <td>{String(e.key_id || e.model || "—")}</td>
                  <td>{fmtTime(e.ts)}</td>
                  <td style={{ color: "var(--dim)" }}>{String(e.hash || "").slice(0, 12)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Shell>
  );
}
