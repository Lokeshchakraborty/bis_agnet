"""
Hybrid Retrieval Tools
======================
BM25 sparse retrieval + Chroma dense retrieval fused together,
followed by cosine-similarity reranking to select the top-N most relevant
chunks before they are passed to the LLM synthesizer.

Token savings: 5 candidates reranked down to 2 focused chunks.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

logger = logging.getLogger("bis_retrieval")


# ---------------------------------------------------------------------------
# BM25 in-memory index (built lazily per domain on first use)
# ---------------------------------------------------------------------------
class _BM25Index:
    """Lightweight BM25 index built on top of rank_bm25."""

    def __init__(self, docs: list[Document]) -> None:
        from rank_bm25 import BM25Okapi  # noqa: PLC0415
        self._docs = docs
        tokenized = [self._tokenize(d.page_content) for d in docs]
        self._bm25 = BM25Okapi(tokenized)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return text.lower().split()

    def get_top_k(self, query: str, k: int = 5) -> list[Document]:
        if not self._docs:
            return []
        scores = self._bm25.get_scores(self._tokenize(query))
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [self._docs[i] for i in top_indices if scores[i] > 0]


_bm25_cache: dict[str, _BM25Index] = {}


def _get_bm25_index(domain: str, chroma_db: Chroma) -> Optional[_BM25Index]:
    """Build or return cached BM25 index for a domain."""
    if domain not in _bm25_cache:
        try:
            all_results = chroma_db._collection.get(include=["documents", "metadatas"])
            docs = [
                Document(page_content=text, metadata=meta or {})
                for text, meta in zip(
                    all_results.get("documents", []),
                    all_results.get("metadatas", []),
                )
            ]
            if docs:
                _bm25_cache[domain] = _BM25Index(docs)
                logger.info("Built BM25 index for '%s' with %d docs", domain, len(docs))
            else:
                logger.warning("Domain '%s' has 0 documents - BM25 index empty", domain)
                return None
        except Exception as exc:
            logger.warning("Failed to build BM25 index for '%s': %s", domain, exc)
            return None
    return _bm25_cache[domain]


def reset_bm25_cache() -> None:
    """Call after re-ingesting documents to force BM25 index rebuild."""
    _bm25_cache.clear()


# ---------------------------------------------------------------------------
# Cosine-similarity reranker (no extra dependencies)
# ---------------------------------------------------------------------------
def _cosine_rerank(
    docs: list[Document],
    query_embedding: list[float],
    doc_embeddings: list[list[float]],
    top_n: int = 2,
) -> list[Document]:
    """Rerank docs by cosine similarity to query embedding."""
    if not docs:
        return []

    q = np.array(query_embedding, dtype=np.float32)
    q_norm = q / (np.linalg.norm(q) + 1e-9)

    scored: list[tuple[float, Document]] = []
    for doc, emb in zip(docs, doc_embeddings):
        d = np.array(emb, dtype=np.float32)
        d_norm = d / (np.linalg.norm(d) + 1e-9)
        score = float(np.dot(q_norm, d_norm))
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_n]]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def hybrid_retrieve(
    query: str,
    chroma_db: Chroma,
    embeddings: Embeddings,
    domain: str,
    dense_k: int = 5,
    bm25_k: int = 5,
    rerank_top_n: int = 2,
) -> tuple[list[Document], str]:
    """
    Retrieve relevant documents using BM25 + dense retrieval, then rerank.

    Returns:
        (top_docs, context_str) - reranked docs + formatted context string.
    """
    # 1. Dense retrieval
    dense_docs: list[Document] = []
    try:
        retriever = chroma_db.as_retriever(search_kwargs={"k": dense_k})
        dense_docs = retriever.invoke(query)
        logger.info("Dense retrieval: %d docs for domain '%s'", len(dense_docs), domain)
    except Exception as exc:
        logger.warning("Dense retrieval failed for '%s': %s", domain, exc)

    # 2. BM25 retrieval
    bm25_docs: list[Document] = []
    bm25_index = _get_bm25_index(domain, chroma_db)
    if bm25_index:
        bm25_docs = bm25_index.get_top_k(query, k=bm25_k)
        logger.info("BM25 retrieval: %d docs for domain '%s'", len(bm25_docs), domain)

    # 3. Merge and deduplicate
    seen: set[str] = set()
    merged: list[Document] = []
    for doc in dense_docs + bm25_docs:
        key = doc.page_content[:100]
        if key not in seen:
            seen.add(key)
            merged.append(doc)

    if not merged:
        logger.warning("No documents for domain '%s' query: %r", domain, query)
        return [], "No relevant documents found in the knowledge base."

    # 4. Rerank by cosine similarity
    try:
        query_emb = embeddings.embed_query(query)
        doc_embs = embeddings.embed_documents([doc.page_content for doc in merged])
        top_docs = _cosine_rerank(merged, query_emb, doc_embs, top_n=rerank_top_n)
        logger.info("Reranked to top %d docs", len(top_docs))
    except Exception as exc:
        logger.warning("Reranking failed: %s - using top-%d merged", exc, rerank_top_n)
        top_docs = merged[:rerank_top_n]

    # 5. Build context string with source attribution
    context_parts: list[str] = []
    for i, doc in enumerate(top_docs, 1):
        src = doc.metadata.get("source_filename", "BIS Document")
        page = doc.metadata.get("page", "")
        citation = f"{src} (page {page})" if page else src
        context_parts.append(f"[Source {i}: {citation}]\n{doc.page_content}")

    context_str = "\n\n".join(context_parts)
    return top_docs, context_str
