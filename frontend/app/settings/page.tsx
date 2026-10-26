"use client";
import Shell from "@/components/Shell";
export default function Page() {
  return (
    <Shell crumb="MUSEBREAK / SECURITY / SETTINGS">
      <div className="page-head"><div><h1>SETTINGS</h1><div className="sub">Gateway URL, demo key, guard LLM (stub)</div></div></div>
      <div className="stub">
        <h2>SETTINGS</h2>
        <p>Gateway URL, demo key, guard LLM (stub). Wired views land here; the Overview dashboard already covers the live two-gate flow.</p>
        <p style={{marginTop:12}}><a href="/" style={{color:"var(--green)"}}>← Back to Access Control</a> · <a href="/legacy" style={{color:"var(--muted)"}}>Classic demo</a></p>
      </div>
    </Shell>
  );
}
