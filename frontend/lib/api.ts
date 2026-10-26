/** Gateway client for the Access Control dashboard. Falls back to simulated mode when unreachable. */
import { KEY_ID, deviceFingerprint, nextCounter, nfcTap, qrSign, type QRPayload } from "./metakey";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Mode = "live" | "simulator";
export type Chal = {
  challenge_id: string;
  challenge: string;
  expires_in: number;
  qr_payload: QRPayload;
};
export type AuditEntry = {
  event: string;
  ts: number;
  sub?: string;
  key_id?: string;
  model?: string;
  hash?: string;
  _sim?: boolean;
  [k: string]: unknown;
};

export async function probeGateway(timeoutMs = 800): Promise<boolean> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    const r = await fetch(API + "/health", { signal: ctrl.signal });
    clearTimeout(t);
    return r.ok;
  } catch {
    return false;
  }
}

async function post(path: string, body: unknown, token?: string | null, fp?: string) {
  const r = await fetch(API + path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: {
      "content-type": "application/json",
      ...(fp ? { "x-device-fingerprint": fp } : {}),
      ...(token ? { authorization: "Bearer " + token } : {}),
    },
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail || j));
  return j;
}

export async function loginGate1(user: string, password: string, fp: string) {
  return post("/login", { username: user, password, device_fingerprint: fp }, null, fp) as Promise<{
    gate1_token: string;
    expires_in: number;
    device_fp: string;
  }>;
}

export async function issueChallenge(gate1: string, model: string, fp: string) {
  return post("/challenge", { key_id: KEY_ID, model }, gate1, fp) as Promise<Chal>;
}

/** Full Gate2: NFC HMAC + QR P-256 over the challenge → Wonder token. */
export async function authorizeGate2(gate1: string, chal: Chal, fp: string) {
  const counter = nextCounter();
  const mac = await nfcTap(chal.challenge, fp, counter);
  const sig = await qrSign(chal.qr_payload);
  return post(
    "/authorize",
    { challenge_id: chal.challenge_id, key_id: KEY_ID, nfc_hmac: mac, counter, qr_signature: sig },
    gate1,
    fp,
  ) as Promise<{ wonder_token: string; expires_in: number; model: string; tier: string }>;
}

export async function museQuery(wonder: string, prompt: string, fp: string) {
  return post("/muse/query", { prompt }, wonder, fp);
}

export async function fetchAudit(limit = 20): Promise<{ chain_valid: boolean; entries: AuditEntry[] }> {
  const r = await fetch(API + `/audit?limit=${limit}`);
  if (!r.ok) throw new Error("audit fetch failed");
  return r.json();
}

/** Simulated Gate1+challenge for offline demo (clearly labeled). */
export function simulateSession(fp: string) {
  const sid = "mb_" + Math.random().toString(16).slice(2, 6);
  const now = Date.now();
  return {
    sessionId: sid,
    gate1Token: "sim.gate1." + sid,
    expiresAt: now + 5 * 60 * 1000,
    fingerprint: fp,
    challenge: {
      challenge_id: "cha1_" + Math.random().toString(16).slice(2, 10),
      challenge: "00".repeat(32),
      expires_in: 30,
      qr_payload: { v: 1, cid: "cha1_sim", nonce: "n", model: "muse-wonder", tier: "blue" } as QRPayload,
    } as Chal,
  };
}

export { KEY_ID, deviceFingerprint };
