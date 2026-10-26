"use client";

import { useState } from "react";
import Shell from "@/components/Shell";
import { VerifyButton } from "@/components/zkvm/VerifyButton";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const b64uToBuf = (s: string) => {
  const b = atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4));
  return Uint8Array.from(b, (c) => c.charCodeAt(0)).buffer;
};
const bufToB64u = (b: ArrayBuffer) =>
  btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

async function post(path: string, body: unknown) {
  const r = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json();
  if (!r.ok) throw new Error(j.detail || r.statusText);
  return j;
}

/**
 * MetaKey online plane: UTR → WebAuthn assertion → MuV approve → verify.
 * Real navigator.credentials when an authenticator is present; otherwise a SIMULATED
 * assertion (challenge echo, no signature) that the backend labels simulated_assertion.
 * Proofs are hash-commitment-mvp, not zero-knowledge.
 */
export default function AuthPage() {
  const [orderId, setOrderId] = useState("order-1001");
  const [shopId, setShopId] = useState("shop-kochi-01");
  const [utr, setUtr] = useState("");
  const [draft, setDraft] = useState<any>(null);
  const [bound, setBound] = useState<any>(null);
  const [muv, setMuv] = useState(false);
  const [approved, setApproved] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const add = (s: string) => setLog((l) => [...l, s]);

  async function register() {
    try {
      const { options } = await post("/auth/register/options", { user_id: "demo-user" });
      const o = JSON.parse(options);
      const cred = (await navigator.credentials.create({
        publicKey: { ...o, challenge: b64uToBuf(o.challenge), user: { ...o.user, id: b64uToBuf(o.user.id) },
          excludeCredentials: [] },
      })) as PublicKeyCredential;
      const res = cred.response as AuthenticatorAttestationResponse;
      const out = await post("/auth/register/verify", { user_id: "demo-user", credential: {
        id: cred.id, rawId: bufToB64u(cred.rawId), type: cred.type,
        response: { clientDataJSON: bufToB64u(res.clientDataJSON), attestationObject: bufToB64u(res.attestationObject) } } });
      add(`registered credential ${out.credential_id.slice(0, 12)}… (real WebAuthn)`);
    } catch (e: any) { add(`register failed: ${e.message}`); }
  }

  async function makeDraft() {
    try {
      const d = await post("/auth/draft", { order_id: orderId, shop_id: shopId, utr,
        items: [{ sku: "laptop-dell-1", qty: 1, price: 1000 }] });
      setDraft(d); setBound(null); setApproved(false); add(`draft ${d.draft_id.slice(0, 8)} created`);
    } catch (e: any) { add(`draft failed: ${e.message}`); }
  }

  async function bind(simulate: boolean) {
    try {
      let assertion: any;
      if (simulate) {
        assertion = { simulated: true, challenge: draft.challenge };
      } else {
        const cred = (await navigator.credentials.get({ publicKey: {
          challenge: b64uToBuf(draft.challenge), rpId: draft.rp_id, userVerification: "preferred",
          allowCredentials: draft.allow_credentials.map((c: any) => ({ type: "public-key", id: b64uToBuf(c.id) })) } })) as PublicKeyCredential;
        const r = cred.response as AuthenticatorAssertionResponse;
        assertion = { id: cred.id, rawId: bufToB64u(cred.rawId), type: cred.type, response: {
          clientDataJSON: bufToB64u(r.clientDataJSON), authenticatorData: bufToB64u(r.authenticatorData),
          signature: bufToB64u(r.signature), userHandle: r.userHandle ? bufToB64u(r.userHandle) : null } };
      }
      const dh = bufToB64u(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(navigator.userAgent)));
      const b = await post("/auth/bind", { draft_id: draft.draft_id, assertion, device_hash: dh });
      setBound(b);
      add(`bound — ${b.simulated_assertion ? "SIMULATED assertion (no signature)" : "WebAuthn signature verified"}`);
    } catch (e: any) { add(`bind failed: ${e.message}`); }
  }

  async function approve() {
    try { await post("/auth/approve", { draft_id: draft.draft_id, muv_approved: muv }); setApproved(true); add("MuV approved"); }
    catch (e: any) { add(`approve failed: ${e.message}`); }
  }

  return (
    <Shell>
      <h1>MetaKey Auth — online plane</h1>
      <p className="muted">UTR + FIDO2/WebAuthn bound into a <b>hash-commitment-mvp</b> transcript (not zero-knowledge).</p>
      <section className="card">
        <h3>0 · Register authenticator (once)</h3>
        <button onClick={register}>Register with navigator.credentials.create</button>
      </section>
      <section className="card">
        <h3>1 · Enter UTR</h3>
        <input value={orderId} onChange={(e) => setOrderId(e.target.value)} placeholder="order id" />
        <input value={shopId} onChange={(e) => setShopId(e.target.value)} placeholder="shop id" />
        <input value={utr} onChange={(e) => setUtr(e.target.value.replace(/\D/g, "").slice(0, 12))} placeholder="12-digit UTR" />
        <button disabled={utr.length !== 12} onClick={makeDraft}>Create draft</button>
      </section>
      <section className="card">
        <h3>2 · Tap MetaKey (WebAuthn)</h3>
        <button disabled={!draft} onClick={() => bind(false)}>Sign with security key</button>{" "}
        <button disabled={!draft || !draft.simulated_allowed} onClick={() => bind(true)}>Simulate assertion (demo — not real)</button>
      </section>
      <section className="card">
        <h3>3 · MuV approve</h3>
        <label><input type="checkbox" checked={muv} onChange={(e) => setMuv(e.target.checked)} /> I reviewed this order (human approval)</label>{" "}
        <button disabled={!bound} onClick={approve}>Approve</button>
      </section>
      <section className="card">
        <h3>4 · Verify commitment</h3>
        {bound && approved ? (
          <VerifyButton proof_b64={bound.proof.proof_b64} statement_hash_hex={bound.proof.statement_hash_hex} />
        ) : <span className="muted">bind + approve first</span>}
      </section>
      <pre className="card">{log.join("\n")}</pre>
    </Shell>
  );
}
