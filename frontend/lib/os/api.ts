import { API } from "@/lib/api";

async function req(path: string, init?: RequestInit) {
  const r = await fetch(API + path, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers || {}) },
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail || j));
  return j;
}

export async function fetchOsModels() {
  return req("/os/models");
}

export async function createOsTask(body: {
  prompt: string;
  force_size?: string | null;
  medium_api_configured?: boolean;
  large_api_configured?: boolean;
}) {
  return req("/os/tasks", { method: "POST", body: JSON.stringify(body) });
}

export async function listOsTasks() {
  return req("/os/tasks");
}

export async function jevApprove(taskId: string, approver: string, note = "") {
  return req(`/os/tasks/${taskId}/jev`, {
    method: "POST",
    body: JSON.stringify({ approver, note }),
  });
}

export async function completeOsTask(
  taskId: string,
  body: { text: string; source: string; model_id?: string; simulated?: boolean; tokens?: number },
) {
  return req(`/os/tasks/${taskId}/complete`, { method: "POST", body: JSON.stringify(body) });
}

export async function fetchZkvmStatus() {
  return req("/os/zkvm/status");
}

export async function commitZkvmNow() {
  return req("/os/zkvm/commit", { method: "POST", body: "{}" });
}

export async function callOpenAiCompat(
  baseUrl: string,
  prompt: string,
  modelHint: string,
): Promise<{ text: string; model: string; simulated: false }> {
  const url = baseUrl.replace(/\/$/, "") + "/v1/chat/completions";
  const r = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model: modelHint,
      messages: [{ role: "user", content: prompt }],
      max_tokens: 512,
      temperature: 0.7,
    }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error?.message || j.detail || `API ${r.status}`);
  const text = j.choices?.[0]?.message?.content || "";
  return { text, model: j.model || modelHint, simulated: false };
}
