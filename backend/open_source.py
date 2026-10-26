"""Open-source Meta stack adapter for MuseBreak.

When USE_OPEN_SOURCE_ONLY=true, /muse/query and the guard target a Llama Stack /
OGX OpenAI-compatible endpoint (LLAMA_STACK_URL) instead of any closed API.

Model ids below are **open-weight Hugging Face repos** (verified). We do NOT
assert a proprietary Meta Muse endpoint; proprietary Muse names are mapped to
these open equivalents and clearly labeled in responses.
"""
from __future__ import annotations

import os
from typing import Any

# Proprietary / product label → open HF id (source of truth for offline judges)
OPEN_MODEL_MAP: dict[str, dict[str, str]] = {
    "muse-wonderful": {
        "hf": "meta-llama/Llama-3.3-70B-Instruct",
        "ollama": "llama3.3:70b",
        "label": "Muse Wonderful ≡ Llama-3.3-70B-Instruct (open)",
    },
    "muse-wonder": {
        "hf": "meta-llama/Llama-3.3-70B-Instruct",
        "ollama": "llama3.3:70b",
        "label": "Muse Wonder ≡ Llama-3.3-70B-Instruct (open)",
    },
    "muse-code": {
        "hf": "meta-llama/CodeLlama-13b-Instruct-hf",
        "ollama": "codellama:13b-instruct",
        "label": "Muse Code ≡ CodeLlama-13b-Instruct (open)",
    },
    "muse-spark-1.1": {
        "hf": "meta-llama/Llama-3.1-8B-Instruct",
        "ollama": "llama3.1:8b",
        "label": "Muse Spark ≡ Llama-3.1-8B-Instruct (open)",
    },
    "glimmer": {
        "hf": "meta-llama/Llama-3.1-8B-Instruct",
        "ollama": "llama3.1:8b",
        "label": "Glimmer ≡ Llama-3.1-8B-Instruct (open)",
    },
    "red-defensive-research": {
        "hf": "meta-llama/Llama-3.3-70B-Instruct",
        "ollama": "llama3.3:70b",
        "label": "red-defensive ≡ Llama-3.3-70B-Instruct (open, defensive only)",
    },
    "guard": {
        "hf": "meta-llama/Llama-Guard-3-8B",
        "ollama": "llama-guard3:8b",
        "label": "guard ≡ Llama-Guard-3-8B (open)",
    },
    "vision": {
        "hf": "meta-llama/Llama-3.2-11B-Vision-Instruct",
        "ollama": "llama3.2-vision",
        "label": "vision ≡ Llama-3.2-11B-Vision-Instruct (open)",
    },
}

DEFAULT_INFERENCE = os.getenv("INFERENCE_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
DEFAULT_SAFETY = os.getenv("SAFETY_MODEL", "meta-llama/Llama-Guard-3-8B")
DEFAULT_VISION = os.getenv("VISION_MODEL", "meta-llama/Llama-3.2-11B-Vision-Instruct")


def use_open_source_only() -> bool:
    return os.getenv("USE_OPEN_SOURCE_ONLY", "").strip().lower() in ("1", "true", "yes", "on")


def llama_stack_base() -> str:
    """Base URL of Llama Stack / OGX (no trailing slash). Default http://localhost:8321."""
    return (os.getenv("LLAMA_STACK_URL") or "http://localhost:8321").rstrip("/")


def openai_compat_base() -> str:
    """OpenAI-compatible API root (…/v1). Prefer LLAMA_STACK_OPENAI_BASE if set.

    Current OGX/Llama Stack exposes POST /v1/chat/completions.
    Older builds used /v1/openai/v1/chat/completions — override via env if needed.
    """
    override = os.getenv("LLAMA_STACK_OPENAI_BASE", "").rstrip("/")
    if override:
        return override
    return llama_stack_base() + "/v1"


def chat_completions_url() -> str:
    return openai_compat_base() + "/chat/completions"


def resolve_model_id(muse_model: str) -> tuple[str, str]:
    """Return (provider_model_id, human_label) for a Muse / gateway model name."""
    prefer_ollama = os.getenv("OPEN_SOURCE_MODEL_STYLE", "hf").strip().lower() == "ollama"
    info = OPEN_MODEL_MAP.get(muse_model)
    if info:
        mid = info["ollama"] if prefer_ollama else info["hf"]
        return mid, info["label"]
    # Fall back to configured inference model
    return DEFAULT_INFERENCE, f"{muse_model} → {DEFAULT_INFERENCE} (open fallback)"


def apply_open_source_env() -> dict[str, str]:
    """When USE_OPEN_SOURCE_ONLY, fill META_MODEL_API_* and GUARD_LLM_* if unset.

    Safe to call at process start; does not override explicit user env.
    Returns the effective settings (for /health).
    """
    out: dict[str, str] = {
        "use_open_source_only": str(use_open_source_only()).lower(),
        "llama_stack_url": llama_stack_base() if use_open_source_only() else "",
        "inference_model": DEFAULT_INFERENCE,
        "safety_model": DEFAULT_SAFETY,
        "vision_model": DEFAULT_VISION,
    }
    if not use_open_source_only():
        return out

    chat = chat_completions_url()
    if not os.getenv("META_MODEL_API_URL"):
        os.environ["META_MODEL_API_URL"] = chat
    if not os.getenv("META_MODEL_API_KEY"):
        os.environ["META_MODEL_API_KEY"] = os.getenv("LLAMA_STACK_API_KEY", "none")
    if not os.getenv("GUARD_LLM_URL"):
        os.environ["GUARD_LLM_URL"] = openai_compat_base()
    if not os.getenv("GUARD_LLM_MODEL"):
        style = os.getenv("OPEN_SOURCE_MODEL_STYLE", "hf").strip().lower()
        os.environ["GUARD_LLM_MODEL"] = (
            OPEN_MODEL_MAP["guard"]["ollama"] if style == "ollama" else DEFAULT_SAFETY
        )
    out["meta_model_api_url"] = os.environ["META_MODEL_API_URL"]
    out["guard_llm_url"] = os.environ["GUARD_LLM_URL"]
    out["guard_llm_model"] = os.environ["GUARD_LLM_MODEL"]
    return out


def build_chat_payload(muse_model: str, prompt: str, max_tokens: int) -> dict[str, Any]:
    model_id, label = resolve_model_id(muse_model)
    return {
        "model": model_id,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are the open-weight stand-in for '{muse_model}' ({label}). "
                    "Defensive / authorized-lab use only. Do not generate exploits or attack tooling."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        # Echoed by gateway for auditors — not an OpenAI field; stripped before POST if needed
        "_musebreak_open_label": label,
        "_musebreak_hf_or_ollama_id": model_id,
    }


def strip_internal_keys(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    meta = {
        "open_label": payload.pop("_musebreak_open_label", ""),
        "open_model_id": payload.pop("_musebreak_hf_or_ollama_id", ""),
    }
    return payload, meta
