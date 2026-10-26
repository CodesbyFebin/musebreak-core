"""Unit tests for the open-source Meta stack adapter (no network, no GPU)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import open_source as oss


def setup_function(_):
    for k in list(os.environ):
        if k.startswith(("USE_OPEN", "LLAMA_STACK", "META_MODEL", "GUARD_LLM", "OPEN_SOURCE",
                         "INFERENCE_MODEL", "SAFETY_MODEL", "VISION_MODEL")):
            os.environ.pop(k, None)


def test_mapping_verified_hf_ids():
    mid, label = oss.resolve_model_id("muse-wonderful")
    assert mid == "meta-llama/Llama-3.3-70B-Instruct"
    assert "open" in label.lower()
    mid, _ = oss.resolve_model_id("guard")
    assert mid == "meta-llama/Llama-Guard-3-8B"


def test_ollama_style():
    os.environ["OPEN_SOURCE_MODEL_STYLE"] = "ollama"
    mid, _ = oss.resolve_model_id("muse-wonderful")
    assert mid == "llama3.3:70b"


def test_apply_sets_urls_when_flagged():
    os.environ["USE_OPEN_SOURCE_ONLY"] = "true"
    os.environ["LLAMA_STACK_URL"] = "http://llama-stack:8321"
    cfg = oss.apply_open_source_env()
    assert cfg["use_open_source_only"] == "true"
    assert os.environ["META_MODEL_API_URL"].endswith("/v1/chat/completions")
    assert os.environ["GUARD_LLM_URL"].endswith("/v1")
    assert "Llama-Guard" in os.environ["GUARD_LLM_MODEL"] or "guard" in os.environ["GUARD_LLM_MODEL"]


def test_apply_noop_without_flag():
    cfg = oss.apply_open_source_env()
    assert cfg["use_open_source_only"] == "false"
    assert "META_MODEL_API_URL" not in os.environ or os.environ.get("META_MODEL_API_URL") == ""


def test_payload_strips_internal_keys():
    payload = oss.build_chat_payload("muse-wonder", "hello", 16)
    clean, meta = oss.strip_internal_keys(payload)
    assert "_musebreak_open_label" not in clean
    assert meta["open_model_id"] == "meta-llama/Llama-3.3-70B-Instruct"
    assert clean["messages"][0]["role"] == "system"
