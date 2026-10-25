import os
from dataclasses import dataclass


@dataclass
class Config:
    gateway: str = os.getenv("MUSEBREAK_GATEWAY", "http://localhost:8000")
    proxy: str = os.getenv("MUSEBREAK_PROXY", "http://localhost:8443")
    token_file: str = os.getenv("MUSEBREAK_TOKEN_FILE", os.path.expanduser("~/.musebreak/session.json"))
    key_file: str = os.getenv("METAKEY_FILE", os.path.expanduser("~/.musebreak/dev_key.json"))
    # When True (default on this box / no gateway), models and sandbox are mocked so everything runs offline.
    mock: bool = os.getenv("MUSEBREAK_MOCK", "1") == "1"


CONFIG = Config()
