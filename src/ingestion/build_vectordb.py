"""
BIS ChromaDB Document Ingestion Pipeline
========================================
Parses procedures and policy PDFs/TXTs from data/procedures/<domain>/,
generates embeddings, and stores them in distinct domain collections in ChromaDB.

Usage:
    python src/ingestion/build_vectordb.py [--clean]
"""
from __future__ import annotations

import argparse
import logging
import shutil
import time
from pathlib import Path
from typing import Dict, List

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_ollama import OllamaEmbeddings

from src.config import CONFIG, DATA_DIR
from src.schemas import DOMAIN_COLLECTIONS
from src.tools.retriever import reset_bm25_cache

logger = logging.getLogger("bis_ingestion")

PROCEDURES_DIR = Path(CONFIG.procedures_path)
PERSIST_DIR = Path(CONFIG.db_path)
SEGMENTS = [d.value for d in DOMAIN_COLLECTIONS]


def get_embeddings_model() -> Embeddings:
    """Return embedding provider configured in environment."""
    provider = CONFIG.embedding_provider.lower()
    if provider == "fastembed":
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
        logger.info("Using FastEmbed embeddings: %s", CONFIG.embedding_model)
        return FastEmbedEmbeddings(model_name=CONFIG.embedding_model)
    elif provider == "google":
        logger.info("Using Google Generative AI embeddings: %s", CONFIG.embedding_model)
        return GoogleGenerativeAIEmbeddings(model=CONFIG.embedding_model)
    elif provider in ("mistral", "mistralaiembeddings"):
        from langchain_mistralai import MistralAIEmbeddings
        logger.info("Using Mistral AI embeddings: %s", CONFIG.embedding_model)
        return MistralAIEmbeddings(model=CONFIG.embedding_model)
    else:
        logger.info("Using Ollama embeddings: %s", CONFIG.embedding_model)
        return OllamaEmbeddings(model=CONFIG.embedding_model, base_url=CONFIG.embedding_base_url)


def _add_metadata(docs: List[Document], domain: str) -> List[Document]:
    clean_docs: List[Document] = []
    for doc in docs:
        text = doc.page_content.strip()
        if len(text) < 30:
            continue
        src = doc.metadata.get("source", "")
        doc.metadata["domain"] = domain
        doc.metadata["source_filename"] = Path(src).name if src else "unknown"
        doc.metadata["page"] = doc.metadata.get("page", 0)
        clean_docs.append(doc)
    return clean_docs


def ingest_segment(segment: str, embeddings: Embeddings, reset: bool = True) -> int:
    """Ingest PDF and TXT documents for a specific domain folder into Chroma collection."""
    folder = PROCEDURES_DIR / segment

    if not folder.exists():
        logger.warning("Directory not found: %s -- skipping.", folder)
        return 0

    logger.info("Processing domain: '%s' from %s", segment, folder)

    # 1. Load PDFs
    pdf_docs: List[Document] = []
    pdf_files = sorted(list(folder.glob("**/*.pdf")))
    for pdf_path in pdf_files:
        try:
            loader = PyPDFLoader(str(pdf_path))
            loaded = loader.load()
            pdf_docs.extend(loaded)
            logger.info("  Loaded PDF: %s (%d pages)", pdf_path.name, len(loaded))
        except Exception as exc:
            logger.warning("  Failed to load PDF %s: %s", pdf_path.name, exc)

    # 2. Load TXT files
    txt_docs: List[Document] = []
    txt_files = sorted(list(folder.glob("**/*.txt")))
    for txt_path in txt_files:
        try:
            loader = TextLoader(str(txt_path), encoding="utf-8")
            loaded = loader.load()
            txt_docs.extend(loaded)
            logger.info("  Loaded TXT: %s", txt_path.name)
        except Exception as exc:
            logger.warning("  Failed to load TXT %s: %s", txt_path.name, exc)

    all_docs = pdf_docs + txt_docs
    if not all_docs:
        logger.warning("No documents found in %s -- skipping.", folder)
        return 0

    # 3. Clean Text Splitting
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n\n", "\n", "Step ", "Clause ", "Section ", ". ", " "],
    )
    raw_chunks = splitter.split_documents(all_docs)
    chunks = _add_metadata(raw_chunks, segment)

    if not chunks:
        return 0

    # 4. Ingest into Chroma Collection
    db = Chroma(
        collection_name=segment,
        embedding_function=embeddings,
        persist_directory=str(PERSIST_DIR),
    )

    if reset:
        try:
            db.delete_collection()
            db = Chroma(
                collection_name=segment,
                embedding_function=embeddings,
                persist_directory=str(PERSIST_DIR),
            )
        except Exception:
            pass

    batch_size = 100
    t_start = time.time()
    for b_idx in range(0, len(chunks), batch_size):
        batch = chunks[b_idx : b_idx + batch_size]
        db.add_documents(batch)

    t_total = time.time() - t_start
    total_in_db = db._collection.count()
    logger.info(
        "Domain '%s' complete: %d chunks embedded in %.2fs.",
        segment,
        total_in_db,
        t_total,
    )
    return total_in_db


def ingest_all(clean_db: bool = False) -> None:
    """Ingest all configured domains into ChromaDB."""
    logger.info("Starting BIS Document Ingestion...")
    logger.info("Persist directory: %s", PERSIST_DIR)

    if clean_db and PERSIST_DIR.exists():
        logger.info("Cleaning existing database directory: %s", PERSIST_DIR)
        shutil.rmtree(PERSIST_DIR, ignore_errors=True)

    embeddings = get_embeddings_model()
    summary: Dict[str, int] = {}

    for segment in SEGMENTS:
        try:
            count = ingest_segment(segment, embeddings, reset=True)
            summary[segment] = count
        except Exception as exc:
            logger.error("Failed to ingest segment '%s': %s", segment, exc)
            summary[segment] = 0

    reset_bm25_cache()

    logger.info("\n=== INGESTION SUMMARY ===")
    for seg, count in summary.items():
        logger.info("  %-15s : %d chunks", seg, count)
    logger.info("  %-15s : %d chunks total", "TOTAL", sum(summary.values()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest BIS domain documents into ChromaDB")
    parser.add_argument("--clean", action="store_true", help="Wipe database before ingestion")
    args = parser.parse_args()
    ingest_all(clean_db=args.clean)


if __name__ == "__main__":
    main()
