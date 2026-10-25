"""Metabolic M1 simulator — a *simulation* of a custom MoE inference ASIC.
Numbers are illustrative, not real hardware specs."""
import hashlib
import random
import time

PROFILES = {
    # model: (experts_active/total, tokens_per_s, usd_per_1k_tokens)
    "muse-wonder": ("8/128 MoE, GQA, MXFP4", 420.0, 0.0060),
    "muse-wonderful": ("8/128 MoE, GQA, MXFP4, long-context", 180.0, 0.0120),
}


def infer(model: str, prompt: str, max_tokens: int = 256) -> dict:
    arch, tps, cost = PROFILES.get(model, ("dense", 900.0, 0.0010))
    seed = int(hashlib.sha256((model + prompt).encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    prompt_tokens = max(1, len(prompt) // 4)
    out_tokens = min(max_tokens, 64 + rng.randint(0, 128))
    ttft_ms = round(rng.uniform(35, 90), 1)
    decode_ms = round(out_tokens / tps * 1000, 1)
    time.sleep(min(0.05, ttft_ms / 1000))  # tiny real delay for demo feel
    return {
        "silicon": "Metabolic-M1 (simulated)",
        "architecture": arch,
        "chip_shard": f"mtb-{rng.randint(0, 4095):04x}",
        "prompt_tokens": prompt_tokens,
        "output_tokens": out_tokens,
        "ttft_ms": ttft_ms,
        "decode_ms": decode_ms,
        "est_cost_usd": round((prompt_tokens + out_tokens) / 1000 * cost, 6),
    }
