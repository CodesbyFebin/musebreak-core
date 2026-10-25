#!/usr/bin/env node
/**
 * MetaKey phone simulator (Node >= 18). Computes exactly what the ESP32 key does:
 *   NFC: HMAC-SHA256(device_secret, "MUSEBREAK-NFC|" + challenge(32B) + "|" + sha256(fp) + "|" + key_id)
 *   QR : ECDSA-P256-SHA256 over "MUSEBREAK-INTENT|cid|nonce|model" (raw r||s, hex)
 * Usage: node metakey_sim.js [API_URL]   -> runs the full 2-gate flow end-to-end.
 * DEMO KEY MATERIAL IS PUBLIC. Never use it in production.
 */
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

// METAKEY_FILE = JSON written by tools/enroll_dev_key.py ({key_id, secret_hex, priv_pem}); else demo key.
const ENROLLED = process.env.METAKEY_FILE ? JSON.parse(fs.readFileSync(process.env.METAKEY_FILE, "utf8")) : null;
const KEY_ID = ENROLLED ? ENROLLED.key_id : (process.env.METAKEY_ID || "metakey-demo-001");
const SECRET = Buffer.from(ENROLLED ? ENROLLED.secret_hex : (process.env.METAKEY_SECRET ||
  "6d757365627265616b2d64656d6f2d6465766963652d7365637265742d303031"), "hex");
const PRIV = crypto.createPrivateKey(ENROLLED ? ENROLLED.priv_pem :
  fs.readFileSync(path.join(__dirname, "demo_metakey_private.pem")));
const USER = ENROLLED ? ENROLLED.owner : "judge";
const PASS = process.env.DEMO_PASSWORD || "musebreak";

// Monotonic counter (a real key keeps this in NVS/secure element). Sim: persisted, and never below wall-clock ms
// so the browser sim and node sim sharing the demo key never collide.
const CTR_FILE = path.join(__dirname, ".metakey_sim_counter_" + KEY_ID);
function nextCounter() {
  let last = 0; try { last = parseInt(fs.readFileSync(CTR_FILE, "utf8"), 10) || 0; } catch {}
  const c = Math.max(last + 1, Date.now()); fs.writeFileSync(CTR_FILE, String(c)); return c;
}

const sha256hex = (s) => crypto.createHash("sha256").update(s).digest("hex");

function nfcTap(challengeHex, fingerprint, counter, keyId = KEY_ID) {
  const msg = Buffer.concat([Buffer.from("MUSEBREAK-NFC|"), Buffer.from(challengeHex, "hex"),
    Buffer.from("|" + sha256hex(fingerprint) + "|" + keyId + "|" + counter)]);
  return crypto.createHmac("sha256", SECRET).update(msg).digest("hex");
}

function qrSign(qr) {
  const msg = Buffer.from(`MUSEBREAK-INTENT|${qr.cid}|${qr.nonce}|${qr.model}`);
  return crypto.sign("sha256", msg, { key: PRIV, dsaEncoding: "ieee-p1363" }).toString("hex");
}

async function e2e(api) {
  const fp = "metakey-sim-phone-" + crypto.randomBytes(4).toString("hex");
  const post = async (p, body, headers = {}) => {
    const r = await fetch(api + p, { method: "POST", headers: { "content-type": "application/json", ...headers },
      body: JSON.stringify(body) });
    return { status: r.status, body: await r.json() };
  };
  const step = (n, r) => console.log(`${r.status < 300 ? "PASS" : "FAIL"} ${n} -> ${r.status}`);

  const l = await post("/login", { username: USER, password: PASS, device_fingerprint: fp }); step("Gate1 login", l);
  const h = { authorization: "Bearer " + l.body.gate1_token, "x-device-fingerprint": fp };
  const ch = await post("/challenge", { key_id: KEY_ID, model: "muse-wonder" }, h); step("challenge", ch);
  const counter = nextCounter();
  const body = { challenge_id: ch.body.challenge_id, key_id: KEY_ID, counter,
    nfc_hmac: nfcTap(ch.body.challenge, fp, counter), qr_signature: qrSign(ch.body.qr_payload) };
  const a = await post("/authorize", body, h); step("Gate2 authorize (NFC HMAC + QR P-256)", a);
  const replay = await post("/authorize", body, h);
  console.log(`${replay.status === 401 ? "PASS" : "FAIL"} replay rejected -> ${replay.status}`);
  const q = await post("/muse/query", { prompt: "Explain Metabolic vs Jalapeño" },
    { authorization: "Bearer " + a.body.wonder_token, "x-device-fingerprint": fp }); step("muse/query", q);
  console.log(JSON.stringify(q.body, null, 2));
  let px = { status: 200 };
  if (process.env.PROXY_URL) {
    const r = await fetch(process.env.PROXY_URL + "/v1/chat/completions", { method: "POST",
      headers: { "content-type": "application/json", authorization: "Bearer " + a.body.wonder_token, "x-device-fingerprint": fp },
      body: JSON.stringify({ model: "muse-wonder", messages: [{ role: "user", content: "ping" }] }) });
    px = { status: r.status }; step("Go proxy forward (verified wonder token)", px);
    const bad = await fetch(process.env.PROXY_URL + "/v1/chat/completions", { method: "POST",
      headers: { authorization: "Bearer " + l.body.gate1_token, "x-device-fingerprint": fp } });
    console.log(`${bad.status === 401 ? "PASS" : "FAIL"} proxy rejects Gate1-only token -> ${bad.status}`);
    if (bad.status !== 401) px.status = 500;
  }
  const au = await (await fetch(api + "/audit?limit=5")).json();
  console.log(`${au.chain_valid ? "PASS" : "FAIL"} audit chain valid (${au.entries.length} recent entries)`);
  if (l.status !== 200 || a.status !== 200 || q.status !== 200 || replay.status !== 401 || !au.chain_valid || px.status !== 200) process.exit(1);
}

module.exports = { nfcTap, qrSign, nextCounter };
if (require.main === module) e2e(process.argv[2] || "http://localhost:8000").catch((e) => { console.error(e); process.exit(1); });
