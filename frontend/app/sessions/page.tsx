"use client";
import Shell from "@/components/Shell";
export default function Page() {
  return (
    <Shell crumb="MUSEBREAK / SECURITY / SESSIONS">
      <div className="page-head"><div><h1>SESSIONS</h1><div className="sub">Active Gate1/Wonder sessions (stub)</div></div></div>
      <div className="stub">
        <h2>SESSIONS</h2>
        <p>Active Gate1/Wonder sessions (stub). Wired views land here; the Overview dashboard already covers the live two-gate flow.</p>
        <p style={{marginTop:12}}><a href="/" style={{color:"var(--green)"}}>← Back to Access Control</a> · <a href="/legacy" style={{color:"var(--muted)"}}>Classic demo</a></p>
      </div>
    </Shell>
  );
}
