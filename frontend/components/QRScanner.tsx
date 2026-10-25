"use client";
import { useEffect, useState } from "react";
import type { QRPayload } from "@/lib/metakey";

// Visual QR rendered from the payload hash (simulated e-ink display); "scan" signs the intent with P-256.
export default function QRScanner({ payload, onScan, expiresIn }:
  { payload: QRPayload | null; onScan: () => Promise<void>; expiresIn: number }) {
  const [left, setLeft] = useState(expiresIn);
  const [scanned, setScanned] = useState(false);
  useEffect(() => { setLeft(expiresIn); setScanned(false);
    const t = setInterval(() => setLeft((l) => Math.max(0, l - 1)), 1000); return () => clearInterval(t); }, [payload, expiresIn]);
  const bits = payload ? (payload.cid + payload.nonce).split("").flatMap((c) => parseInt(c, 16).toString(2).padStart(4, "0").split("")) : [];
  return (
    <div className="card">
      <h3>Gate 2b · QR Intent</h3>
      <div className="qrwrap">
        <div className="qr">{Array.from({ length: 256 }).map((_, i) => <i key={i} className={bits[i % bits.length] === "1" ? "on" : ""} />)}</div>
        {!scanned && payload && <div className="scanline" />}
      </div>
      {payload && <p className="muted">Intent: <b>{payload.model}</b> ({payload.tier}) · expires in {left}s</p>}
      <button disabled={!payload || scanned || left === 0}
        onClick={async () => { await onScan(); setScanned(true); }}>Scan & approve intent</button>
    </div>
  );
}
