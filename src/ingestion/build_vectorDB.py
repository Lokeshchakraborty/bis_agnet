"""
BIS ChromaDB Ingestion
======================
Ingests PDFs and .txt files from data/procedures/<domain>/ into separate
Chroma collections, one per domain, with rich metadata on each chunk.

Run after download_bis_docs.py:
    python src/ingestion/build_vectorDB.py
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from langchain_community.document_loaders import (
    DirectoryLoader,
    PyPDFLoader,
    TextLoader,
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("bis_ingestion")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_DATA_DIR = PROJECT_ROOT / "data" / "procedures"
PERSIST_DIR = str(PROJECT_ROOT / "data" / "chroma_db")

# Canonical domain names (must match Intent enum values in main.py)
SEGMENTS = ["hallmark", "registration", "certification", "laboratory", "manakonline"]

# Map filesystem folder names to canonical names (handles typos)
FOLDER_ALIASES = {
    "labratory": "laboratory",   # fix the typo that exists in the filesystem
}


def _get_folder(segment: str) -> Path:
    """Return the procedures folder for a segment, handling folder name aliases."""
    direct = BASE_DATA_DIR / segment
    if direct.exists():
        return direct
    # Check aliases
    for alias, canonical in FOLDER_ALIASES.items():
        if canonical == segment:
            aliased = BASE_DATA_DIR / alias
            if aliased.exists():
                return aliased
    return direct  # return even if missing; caller will handle


def _add_metadata(docs: list[Document], domain: str) -> list[Document]:
    """Stamp each chunk with domain + source file metadata."""
    for doc in docs:
        src = doc.metadata.get("source", "")
        doc.metadata["domain"] = domain
        doc.metadata["source_filename"] = Path(src).name if src else "unknown"
        doc.metadata["page"] = doc.metadata.get("page", 0)
    return docs


def ingest_segment(segment: str, embeddings: OllamaEmbeddings) -> None:
    folder = _get_folder(segment)
    
    if not folder.exists():
        logger.warning("Directory not found: %s -- creating empty folder.", folder)
        folder.mkdir(parents=True, exist_ok=True)
        logger.info("Place PDFs or .txt files in %s and re-run.", folder)
        return

    logger.info("\nProcessing segment: '%s' from %s", segment, folder)

    # Load PDFs
    pdf_docs: list[Document] = []
    pdf_files = list(folder.glob("**/*.pdf"))
    if pdf_files:
        logger.info("  Found %d PDF(s)", len(pdf_files))
        for pdf_path in pdf_files:
            try:
                loader = PyPDFLoader(str(pdf_path))
                pdf_docs.extend(loader.load())
            except Exception as exc:
                logger.warning("  Failed to load %s: %s", pdf_path.name, exc)

    # Load .txt files
    txt_docs: list[Document] = []
    txt_files = list(folder.glob("**/*.txt"))
    if txt_files:
        logger.info("  Found %d TXT file(s)", len(txt_files))
        for txt_path in txt_files:
            try:
                loader = TextLoader(str(txt_path), encoding="utf-8")
                txt_docs.extend(loader.load())
            except Exception as exc:
                logger.warning("  Failed to load %s: %s", txt_path.name, exc)

    all_docs = pdf_docs + txt_docs
    if not all_docs:
        logger.warning("  No documents found in %s -- skipping.", folder)
        return

    logger.info("  Total pages/chunks before split: %d", len(all_docs))

    # Smaller chunks = more precise retrieval hits
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
        separators=["\n\n", "\n", "Step ", "Clause ", ". ", " "],
    )
    chunks = splitter.split_documents(all_docs)
    chunks = _add_metadata(chunks, segment)
    logger.info("  Split into %d chunks", len(chunks))

    logger.info("  Embedding and saving to Chroma collection '%s'...", segment)
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=segment,
        persist_directory=PERSIST_DIR,
    )
    logger.info("  Done -- %d chunks saved for '%s'.", len(chunks), segment)


def ingest_pdfs_to_chroma() -> None:
    logger.info("Starting BIS PDF Ingestion to ChromaDB...")
    logger.info("Persist dir: %s", PERSIST_DIR)

    embeddings = OllamaEmbeddings(
        model=os.getenv("BIS_EMBEDDING_MODEL", "embeddinggemma"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    for segment in SEGMENTS:
        try:
            ingest_segment(segment, embeddings)
        except Exception as exc:
            logger.error("Failed to ingest segment '%s': %s", segment, exc)

    logger.info("\nIngestion complete!")


if __name__ == "__main__":
    ingest_pdfs_to_chroma()
