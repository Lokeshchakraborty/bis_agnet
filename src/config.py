"""
Configuration and Environment Settings for BIS Agent.
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

# Base directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"

# Clean up SSL keylog environment issue if present
if "SSLKEYLOGFILE" in os.environ:
    try:
        with open(os.environ["SSLKEYLOGFILE"], "a"):
            pass
    except Exception:
        os.environ.pop("SSLKEYLOGFILE", None)

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load .env file
load_dotenv(PROJECT_ROOT / ".env")

console = Console()


@dataclass(frozen=True)
class Config:
    """Central configuration for models, paths, retrieval parameters, and caching."""
    embedding_provider: str = os.getenv("BIS_EMBEDDING_PROVIDER", "MistralAIEmbeddings")
    embedding_model: str = os.getenv("BIS_EMBEDDING_MODEL", "mistral-embed-2312")
    embedding_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    llm_model: str = os.getenv("BIS_LLM_MODEL", "gemini-3.5-flash-lite")
    llm_temperature: float = float(os.getenv("BIS_LLM_TEMPERATURE", "0.2"))
    db_path: str = os.getenv("BIS_CHROMA_PATH", str(DATA_DIR / "chroma_db"))
    cache_path: str = os.getenv("BIS_CACHE_PATH", str(DATA_DIR / "cache.json"))
    procedures_path: str = os.getenv("BIS_PROCEDURES_PATH", str(DATA_DIR / "procedures"))
    retriever_k: int = int(os.getenv("BIS_RETRIEVER_K", "3"))
    rerank_top_n: int = int(os.getenv("BIS_RERANK_TOP_N", "2"))
    history_window: int = int(os.getenv("BIS_HISTORY_WINDOW", "3"))
    max_stored_history: int = int(os.getenv("BIS_MAX_STORED_HISTORY", "5"))
    max_retries: int = int(os.getenv("BIS_LLM_MAX_RETRIES", "3"))
    retry_backoff_seconds: float = float(os.getenv("BIS_RETRY_BACKOFF", "1.5"))
    log_level: str = os.getenv("BIS_LOG_LEVEL", "INFO")
    cache_enabled: bool = os.getenv("BIS_CACHE_ENABLED", "true").lower() == "true"
    vector_store_type: str = os.getenv("BIS_VECTOR_STORE_TYPE", "pgvector")
    database_url: str = os.getenv("DATABASE_URL", "")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", os.getenv("SUPABASE_ANON_KEY", os.getenv("SUPABASE_SERVICE_KEY", "")))

    def get_pgvector_connection_string(self) -> str:
        """Format database URL for psycopg3 driver used by PGVector."""
        db_url = self.database_url
        if not db_url:
            return ""
        if db_url.startswith("postgresql+asyncpg://"):
            return db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        elif db_url.startswith("postgresql://"):
            return db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return db_url




CONFIG = Config()

# Setup root logger for bis_agent
logging.basicConfig(
    level=getattr(logging, CONFIG.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bis_agent")


def validate_environment() -> None:
    """Verify required API keys and notify about missing paths."""
    missing = [key for key in ("GOOGLE_API_KEY",) if not os.getenv(key)]
    if missing:
        console.print(
            f"[bold red]Missing required environment variable(s): {', '.join(missing)}[/bold red]\n"
            "Please configure them in your .env file."
        )
        sys.exit(1)

    if not Path(CONFIG.db_path).exists():
        console.print(
            f"[yellow]Warning: Chroma DB path '{CONFIG.db_path}' does not exist yet. "
            "Run 'python src/ingestion/build_vectordb.py' to populate it.[/yellow]"
        )
