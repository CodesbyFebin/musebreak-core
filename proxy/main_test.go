package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"
)

var secret = []byte("test-secret-test-secret-test-secret!!")

func mint(t *testing.T, c map[string]any, key []byte, alg string) string {
	h, _ := json.Marshal(map[string]string{"alg": alg, "typ": "JWT"})
	p, _ := json.Marshal(c)
	s := b64.EncodeToString(h) + "." + b64.EncodeToString(p)
	m := hmac.New(sha256.New, key)
	m.Write([]byte(s))
	return s + "." + b64.EncodeToString(m.Sum(nil))
}

func fp(s string) string { h := sha256.Sum256([]byte(s)); return hex.EncodeToString(h[:]) }

func good() map[string]any {
	return map[string]any{"sub": "judge", "typ": "wonder", "fp": fp("dev1"), "gate1": true, "gate2": true,
		"model": "muse-wonder", "exp": time.Now().Unix() + 60}
}

func TestVerify(t *testing.T) {
	now := time.Now()
	if _, err := VerifyWonder(mint(t, good(), secret, "HS256"), secret, "dev1", now); err != nil {
		t.Fatalf("valid token rejected: %v", err)
	}
	cases := map[string]func() (string, string){
		"wrong key": func() (string, string) {
			return mint(t, good(), []byte("other-key-other-key-other-key-xx"), "HS256"), "dev1"
		},
		"alg none":    func() (string, string) { return mint(t, good(), secret, "none"), "dev1" },
		"wrong fp":    func() (string, string) { return mint(t, good(), secret, "HS256"), "dev2" },
		"gate1 token": func() (string, string) { c := good(); c["typ"] = "gate1"; return mint(t, c, secret, "HS256"), "dev1" },
		"no gate2":    func() (string, string) { c := good(); c["gate2"] = false; return mint(t, c, secret, "HS256"), "dev1" },
		"expired": func() (string, string) {
			c := good()
			c["exp"] = now.Unix() - 1
			return mint(t, c, secret, "HS256"), "dev1"
		},
		"prefix only": func() (string, string) { return "MUSE_SESSION_TEST_VALID_OPERATOR_001", "dev1" },
	}
	for name, f := range cases {
		tok, d := f()
		if _, err := VerifyWonder(tok, secret, d, now); err == nil {
			t.Errorf("%s: accepted", name)
		}
	}
}

func TestProxyForwardsOnlyVerified(t *testing.T) {
	var gotAuth string
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		w.Write([]byte(`{"ok":true}`))
	}))
	defer up.Close()
	u, _ := url.Parse(up.URL)
	px := httptest.NewServer(NewHandler(secret, u, "upstream-key"))
	defer px.Close()
	do := func(tok, dev string) int {
		req, _ := http.NewRequest("POST", px.URL+"/v1/chat/completions", nil)
		req.Header.Set("Authorization", "Bearer "+tok)
		req.Header.Set("X-Device-Fingerprint", dev)
		r, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		return r.StatusCode
	}
	if c := do(mint(t, good(), secret, "HS256"), "dev1"); c != 200 || gotAuth != "Bearer upstream-key" {
		t.Fatalf("valid: %d auth=%q", c, gotAuth)
	}
	if c := do("garbage", "dev1"); c != 401 {
		t.Fatalf("garbage: %d", c)
	}
}
