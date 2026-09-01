"""
Response Cache
==============
SHA-256 keyed cache for BISResponse objects.
Stores responses in data/cache.json with a configurable TTL (default 24 hours).

Usage:
    cache = ResponseCache()
    key = cache.make_key(intent, query)
    hit = cache.get(key)        # returns payload dict or None
    cache.set(key, payload)     # stores payload dict
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bis_cache")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_FILE = PROJECT_ROOT / "data" / "cache.json"
TTL_SECONDS = 24 * 60 * 60  # 24 hours


def _normalize(text: str) -> str:
    """Lower-case and strip punctuation for cache key stability."""
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


class ResponseCache:
    def __init__(self, cache_file: Path = CACHE_FILE, ttl: int = TTL_SECONDS) -> None:
        self._file = cache_file
        self._ttl = ttl
        self._store: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Cache file corrupted - starting fresh.")
        return {}

    def _save(self) -> None:
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(
                json.dumps(self._store, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Failed to save cache: %s", exc)

    def make_key(self, intent: str, query: str) -> str:
        normalized = f"{intent}::{_normalize(query)}"
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def get(self, key: str) -> Optional[dict]:
        """Return cached payload dict if valid and not expired, else None."""
        entry = self._store.get(key)
        if not entry:
            return None
        if time.time() - entry.get("ts", 0) > self._ttl:
            logger.info("Cache entry expired for key %s", key)
            del self._store[key]
            self._save()
            return None
        logger.info("Cache HIT for key %s", key)
        return entry.get("payload")

    def set(self, key: str, payload: dict) -> None:
        """Store a response payload dict in the cache."""
        self._store[key] = {"ts": time.time(), "payload": payload}
        self._save()
        logger.info("Cache SET for key %s", key)

    def clear(self) -> None:
        self._store = {}
        self._save()
        logger.info("Cache cleared.")

    def stats(self) -> dict:
        valid = sum(
            1 for e in self._store.values()
            if time.time() - e.get("ts", 0) <= self._ttl
        )
        return {"total": len(self._store), "valid": valid}
