"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Verify a Trust Plane hash-commitment proof via POST /zkvm/verify.
 * This is NOT a real zero-knowledge verifier — see docs/TRUST_PLANE.md.
 */
export function VerifyButton({
  proof_b64,
  statement_hash_hex,
}: {
  proof_b64: string;
  statement_hash_hex: string;
}) {
  const [status, setStatus] = useState<"idle" | "verifying" | "verified" | "failed" | "error">("idle");
  const [timeMs, setTimeMs] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [implementation, setImplementation] = useState("");

  async function verify() {
    setStatus("verifying");
    setReason("");
    try {
      const start = Date.now();
      const res = await fetch(`${API}/zkvm/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proof_b64, statement_hash_hex }),
      });
      const data = await res.json();
      const elapsed = typeof data.verify_time_ms === "number" ? data.verify_time_ms : Date.now() - start;
      setTimeMs(elapsed);
      setImplementation(data.implementation || "hash-commitment-mvp");
      setReason(data.reason || "");
      setStatus(data.verified ? "verified" : "failed");
    } catch (e) {
      setStatus("error");
      setReason(e instanceof Error ? e.message : "network error");
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <button
        type="button"
        onClick={verify}
        disabled={!proof_b64 || !statement_hash_hex || status === "verifying"}
        style={{
          background: "#1bff6b",
          color: "#0a0a0a",
          border: "none",
          borderRadius: 8,
          padding: "10px 16px",
          fontWeight: 600,
          cursor: "pointer",
          fontFamily: "inherit",
        }}
      >
        {status === "idle" && "Verify hash-commitment proof"}
        {status === "verifying" && "Verifying…"}
        {status === "verified" && "Verified"}
        {status === "failed" && "Failed — retry"}
        {status === "error" && "Error — retry"}
      </button>
      {status === "verified" && (
        <span style={{ color: "#1bff6b", fontSize: 13 }}>
          ✓ verified{timeMs != null ? ` · ${timeMs}ms measured` : ""} · {implementation} · encoding
          artifact (not ZK)
        </span>
      )}
      {(status === "failed" || status === "error") && (
        <span style={{ color: "#ff4d4d", fontSize: 13 }}>✗ {reason || "not verified"}</span>
      )}
      <span style={{ color: "#8a8a96", fontSize: 11 }}>
        Calls POST /zkvm/verify. Implementation is hash-commitment-mvp (SHA-256 commitment), not a
        real zero-knowledge proof. Future: SP1 / RISC Zero.
      </span>
    </div>
  );
}
