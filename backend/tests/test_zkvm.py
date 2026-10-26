"""Trust Plane hash-commitment MVP tests — only claims we can actually verify."""
from __future__ import annotations
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.pop("REDIS_URL", None)
os.environ["AUDIT_PATH"] = os.path.join(tempfile.mkdtemp(), "audit.jsonl")
os.environ.setdefault("USE_OPEN_SOURCE_ONLY", "true")

import base64
import pytest
from fastapi.testclient import TestClient

from zkvm.canonical import canonicalize, canonical_json_str
from zkvm.hash import hash_canonical, hash_chain
from zkvm.prover import ZKProver, GuardBlockedError
from zkvm.verifier import ZKVerifier
from zkvm.circuits.order_approve import OrderApproveCircuit
from zkvm.circuits.audit_chain import AuditChainCircuit
from zkvm.circuits.utr_unique import UTRUniqueCircuit
from zkvm.circuits.vuln_chain import VulnChainCircuit
from zkvm.circuits.business_isolation import BusinessIsolationCircuit
import main


def test_canonical_deterministic():
    a = {"b": 1, "a": [3, 2], "z": {"y": True, "x": None}}
    b = {"z": {"x": None, "y": True}, "a": [3, 2], "b": 1}
    assert canonicalize(a) == canonicalize(b)
    assert canonicalize(a) == canonicalize(a)
    assert canonical_json_str(a) == canonicalize(a).decode()


def test_hash_canonical_and_chain():
    h1 = hash_canonical({"n": 1})
    h2 = hash_canonical({"n": 1})
    assert h1["hex"] == h2["hex"]
    assert len(h1["bytes"]) == 32
    chained = hash_chain("0" * 64, h1["canonical_bytes"])
    assert len(chained) == 64
    assert chained != h1["hex"]


def test_prove_verify_roundtrip_true():
    items = [{"sku": "laptop-dell-1", "qty": 1, "price": 1000}]
    pub = {
        "order_id": "o1",
        "shop_id": "s1",
        "items_hash": hash_canonical(items)["hex"],
        "total": 1000,
        "prev_audit_hash": "0" * 64,
    }
    wit = {"stock_available": {"laptop-dell-1": 5}, "items": items}
    proof = ZKProver().prove("order_approve", pub, wit)
    assert proof["simulated"] is True
    assert proof["implementation"] == "hash-commitment-mvp"
    raw = base64.b64decode(proof["proof_b64"])
    assert len(raw) == 256  # encoding artifact size
    assert raw[:32].hex() == proof["statement_hash_hex"]
    res = ZKVerifier().verify(proof["proof_b64"], proof["statement_hash_hex"])
    assert res["verified"] is True
    assert res["implementation"] == "hash-commitment-mvp"


def test_tampered_statement_verify_false():
    items = [{"sku": "laptop-dell-1", "qty": 1, "price": 1000}]
    pub = {
        "order_id": "o1",
        "shop_id": "s1",
        "items_hash": hash_canonical(items)["hex"],
        "total": 1000,
        "prev_audit_hash": "0" * 64,
    }
    wit = {"stock_available": {"laptop-dell-1": 5}, "items": items}
    proof = ZKProver().prove("order_approve", pub, wit)
    bad_hash = "a" * 64
    res = ZKVerifier().verify(proof["proof_b64"], bad_hash)
    assert res["verified"] is False
    assert "mismatch" in res["reason"]


def test_guard_blocks_pii_before_prove():
    pub = {"order_id": "o1", "note": "aadhaar 1234 5678 9012"}
    wit = {"items": []}
    with pytest.raises(GuardBlockedError):
        ZKProver().prove("order_approve", pub, wit)


def test_order_approve_rejects_oversell():
    items = [{"sku": "laptop-dell-1", "qty": 99, "price": 10}]
    pub = {
        "order_id": "o1",
        "shop_id": "s1",
        "items_hash": hash_canonical(items)["hex"],
        "total": 990,
        "prev_audit_hash": "0" * 64,
    }
    wit = {"stock_available": {"laptop-dell-1": 1}, "items": items}
    r = OrderApproveCircuit.verify(pub, wit)
    assert r["valid"] is False
    assert "oversell" in r["reason"]


def test_audit_chain_intact():
    current = {"event": "x", "n": 1}
    cur_hash = hash_canonical(current)["hex"]
    pub = {"prev_hash": "0" * 64, "current_hash": cur_hash, "chain_id": "c1"}
    wit = {"prev_data": None, "current_data": current}
    r = AuditChainCircuit.verify(pub, wit)
    assert r["intact"] is True


def test_utr_unique_and_replay():
    pub = {"utr": "123456789012", "shop_id": "s1"}
    assert UTRUniqueCircuit.verify(pub, {"utr_list": []})["unique"] is True
    assert UTRUniqueCircuit.verify(pub, {"utr_list": ["123456789012"]})["unique"] is False


def test_vuln_chain_and_isolation():
    findings = [
        {"type": "idor", "cvss": 5.0},
        {"type": "auth_bypass", "cvss": 6.0},
        {"type": "info_leak", "cvss": 4.5},
    ]
    assert VulnChainCircuit.verify({"chain_id": "v1", "findings_hash": "abc"}, {"findings": findings})[
        "critical"
    ] is True
    iso = BusinessIsolationCircuit.verify(
        {"shop_a_id": "a", "shop_b_id": "b"},
        {"shop_a_data": {"pii_hashes": ["h1"]}, "shop_b_data": {"pii_hashes": ["h2"]}},
    )
    assert iso["isolated"] is True
    leak = BusinessIsolationCircuit.verify(
        {"shop_a_id": "a", "shop_b_id": "b"},
        {"shop_a_data": {"pii_hashes": ["h1"]}, "shop_b_data": {"pii_hashes": ["h1"]}},
    )
    assert leak["isolated"] is False


def test_api_prove_verify_and_orders():
    c = TestClient(main.app)
    circuits = c.get("/zkvm/circuits")
    assert circuits.status_code == 200
    assert "order_approve" in circuits.json()["circuits"]
    assert circuits.json()["implementation"] == "hash-commitment-mvp"

    items = [{"sku": "laptop-dell-1", "qty": 1, "price": 1000}]
    draft = c.post(
        "/orders/draft",
        json={"order_id": "ord-t", "shop_id": "shop-1", "items": items, "total": 1000},
    )
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert body["simulated"] is True
    proof = body["proof"]
    ver = c.post(
        "/zkvm/verify",
        json={"proof_b64": proof["proof_b64"], "statement_hash_hex": proof["statement_hash_hex"]},
    )
    assert ver.status_code == 200
    assert ver.json()["verified"] is True

    # PII blocked via API
    bad = c.post(
        "/zkvm/prove",
        json={
            "circuit": "order_approve",
            "public_inputs": {"order_id": "x", "ssn": "123-45-6789"},
            "private_witness": {"items": [], "stock_available": {}},
        },
    )
    assert bad.status_code == 400
    assert "Guard" in bad.json()["detail"] or "PII" in bad.json()["detail"]


def test_agents_orchestrator_scaffold_importable():
    from agents.orchestrator_v2 import OrchestratorV2
    out = OrchestratorV2(mock=True).run({"name": "unit"})
    assert out["simulated"] is True
    assert len(out["steps"]) == 7
