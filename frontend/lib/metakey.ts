// Browser MetaKey simulator (WebCrypto) — identical math to hardware/metakey_sim.js and the ESP32 firmware.
// DEMO KEY MATERIAL IS PUBLIC. Requires a secure context (https or localhost).
export const KEY_ID = "metakey-demo-001";
const SECRET_HEX = "6d757365627265616b2d64656d6f2d6465766963652d7365637265742d303031";
const PRIV_PKCS8_B64 = "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgNRrsfLfRy0sEKJ0vq5hWOkEzMiWbyvae0pg31ATzzQ+hRANCAARaxQsxoHPVYHhhpp94piDP19fVnhuY76+1+IlwucI5pFVP6ZfZk1FA2XzrIdt4UOSP1vW8USeNwTiOichF0byH";

const hexToBytes = (h: string) => new Uint8Array(h.match(/../g)!.map((b) => parseInt(b, 16)));
const toHex = (b: ArrayBuffer) => Array.from(new Uint8Array(b)).map((x) => x.toString(16).padStart(2, "0")).join("");
const enc = new TextEncoder();

export async function sha256Hex(s: string) { return toHex(await crypto.subtle.digest("SHA-256", enc.encode(s))); }

export function nextCounter(): number {
  const k = "musebreak_ctr_" + KEY_ID;
  const c = Math.max((parseInt(localStorage.getItem(k) || "0", 10) || 0) + 1, Date.now());
  localStorage.setItem(k, String(c)); return c;
}

export async function nfcTap(challengeHex: string, fingerprint: string, counter: number): Promise<string> {
  const key = await crypto.subtle.importKey("raw", hexToBytes(SECRET_HEX), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const tail = enc.encode("|" + (await sha256Hex(fingerprint)) + "|" + KEY_ID + "|" + counter);
  const head = enc.encode("MUSEBREAK-NFC|"), chal = hexToBytes(challengeHex);
  const msg = new Uint8Array(head.length + chal.length + tail.length);
  msg.set(head); msg.set(chal, head.length); msg.set(tail, head.length + chal.length);
  return toHex(await crypto.subtle.sign("HMAC", key, msg));
}

export type QRPayload = { v: number; cid: string; nonce: string; model: string; tier: string };

export async function qrSign(qr: QRPayload): Promise<string> {
  const der = Uint8Array.from(atob(PRIV_PKCS8_B64), (c) => c.charCodeAt(0));
  const key = await crypto.subtle.importKey("pkcs8", der, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key,
    enc.encode(`MUSEBREAK-INTENT|${qr.cid}|${qr.nonce}|${qr.model}`));
  return toHex(sig); // raw r||s (64 bytes)
}

export function deviceFingerprint(): string {
  const k = "musebreak_fp";
  let fp = localStorage.getItem(k);
  if (!fp) {
    fp = [navigator.userAgent, screen.width + "x" + screen.height, Intl.DateTimeFormat().resolvedOptions().timeZone,
      crypto.getRandomValues(new Uint32Array(2)).join("-")].join("|");
    localStorage.setItem(k, fp);
  }
  return fp;
}
