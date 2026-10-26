"use client";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import type { Mode } from "@/lib/api";

export default function Shell({
  children,
  mode = "simulator",
  crumb = "MUSEBREAK / SECURITY / OVERVIEW",
}: {
  children: React.ReactNode;
  mode?: Mode;
  crumb?: string;
}) {
  return (
    <div className="shell">
      <Sidebar />
      <div className="shell-main">
        <TopBar mode={mode} />
        <div className="page">
          <div className="crumb"><b>{crumb}</b></div>
          {children}
        </div>
        <footer className="footer">
          <div className="left">
            <span><span className="dot" />Demo environment</span>
            <span>No hardware connected</span>
          </div>
          <div>UI concept · Illustrative session data{mode === "simulator" ? " · SIMULATED" : ""}</div>
        </footer>
      </div>
    </div>
  );
}
