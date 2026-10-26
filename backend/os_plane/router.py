"""Business OS API — task queue, open routing, Jev gate, zkVM heartbeat status."""
from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .task_router import (
    MODEL_TIERS,
    OS_AGENT_ROSTER,
    classify_task,
    route_task,
)
from .heartbeat import ZkvmHeartbeat

router = APIRouter(prefix="/os", tags=["business-os"])

_tasks: dict[str, dict[str, Any]] = {}
_tasks_lock = threading.Lock()
_heartbeat: ZkvmHeartbeat | None = None
_audit_ref = None


def bind_audit(audit) -> ZkvmHeartbeat:
    """Called from main.py once at import to wire the shared AuditLog."""
    global _heartbeat, _audit_ref
    _audit_ref = audit
    interval = float(os.getenv("ZKVM_HEARTBEAT_INTERVAL_S", "15"))
    _heartbeat = ZkvmHeartbeat(audit, interval_s=interval)
    if os.getenv("ZKVM_HEARTBEAT_DISABLE", "").lower() not in ("1", "true", "yes"):
        _heartbeat.start()
    return _heartbeat


def _api_configured(env_key: str) -> bool:
    v = os.getenv(env_key, "").strip()
    # Also accept localStorage-style mirror via MUSEBREAK_*_API_URL
    return bool(v)


class TaskCreate(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    force_size: str | None = None
    medium_api_configured: bool = False  # frontend reports localStorage key presence
    large_api_configured: bool = False


class JevApprove(BaseModel):
    approver: str = Field(..., min_length=1, max_length=64)
    note: str = ""


@router.get("/models")
def list_models():
    return {
        "tiers": MODEL_TIERS,
        "agents": OS_AGENT_ROSTER,
        "use_open_source_only": os.getenv("USE_OPEN_SOURCE_ONLY", "true").lower() == "true",
        "medium_api_configured": _api_configured("MUSEBREAK_MEDIUM_API_URL"),
        "large_api_configured": _api_configured("MUSEBREAK_LARGE_API_URL"),
        "note": "Small tier = real in-browser WebLLM. Medium/Large need API URLs or are UNAVAILABLE.",
    }


@router.post("/route")
def preview_route(req: TaskCreate):
    decision = route_task(
        req.prompt,
        force_size=req.force_size,
        medium_api_configured=req.medium_api_configured or _api_configured("MUSEBREAK_MEDIUM_API_URL"),
        large_api_configured=req.large_api_configured or _api_configured("MUSEBREAK_LARGE_API_URL"),
        jev_approved=False,
    )
    return decision.to_dict()



def _public_task(t: dict) -> dict:
    out = {k: v for k, v in t.items() if not k.startswith("_")}
    return out

@router.post("/tasks")
def create_task(req: TaskCreate):
    med = req.medium_api_configured or _api_configured("MUSEBREAK_MEDIUM_API_URL")
    large = req.large_api_configured or _api_configured("MUSEBREAK_LARGE_API_URL")
    decision = route_task(
        req.prompt,
        force_size=req.force_size,
        medium_api_configured=med,
        large_api_configured=large,
        jev_approved=False,
    )
    tid = "task_" + uuid.uuid4().hex[:12]
    task = {
        "id": tid,
        "prompt": req.prompt,
        "created_at": time.time(),
        "route": decision.to_dict(),
        "jev": {
            "required": decision.requires_jev,
            "approved": False,
            "approver": None,
            "approved_at": None,
            "note": "",
        },
        "result": None,
        "status": decision.status,  # ready | awaiting_jev | unavailable
        "_api_flags": {"medium": med, "large": large},
    }
    with _tasks_lock:
        _tasks[tid] = task
    if _audit_ref is not None:
        _audit_ref.append(
            "os.task_created",
            task_id=tid,
            size=decision.size,
            muse_label=decision.muse_label,
            agent=decision.agent.get("id"),
            status=decision.status,
        )
    return _public_task(task)


@router.get("/tasks")
def list_tasks(limit: int = 50):
    with _tasks_lock:
        items = sorted(_tasks.values(), key=lambda t: t["created_at"], reverse=True)[:limit]
    return {"tasks": [_public_task(t) for t in items], "count": len(items)}


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    with _tasks_lock:
        t = _tasks.get(task_id)
    if not t:
        raise HTTPException(404, "task not found")
    return _public_task(t)


@router.post("/tasks/{task_id}/jev")
def jev_approve(task_id: str, req: JevApprove):
    """Human-in-the-loop Jev gate. Default-deny until this is called."""
    with _tasks_lock:
        t = _tasks.get(task_id)
        if not t:
            raise HTTPException(404, "task not found")
        if t["status"] == "unavailable":
            raise HTTPException(400, "tier UNAVAILABLE — configure API URL first")
        flags = t.get("_api_flags", {"medium": False, "large": False})
        t["jev"] = {
            "required": True,
            "approved": True,
            "approver": req.approver.strip(),
            "approved_at": time.time(),
            "note": req.note,
        }
        decision = route_task(
            t["prompt"],
            force_size=t["route"].get("size"),
            medium_api_configured=flags.get("medium", False),
            large_api_configured=flags.get("large", False),
            jev_approved=True,
        )
        t["route"] = decision.to_dict()
        t["status"] = decision.status
        out = dict(t)
        out.pop("_api_flags", None)
    if _audit_ref is not None:
        _audit_ref.append(
            "os.jev_approved",
            task_id=task_id,
            approver=req.approver.strip(),
            status=out["status"],
        )
    return out


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: str, body: dict[str, Any]):
    """Record a completion payload from the browser (WebLLM output or API).

    The backend does NOT run inference here. Browser posts real WebLLM tokens
    for small tier; medium/large only when an API was used client-side.
    """
    with _tasks_lock:
        t = _tasks.get(task_id)
        if not t:
            raise HTTPException(404, "task not found")
        if t["status"] == "awaiting_jev":
            raise HTTPException(403, "Jev approval required before completion")
        if t["status"] == "unavailable":
            raise HTTPException(400, "cannot complete UNAVAILABLE tier")
        result = {
            "text": body.get("text", ""),
            "source": body.get("source", "unknown"),  # webllm | api | none
            "model_id": body.get("model_id"),
            "simulated": bool(body.get("simulated", False)),
            "tokens": body.get("tokens"),
            "completed_at": time.time(),
        }
        t["result"] = result
        t["status"] = "done"
        out = dict(t)
    if _audit_ref is not None:
        _audit_ref.append(
            "os.task_done",
            task_id=task_id,
            source=result["source"],
            simulated=result["simulated"],
            model_id=result.get("model_id"),
        )
    return out


@router.get("/zkvm/status")
def zkvm_status():
    if _heartbeat is None:
        return {
            "running": False,
            "implementation": "hash-commitment-mvp",
            "is_zk": False,
            "note": "heartbeat not bound — call bind_audit from main",
        }
    return _heartbeat.status()


@router.post("/zkvm/commit")
def zkvm_commit_now():
    if _heartbeat is None:
        raise HTTPException(503, "heartbeat not bound")
    return _heartbeat.commit_now()


@router.get("/classify")
def classify_endpoint(prompt: str, force_size: str | None = None):
    size = classify_task(prompt, force_size=force_size)
    return {"size": size.value, "prompt_len": len(prompt or "")}
