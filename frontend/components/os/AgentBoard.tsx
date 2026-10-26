"use client";
import { OS_AGENTS, MODEL_TIERS, type TierSize } from "@/lib/os/models";

type TaskLite = {
  id: string;
  status: string;
  route?: { size?: string; agent?: { id?: string }; muse_label?: string };
};

type Props = {
  tasks: TaskLite[];
  claws: Record<string, boolean>;
  onToggleClaw: (id: string, on: boolean) => void;
};

export default function AgentBoard({ tasks, claws, onToggleClaw }: Props) {
  return (
    <div className="os-agents">
      {OS_AGENTS.map((a) => {
        const assigned = tasks.filter((t) => t.route?.agent?.id === a.id);
        const tier = MODEL_TIERS[a.defaultSize as TierSize];
        const busy = assigned.some((t) => t.status === "ready" || t.status === "awaiting_jev");
        return (
          <div key={a.id} className={`os-agent ${busy ? "busy" : ""}`}>
            <div className="os-agent-head">
              <strong>{a.name}</strong>
              <span className="os-pill dim">{a.id}</span>
            </div>
            <div className="os-muted">
              default → {tier.museLabel} ≡ {tier.openEquivalent.split(" ")[0]}
            </div>
            <div className="os-claws">
              {a.claw.map((c) => (
                <label key={c} className="os-claw">
                  <input
                    type="checkbox"
                    checked={!!claws[`${a.id}:${c}`]}
                    onChange={(e) => onToggleClaw(`${a.id}:${c}`, e.target.checked)}
                  />
                  {c}
                </label>
              ))}
            </div>
            <div className="os-agent-tasks">
              {assigned.length === 0 ? (
                <span className="os-muted">no tasks</span>
              ) : (
                assigned.slice(0, 3).map((t) => (
                  <div key={t.id} className="os-task-chip">
                    <code>{t.id.slice(-6)}</code>{" "}
                    <span className={`os-pill ${t.status === "done" ? "ok" : t.status === "unavailable" ? "warn" : "dim"}`}>
                      {t.status}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
