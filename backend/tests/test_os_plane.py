"""Business OS plane tests — router classification, Jev gate, heartbeat."""
from __future__ import annotations
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.pop("REDIS_URL", None)
os.environ["AUDIT_PATH"] = os.path.join(tempfile.mkdtemp(), "audit.jsonl")
os.environ["ZKVM_HEARTBEAT_INTERVAL_S"] = "60"
os.environ.setdefault("USE_OPEN_SOURCE_ONLY", "true")
# Ensure no API URLs so large/medium are UNAVAILABLE by default
os.environ.pop("MUSEBREAK_MEDIUM_API_URL", None)
os.environ.pop("MUSEBREAK_LARGE_API_URL", None)

from fastapi.testclient import TestClient
from os_plane.task_router import classify_task, route_task, TaskSize, needs_jev
import main


def test_classify_small_medium_large():
    assert classify_task("hi") == TaskSize.SMALL
    assert classify_task("please implement a unit test for this function") == TaskSize.MEDIUM
    assert classify_task("write a full security audit report and threat model for the architecture") == TaskSize.LARGE
    assert classify_task("x", force_size="large") == TaskSize.LARGE


def test_needs_jev_for_actions_and_large():
    assert needs_jev("hi", TaskSize.SMALL) is False
    assert needs_jev("run shell command please", TaskSize.SMALL) is True
    assert needs_jev("plan", TaskSize.LARGE) is True
    assert needs_jev("patch this", TaskSize.MEDIUM) is True


def test_route_small_ready_without_jev():
    d = route_task("summarize this sentence briefly")
    assert d.size == "small"
    assert d.runtime == "browser-webllm"
    assert d.webllm_model_id
    assert d.status == "ready"
    assert d.requires_api is False


def test_route_large_unavailable_without_api():
    d = route_task("architect a multi-agent wonder full system", large_api_configured=False)
    assert d.size == "large"
    assert d.status == "unavailable"
    assert d.requires_jev is True


def test_route_large_awaiting_jev_when_api_ok():
    d = route_task(
        "architect a multi-agent muse wonder system",
        large_api_configured=True,
        jev_approved=False,
    )
    assert d.size == "large"
    assert d.status == "awaiting_jev"
    d2 = route_task(
        "architect a multi-agent muse wonder system",
        large_api_configured=True,
        jev_approved=True,
    )
    assert d2.status == "ready"


def test_os_api_models_and_task_flow():
    c = TestClient(main.app)
    r = c.get("/os/models")
    assert r.status_code == 200
    body = r.json()
    assert "small" in body["tiers"]
    assert body["tiers"]["small"]["runtime"] == "browser-webllm"
    assert body["use_open_source_only"] is True

    # small task — ready immediately
    r = c.post("/os/tasks", json={"prompt": "say hello in one word"})
    assert r.status_code == 200
    task = r.json()
    assert task["status"] == "ready"
    assert task["route"]["size"] == "small"
    assert "_api_flags" not in task

    # large without API — unavailable
    r = c.post(
        "/os/tasks",
        json={"prompt": "write a full threat model and security audit report", "force_size": "large"},
    )
    assert r.status_code == 200
    big = r.json()
    assert big["status"] == "unavailable"

    # medium with client saying API configured → awaiting Jev
    r = c.post(
        "/os/tasks",
        json={
            "prompt": "implement a unit test helper",
            "force_size": "medium",
            "medium_api_configured": True,
        },
    )
    med = r.json()
    assert med["status"] == "awaiting_jev"
    # complete before Jev must fail
    r = c.post(f"/os/tasks/{med['id']}/complete", json={"text": "nope", "source": "api"})
    assert r.status_code == 403
    # Jev approve
    r = c.post(f"/os/tasks/{med['id']}/jev", json={"approver": "jev-demo"})
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    assert r.json()["jev"]["approved"] is True
    # complete
    r = c.post(
        f"/os/tasks/{med['id']}/complete",
        json={"text": "ok", "source": "api", "model_id": "codellama", "simulated": False},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"


def test_zkvm_heartbeat_status():
    c = TestClient(main.app)
    # Force a commit
    r = c.post("/os/zkvm/commit")
    assert r.status_code == 200
    st = r.json()
    assert st["implementation"] == "hash-commitment-mvp"
    assert st["is_zk"] is False
    assert st["commits"] >= 1
    assert st["last"] is not None
    assert st["last"]["statement_hash_hex"]
    r = c.get("/os/zkvm/status")
    assert r.status_code == 200
    assert r.json()["implementation"] == "hash-commitment-mvp"
