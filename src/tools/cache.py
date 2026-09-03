"""
Response Cache
==============
SHA-256 keyed cache for BIS responses with configurable TTL.
Stores responses in data/cache.json.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import CONFIG

logger = logging.getLogger("bis_cache")

DEFAULT_CACHE_FILE = Path(CONFIG.cache_path)
DEFAULT_TTL = 24 * 60 * 60  # 24 hours


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for stable cache key generation."""
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


class ResponseCache:
    """Manages persistent caching of synthesized responses."""

    def __init__(self, cache_file: Path = DEFAULT_CACHE_FILE, ttl: int = DEFAULT_TTL) -> None:
        self._file = Path(cache_file)
        self._ttl = ttl
        self._store: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Cache file corrupted or unreadable (%s) - starting fresh.", exc)
        return {}

    def _save(self) -> None:
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(
                json.dumps(self._store, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Failed to save cache file: %s", exc)

    def make_key(self, intent: str, query: str, user_id: str = "default_user") -> str:
        """Create a short, deterministic SHA-256 hash key isolated per user_id."""
        normalized = f"{user_id or 'default_user'}::{intent}::{_normalize(query)}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Return cached payload if valid and not expired, else None."""
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

    def set(self, key: str, payload: Dict[str, Any]) -> None:
        """Store a response payload in cache."""
        self._store[key] = {"ts": time.time(), "payload": payload}
        self._save()
        logger.info("Cache SET for key %s", key)

    def clear(self) -> None:
        """Clear all entries in the cache."""
        self._store = {}
        self._save()
        logger.info("Cache cleared successfully.")

    def stats(self) -> Dict[str, int]:
        """Return cache statistics."""
        valid = sum(
            1 for e in self._store.values()
            if time.time() - e.get("ts", 0) <= self._ttl
        )
        return {"total": len(self._store), "valid": valid}
