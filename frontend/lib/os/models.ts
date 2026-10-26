/** Muse product labels → open models. Small = real WebLLM in-browser. */

export type TierSize = "small" | "medium" | "large";

export type TierConfig = {
  size: TierSize;
  museLabel: string;
  openEquivalent: string;
  webllmModelId?: string;
  runtime: "browser-webllm" | "api";
  requiresApi: boolean;
  requiresJev: boolean;
  note: string;
  localStorageKey?: string;
};

export const MODEL_TIERS: Record<TierSize, TierConfig> = {
  small: {
    size: "small",
    museLabel: "Muse Spark",
    openEquivalent: "Llama-3.2-1B-Instruct (WebLLM q4f32_1)",
    webllmModelId: "Llama-3.2-1B-Instruct-q4f32_1-MLC",
    runtime: "browser-webllm",
    requiresApi: false,
    requiresJev: false,
    note: "Runs fully in-browser via WebGPU. Real local inference.",
  },
  medium: {
    size: "medium",
    museLabel: "Muse Code",
    openEquivalent: "CodeLlama-13b-Instruct / Llama-3.1-8B-Instruct",
    runtime: "api",
    requiresApi: true,
    requiresJev: true,
    note: "Needs API URL in Settings / localStorage. UNAVAILABLE when unset.",
    localStorageKey: "musebreak.mediumApiUrl",
  },
  large: {
    size: "large",
    museLabel: "Muse Wonder Full",
    openEquivalent: "Llama-3.3-70B-Instruct",
    runtime: "api",
    requiresApi: true,
    requiresJev: true,
    note: "Needs API URL in Settings / localStorage. UNAVAILABLE when unset.",
    localStorageKey: "musebreak.largeApiUrl",
  },
};

/** Optional smaller alternate if 1B is too heavy on very low-end devices. */
export const WEBLLM_ALT_MODEL = "Llama-3.2-1B-Instruct-q4f16_1-MLC";

export const OS_AGENTS = [
  { id: "orchestrator", name: "Orchestrator", defaultSize: "large" as TierSize, claw: ["plan", "assign"] },
  { id: "recon", name: "Recon-Analyst", defaultSize: "small" as TierSize, claw: ["read"] },
  { id: "code", name: "Muse Code", defaultSize: "medium" as TierSize, claw: ["code_write"] },
  { id: "review", name: "Reviewer/Guard", defaultSize: "small" as TierSize, claw: ["read", "review"] },
  { id: "reporter", name: "Reporter", defaultSize: "medium" as TierSize, claw: ["read", "report"] },
  { id: "claw-worker", name: "Claw Worker", defaultSize: "small" as TierSize, claw: ["read"] },
];

export function readApiUrl(size: TierSize): string {
  if (typeof window === "undefined") return "";
  const key = MODEL_TIERS[size].localStorageKey;
  if (!key) return "";
  return (window.localStorage.getItem(key) || "").trim();
}

export function writeApiUrl(size: TierSize, url: string) {
  const key = MODEL_TIERS[size].localStorageKey;
  if (!key || typeof window === "undefined") return;
  if (url.trim()) window.localStorage.setItem(key, url.trim());
  else window.localStorage.removeItem(key);
}
