"""Benchmark harness tests — scorer determinism, role reconciliation, honesty."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cli"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from musebreak_cli.benchmark import (
    BENCH_ROLES, BenchTask, ModelEntry, TASK_SUITE,
    bench_role_assignment, model_availability, model_set,
    run_benchmark, score_answer, write_results,
)
from musebreak_cli.model_router import AGENT_ROSTER


# ── scorer ────────────────────────────────────────────────────────────────────
def test_scorer_success_requires_all_tokens():
    t = BenchTask("x", "discovery", "p", required=["22", "8080"])
    full = score_answer(t, "open ports 22 and 8080", steps=2, simulated=True)
    assert full.success is True and full.score == 1.0 and full.missing == []
    partial = score_answer(t, "only 22 here", steps=2, simulated=True)
    assert partial.success is False and partial.score == 0.5 and partial.missing == ["8080"]
    none = score_answer(t, "nothing", steps=1, simulated=False)
    assert none.success is False and none.score == 0.0


def test_scorer_is_case_insensitive_and_deterministic():
    t = BenchTask("x", "monitor", "p", required=["BLOCK"])
    a = score_answer(t, "decision: block", steps=1, simulated=True)
    b = score_answer(t, "decision: block", steps=1, simulated=True)
    assert a.success and b.success and a.score == b.score == 1.0


def test_scorer_preserves_simulated_flag():
    t = BenchTask("x", "tooling", "p", required=["nmap"])
    assert score_answer(t, "nmap", steps=1, simulated=True).simulated is True
    assert score_answer(t, "nmap", steps=1, simulated=False).simulated is False


# ── role reconciliation ─────────────────────────────────────────────────────
def test_bench_roles_map_to_existing_canonical_roles():
    rows = {r["bench_role"]: r for r in bench_role_assignment()}
    assert set(rows) == {"discovery", "exploit-writer", "monitor", "tooling"}
    for r in rows.values():
        assert r["canonical_exists"], f"{r['bench_role']} → {r['canonical_role']} not in roster"
        assert r["canonical_role"] in AGENT_ROSTER


def test_role_weighting_matches_operator_request():
    # Muse Wonder Full = discovery lead, carries the most weight
    assert BENCH_ROLES["discovery"]["muse_model"] == "muse-wonder"
    assert BENCH_ROLES["discovery"]["weight"] == max(r["weight"] for r in BENCH_ROLES.values())
    # Spark = exploit-writer, Llama = monitor, Code = tooling
    assert BENCH_ROLES["exploit-writer"]["muse_model"] == "muse-spark-1.1"
    assert BENCH_ROLES["monitor"]["muse_model"] == "glimmer"
    assert BENCH_ROLES["tooling"]["muse_model"] == "muse-code"


# ── availability honesty ─────────────────────────────────────────────────────
def test_mock_mode_marks_everything_unavailable_and_simulated():
    for e in model_set():
        status, reason = model_availability(e, mock=True)
        assert status == "unavailable" and "simulated" in reason.lower()


def test_api_available_only_when_endpoint_configured(monkeypatch):
    e = ModelEntry("muse-wonder", "Llama-3.3-70B-Instruct", "api", "discovery")
    monkeypatch.delenv("META_MODEL_API_URL", raising=False)
    monkeypatch.delenv("LLAMA_STACK_URL", raising=False)
    assert model_availability(e, mock=False)[0] == "unavailable"
    monkeypatch.setenv("META_MODEL_API_URL", "http://localhost:9999/v1/chat/completions")
    assert model_availability(e, mock=False)[0] == "available"


def test_webllm_backend_unavailable_in_cli():
    e = ModelEntry("muse-spark", "Llama-3.2-1B", "browser-webllm", "discovery")
    status, reason = model_availability(e, mock=False)
    assert status == "unavailable" and "browser" in reason.lower()


# ── end-to-end run ────────────────────────────────────────────────────────────
def test_run_benchmark_simulated_and_no_fake_available():
    res = run_benchmark(mock=True)
    assert res["simulated"] is True
    assert res["task_count"] == len(TASK_SUITE)
    assert res["model_count"] == len(model_set())
    for m in res["results"]:
        # Nothing may claim 'available' in mock mode.
        assert m["status"] == "unavailable" and m["simulated"] is True
        assert 0.0 <= m["composite"] <= 1.0
        assert len(m["tasks"]) == len(TASK_SUITE)


def test_monitor_task_blocks_offensive_intent():
    res = run_benchmark(mock=True)
    for m in res["results"]:
        mon = [t for t in m["tasks"] if t["task_id"] == "mon-01"][0]
        # guard must have blocked and the scorer counts the block as success
        assert mon["success"] is True


def test_write_results_roundtrip():
    res = run_benchmark(mock=True)
    path = os.path.join(tempfile.mkdtemp(), "b.json")
    write_results(res, path)
    import json
    loaded = json.load(open(path))
    assert loaded["harness"] == "musebreak-benchmark"
