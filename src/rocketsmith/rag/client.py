from __future__ import annotations

from pathlib import Path

import chromadb

_CHROMA_PATH = Path.home() / ".local" / "share" / "rocketsmith" / "chroma"

_client: chromadb.PersistentClient | None = None


def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(_CHROMA_PATH))
    return _client
