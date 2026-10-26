"use client";
import { MODEL_TIERS, type TierSize } from "@/lib/os/models";

type Props = {
  selected?: TierSize | null;
  mediumConfigured: boolean;
  largeConfigured: boolean;
  webgpuOk: boolean | null;
  onSelect: (s: TierSize | null) => void;
};

export default function ModelTiers({
  selected,
  mediumConfigured,
  largeConfigured,
  webgpuOk,
  onSelect,
}: Props) {
  const sizes: TierSize[] = ["small", "medium", "large"];
  return (
    <div className="os-tiers">
      {sizes.map((s) => {
        const t = MODEL_TIERS[s];
        const available =
          s === "small" ? webgpuOk !== false : s === "medium" ? mediumConfigured : largeConfigured;
        const active = selected === s;
        return (
          <button
            key={s}
            type="button"
            className={`os-tier ${active ? "active" : ""} ${available ? "" : "unavail"}`}
            onClick={() => onSelect(active ? null : s)}
          >
            <div className="os-tier-top">
              <strong>{t.museLabel}</strong>
              <span className={`os-pill ${available ? "ok" : "warn"}`}>
                {s === "small"
                  ? webgpuOk === null
                    ? "checking"
                    : webgpuOk
                      ? "WebLLM"
                      : "no WebGPU"
                  : available
                    ? "API set"
                    : "UNAVAILABLE"}
              </span>
            </div>
            <div className="os-tier-eq">≡ {t.openEquivalent}</div>
            <div className="os-muted">{t.note}</div>
            <div className="os-tier-meta">
              <span>{s}</span>
              <span>{t.runtime}</span>
              {t.requiresJev ? <span>Jev</span> : null}
            </div>
          </button>
        );
      })}
    </div>
  );
}
