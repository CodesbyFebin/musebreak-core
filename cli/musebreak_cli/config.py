"""CLI configuration and persistent state under ~/.musebreak/."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict


STATE_DIR = os.path.expanduser("~/.musebreak")
DEFAULT_TOKEN = os.path.join(STATE_DIR, "token")
DEFAULT_AUDIT = os.path.join(STATE_DIR, "audit.jsonl")
DEFAULT_AGENTS = os.path.join(STATE_DIR, "agents.json")


@dataclass
class Config:
    gateway: str = os.getenv("MUSEBREAK_GATEWAY", "http://localhost:8000")
    proxy: str = os.getenv("MUSEBREAK_PROXY", "http://localhost:8443")
    token_file: str = os.getenv("MUSEBREAK_TOKEN_FILE", DEFAULT_TOKEN)
    # legacy session.json still accepted as a fallback path
    session_file: str = os.path.expanduser("~/.musebreak/session.json")
    key_file: str = os.getenv("METAKEY_FILE", os.path.expanduser("~/.musebreak/dev_key.json"))
    audit_file: str = os.getenv("MUSEBREAK_AUDIT", DEFAULT_AUDIT)
    agents_file: str = DEFAULT_AGENTS
    # When True (default), models + Kali cage are mocked so the CLI runs offline.
    mock: bool = os.getenv("MUSEBREAK_MOCK", "1") == "1"
    kali_image: str = os.getenv("FC_ROOTFS", os.getenv("MUSEBREAK_KALI_IMAGE", ""))

    def ensure_state(self) -> None:
        os.makedirs(STATE_DIR, exist_ok=True)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["token_present"] = os.path.exists(self.token_file)
        return d


CONFIG = Config()


def save_token(payload: dict) -> str:
    """Persist a MUSE_ROUTING_KEY_… Wonder token under ~/.musebreak/token."""
    CONFIG.ensure_state()
    with open(CONFIG.token_file, "w") as f:
        json.dump(payload, f, indent=2)
    os.chmod(CONFIG.token_file, 0o600)
    return CONFIG.token_file


def load_token() -> dict | None:
    path = CONFIG.token_file
    if not os.path.exists(path) and os.path.exists(CONFIG.session_file):
        path = CONFIG.session_file
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)
