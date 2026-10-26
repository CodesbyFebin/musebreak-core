"""Voice agent scaffold — SeamlessM4T Malayalam stub."""
from __future__ import annotations
from typing import Any


class VoiceAgent:
    role = "voice"
    scaffold = True

    def __init__(self, mock: bool = True, lang: str = "ml"):
        self.mock = mock
        self.lang = lang

    def run(self, context: dict | None = None) -> dict[str, Any]:
        context = context or {}
        text = context.get("text", "MuseBreak Trust Plane ready.")
        return {
            "agent": self.role,
            "scaffold": True,
            "simulated": True,
            "lang": self.lang,
            "text": text,
            "audio": None,
            "note": "SeamlessM4T not loaded — voice stub only. Install vision-extras profile for real TTS/ASR.",
        }
