"""Business OS plane: task routing, Jev approval gate, zkVM heartbeat.

Open routing maps Muse Spark / Wonder / Code to open Llama models.
Local WebLLM (small tier) runs in the browser; medium/large require a
configured API and are UNAVAILABLE when unset — never faked.
"""
from .task_router import classify_task, TaskSize, MODEL_TIERS, route_task
from .heartbeat import ZkvmHeartbeat

__all__ = [
    "classify_task",
    "TaskSize",
    "MODEL_TIERS",
    "route_task",
    "ZkvmHeartbeat",
]
