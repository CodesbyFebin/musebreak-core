// MuseBreak Go reverse proxy — hot path in front of the model server (vLLM / Meta Model API).
// Every request must carry a *cryptographically verified* Wonder token (HS256, shared JWT_SECRET with the
// FastAPI gateway) with typ=wonder, gate1=gate2=true, unexpired, and bound to the caller's device
// fingerprint. No prefix checks, no bypass. Stdlib only.
package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"
	"time"
)

type Claims struct {
	Sub   string  `json:"sub"`
	Typ   string  `json:"typ"`
	FP    string  `json:"fp"`
	Gate1 bool    `json:"gate1"`
	Gate2 bool    `json:"gate2"`
	Model string  `json:"model"`
	Tier  string  `json:"tier"`
	KeyID string  `json:"key_id"`
	Exp   float64 `json:"exp"`
	Iat   float64 `json:"iat"`
}

var b64 = base64.RawURLEncoding

// VerifyWonder validates an HS256 JWT and the MuseBreak policy claims.
func VerifyWonder(token string, secret []byte, fingerprint string, now time.Time) (*Claims, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, errors.New("malformed token")
	}
	hb, err := b64.DecodeString(parts[0])
	if err != nil {
		return nil, errors.New("bad header")
	}
	var hdr struct{ Alg, Typ string }
	if json.Unmarshal(hb, &hdr) != nil || hdr.Alg != "HS256" { // reject alg=none / alg confusion
		return nil, errors.New("unsupported alg")
	}
	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(parts[0] + "." + parts[1]))
	sig, err := b64.DecodeString(parts[2])
	if err != nil || !hmac.Equal(sig, mac.Sum(nil)) {
		return nil, errors.New("bad signature")
	}
	pb, err := b64.DecodeString(parts[1])
	if err != nil {
		return nil, errors.New("bad payload")
	}
	var c Claims
	if json.Unmarshal(pb, &c) != nil {
		return nil, errors.New("bad claims")
	}
	if c.Typ != "wonder" || !c.Gate1 || !c.Gate2 {
		return nil, errors.New("both gates required")
	}
	if float64(now.Unix()) >= c.Exp {
		return nil, errors.New("token expired")
	}
	fh := sha256.Sum256([]byte(fingerprint))
	if fingerprint == "" || !hmac.Equal([]byte(hex.EncodeToString(fh[:])), []byte(c.FP)) {
		return nil, errors.New("device fingerprint mismatch")
	}
	return &c, nil
}

func deny(w http.ResponseWriter, code int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

func NewHandler(secret []byte, upstream *url.URL, upstreamKey string) http.Handler {
	rp := httputil.NewSingleHostReverseProxy(upstream)
	orig := rp.Director
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) { w.Write([]byte("ok")) })
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		auth := r.Header.Get("Authorization")
		if !strings.HasPrefix(auth, "Bearer ") {
			deny(w, http.StatusUnauthorized, "missing wonder token")
			return
		}
		c, err := VerifyWonder(auth[7:], secret, r.Header.Get("X-Device-Fingerprint"), time.Now())
		if err != nil {
			log.Printf("DENY %s %s: %v", r.Method, r.URL.Path, err)
			deny(w, http.StatusUnauthorized, err.Error())
			return
		}
		r2 := r.Clone(r.Context())
		rp.Director = func(req *http.Request) {
			orig(req)
			req.Header.Del("Authorization") // never leak the wonder token upstream
			if upstreamKey != "" {
				req.Header.Set("Authorization", "Bearer "+upstreamKey)
			}
			req.Header.Set("X-MuseBreak-Sub", c.Sub)
			req.Header.Set("X-MuseBreak-Model", c.Model)
			req.Header.Set("X-MuseBreak-Tier", c.Tier)
			req.Header.Set("X-MuseBreak-Key", c.KeyID)
		}
		rp.ServeHTTP(w, r2)
	})
	return mux
}

func main() {
	secret := os.Getenv("JWT_SECRET")
	if len(secret) < 32 {
		log.Fatal("JWT_SECRET must be set (>=32 chars) and identical to the gateway's")
	}
	up, err := url.Parse(getenv("UPSTREAM_URL", "http://localhost:9000"))
	if err != nil {
		log.Fatal(err)
	}
	addr := getenv("LISTEN", ":8443")
	log.Printf("MuseBreak proxy %s -> %s", addr, up)
	srv := &http.Server{Addr: addr, Handler: NewHandler([]byte(secret), up, os.Getenv("UPSTREAM_API_KEY")),
		ReadHeaderTimeout: 5 * time.Second}
	if cert, key := os.Getenv("TLS_CERT"), os.Getenv("TLS_KEY"); cert != "" {
		log.Fatal(srv.ListenAndServeTLS(cert, key))
	}
	log.Fatal(srv.ListenAndServe())
}

func getenv(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}
