-- =============================================================================
-- Supabase Schema for BIS Agentic RAG Assistant (BIS SATHI)
-- =============================================================================

-- Enable uuid and vector extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- 0. Users Table for User Registration & Auth
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    total_tokens_burned INT DEFAULT 0,
    total_queries_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 1. Conversation Sessions Table (Per-User Session Storage)
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT 'default_user',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    active_product_context TEXT DEFAULT '',
    turn_count INT DEFAULT 0,
    history JSONB DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC);

-- 2. Immutable Audit Ledger Table
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

CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_session_id ON audit_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp_utc DESC);

-- 3. Persistent Response Cache Table
CREATE TABLE IF NOT EXISTS response_cache (
    cache_key TEXT PRIMARY KEY,
    intent TEXT,
    query_text TEXT,
    cached_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cache_created_at ON response_cache(created_at DESC);
