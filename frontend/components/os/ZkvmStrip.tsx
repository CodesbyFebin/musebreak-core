"use client";

type Status = {
  running?: boolean;
  implementation?: string;
  is_zk?: boolean;
  commits?: number;
  uptime_s?: number;
  interval_s?: number;
  last?: {
    statement_hash_hex?: string;
    audit_tip?: string;
    entry_count?: number;
    committed_at?: number;
  } | null;
  note?: string;
};

export default function ZkvmStrip({
  status,
  onCommit,
  online,
}: {
  status: Status | null;
  onCommit: () => void;
  online: boolean;
}) {
  const tip = status?.last?.statement_hash_hex?.slice(0, 16) || "—";
  return (
    <div className="os-zkvm">
      <div className="os-zkvm-left">
        <span className={`os-dot ${status?.running ? "on" : ""}`} />
        <strong>zkVM heartbeat</strong>
        <span className="os-pill warn">hash-commitment-mvp · NOT ZK</span>
        {!online ? <span className="os-pill warn">gateway offline</span> : null}
      </div>
      <div className="os-zkvm-meta">
        <span>commits {status?.commits ?? 0}</span>
        <span>every {status?.interval_s ?? "—"}s</span>
        <span>audit entries {status?.last?.entry_count ?? "—"}</span>
        <span title={status?.last?.statement_hash_hex || ""}>stmt {tip}…</span>
      </div>
      <button type="button" className="os-btn ghost" onClick={onCommit} disabled={!online}>
        Commit now
      </button>
    </div>
  );
}
