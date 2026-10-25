/*
 * MetaKey firmware — ESP32 + PN532 (NFC, I2C) + 2.13" e-ink (GxEPD2).
 * NFC: phone writes a 32-byte challenge + context via ISO14443-4 (card emulation APDU);
 *      key returns HMAC-SHA256(device_secret, "MUSEBREAK-NFC|"+challenge+"|"+fp_hash+"|"+key_id).
 * QR : key renders the intent (cid|nonce|model) + its P-256 signature as a QR on e-ink after
 *      the user presses the physical approve button.
 * Libraries: Adafruit_PN532, GxEPD2, QRCode (ricmoo), mbedTLS (bundled with ESP32 core).
 * Store DEVICE_SECRET / private key in eFuse / NVS encrypted storage in a real build.
 */
#include <Wire.h>
#include <Adafruit_PN532.h>
#include <GxEPD2_BW.h>
#include <qrcode.h>
#include "mbedtls/md.h"
#include "mbedtls/ecdsa.h"
#include "mbedtls/ctr_drbg.h"
#include "mbedtls/entropy.h"
#include "mbedtls/sha256.h"
#include <Preferences.h>
Preferences nvs;  // monotonic counter persisted in NVS

#define PN532_IRQ 4
#define PN532_RST 5
#define APPROVE_BTN 0
Adafruit_PN532 nfc(PN532_IRQ, PN532_RST);
GxEPD2_BW<GxEPD2_213_BN, GxEPD2_213_BN::HEIGHT> epd(GxEPD2_213_BN(15, 27, 26, 25));

static const char* KEY_ID = "metakey-demo-001";
// DEMO ONLY ("musebreak-demo-device-secret-001")
static const uint8_t DEVICE_SECRET[32] = {
  0x6d,0x75,0x73,0x65,0x62,0x72,0x65,0x61,0x6b,0x2d,0x64,0x65,0x6d,0x6f,0x2d,0x64,
  0x65,0x76,0x69,0x63,0x65,0x2d,0x73,0x65,0x63,0x72,0x65,0x74,0x2d,0x30,0x30,0x31};
// DEMO ONLY P-256 private scalar (matches hardware/demo_metakey_private.pem)
static const char* PRIV_D_HEX = "351aec7cb7d1cb4b04289d2fab98563a413332259bcaf69ed29837d404f3cd0f";

uint32_t nextCounter() { uint32_t c = nvs.getUInt("ctr", 0) + 1; nvs.putUInt("ctr", c); return c; }

void hmacNfc(const uint8_t* chal, const char* fpHash, uint32_t counter, uint8_t out[32]) {
  mbedtls_md_context_t ctx; mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 1);
  mbedtls_md_hmac_starts(&ctx, DEVICE_SECRET, 32);
  mbedtls_md_hmac_update(&ctx, (const uint8_t*)"MUSEBREAK-NFC|", 14);
  mbedtls_md_hmac_update(&ctx, chal, 32);
  mbedtls_md_hmac_update(&ctx, (const uint8_t*)"|", 1);
  mbedtls_md_hmac_update(&ctx, (const uint8_t*)fpHash, 64);
  mbedtls_md_hmac_update(&ctx, (const uint8_t*)"|", 1);
  mbedtls_md_hmac_update(&ctx, (const uint8_t*)KEY_ID, strlen(KEY_ID));
  char ctr[12]; int n = snprintf(ctr, sizeof(ctr), "|%lu", (unsigned long)counter);
  mbedtls_md_hmac_update(&ctx, (const uint8_t*)ctr, n);
  mbedtls_md_hmac_finish(&ctx, out); mbedtls_md_free(&ctx);
}

bool signIntent(const String& intent, uint8_t sig[64]) {
  mbedtls_ecdsa_context ec; mbedtls_entropy_context ent; mbedtls_ctr_drbg_context drbg;
  mbedtls_ecdsa_init(&ec); mbedtls_entropy_init(&ent); mbedtls_ctr_drbg_init(&drbg);
  mbedtls_ctr_drbg_seed(&drbg, mbedtls_entropy_func, &ent, nullptr, 0);
  mbedtls_ecp_group_load(&ec.grp, MBEDTLS_ECP_DP_SECP256R1);
  mbedtls_mpi_read_string(&ec.d, 16, PRIV_D_HEX);
  uint8_t h[32]; mbedtls_sha256((const uint8_t*)intent.c_str(), intent.length(), h, 0);
  mbedtls_mpi r, s; mbedtls_mpi_init(&r); mbedtls_mpi_init(&s);
  int rc = mbedtls_ecdsa_sign(&ec.grp, &r, &s, &ec.d, h, 32, mbedtls_ctr_drbg_random, &drbg);
  mbedtls_mpi_write_binary(&r, sig, 32); mbedtls_mpi_write_binary(&s, sig + 32, 32);  // raw r||s
  mbedtls_mpi_free(&r); mbedtls_mpi_free(&s); mbedtls_ecdsa_free(&ec);
  return rc == 0;
}

String hex(const uint8_t* b, size_t n) { String s; char t[3]; for (size_t i=0;i<n;i++){sprintf(t,"%02x",b[i]); s+=t;} return s; }

void showQR(const String& payload) {
  QRCode qr; uint8_t buf[qrcode_getBufferSize(10)];
  qrcode_initText(&qr, buf, 10, ECC_LOW, payload.c_str());
  epd.setFullWindow(); epd.firstPage();
  do { epd.fillScreen(GxEPD_WHITE);
    for (uint8_t y=0;y<qr.size;y++) for (uint8_t x=0;x<qr.size;x++)
      if (qrcode_getModule(&qr,x,y)) epd.fillRect(10+x*2, 10+y*2, 2, 2, GxEPD_BLACK);
  } while (epd.nextPage());
}

void setup() {
  Serial.begin(115200); pinMode(APPROVE_BTN, INPUT_PULLUP);
  nvs.begin("metakey", false); nfc.begin(); nfc.SAMConfig(); epd.init(115200);
  Serial.println("MetaKey ready");
}

void loop() {
  // APDU from phone: [32B challenge][64B fp_hash ascii][cid 32 ascii][nonce 32 ascii][model...]
  uint8_t apdu[255]; uint8_t len = sizeof(apdu);
  if (!nfc.inListPassiveTarget()) { delay(50); return; }
  if (!nfc.inDataExchange((uint8_t*)"\x00\xA4\x04\x00", 4, apdu, &len) || len < 160) return;
  uint8_t mac[32]; char fp[65]; memcpy(fp, apdu + 32, 64); fp[64] = 0;
  uint32_t ctr = nextCounter();
  hmacNfc(apdu, fp, ctr, mac);
  uint8_t resp[36]; memcpy(resp, mac, 32); resp[32]=ctr>>24; resp[33]=ctr>>16; resp[34]=ctr>>8; resp[35]=ctr;
  nfc.inDataExchange(resp, 36, apdu, &len);  // return HMAC + counter over NFC
  String cid((char*)apdu + 96, 32), nonce((char*)apdu + 128, 32), model((char*)apdu + 160, len - 160);
  String intent = "MUSEBREAK-INTENT|" + cid + "|" + nonce + "|" + model;
  while (digitalRead(APPROVE_BTN) == HIGH) delay(10);  // human presence / intent
  uint8_t sig[64]; if (signIntent(intent, sig)) showQR("{\"cid\":\"" + cid + "\",\"sig\":\"" + hex(sig, 64) + "\"}");
}
