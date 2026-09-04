"""
Vector Store Management & Abstraction Layer
============================================
Supports both Supabase PostgreSQL (pgvector) and local ChromaDB.
Disables client-side prepared statement caching for PgBouncer compatibility.
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from sqlalchemy import create_engine, text

from src.config import CONFIG

logger = logging.getLogger("bis_vector_store")

_sync_engine = None


def get_pg_sync_engine():
    """Retrieve or create SQLAlchemy engine with prepare_threshold=None for PgBouncer compatibility."""
    global _sync_engine
    if _sync_engine is not None:
        return _sync_engine

    conn_str = CONFIG.get_pgvector_connection_string()
    if not conn_str:
        return None

    try:
        _sync_engine = create_engine(
            conn_str,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"prepare_threshold": None},
        )
        return _sync_engine
    except Exception as exc:
        logger.warning("Failed to create SQLAlchemy engine for PGVector: %s", exc)
        return None


def get_vector_store(collection_name: str, embeddings: Embeddings):
    """
    Factory function returning PGVector (Supabase) or Chroma instance
    based on configuration.
    """
    store_type = CONFIG.vector_store_type.lower()
    engine = get_pg_sync_engine()

    if store_type in ("pgvector", "supabase", "postgres") and engine is not None:
        try:
            from langchain_postgres.vectorstores import PGVector
            logger.info("Initializing PGVector collection '%s' on Supabase PostgreSQL", collection_name)
            store = PGVector(
                embeddings=embeddings,
                collection_name=collection_name,
                connection=engine,
                use_jsonb=True,
            )
            try:
                store.create_tables_if_not_exists()
            except Exception:
                pass
            return store
        except Exception as exc:
            logger.warning("Failed to initialize PGVector ('%s'), falling back to Chroma: %s", collection_name, exc)

    # Default / Fallback: Local ChromaDB
    from langchain_chroma import Chroma
    logger.info("Initializing Chroma collection '%s' at %s", collection_name, CONFIG.db_path)
    return Chroma(
        collection_name=collection_name,
        persist_directory=CONFIG.db_path,
        embedding_function=embeddings,
    )


def delete_vector_collection(collection_name: str, embeddings: Embeddings, vector_store=None) -> bool:
    """Delete/reset a vector collection in PGVector or Chroma."""
    # 1. Direct SQL purge on Supabase PGVector
    engine = get_pg_sync_engine()
    if engine is not None and CONFIG.vector_store_type.lower() in ("pgvector", "supabase", "postgres"):
        try:
            sql_del = """
            DELETE FROM langchain_pg_embedding
            WHERE collection_id IN (
                SELECT uuid FROM langchain_pg_collection WHERE name = :name
            );
            """
            with engine.begin() as conn:
                conn.execute(text(sql_del), {"name": collection_name})
            logger.info("Purged PGVector embeddings for collection '%s' via direct SQL.", collection_name)
            return True
        except Exception as exc:
            logger.warning("Direct SQL purge failed for collection '%s': %s", collection_name, exc)

    # 2. Chroma or object method deletion
    if vector_store is None:
        vector_store = get_vector_store(collection_name, embeddings)

    try:
        if hasattr(vector_store, "delete_collection"):
            vector_store.delete_collection()
            logger.info("Deleted vector collection '%s'", collection_name)
            return True
    except Exception as exc:
        logger.warning("Could not delete vector collection '%s': %s", collection_name, exc)

    return False


def get_all_documents_for_domain(domain: str, vector_store) -> List[Document]:
    """Retrieve all document contents and metadatas for a collection (used by BM25)."""
    # 1. PGVector direct SQL fetch
    engine = get_pg_sync_engine()
    if engine is not None and CONFIG.vector_store_type.lower() in ("pgvector", "supabase", "postgres"):
        try:
            sql_get = """
            SELECT e.document, e.cmetadata
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE c.name = :name;
            """
            with engine.connect() as conn:
                res = conn.execute(text(sql_get), {"name": domain})
                rows = res.fetchall()
                docs = []
                for row in rows:
                    txt = row.document or ""
                    meta = row.cmetadata or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = {}
                    if txt:
                        docs.append(Document(page_content=txt, metadata=meta))
                if docs:
                    return docs
        except Exception as exc:
            logger.warning("Failed to fetch documents for domain '%s' via PGVector SQL: %s", domain, exc)

    # 2. ChromaDB internal API
    if hasattr(vector_store, "_collection") and hasattr(vector_store._collection, "get"):
        try:
            all_results = vector_store._collection.get(include=["documents", "metadatas"])
            docs = [
                Document(page_content=text, metadata=meta or {})
                for text, meta in zip(
                    all_results.get("documents", []),
                    all_results.get("metadatas", []),
                )
            ]
            if docs:
                return docs
        except Exception as exc:
            logger.debug("Chroma collection get failed: %s", exc)

    # 3. Fallback: similarity search with empty query
    try:
        return vector_store.similarity_search("", k=500)
    except Exception:
        return []
