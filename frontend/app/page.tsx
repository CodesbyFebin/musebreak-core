"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Shell from "@/components/Shell";
import {
  API,
  authorizeGate2,
  deviceFingerprint,
  fetchAudit,
  issueChallenge,
  loginGate1,
  museQuery,
  probeGateway,
  simulateSession,
  type AuditEntry,
  type Chal,
  type Mode,
} from "@/lib/api";

type LogLine = { n: string; text: string; kind: "ok" | "pend" | "lock" | "info" };

function fmtTime(ts: number) {
  return new Date(ts).toLocaleTimeString("en-GB", { hour12: false });
}
function fmtRemain(ms: number) {
  if (ms <= 0) return "expired";
  const s = Math.ceil(ms / 1000);
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m > 0) return `in ${m} min ${r.toString().padStart(2, "0")} s`;
  return `in ${s} s`;
}
function fmtMMSS(ms: number) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
}
function shortFp(fp: string) {
  if (!fp) return "—";
  const h = fp.length > 16 ? fp : fp;
  return h.slice(0, 4) + "…" + h.slice(-4);
}
function copy(text: string) {
  try { navigator.clipboard?.writeText(text); } catch {}
}

export default function AccessControlPage() {
  const [mode, setMode] = useState<Mode>("simulator");
  const [fp, setFp] = useState("");
  const [sessionId, setSessionId] = useState("mb_····");
  const [gate1, setGate1] = useState<string | null>(null);
  const [sessionExp, setSessionExp] = useState(0);
  const [chal, setChal] = useState<Chal | null>(null);
  const [chalExp, setChalExp] = useState(0);
  const [wonder, setWonder] = useState<string | null>(null);
  const [tier, setTier] = useState("Blue");
  const [model, setModel] = useState("Muse Wonder");
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [prompt, setPrompt] = useState("");
  const [answer, setAnswer] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [now, setNow] = useState(Date.now());
  const boot = useRef(false);

  // live clocks
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, []);

  const pushLog = useCallback((line: LogLine) => {
    setLogs((L) => [...L.slice(-40), line]);
  }, []);

  const refreshAudit = useCallback(async (live: boolean, sid: string) => {
    if (!live) {
      setAudit((prev) => prev);
      return;
    }
    try {
      const a = await fetchAudit(12);
      setAudit(a.entries.slice().reverse());
    } catch {
      /* keep existing */
    }
  }, []);

  // boot: probe gateway, then Gate1 (+ challenge)
  useEffect(() => {
    if (boot.current) return;
    boot.current = true;
    (async () => {
      const f = deviceFingerprint();
      setFp(f);
      const live = await probeGateway();
      setMode(live ? "live" : "simulator");
      try {
        if (live) {
          const g1 = await loginGate1("judge", "musebreak", f);
          setGate1(g1.gate1_token);
          setSessionExp(Date.now() + g1.expires_in * 1000);
          const sid = "mb_" + g1.gate1_token.slice(-8, -4);
          setSessionId(sid);
          pushLog({ n: "01", text: `Session verified (${sid})`, kind: "ok" });
          pushLog({ n: "02", text: "Awaiting MetaKey approval…", kind: "pend" });
          pushLog({ n: "03", text: "Model access locked.", kind: "lock" });
          const c = await issueChallenge(g1.gate1_token, "muse-wonder", f);
          setChal(c);
          setChalExp(Date.now() + c.expires_in * 1000);
          setAudit([{ event: "gate1_pass", ts: Date.now() / 1000, sub: "judge" },
            { event: "challenge_issued", ts: Date.now() / 1000 + 0.001, sub: "judge" }]);
          await refreshAudit(true, sid);
        } else {
          const sim = simulateSession(f);
          setGate1(sim.gate1Token);
          setSessionId(sim.sessionId);
          setSessionExp(sim.expiresAt);
          setChal(sim.challenge);
          setChalExp(Date.now() + 30_000);
          pushLog({ n: "01", text: `Session verified (${sim.sessionId}) [SIMULATED]`, kind: "ok" });
          pushLog({ n: "02", text: "Awaiting MetaKey approval…", kind: "pend" });
          pushLog({ n: "03", text: "Model access locked.", kind: "lock" });
          setAudit([
            { event: "gate1_pass", ts: Date.now() / 1000, sub: "judge", _sim: true },
            { event: "challenge_issued", ts: Date.now() / 1000 + 0.001, sub: "judge", _sim: true },
          ]);
        }
      } catch (e) {
        setErr(String(e));
        // fall back to simulator
        const sim = simulateSession(f);
        setMode("simulator");
        setGate1(sim.gate1Token);
        setSessionId(sim.sessionId);
        setSessionExp(sim.expiresAt);
        setChal(sim.challenge);
        setChalExp(Date.now() + 30_000);
        pushLog({ n: "01", text: `Session verified (${sim.sessionId}) [SIMULATED]`, kind: "ok" });
        pushLog({ n: "02", text: "Awaiting MetaKey approval…", kind: "pend" });
        pushLog({ n: "03", text: "Model access locked.", kind: "lock" });
        setAudit([
          { event: "gate1_pass", ts: Date.now() / 1000, sub: "judge", _sim: true },
          { event: "challenge_issued", ts: Date.now() / 1000 + 0.001, sub: "judge", _sim: true },
        ]);
      }
    })();
  }, [pushLog, refreshAudit]);

  const gate2Done = !!wonder;
  const sessionLeft = sessionExp - now;
  const chalLeft = chalExp - now;

  async function onApprove() {
    if (!gate1 || !chal || busy || gate2Done) return;
    setBusy(true); setErr("");
    try {
      if (mode === "live") {
        const j = await authorizeGate2(gate1, chal, fp);
        setWonder(j.wonder_token);
        setModel(j.model || "muse-wonder");
        setTier((j.tier || "blue").replace(/^\w/, (c) => c.toUpperCase()));
        pushLog({ n: "04", text: "MetaKey approved (NFC HMAC + P-256)", kind: "ok" });
        pushLog({ n: "05", text: `Wonder token issued · model ${j.model}`, kind: "ok" });
        pushLog({ n: "06", text: "Model access unlocked.", kind: "ok" });
        await refreshAudit(true, sessionId);
      } else {
        // clearly-labeled simulated Gate2
        await new Promise((r) => setTimeout(r, 600));
        setWonder("sim.wonder." + sessionId);
        setModel("Muse Wonder");
        setTier("Blue");
        pushLog({ n: "04", text: "MetaKey approved [SIMULATED]", kind: "ok" });
        pushLog({ n: "05", text: "Wonder token issued · muse-wonder [SIMULATED]", kind: "ok" });
        pushLog({ n: "06", text: "Model access unlocked.", kind: "ok" });
        setAudit((a) => [
          { event: "gate2_pass", ts: Date.now() / 1000, sub: "judge", key_id: "metakey-demo-001", model: "muse-wonder", _sim: true },
          ...a,
        ]);
      }
    } catch (e) {
      setErr(String(e));
      pushLog({ n: "!!", text: `Gate2 failed: ${String(e)}`, kind: "lock" });
    } finally {
      setBusy(false);
    }
  }

  async function onQuery() {
    if (!wonder || !prompt.trim() || busy) return;
    setBusy(true); setErr("");
    try {
      if (mode === "live") {
        const j = await museQuery(wonder, prompt, fp);
        setAnswer(j);
        pushLog({ n: "07", text: "Query forwarded through gateway", kind: "ok" });
        await refreshAudit(true, sessionId);
      } else {
        await new Promise((r) => setTimeout(r, 400));
        setAnswer({
          _label: "SIMULATED RESPONSE — gateway unreachable; not a real Meta Model output",
          model: "muse-wonder",
          prompt,
          text: "This is a clearly-labeled simulated MuseBreak response. Start the FastAPI gateway to get live Metabolic-sim / Meta Model routing.",
        });
        pushLog({ n: "07", text: "Query answered [SIMULATED]", kind: "ok" });
        setAudit((a) => [
          { event: "muse_query", ts: Date.now() / 1000, sub: "judge", model: "muse-wonder", _sim: true },
          ...a,
        ]);
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  const prettyModel = useMemo(() => {
    const m = (model || "muse-wonder").toLowerCase();
    if (m.startsWith("muse-")) {
      return "Muse " + m.slice(5).split("-").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ");
    }
    return model;
  }, [model]);

  return (
    <Shell mode={mode} crumb="MUSEBREAK / SECURITY / OVERVIEW">
      <div className="page-head">
        <div>
          <h1>ACCESS CONTROL</h1>
          <div className="sub">Verify identity. Confirm intent. Review evidence.</div>
        </div>
        <div className="right-label">
          TWO-GATE AUTHORIZATION<br />CONTROLLED MODEL ACCESS
        </div>
      </div>

      <div className="gates">
        <div className="gate ok">
          <span className="num">01</span>
          <span>IDENTITY VERIFIED</span>
          <span className="ico" style={{ marginLeft: "auto" }}>✓</span>
        </div>
        <div className="gate-line" />
        <div className={`gate ${gate2Done ? "ok" : "pending"}`}>
          <span className="num">02</span>
          <span>{gate2Done ? "METAKEY APPROVED" : "METAKEY AWAITING APPROVAL"}</span>
          <span className="ico" style={{ marginLeft: "auto" }}>{gate2Done ? "✓" : "◷"}</span>
        </div>
        <div className="gate-line" />
        <div className={`gate ${gate2Done ? "ok" : "locked"}`}>
          <span className="num">03</span>
          <span>{gate2Done ? "MODEL ACCESS OPEN" : "MODEL ACCESS LOCKED"}</span>
          <span className="ico" style={{ marginLeft: "auto" }}>{gate2Done ? "✓" : "🔒"}</span>
        </div>
      </div>

      <div className="dash">
        {/* LEFT */}
        <div className="col">
          <div className="panel">
            <div className="panel-h"><span className="n">01</span> IDENTITY</div>
            <div className="panel-b">
              <div className="status-bar">● SESSION VERIFIED</div>
              <div className="kv">
                <div className="k">Session ID</div>
                <div className="v">{sessionId} <button className="copy" onClick={() => copy(sessionId)} title="Copy">⧉</button></div>
                <div className="k">JWT validity</div>
                <div className="v">5 min</div>
                <div className="k">Device fingerprint</div>
                <div className="v">{shortFp(fp)} <button className="copy" onClick={() => copy(fp)} title="Copy">⧉</button></div>
                <div className="k">Session expires</div>
                <div className="v">
                  {sessionExp ? fmtTime(sessionExp) : "—"}
                  <span className="muted">({fmtRemain(sessionLeft)})</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* CENTER */}
        <div className="col">
          <div className="panel">
            <div className="panel-h"><span className="n">02</span> METAKEY · INTENT APPROVAL</div>
            <div className="panel-b">
              <div className="metakey-wrap">
                <div className="device">
                  {!gate2Done && <><span className="nfc-ring" /><span className="nfc-ring r2" /><span className="nfc-ring r3" /></>}
                  <div className="screen">{gate2Done ? "Intent\nconfirmed" : "Confirm\nintent"}</div>
                  <div className="label">Muse Wonder</div>
                </div>
                <div className="tap-label">{gate2Done ? "Approved via NFC" : "Tap via NFC"}</div>
                <div className="badges">
                  <span className={`badge ${gate2Done || chal ? "on" : ""}`}>NFC HMAC</span>
                  <span className={`badge ${gate2Done ? "on" : ""}`}>P-256 signature</span>
                </div>
                <div className="chal-row">
                  <div>
                    <div className="k">Challenge ID</div>
                    <div className="v">{chal?.challenge_id || "—"}{" "}
                      {chal && <button className="copy" onClick={() => copy(chal.challenge_id)}>⧉</button>}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="k">Expires in</div>
                    <div className={`timer ${gate2Done ? "ok" : ""}`}>
                      {gate2Done ? "00:00" : fmtMMSS(chalLeft)}
                    </div>
                  </div>
                </div>
                <button className="btn-approve" disabled={!chal || gate2Done || busy || chalLeft <= 0} onClick={onApprove}>
                  {gate2Done ? "✓ APPROVED" : busy ? "AUTHORIZING…" : "((●))  SIMULATE TAP & APPROVE  ›"}
                </button>
                <div className="note">ℹ Browser simulator — hardware not connected.{mode === "simulator" ? " · Offline fallback." : ` · Live → ${API}`}</div>
                {err && <div className="err">⚠ {err}</div>}
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-h"><span className="n">07</span> MODEL CONSOLE</div>
            <div className="panel-b">
              <div className="console">
                {logs.map((l, i) => (
                  <div className="ln" key={i}>
                    <span className="n">{l.n} ›</span>
                    <span className={l.kind === "ok" ? "ok" : l.kind === "pend" ? "pend" : "lock"}>{l.text}</span>
                  </div>
                ))}
              </div>
              <div className="console-input">
                <input
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Ask a question after both gates pass…"
                  disabled={!gate2Done}
                  onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onQuery(); }}
                />
                <button disabled={!gate2Done || !prompt.trim() || busy} onClick={onQuery}>
                  Send query <span className="kbd">⌘ ↵</span>
                </button>
              </div>
              {answer !== null && (
                <div className="answer">
                  {mode === "simulator" && <span className="tag">SIMULATED — not a live Meta Model response</span>}
                  {JSON.stringify(answer, null, 2)}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div className="col right">
          <div className="panel">
            <div className="panel-h"><span className="n">04</span> SESSION POLICY</div>
            <div className="panel-b policy">
              <div className="row"><span className="k">Model</span><span className="v">{prettyModel}</span></div>
              <div className="row"><span className="k">Tier</span><span className="tier">{tier}</span></div>
              <div className="row"><span className="k">Prompt review</span><span className="v">Regex only</span></div>
              <div className="row"><span className="k">Guard model</span><span className="v">Not configured</span></div>
              <div className="row">
                <span className="k">Access</span>
                <span className={`lock-pill ${gate2Done ? "open" : ""}`}>
                  {gate2Done ? "✓ Open" : "🔒 Locked"}
                </span>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-h"><span className="n">05</span> MODEL ROUTE</div>
            <div className="panel-b route">
              <div className="route-flow">
                <span className="node">Gateway</span>
                <span className="arrow">→</span>
                <span className="node">{mode === "live" ? "Metabolic sim" : "Simulator"}</span>
              </div>
              <span className="sim-badge">
                {mode === "live" ? "LIVE · ENV-GATED UPSTREAM" : "SIMULATED INFERENCE"}
              </span>
            </div>
          </div>

          <div className="panel">
            <div className="panel-h"><span className="n">06</span> DEPLOYMENT CHECKS</div>
            <div className="panel-b checks">
              <div className="row"><span className="k">Replay protection</span><span className="v ok">Implemented ✓</span></div>
              <div className="row"><span className="k">Independent approval</span><span className="v ok">Required ✓</span></div>
              <div className="row"><span className="k">Hardware validation</span><span className="v pend">Pending △</span></div>
            </div>
          </div>
        </div>
      </div>

      {/* AUDIT — full width under grid */}
      <div className="panel">
        <div className="panel-h"><span className="n">08</span> AUDIT EVIDENCE</div>
        <div className="panel-b" style={{ paddingTop: 6 }}>
          <table className="table">
            <thead>
              <tr><th>#</th><th>EVENT</th><th>SESSION</th><th>RESULT</th><th>TIME</th></tr>
            </thead>
            <tbody>
              {audit.length === 0 && (
                <tr><td colSpan={5} style={{ color: "var(--muted)" }}>No events yet</td></tr>
              )}
              {audit.slice(0, 8).map((e, i) => {
                const ok = /_pass$|muse_query|key_enrolled/.test(e.event);
                const fail = /_fail$|guard_block/.test(e.event);
                const pend = /challenge_issued|awaiting/.test(e.event);
                const cls = fail ? "fail" : ok ? "ok" : "pend";
                const label = fail ? "Failed" : ok ? "Verified" : pend ? "Pending" : "Recorded";
                return (
                  <tr key={i}>
                    <td>{String(i + 1).padStart(3, "0")}</td>
                    <td>{e.event}{e._sim ? " · sim" : ""}</td>
                    <td>{sessionId}</td>
                    <td><span className={`res ${cls}`}><span className="d" />{label}</span></td>
                    <td>{fmtTime((e.ts || Date.now() / 1000) * 1000)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </Shell>
  );
}
