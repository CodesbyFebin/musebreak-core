"use client";

type Props = {
  open: boolean;
  taskId: string;
  size: string;
  museLabel: string;
  reason: string;
  onApprove: (approver: string) => void;
  onCancel: () => void;
  busy?: boolean;
};

export default function JevGate({
  open,
  taskId,
  size,
  museLabel,
  reason,
  onApprove,
  onCancel,
  busy,
}: Props) {
  if (!open) return null;
  return (
    <div className="os-modal" role="dialog" aria-modal="true" aria-label="Jev approval gate">
      <div className="os-modal-card">
        <div className="os-modal-head">
          <span className="os-pill warn">JEV APPROVAL GATE</span>
          <span className="os-muted">default-deny</span>
        </div>
        <h3>Human approval required</h3>
        <p>
          Task <code>{taskId}</code> is routed to <strong>{museLabel}</strong> ({size}).
          Large-model calls and any action-like step need an explicit Jev approve before they proceed.
        </p>
        <p className="os-muted">{reason}</p>
        <p className="os-note">
          This gate is an approval UI over the task pipeline. It does not execute shell, Kali, or
          host commands in the browser — those capabilities are not available here.
        </p>
        <label className="os-field">
          Approver name
          <input id="jev-approver" defaultValue="jev" placeholder="your name" />
        </label>
        <div className="os-modal-actions">
          <button type="button" className="os-btn ghost" onClick={onCancel} disabled={busy}>
            Deny
          </button>
          <button
            type="button"
            className="os-btn primary"
            disabled={busy}
            onClick={() => {
              const el = document.getElementById("jev-approver") as HTMLInputElement | null;
              onApprove((el?.value || "jev").trim() || "jev");
            }}
          >
            {busy ? "Approving…" : "Approve (Jev)"}
          </button>
        </div>
      </div>
    </div>
  );
}
