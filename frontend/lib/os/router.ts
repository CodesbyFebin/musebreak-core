/** Client-side task classifier — mirrors backend/os_plane/task_router.py. */
import { MODEL_TIERS, OS_AGENTS, type TierSize } from "./models";

const LARGE_HINTS =
  /\b(architect|refactor\s+(entire|whole|all)|migrate\s+codebase|multi[- ]?agent|security\s+audit\s+report|threat\s+model|wonder\s*full|muse\s*wonder|70b|large\s+model)\b/i;
const MEDIUM_HINTS =
  /\b(code|patch|fix|implement|write\s+function|unit\s*test|docker|kubernetes|sql|api\s+design|muse\s*code|codellama)\b/i;
const ACTION_HINTS =
  /\b(exec|shell|run\s+command|write\s+file|deploy|delete|rm\s+-|kali|exploit|payload)\b/i;

export function classifyTask(prompt: string, forceSize?: TierSize | null): TierSize {
  if (forceSize) return forceSize;
  const text = (prompt || "").trim();
  if (!text) return "small";
  if (LARGE_HINTS.test(text) || text.length > 1200) return "large";
  if (MEDIUM_HINTS.test(text) || text.length > 280) return "medium";
  return "small";
}

export function needsJev(prompt: string, size: TierSize): boolean {
  if (size === "medium" || size === "large") return true;
  return ACTION_HINTS.test(prompt || "");
}

export function pickAgent(size: TierSize, prompt: string) {
  const p = (prompt || "").toLowerCase();
  if (p.includes("recon") || p.includes("scan") || p.includes("inventory")) {
    return OS_AGENTS.find((a) => a.id === "recon")!;
  }
  if (size === "large" || p.includes("plan") || p.includes("orchestr")) {
    return OS_AGENTS.find((a) => a.id === "orchestrator")!;
  }
  if (size === "medium" || MEDIUM_HINTS.test(p)) {
    if (p.includes("report") || p.includes("summar")) {
      return OS_AGENTS.find((a) => a.id === "reporter")!;
    }
    return OS_AGENTS.find((a) => a.id === "code")!;
  }
  if (p.includes("review") || p.includes("guard")) {
    return OS_AGENTS.find((a) => a.id === "review")!;
  }
  return OS_AGENTS.find((a) => a.id === "claw-worker")!;
}

export type LocalRoute = {
  size: TierSize;
  museLabel: string;
  openEquivalent: string;
  runtime: string;
  webllmModelId?: string;
  requiresApi: boolean;
  requiresJev: boolean;
  agent: (typeof OS_AGENTS)[number];
  status: "ready" | "awaiting_jev" | "unavailable";
  note: string;
  apiConfigured: boolean;
};

export function routeLocal(
  prompt: string,
  opts: {
    forceSize?: TierSize | null;
    mediumApiConfigured: boolean;
    largeApiConfigured: boolean;
    jevApproved?: boolean;
  },
): LocalRoute {
  const size = classifyTask(prompt, opts.forceSize);
  const tier = MODEL_TIERS[size];
  const agent = pickAgent(size, prompt);
  const jev = needsJev(prompt, size) || tier.requiresJev;
  let apiOk = true;
  if (tier.requiresApi) {
    apiOk = size === "medium" ? opts.mediumApiConfigured : opts.largeApiConfigured;
  }
  let status: LocalRoute["status"] = "ready";
  if (!apiOk) status = "unavailable";
  else if (jev && !opts.jevApproved) status = "awaiting_jev";
  return {
    size,
    museLabel: tier.museLabel,
    openEquivalent: tier.openEquivalent,
    runtime: tier.runtime,
    webllmModelId: tier.webllmModelId,
    requiresApi: tier.requiresApi,
    requiresJev: jev,
    agent,
    status,
    note: tier.note,
    apiConfigured: apiOk,
  };
}
