/*
 * MetaKey auth core (STM32 + NXP SE050). Computes the Gate-2 NFC response:
 *   HMAC-SHA256(secret, "MUSEBREAK-NFC|" || challenge[32] || "|" || fp_hash_hex[64] || "|" || key_id || "|" || counter)
 * and increments a NON-VOLATILE monotonic counter BEFORE releasing the MAC (fixes the reference's
 * uint16 RAM counter, which reset on power loss and wrapped at 65535 — both enable replay).
 *
 * Target build: secret never leaves the SE050; mac is computed with the NXP Plug&Trust MW
 * (sss_mac_one_go on a HMAC key object) and the counter is an SE050 monotonic counter object.
 * Host build (-DHOST_SIM): OpenSSL + a file-backed counter, for cross-checking against the gateway.
 *   gcc -DHOST_SIM metakey_auth.c -lcrypto -o metakey_auth && ./metakey_auth <challenge_hex> <fp_hash_hex> <key_id>
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define CHALLENGE_LEN 32
#define FP_HEX_LEN 64

#ifdef HOST_SIM
#include <openssl/hmac.h>
#include <stdlib.h>
static const uint8_t DEMO_SECRET[32] = "musebreak-demo-device-secret-001"; /* DEMO ONLY */
static int nv_counter_increment(uint32_t *out) {
    FILE *f = fopen(".metakey_counter", "r+");
    uint32_t c = 0;
    if (!f) f = fopen(".metakey_counter", "w+");
    if (!f) return -1;
    if (fscanf(f, "%u", &c) != 1) c = 0;
    if (c == UINT32_MAX) { fclose(f); return -1; } /* exhausted: key must be re-enrolled, never wrap */
    c++;
    rewind(f); fprintf(f, "%u\n", c); fflush(f); fclose(f);
    *out = c; return 0;
}
static int se_hmac(const uint8_t *msg, size_t n, uint8_t mac[32]) {
    unsigned int len = 32;
    return HMAC(EVP_sha256(), DEMO_SECRET, 32, msg, n, mac, &len) ? 0 : -1;
}
#else
/* Implemented in the SE050 port (Plug&Trust MW, I2C T=1 at addr 0x48) — see hardware/WIRING.md */
int nv_counter_increment(uint32_t *out); /* SE050 counter object: sss_se05x_... increment + read */
int se_hmac(const uint8_t *msg, size_t n, uint8_t mac[32]); /* sss_mac_one_go(kAlgorithm_SSS_HMAC_SHA256) */
#endif

/* Returns 0 on success. counter_out receives the value that MUST be sent to /authorize. */
int metakey_nfc_response(const uint8_t challenge[CHALLENGE_LEN], const char fp_hash_hex[FP_HEX_LEN],
                         const char *key_id, uint8_t mac_out[32], uint32_t *counter_out) {
    uint8_t msg[256];
    size_t kid = strlen(key_id), n = 0;
    uint32_t ctr;
    if (kid > 64) return -2;
    if (nv_counter_increment(&ctr) != 0) return -3; /* increment first: a crash can only skip, never reuse */
    memcpy(msg + n, "MUSEBREAK-NFC|", 14); n += 14;
    memcpy(msg + n, challenge, CHALLENGE_LEN); n += CHALLENGE_LEN;
    msg[n++] = '|';
    memcpy(msg + n, fp_hash_hex, FP_HEX_LEN); n += FP_HEX_LEN;
    msg[n++] = '|';
    memcpy(msg + n, key_id, kid); n += kid;
    n += (size_t)snprintf((char *)msg + n, sizeof(msg) - n, "|%u", ctr);
    if (se_hmac(msg, n, mac_out) != 0) return -4;
    *counter_out = ctr;
    return 0;
}

#ifdef HOST_SIM
int main(int argc, char **argv) {
    uint8_t ch[32], mac[32]; uint32_t ctr;
    if (argc != 4 || strlen(argv[1]) != 64 || strlen(argv[2]) != 64) {
        fprintf(stderr, "usage: %s <challenge_hex32B> <fp_sha256_hex> <key_id>\n", argv[0]); return 1;
    }
    for (int i = 0; i < 32; i++) sscanf(argv[1] + 2 * i, "%2hhx", &ch[i]);
    if (metakey_nfc_response(ch, argv[2], argv[3], mac, &ctr) != 0) return 2;
    printf("%u ", ctr);
    for (int i = 0; i < 32; i++) printf("%02x", mac[i]);
    printf("\n");
    return 0;
}
#endif
