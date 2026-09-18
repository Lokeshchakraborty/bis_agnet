"""
Supabase Client & Database Service Module for BIS Agent Backend (BIS SATHI).
=============================================================================
Manages async PostgreSQL connection pooling via SQLAlchemy/asyncpg
and official Supabase SDK integration for User Auth, Sessions, Audit Logs, and Cache Persistence.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from src.config import CONFIG

logger = logging.getLogger("bis_supabase")

# Global instances
_supabase_client = None
_async_engine = None
_async_engine_loop = None


def hash_password(password: str) -> str:
    """Hash password securely using SHA-256 with salt."""
    salt = "bis_sathi_secure_salt_2026"
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def get_supabase_client():
    """Retrieve or initialize global Supabase Py Client instance."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url = CONFIG.supabase_url
    key = CONFIG.supabase_key

    if not url or not key:
        logger.debug("Supabase URL or Key missing. Supabase Client SDK disabled.")
        return None

    try:
        from supabase import create_client, Client
        _supabase_client = create_client(url, key)
        logger.info("Supabase Python SDK client initialized successfully [%s]", url)
        return _supabase_client
    except Exception as exc:
        logger.warning("Failed to initialize Supabase Py Client: %s", exc)
        return None


def get_async_db_engine():
    """Retrieve or initialize SQLAlchemy Async Engine for Supabase PostgreSQL pool."""
    global _async_engine, _async_engine_loop

    current_loop = None
    try:
        import asyncio
        current_loop = asyncio.get_running_loop()
    except Exception:
        pass

    if _async_engine is not None:
        if _async_engine_loop is not None and current_loop is not None and (_async_engine_loop != current_loop or _async_engine_loop.is_closed()):
            _async_engine = None
            _async_engine_loop = None
        else:
            return _async_engine

    db_url = CONFIG.database_url
    if not db_url:
        logger.debug("DATABASE_URL is not configured.")
        return None

    # Standardize async driver for SQLAlchemy if missing
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        _async_engine = create_async_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
            },
        )
        _async_engine_loop = current_loop
        logger.info("Supabase PostgreSQL AsyncEngine initialized.")

        return _async_engine
    except Exception as exc:
        logger.warning("Failed to initialize SQLAlchemy AsyncEngine: %s", exc)
        return None


async def close_async_db_engine() -> None:
    """Gracefully dispose and close SQLAlchemy AsyncEngine pool on server shutdown."""
    global _async_engine
    if _async_engine is not None:
        try:
            await _async_engine.dispose()
            logger.info("Supabase PostgreSQL AsyncEngine closed cleanly.")
        except Exception as exc:
            logger.warning("Error during AsyncEngine disposal: %s", exc)
        finally:
            _async_engine = None


async def init_supabase_db() -> bool:
    """Initialize Supabase PostgreSQL tables if not already present."""
    engine = get_async_db_engine()
    if not engine:
        return False

    ddl_statements = [
        "CREATE EXTENSION IF NOT EXISTS vector;",
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'default_user',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            active_product_context TEXT DEFAULT '',
            turn_count INT DEFAULT 0,
            history JSONB DEFAULT '[]'::jsonb
        );
        """,
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_tokens_burned INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_queries_count INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user';",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_provider TEXT DEFAULT 'google';",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_model TEXT DEFAULT 'gemini-3.5-flash';",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_api_key TEXT DEFAULT '';",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_base_url TEXT DEFAULT '';",
        "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id TEXT DEFAULT 'default_user';",

        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            interaction_id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'default_user',
            timestamp_utc TIMESTAMPTZ DEFAULT NOW(),
            session_id TEXT NOT NULL,
            user_query TEXT NOT NULL,
            standalone_query TEXT,
            prompt_sha256 TEXT,
            intent TEXT,
            intent_localized TEXT,
            model_checkpoint TEXT,
            embedding_provider TEXT,
            cache_hit BOOLEAN DEFAULT FALSE,
            response_time_ms DOUBLE PRECISION DEFAULT 0.0,
            confidence_metrics JSONB DEFAULT '{}'::jsonb,
            compliance_metadata JSONB DEFAULT '{}'::jsonb,
            token_usage JSONB DEFAULT '{}'::jsonb,
            payload_sha256 TEXT,
            payload JSONB DEFAULT '{}'::jsonb
        );
        """,
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_id TEXT DEFAULT 'default_user';",
        """
        CREATE TABLE IF NOT EXISTS response_cache (
            cache_key TEXT PRIMARY KEY,
            intent TEXT,
            query_text TEXT,
            cached_payload JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    ]


    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            for stmt in ddl_statements:
                await conn.execute(text(stmt))
        logger.info("Supabase database tables verified / initialized successfully.")
        return True
    except Exception as exc:
        logger.error("Error executing Supabase DDL initialization: %s", exc)
        return False


# =============================================================================
# USER AUTHENTICATION CRUD METHODS
# =============================================================================

async def create_user_in_supabase(email: str, password: str, full_name: str) -> Dict[str, Any]:
    """Register new user in Supabase PostgreSQL."""
    engine = get_async_db_engine()
    clean_email = email.strip().lower()
    pw_hash = hash_password(password)
    new_user_id = f"usr_{uuid.uuid4().hex[:12]}"

    if not engine:
        return {"success": False, "error": "Database not initialized"}

    sql_check = "SELECT user_id FROM users WHERE LOWER(email) = :email;"
    sql_insert = """
    INSERT INTO users (user_id, email, full_name, password_hash, role, created_at)
    VALUES (:user_id, :email, :full_name, :password_hash, :role, NOW())
    RETURNING user_id, email, full_name, role, created_at;
    """

    is_admin = bool("admin" in clean_email or clean_email.endswith("@bis.gov.in"))
    user_role = "admin" if is_admin else "user"

    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            existing = await conn.execute(text(sql_check), {"email": clean_email})
            if existing.fetchone():
                return {"success": False, "error": "An account with this email already exists."}

            result = await conn.execute(
                text(sql_insert),
                {
                    "user_id": new_user_id,
                    "email": clean_email,
                    "full_name": full_name,
                    "password_hash": pw_hash,
                    "role": user_role,
                },
            )
            row = result.fetchone()
            logger.info("User created successfully: %s [%s] (role=%s)", clean_email, new_user_id, user_role)
            return {
                "success": True,
                "user": {
                    "user_id": row.user_id,
                    "email": row.email,
                    "full_name": row.full_name,
                    "role": user_role,
                    "is_admin": is_admin,
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                },
            }
    except Exception as exc:
        logger.error("Failed to create user in Supabase: %s", exc)
        return {"success": False, "error": str(exc)}


async def authenticate_user_in_supabase(email: str, password: str) -> Dict[str, Any]:
    """Authenticate email & password against Supabase PostgreSQL."""
    engine = get_async_db_engine()
    clean_email = email.strip().lower()
    pw_hash = hash_password(password)

    if not engine:
        return {"success": False, "error": "Database connection unavailable"}

    sql = "SELECT user_id, email, full_name, password_hash, role, llm_provider, llm_model, llm_api_key, llm_base_url, created_at FROM users WHERE LOWER(email) = :email;"

    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), {"email": clean_email})
            row = result.fetchone()
            if not row:
                return {"success": False, "error": "Invalid email or password."}

            if row.password_hash != pw_hash:
                return {"success": False, "error": "Invalid email or password."}

            user_role = getattr(row, "role", None) or ("admin" if ("admin" in clean_email or clean_email.endswith("@bis.gov.in")) else "user")
            is_admin = (user_role == "admin")

            logger.info("User authenticated successfully: %s [%s] (is_admin=%s)", clean_email, row.user_id, is_admin)
            return {
                "success": True,
                "user": {
                    "user_id": row.user_id,
                    "email": row.email,
                    "full_name": row.full_name,
                    "role": user_role,
                    "is_admin": is_admin,
                    "llm_provider": getattr(row, "llm_provider", "google") or "google",
                    "llm_model": getattr(row, "llm_model", "gemini-3.5-flash") or "gemini-3.5-flash",
                    "llm_api_key": getattr(row, "llm_api_key", "") or "",
                    "llm_base_url": getattr(row, "llm_base_url", "") or "",
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                },
            }
    except Exception as exc:
        logger.error("Failed to authenticate user: %s", exc)
        return {"success": False, "error": str(exc)}


async def change_user_password_in_supabase(user_id: str, old_password: str, new_password: str) -> Dict[str, Any]:
    """Verify old password and update to new password in Supabase PostgreSQL."""
    engine = get_async_db_engine()
    if not engine:
        return {"success": False, "error": "Database connection unavailable"}

    old_hash = hash_password(old_password)
    new_hash = hash_password(new_password)

    sql_get = "SELECT password_hash FROM users WHERE user_id = :user_id;"
    sql_update = "UPDATE users SET password_hash = :new_hash WHERE user_id = :user_id;"

    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            result = await conn.execute(text(sql_get), {"user_id": user_id})
            row = result.fetchone()
            if not row:
                return {"success": False, "error": "User account not found."}

            if row.password_hash != old_hash:
                return {"success": False, "error": "Incorrect current password."}

            await conn.execute(text(sql_update), {"user_id": user_id, "new_hash": new_hash})
            logger.info("Password successfully updated for user [%s]", user_id)
            return {"success": True, "message": "Password changed successfully."}
    except Exception as exc:
        logger.error("Failed to change password for user [%s]: %s", user_id, exc)
        return {"success": False, "error": str(exc)}


async def update_user_model_config_in_supabase(
    user_id: str,
    llm_provider: str,
    llm_model: str,
    llm_api_key: str = "",
    llm_base_url: str = "",
) -> Dict[str, Any]:
    """Save user BYOK model provider, model name, API key, and base URL in Supabase PostgreSQL."""
    engine = get_async_db_engine()
    if not engine:
        return {"success": False, "error": "Database unavailable"}

    sql = """
    UPDATE users
    SET llm_provider = :provider,
        llm_model = :model,
        llm_api_key = :key,
        llm_base_url = :url
    WHERE user_id = :user_id;
    """
    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(
                text(sql),
                {
                    "user_id": user_id,
                    "provider": llm_provider or "google",
                    "model": llm_model or "gemini-3.5-flash",
                    "key": llm_api_key or "",
                    "url": llm_base_url or "",
                },
            )
        logger.info("Updated BYOK model config for user [%s]: %s / %s", user_id, llm_provider, llm_model)
        return {"success": True, "message": "Model configuration saved successfully."}
    except Exception as exc:
        logger.error("Failed to update user model config: %s", exc)
        return {"success": False, "error": str(exc)}


async def get_user_model_config_from_supabase(user_id: str) -> Dict[str, Any]:
    """Retrieve saved BYOK model config for a given user_id."""
    engine = get_async_db_engine()
    if not engine or not user_id or user_id == "default_user":
        return {}
    sql = "SELECT llm_provider, llm_model, llm_api_key, llm_base_url FROM users WHERE user_id = :user_id OR LOWER(email) = LOWER(:user_id);"
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), {"user_id": user_id})
            row = result.fetchone()
            if row and row.llm_provider:
                return {
                    "llm_provider": row.llm_provider,
                    "llm_model": row.llm_model,
                    "llm_api_key": row.llm_api_key or "",
                    "llm_base_url": row.llm_base_url or "",
                }
    except Exception as exc:
        logger.warning("Failed to fetch user model config for '%s': %s", user_id, exc)
    return {}




# =============================================================================
# PER-USER SESSION STORAGE METHODS
# =============================================================================

async def save_session_to_supabase(
    session_id: str,
    user_id: str,
    active_product_context: str,
    turn_count: int,
    history: List[tuple[str, str]],
) -> bool:
    """Persist conversation session state to Supabase PostgreSQL linked to user_id."""
    engine = get_async_db_engine()
    if not engine:
        return False

    sql = """
    INSERT INTO sessions (session_id, user_id, active_product_context, turn_count, history, updated_at)
    VALUES (:session_id, :user_id, :context, :turn_count, CAST(:history AS JSONB), NOW())
    ON CONFLICT (session_id) DO UPDATE SET
        user_id = EXCLUDED.user_id,
        active_product_context = EXCLUDED.active_product_context,
        turn_count = EXCLUDED.turn_count,
        history = EXCLUDED.history,
        updated_at = NOW();
    """
    try:
        from sqlalchemy import text
        history_json = json.dumps([{"user": u, "assistant": a} for u, a in history])
        async with engine.begin() as conn:
            await conn.execute(
                text(sql),
                {
                    "session_id": session_id,
                    "user_id": user_id or "default_user",
                    "context": active_product_context,
                    "turn_count": turn_count,
                    "history": history_json,
                },
            )
        return True
    except Exception as exc:
        logger.warning("Failed to save session '%s' for user '%s' to Supabase: %s", session_id, user_id, exc)
        return False


async def get_session_from_supabase(session_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch session record from Supabase PostgreSQL."""
    engine = get_async_db_engine()
    if not engine:
        return None

    if user_id:
        sql = "SELECT session_id, user_id, active_product_context, turn_count, history FROM sessions WHERE session_id = :session_id AND user_id = :user_id;"
        params = {"session_id": session_id, "user_id": user_id}
    else:
        sql = "SELECT session_id, user_id, active_product_context, turn_count, history FROM sessions WHERE session_id = :session_id;"
        params = {"session_id": session_id}

    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            row = result.fetchone()
            if row:
                return {
                    "session_id": row.session_id,
                    "user_id": row.user_id,
                    "active_product_context": row.active_product_context,
                    "turn_count": row.turn_count,
                    "history": row.history,
                }
    except Exception as exc:
        logger.warning("Failed to fetch session '%s' from Supabase: %s", session_id, exc)
    return None


async def list_user_sessions_from_supabase(user_id: str) -> List[Dict[str, Any]]:
    """Retrieve list of active chat sessions for a specific user_id."""
    engine = get_async_db_engine()
    if not engine:
        return []

    sql = """
    SELECT session_id, user_id, active_product_context, turn_count, history, updated_at
    FROM sessions
    WHERE user_id = :user_id
    ORDER BY updated_at DESC;
    """
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), {"user_id": user_id or "default_user"})
            rows = result.fetchall()
            summaries = []
            for row in rows:
                last_q = ""
                raw_hist = getattr(row, "history", None)
                if raw_hist:
                    try:
                        hist_list = raw_hist if isinstance(raw_hist, list) else json.loads(raw_hist)
                        if isinstance(hist_list, list) and len(hist_list) > 0:
                            last_q = hist_list[-1].get("user", "")
                    except Exception:
                        pass
                if not last_q:
                    last_q = row.active_product_context or row.session_id

                summaries.append({
                    "session_id": row.session_id,
                    "user_id": row.user_id,
                    "history_turns": row.turn_count,
                    "last_query": last_q,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else "",
                })
            return summaries
    except Exception as exc:
        logger.warning("Failed to list sessions for user '%s': %s", user_id, exc)
        return []


async def delete_session_from_supabase(session_id: str, user_id: Optional[str] = None) -> bool:
    """Delete a session record from Supabase PostgreSQL."""
    engine = get_async_db_engine()
    if not engine:
        return False

    if user_id:
        sql = "DELETE FROM sessions WHERE session_id = :session_id AND user_id = :user_id;"
        params = {"session_id": session_id, "user_id": user_id}
    else:
        sql = "DELETE FROM sessions WHERE session_id = :session_id;"
        params = {"session_id": session_id}

    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            res = await conn.execute(text(sql), params)
            deleted = (res.rowcount or 0) > 0
        if deleted:
            logger.info("Successfully deleted session '%s' from Supabase PostgreSQL.", session_id)
        return deleted
    except Exception as exc:
        logger.warning("Failed to delete session '%s' from Supabase: %s", session_id, exc)
        return False



async def log_audit_to_supabase(audit_record: Dict[str, Any]) -> bool:
    """Insert immutable audit record into Supabase PostgreSQL audit_logs table."""
    engine = get_async_db_engine()
    if not engine:
        return False

    sql = """
    INSERT INTO audit_logs (
        interaction_id, user_id, timestamp_utc, session_id, user_query, standalone_query,
        prompt_sha256, intent, intent_localized, model_checkpoint, embedding_provider,
        cache_hit, response_time_ms, confidence_metrics, compliance_metadata, token_usage,
        payload_sha256, payload
    ) VALUES (
        :interaction_id, :user_id, NOW(), :session_id, :user_query, :standalone_query,
        :prompt_sha256, :intent, :intent_localized, :model_checkpoint, :embedding_provider,
        :cache_hit, :response_time_ms, CAST(:confidence_metrics AS JSONB), CAST(:compliance_metadata AS JSONB),
        CAST(:token_usage AS JSONB), :payload_sha256, CAST(:payload AS JSONB)
    ) ON CONFLICT (interaction_id) DO NOTHING;
    """
    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            res = await conn.execute(
                text(sql),
                {
                    "interaction_id": audit_record.get("interaction_id"),
                    "user_id": audit_record.get("user_id", "default_user"),
                    "session_id": audit_record.get("session_id", "default"),
                    "user_query": audit_record.get("user_query", ""),
                    "standalone_query": audit_record.get("standalone_query", ""),
                    "prompt_sha256": audit_record.get("prompt_sha256", ""),
                    "intent": audit_record.get("intent", ""),
                    "intent_localized": audit_record.get("intent_localized", ""),
                    "model_checkpoint": audit_record.get("model_checkpoint", ""),
                    "embedding_provider": audit_record.get("embedding_provider", ""),
                    "cache_hit": audit_record.get("cache_hit", False),
                    "response_time_ms": audit_record.get("response_time_ms", 0.0),
                    "confidence_metrics": json.dumps(audit_record.get("confidence_metrics", {})),
                    "compliance_metadata": json.dumps(audit_record.get("compliance_metadata", {})),
                    "token_usage": json.dumps(audit_record.get("token_usage", {})),
                    "payload_sha256": audit_record.get("payload_sha256", ""),
                    "payload": json.dumps(audit_record),
                },
            )
            # Only increment user token burn if a NEW row was actually inserted
            if res.rowcount and res.rowcount > 0:
                user_id = audit_record.get("user_id")
                tu = audit_record.get("token_usage", {})
                if isinstance(tu, str):
                    try:
                        tu = json.loads(tu)
                    except Exception:
                        tu = {}
                burned = 0
                if isinstance(tu, dict):
                    p = int(tu.get("turn_prompt_tokens") or tu.get("prompt_tokens") or 0)
                    c = int(tu.get("turn_completion_tokens") or tu.get("completion_tokens") or 0)
                    burned = int(tu.get("turn_llm_tokens") or tu.get("total_tokens") or (p + c) or 0)
                if user_id and user_id != "default_user" and burned > 0:
                    await record_token_burn_for_user_in_supabase(user_id, burned)
        logger.info("Successfully persisted audit log record %s to Supabase.", audit_record.get("interaction_id", "")[:8])
        return True
    except Exception as exc:
        logger.warning("Failed to insert audit record to Supabase: %s", exc)
        return False


async def record_token_burn_for_user_in_supabase(user_id: str, tokens_burned: int) -> bool:
    """Atomically increment total_tokens_burned and total_queries_count in users table in Supabase PostgreSQL."""
    if not user_id or user_id == "default_user":
        return False

    engine = get_async_db_engine()
    if not engine:
        return False

    sql = """
    UPDATE users
    SET total_tokens_burned = COALESCE(total_tokens_burned, 0) + :tokens_burned,
        total_queries_count = COALESCE(total_queries_count, 0) + 1
    WHERE user_id = :user_id;
    """
    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text(sql), {"user_id": user_id, "tokens_burned": tokens_burned})
        logger.info("Updated total_tokens_burned (+%d) for user [%s] in Supabase PostgreSQL.", tokens_burned, user_id)
        return True
    except Exception as exc:
        logger.warning("Failed to update token burn for user [%s]: %s", user_id, exc)
        return False


async def fetch_audit_logs_from_supabase(session_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve audit log records from Supabase PostgreSQL."""
    engine = get_async_db_engine()
    if not engine:
        return []

    try:
        from sqlalchemy import text
        if session_id:
            sql = "SELECT payload FROM audit_logs WHERE session_id = :session_id ORDER BY timestamp_utc DESC LIMIT :limit;"
            params = {"session_id": session_id, "limit": limit}
        else:
            sql = "SELECT payload FROM audit_logs ORDER BY timestamp_utc DESC LIMIT :limit;"
            params = {"limit": limit}

        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            rows = result.fetchall()
            return [row.payload if isinstance(row.payload, dict) else json.loads(row.payload) for row in rows]
    except Exception as exc:
        logger.warning("Failed to fetch audit logs from Supabase: %s", exc)
        return []


async def clear_all_audit_logs_from_supabase() -> bool:
    """Purge all audit log records from Supabase PostgreSQL audit_logs table."""
    engine = get_async_db_engine()
    if not engine:
        return False

    sql = "TRUNCATE TABLE audit_logs;"
    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text(sql))
        logger.info("Successfully truncated audit_logs table in Supabase PostgreSQL.")
        return True
    except Exception as exc:
        logger.warning("Failed to truncate audit_logs table: %s", exc)
        return False


async def get_user_account_usage_from_supabase(user_id: str) -> Dict[str, Any]:
    """Retrieve user account token usage directly from users table and audit_logs in Supabase PostgreSQL."""
    engine = get_async_db_engine()
    if not engine:
        return {
            "user_id": user_id,
            "total_queries": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens_burned": 0,
            "total_cache_saved_tokens": 0,
        }

    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            # 1. Fetch user record from users table (by user_id or email)
            user_sql = "SELECT user_id, total_tokens_burned, total_queries_count FROM users WHERE user_id = :identifier OR LOWER(email) = LOWER(:identifier);"
            user_res = await conn.execute(text(user_sql), {"identifier": user_id or "default_user"})
            user_row = user_res.fetchone()
            actual_user_id = user_row.user_id if user_row else user_id

            # 2. Fetch detailed breakdown from audit_logs
            logs_sql = "SELECT token_usage FROM audit_logs WHERE user_id = :uid OR user_id = :identifier;"
            logs_res = await conn.execute(text(logs_sql), {"uid": actual_user_id, "identifier": user_id})
            rows = logs_res.fetchall()

            queries_count = user_row.total_queries_count if (user_row and hasattr(user_row, "total_queries_count") and user_row.total_queries_count is not None) else 0
            tokens_count = user_row.total_tokens_burned if (user_row and hasattr(user_row, "total_tokens_burned") and user_row.total_tokens_burned is not None) else 0

            prompt_t = 0
            comp_t = 0
            log_total = 0
            saved_t = 0
            log_queries = len(rows)

            for row in rows:
                tu = row.token_usage
                if isinstance(tu, str):
                    try:
                        tu = json.loads(tu)
                    except Exception:
                        tu = {}
                if isinstance(tu, dict):
                    p = int(tu.get("turn_prompt_tokens") or tu.get("prompt_tokens") or 0)
                    c = int(tu.get("turn_completion_tokens") or tu.get("completion_tokens") or 0)
                    # Turn tokens = prompt + completion for that specific turn
                    t = int(tu.get("turn_llm_tokens") or tu.get("total_tokens") or (p + c) or 0)
                    s = int(tu.get("session_total_saved_tokens") or tu.get("estimated_saved_tokens") or 0)
                    prompt_t += p
                    comp_t += c
                    log_total += t if t > 0 else (p + c)
                    saved_t += s

            # Calculate exact ground-truth total tokens from prompt + completion sum
            final_total_tokens = prompt_t + comp_t if (prompt_t + comp_t) > 0 else (user_row.total_tokens_burned if user_row else 0)
            final_queries = log_queries if log_queries > 0 else (user_row.total_queries_count if user_row else 0)

            # Sync corrected values back to users table if needed
            if user_row and (user_row.total_tokens_burned != final_total_tokens or user_row.total_queries_count != final_queries):
                try:
                    update_sql = "UPDATE users SET total_tokens_burned = :t, total_queries_count = :q WHERE user_id = :uid;"
                    async with engine.begin() as update_conn:
                        await update_conn.execute(text(update_sql), {"t": final_total_tokens, "q": final_queries, "uid": actual_user_id})
                except Exception:
                    pass

            return {
                "user_id": user_id,
                "total_queries": final_queries,
                "total_prompt_tokens": prompt_t,
                "total_completion_tokens": comp_t,
                "total_tokens_burned": final_total_tokens,
                "total_cache_saved_tokens": saved_t,
            }
    except Exception as exc:
        logger.warning("Failed to fetch user account usage for '%s': %s", user_id, exc)
        return {
            "user_id": user_id,
            "total_queries": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens_burned": 0,
            "total_cache_saved_tokens": 0,
        }


