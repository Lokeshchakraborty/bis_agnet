"""
BIS ChromaDB Ingestion
======================
Ingests all PDFs and .txt files from data/procedures/<domain>/ into separate
Chroma collections, one per domain, using fast ONNX-accelerated BGE embeddings
(or Google Cloud / Ollama embeddings if configured).

Usage:
    python src/ingestion/build_vectorDB.py --clean
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
import time
from pathlib import Path

if "SSLKEYLOGFILE" in os.environ:
    try:
        with open(os.environ["SSLKEYLOGFILE"], "a"):
            pass
    except Exception:
        os.environ.pop("SSLKEYLOGFILE", None)

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("bis_ingestion")

BASE_DATA_DIR = PROJECT_ROOT / "data" / "procedures"
PERSIST_DIR = str(PROJECT_ROOT / "data" / "chroma_db")

SEGMENTS = ["hallmark", "registration", "certification", "laboratory", "manakonline"]

FOLDER_ALIASES = {
    "labratory": "laboratory",
}


def get_embeddings_model() -> Embeddings:
    """Return embedding model based on environment configuration."""
    provider = os.getenv("BIS_EMBEDDING_PROVIDER", "fastembed").lower()
    
    # from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    # model_name = os.getenv("BIS_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    # logger.info("Using FastEmbed Multilingual (ONNX): %s", model_name)
    # return FastEmbedEmbeddings(model_name=model_name)
    from langchain_mistralai import MistralAIEmbeddings
    
    return MistralAIEmbeddings(model="mistral-embed-2312")

def _get_folder(segment: str) -> Path:
    direct = BASE_DATA_DIR / segment
    if direct.exists():
        return direct
    for alias, canonical in FOLDER_ALIASES.items():
        if canonical == segment:
            aliased = BASE_DATA_DIR / alias
            if aliased.exists():
                return aliased
    return direct


def _add_metadata(docs: list[Document], domain: str) -> list[Document]:
    clean_docs: list[Document] = []
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
    folder = _get_folder(segment)
    
    if not folder.exists():
        logger.warning("Directory not found: %s -- skipping.", folder)
        return 0

    logger.info("\n==================================================")
    logger.info("Processing domain: '%s' from %s", segment, folder)
    logger.info("==================================================")

    # 1. Load PDFs
    pdf_docs: list[Document] = []
    pdf_files = sorted(list(folder.glob("**/*.pdf")))
    if pdf_files:
        logger.info("Found %d PDF file(s)", len(pdf_files))
        for pdf_path in pdf_files:
            try:
                loader = PyPDFLoader(str(pdf_path))
                loaded = loader.load()
                pdf_docs.extend(loaded)
                logger.info("  Loaded PDF: %s (%d pages)", pdf_path.name, len(loaded))
            except Exception as exc:
                logger.warning("  Failed to load PDF %s: %s", pdf_path.name, exc)

    # 2. Load .txt files
    txt_docs: list[Document] = []
    txt_files = sorted(list(folder.glob("**/*.txt")))
    if txt_files:
        logger.info("Found %d TXT file(s)", len(txt_files))
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

    logger.info("Total pages/documents loaded: %d", len(all_docs))

    # 3. Clean Text Splitting (1200 chars preserves complete clauses & rules)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n\n", "\n", "Step ", "Clause ", "Section ", ". ", " "],
    )
    raw_chunks = splitter.split_documents(all_docs)
    chunks = _add_metadata(raw_chunks, segment)
    logger.info("Created %d meaningful chunks for domain '%s'", len(chunks), segment)

    if not chunks:
        return 0

    # 4. Initialize Chroma Collection
    db = Chroma(
        collection_name=segment,
        embedding_function=embeddings,
        persist_directory=PERSIST_DIR,
    )
    
    if reset:
        try:
            db.delete_collection()
            db = Chroma(
                collection_name=segment,
                embedding_function=embeddings,
                persist_directory=PERSIST_DIR,
            )
        except Exception:
            pass

    # Batch embedding in chunks of 100
    batch_size = 100
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    t_start = time.time()
    
    for b_idx in range(0, len(chunks), batch_size):
        batch = chunks[b_idx : b_idx + batch_size]
        curr_batch_num = (b_idx // batch_size) + 1
        db.add_documents(batch)
        logger.info(
            "  [Batch %d/%d] Embedded chunks [%d..%d] of %d",
            curr_batch_num, total_batches, b_idx + 1, min(b_idx + batch_size, len(chunks)), len(chunks)
        )

    t_total = time.time() - t_start
    total_in_db = db._collection.count()
    logger.info("Domain '%s' complete -- %d chunks embedded in %.2fs (%.1f chunks/sec).",
                segment, total_in_db, t_total, total_in_db / max(t_total, 0.001))
    return total_in_db


def ingest_pdfs_to_chroma(clean_db: bool = False) -> None:
    logger.info("Starting BIS PDF Ingestion to ChromaDB...")
    logger.info("Persist directory: %s", PERSIST_DIR)

    if clean_db and Path(PERSIST_DIR).exists():
        logger.info("Cleaning old persist directory: %s", PERSIST_DIR)
        shutil.rmtree(PERSIST_DIR, ignore_errors=True)

    embeddings = get_embeddings_model()

    summary: dict[str, int] = {}
    for segment in SEGMENTS:
        try:
            count = ingest_segment(segment, embeddings, reset=True)
            summary[segment] = count
        except Exception as exc:
            logger.error("Failed to ingest segment '%s': %s", segment, exc)
            summary[segment] = 0

    try:
        try:
            from src.tools.retrieval_tools import reset_bm25_cache
        except ImportError:
            from tools.retrieval_tools import reset_bm25_cache
        reset_bm25_cache()
    except Exception:
        pass

    logger.info("\n==================================================")
    logger.info("              INGESTION SUMMARY                   ")
    logger.info("==================================================")
    for seg, count in summary.items():
        logger.info("  %-15s : %d chunks", seg, count)
    logger.info("  %-15s : %d chunks total", "TOTAL", sum(summary.values()))
    logger.info("==================================================")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", help="Wipe chroma_db directory before starting")
    args = parser.parse_args()
    ingest_pdfs_to_chroma(clean_db=args.clean)
