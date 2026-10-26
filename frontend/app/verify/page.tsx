"use client";

import { useState } from "react";
import Shell from "@/components/Shell";
import { VerifyButton } from "@/components/zkvm/VerifyButton";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Minimal Trust Plane page: demo prove → verify roundtrip against the gateway.
 * Labelled hash-commitment-mvp throughout.
 */
export default function VerifyPage() {
  const [proofB64, setProofB64] = useState("");
  const [hash, setHash] = useState("");
  const [proveOut, setProveOut] = useState<string>("");
  const [busy, setBusy] = useState(false);

  async function demoProve() {
    setBusy(true);
    setProveOut("");
    try {
      // Build a tiny order_approve demo matching backend stock defaults
      const items = [{ sku: "laptop-dell-1", qty: 1, price: 1000 }];
      // Ask gateway to hash via prove — items_hash must match; compute locally with same canonical rules is hard
      // in browser, so use /orders/draft which computes items_hash server-side.
      const res = await fetch(`${API}/orders/draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_id: "ord-ui-demo",
          shop_id: "shop-1",
          items,
          total: 1000,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setProveOut(JSON.stringify(data, null, 2));
        return;
      }
      const proof = data.proof;
      setProofB64(proof.proof_b64);
      setHash(proof.statement_hash_hex);
      setProveOut(
        JSON.stringify(
          {
            status: data.status,
            simulated: proof.simulated,
            implementation: proof.implementation,
            circuit: proof.circuit,
            statement_hash_hex: proof.statement_hash_hex,
            prover_time_ms: proof.prover_time_ms,
            note: proof.note,
          },
          null,
          2
        )
      );
    } catch (e) {
      setProveOut(e instanceof Error ? e.message : "prove failed (is gateway up?)");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell mode="simulator" crumb="MUSEBREAK / TRUST PLANE / VERIFY">
      <div style={{ maxWidth: 720, display: "flex", flexDirection: "column", gap: 16 }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>Trust Plane Verify</h1>
        <p style={{ color: "var(--muted, #8a8a96)", margin: 0, lineHeight: 1.5 }}>
          Hash-commitment MVP — not a real zero-knowledge proof. The 256-byte payload is{" "}
          <code>SHA-256(statement) || 224 zero bytes</code> (encoding artifact). Future work: swap for
          SP1 / RISC Zero.
        </p>
        <button
          type="button"
          onClick={demoProve}
          disabled={busy}
          style={{
            alignSelf: "flex-start",
            background: "#121214",
            color: "#00d1ff",
            border: "1px solid #2a2a2e",
            borderRadius: 8,
            padding: "8px 14px",
            cursor: "pointer",
          }}
        >
          {busy ? "Proving…" : "Demo: POST /orders/draft → fill proof"}
        </button>
        {proveOut && (
          <pre
            style={{
              background: "#121214",
              border: "1px solid #2a2a2e",
              borderRadius: 8,
              padding: 12,
              fontSize: 12,
              overflow: "auto",
            }}
          >
            {proveOut}
          </pre>
        )}
        <label style={{ fontSize: 12, color: "#8a8a96" }}>
          statement_hash_hex
          <input
            value={hash}
            onChange={(e) => setHash(e.target.value)}
            style={{
              display: "block",
              width: "100%",
              marginTop: 4,
              padding: 8,
              background: "#0a0a0a",
              border: "1px solid #2a2a2e",
              color: "#e8e8ec",
              borderRadius: 6,
              fontFamily: "monospace",
            }}
          />
        </label>
        <label style={{ fontSize: 12, color: "#8a8a96" }}>
          proof_b64
          <textarea
            value={proofB64}
            onChange={(e) => setProofB64(e.target.value)}
            rows={4}
            style={{
              display: "block",
              width: "100%",
              marginTop: 4,
              padding: 8,
              background: "#0a0a0a",
              border: "1px solid #2a2a2e",
              color: "#e8e8ec",
              borderRadius: 6,
              fontFamily: "monospace",
            }}
          />
        </label>
        <VerifyButton proof_b64={proofB64} statement_hash_hex={hash} />
      </div>
    </Shell>
  );
}
