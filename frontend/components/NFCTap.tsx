"use client";
import { useState } from "react";

export default function NFCTap({ onTap, disabled }: { onTap: () => Promise<void>; disabled?: boolean }) {
  const [state, setState] = useState<"idle" | "tapping" | "done" | "error">("idle");
  const tap = async () => {
    setState("tapping");
    try { await new Promise((r) => setTimeout(r, 900)); await onTap(); setState("done"); }
    catch { setState("error"); }
  };
  return (
    <div className="card">
      <h3>Gate 2a · NFC Tap</h3>
      <div className={`nfc ${state}`} onClick={!disabled && state !== "tapping" ? tap : undefined}>
        <div className="ring r1" /><div className="ring r2" /><div className="ring r3" />
        <div className="key">🔑<small>MetaKey</small></div>
      </div>
      <p className="muted">{state === "idle" ? "Tap MetaKey to phone" : state === "tapping" ? "Reading HMAC over challenge…" :
        state === "done" ? "✅ HMAC-SHA256 computed" : "❌ tap failed"}</p>
    </div>
  );
}
