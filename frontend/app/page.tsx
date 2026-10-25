"use client";
import { useEffect, useState } from "react";
import NFCTap from "@/components/NFCTap";
import QRScanner from "@/components/QRScanner";
import { KEY_ID, deviceFingerprint, nextCounter, nfcTap, qrSign, type QRPayload } from "@/lib/metakey";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Chal = { challenge_id: string; challenge: string; expires_in: number; qr_payload: QRPayload };

export default function Page() {
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

  const pill = (ok: boolean, label: string) => <span className={`pill ${ok ? "ok" : ""}`}>{ok ? "●" : "○"} {label}</span>;
  return (
    <main>
      <h1>Muse<span>Break</span></h1>
      <p className="muted">Zero-Trust gateway for Muse models · no password alone reaches Muse Wonder</p>
      <div className="gates">{pill(!!g1, "Gate 1 · JWT+device")}{pill(!!nfc, "NFC HMAC")}{pill(!!wonder, "Gate 2 · MetaKey")}{pill(!!wonder, "Gateway OPEN")}</div>
      {err && <p style={{ color: "var(--bad)" }}>⚠ {err}</p>}
      <div className="grid">
        <div className="card">
          <h3>Gate 1 · Login</h3>
          <input value={user} onChange={(e) => setUser(e.target.value)} placeholder="username" />
          <input value={pw} type="password" onChange={(e) => setPw(e.target.value)} placeholder="password" />
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {["muse-wonder", "muse-wonderful", "muse-spark-1.1", "glimmer"].map((m) => <option key={m}>{m}</option>)}
          </select>
          <button onClick={login}>Login</button> {g1 && <button onClick={newChallenge}>New challenge</button>}
          <p className="muted">Device fingerprint: {fp.slice(0, 40)}…</p>
        </div>
        <NFCTap onTap={onTap} disabled={!chal} />
        <QRScanner payload={chal?.qr_payload ?? null} expiresIn={chal?.expires_in ?? 30} onScan={onScan} />
      </div>
      <div className="grid">
        <div className="card">
          <h3>Forward → Muse</h3>
          <textarea rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          <button disabled={!wonder} onClick={query}>Send query</button>
          {answer !== null && <pre>{JSON.stringify(answer, null, 2)}</pre>}
        </div>
        <div className="card">
          <h3>Audit log {audit && (audit.chain_valid ? "· ✅ chain valid" : "· ❌ chain broken")}</h3>
          <button onClick={refreshAudit}>Refresh</button>
          <pre>{audit ? JSON.stringify(audit.entries.slice().reverse(), null, 1) : "…"}</pre>
        </div>
      </div>
    </main>
  );
}
