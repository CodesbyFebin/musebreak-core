"use client";
import { useEffect, useState } from "react";
import NFCTap from "@/components/NFCTap";
import QRScanner from "@/components/QRScanner";
import { KEY_ID, deviceFingerprint, nextCounter, nfcTap, qrSign, type QRPayload } from "@/lib/metakey";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Chal = { challenge_id: string; challenge: string; expires_in: number; qr_payload: QRPayload };

export default function LegacyPage() {
  const [fp, setFp] = useState("");
  const [user, setUser] = useState("judge"); const [pw, setPw] = useState("musebreak");
  const [model, setModel] = useState("muse-wonder");
  const [g1, setG1] = useState<string | null>(null);
  const [chal, setChal] = useState<Chal | null>(null);
  const [nfc, setNfc] = useState<{ mac: string; counter: number } | null>(null);
  const [wonder, setWonder] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("Explain Metabolic vs Jalapeño");
  const [answer, setAnswer] = useState<unknown>(null);
  const [audit, setAudit] = useState<{ chain_valid: boolean; entries: unknown[] } | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => { setFp(deviceFingerprint()); refreshAudit(); }, []);

  async function call(path: string, body: unknown, token?: string | null) {
    const r = await fetch(API + path, { method: "POST", body: JSON.stringify(body), headers: {
      "content-type": "application/json", "x-device-fingerprint": fp, ...(token ? { authorization: "Bearer " + token } : {}) } });
    const j = await r.json(); if (!r.ok) { setErr(`${path}: ${JSON.stringify(j.detail)}`); throw new Error(path); }
    setErr(""); return j;
  }
  async function refreshAudit() { try { setAudit(await (await fetch(API + "/audit?limit=12")).json()); } catch {} }

  async function login() {
    const j = await call("/login", { username: user, password: pw, device_fingerprint: fp });
    setG1(j.gate1_token); setWonder(null); setNfc(null);
    setChal(await call("/challenge", { key_id: KEY_ID, model }, j.gate1_token)); refreshAudit();
  }
  async function newChallenge() { setNfc(null); setWonder(null); setChal(await call("/challenge", { key_id: KEY_ID, model }, g1)); }
  async function onTap() { if (!chal) throw new Error("no challenge"); const counter = nextCounter(); setNfc({ mac: await nfcTap(chal.challenge, fp, counter), counter }); }
  async function onScan() {
    if (!chal || !nfc) { setErr("Tap the MetaKey first (NFC) — both gates are required"); throw new Error(); }
    const sig = await qrSign(chal.qr_payload);
    const j = await call("/authorize", { challenge_id: chal.challenge_id, key_id: KEY_ID, nfc_hmac: nfc.mac, counter: nfc.counter, qr_signature: sig }, g1);
    setWonder(j.wonder_token); refreshAudit();
  }
  async function query() { setAnswer(await call("/muse/query", { prompt }, wonder)); refreshAudit(); }

  const pill = (ok: boolean, label: string) => <span className={`pill ${ok ? "ok" : ""}`} style={{display:"inline-block",padding:"6px 12px",borderRadius:999,background:ok?"var(--green)":"#222",color:ok?"#021":"inherit",marginRight:8,fontSize:13}}>{ok ? "●" : "○"} {label}</span>;
  return (
    <main style={{maxWidth:1100,margin:"0 auto",padding:24}}>
      <p style={{fontSize:12}}><a href="/" style={{color:"var(--green)"}}>← Access Control dashboard</a></p>
      <h1 style={{margin:"8px 0"}}>Muse<span style={{color:"var(--blue)"}}>Break</span> · classic demo</h1>
      <p style={{color:"var(--muted)",fontSize:13}}>Zero-Trust gateway for Muse models · no password alone reaches Muse Wonder</p>
      <div style={{display:"flex",gap:10,marginTop:12,flexWrap:"wrap"}}>{pill(!!g1,"Gate 1 · JWT+device")}{pill(!!nfc,"NFC HMAC")}{pill(!!wonder,"Gate 2 · MetaKey")}{pill(!!wonder,"Gateway OPEN")}</div>
      {err && <p style={{ color: "var(--red)" }}>⚠ {err}</p>}
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(300px,1fr))",gap:16,marginTop:16}}>
        <div className="panel"><div className="panel-b">
          <h3>Gate 1 · Login</h3>
          <input value={user} onChange={(e) => setUser(e.target.value)} placeholder="username" style={{width:"100%",margin:"4px 0",padding:8,background:"#0a0c0e",border:"1px solid var(--border)",borderRadius:6}} />
          <input value={pw} type="password" onChange={(e) => setPw(e.target.value)} placeholder="password" style={{width:"100%",margin:"4px 0",padding:8,background:"#0a0c0e",border:"1px solid var(--border)",borderRadius:6}} />
          <select value={model} onChange={(e) => setModel(e.target.value)} style={{width:"100%",margin:"4px 0",padding:8,background:"#0a0c0e",border:"1px solid var(--border)",borderRadius:6,color:"var(--fg)"}}>
            {["muse-wonder", "muse-wonderful", "muse-spark-1.1", "glimmer"].map((m) => <option key={m}>{m}</option>)}
          </select>
          <button className="btn-approve" style={{marginTop:8}} onClick={login}>Login</button>
          {g1 && <button onClick={newChallenge} style={{marginLeft:8,padding:"10px 14px",borderRadius:8,border:"1px solid var(--border)",background:"transparent",color:"var(--fg)"}}>New challenge</button>}
          <p style={{color:"var(--muted)",fontSize:12}}>Device fingerprint: {fp.slice(0, 40)}…</p>
        </div></div>
        <NFCTap onTap={onTap} disabled={!chal} />
        <QRScanner payload={chal?.qr_payload ?? null} expiresIn={chal?.expires_in ?? 30} onScan={onScan} />
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(300px,1fr))",gap:16,marginTop:16}}>
        <div className="panel"><div className="panel-b">
          <h3>Forward → Muse</h3>
          <textarea rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)} style={{width:"100%",background:"#0a0c0e",border:"1px solid var(--border)",borderRadius:6,padding:8,color:"var(--fg)"}} />
          <button className="btn-approve" disabled={!wonder} onClick={query}>Send query</button>
          {answer !== null && <pre className="answer">{JSON.stringify(answer, null, 2)}</pre>}
        </div></div>
        <div className="panel"><div className="panel-b">
          <h3>Audit log {audit && (audit.chain_valid ? "· ✅ chain valid" : "· ❌ chain broken")}</h3>
          <button onClick={refreshAudit} style={{padding:"8px 12px",borderRadius:6,border:"1px solid var(--border)",background:"transparent",color:"var(--fg)"}}>Refresh</button>
          <pre className="answer">{audit ? JSON.stringify(audit.entries.slice().reverse(), null, 1) : "…"}</pre>
        </div></div>
      </div>
    </main>
  );
}
