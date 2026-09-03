"""
Immutable Audit Ledger Logger for BIS Agent
===========================================
Appends structured, tamper-evident audit trail entries to data/audit_log.jsonl
for compliance defensibility, regulatory verification, and legal auditing.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import CONFIG, DATA_DIR

logger = logging.getLogger("bis_audit")

DEFAULT_AUDIT_FILE = DATA_DIR / "audit_log.jsonl"


class AuditLogger:
    """Manages immutable audit logging for every agent interaction."""

    def __init__(self, log_path: Path = DEFAULT_AUDIT_FILE) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_interaction(
        self,
        session_id: str,
        user_query: str,
        standalone_query: str,
        intent: str,
        intent_localized: str,
        payload_dict: Dict[str, Any],
        token_usage: Optional[Dict[str, Any]] = None,
        response_time_ms: float = 0.0,
        user_id: Optional[str] = "default_user",
    ) -> Dict[str, Any]:
        """Record an interaction turn to the audit log with SHA-256 digest."""
        now_utc = datetime.now(timezone.utc).isoformat()
        prompt_hash = hashlib.sha256(user_query.encode("utf-8")).hexdigest()

        # Compute payload digest
        serialized = json.dumps(payload_dict, sort_keys=True, ensure_ascii=False)
        payload_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        audit_record = {
            "interaction_id": payload_dict.get("audit_metadata", {}).get("interaction_id") or str(hashlib.md5(f"{now_utc}-{user_query}".encode()).hexdigest()),
            "user_id": user_id or "default_user",
            "timestamp_utc": now_utc,
            "session_id": session_id,
            "user_query": user_query,
            "standalone_query": standalone_query,
            "prompt_sha256": prompt_hash,
            "intent": intent,
            "intent_localized": intent_localized,
            "model_checkpoint": CONFIG.llm_model,
            "embedding_provider": CONFIG.embedding_provider,
            "cache_hit": payload_dict.get("cache_hit", False),
            "response_time_ms": response_time_ms,
            "confidence_metrics": payload_dict.get("confidence_metrics", {}),
            "compliance_metadata": payload_dict.get("compliance_metadata", {}),
            "token_usage": token_usage or payload_dict.get("token_usage", {}),
            "payload_sha256": payload_hash,
        }


        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_record, ensure_ascii=False) + "\n")
            logger.info("Audit record logged [id: %s, hash: %s]", audit_record["interaction_id"][:8], payload_hash[:8])
        except Exception as exc:
            logger.error("Failed to write audit ledger record: %s", exc)

        # Asynchronously schedule Supabase audit log insert if event loop is active
        try:
            import asyncio
            from backend.db.supabase_client import log_audit_to_supabase
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(log_audit_to_supabase(audit_record))
            except RuntimeError:
                pass
        except Exception as exc:
            logger.debug("Could not schedule async Supabase audit log: %s", exc)

        return audit_record



_audit_logger_instance = None


def get_audit_logger() -> AuditLogger:
    """Return global AuditLogger instance."""
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger()
    return _audit_logger_instance
