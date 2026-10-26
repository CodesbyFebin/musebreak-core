"use client";
import type { Mode } from "@/lib/api";

export default function TopBar({ mode, user = "judge" }: { mode: Mode; user?: string }) {
  return (
    <header className="topbar">
      <div className="search">
        <span aria-hidden>⌕</span>
        <input placeholder="Search sessions, keys, evidence..." readOnly />
        <span className="kbd">⌘ K</span>
      </div>
      <div className="pills">
        <span className={`pill ${mode === "simulator" ? "live" : "live"}`}>
          <span className="dot" />
          {mode === "live" ? "LIVE GATEWAY" : "LOCAL DEMO"}
        </span>
        <span className="pill sim">⬡ {mode === "live" ? "GATEWAY" : "SIMULATOR"}</span>
      </div>
      <div className="user">
        <div className="avatar">{user.slice(0, 1).toUpperCase()}</div>
        <span>{user}</span>
      </div>
    </header>
  );
}
