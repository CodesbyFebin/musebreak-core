"""Mock OpenAI-compatible model server (stands in for vLLM / Meta Model API during load tests).
Run: uvicorn mock_upstream:app --port 9000"""
import asyncio, os, time
from fastapi import FastAPI, Request

app = FastAPI()
DELAY = float(os.getenv("MOCK_DELAY_MS", "20")) / 1000


@app.post("/v1/chat/completions")
async def chat(req: Request):
    body = await req.json()
    await asyncio.sleep(DELAY)
    return {"id": "mock", "object": "chat.completion", "created": int(time.time()),
            "model": req.headers.get("x-musebreak-model", body.get("model")),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "[MOCK UPSTREAM] ok"},
                         "finish_reason": "stop"}]}
