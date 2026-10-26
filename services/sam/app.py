"""Minimal health + info stub. Downloads HF weights only when /load is called.
Does NOT claim the model has been run at image build time.
"""
import os
from fastapi import FastAPI, HTTPException

app = FastAPI(title=os.getenv("HF_MODEL_ID", "hf-helper"))
MODEL_ID = os.getenv("HF_MODEL_ID", "")
_loaded = None


@app.get("/health")
def health():
    return {"ok": True, "model_id": MODEL_ID, "loaded": _loaded is not None,
            "note": "Placeholder service — call POST /load on a GPU/CPU host with HF access. "
                    "This image does not bundle weights."}


@app.post("/load")
def load():
    global _loaded
    if not MODEL_ID:
        raise HTTPException(400, "HF_MODEL_ID unset")
    # Lazy import so `docker compose config` / import checks stay light
    try:
        from transformers import AutoModel  # noqa: F401
    except ImportError as e:
        raise HTTPException(500, f"transformers not available: {e}")
    # We intentionally do NOT auto-download at startup — weights are huge.
    # Operators with HF_TOKEN + disk/GPU should replace this with real load code.
    _loaded = {"model_id": MODEL_ID, "status": "declared_only",
               "hint": f"pip/transformers can load `{MODEL_ID}`; wire your inference here."}
    return _loaded


@app.get("/")
def root():
    return health()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8091")))
