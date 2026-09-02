"""
Hybrid Retrieval Module
=======================
Fuses BM25 sparse keyword retrieval with Chroma dense vector retrieval,
followed by cosine-similarity reranking for high-precision, token-efficient context.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from src.config import CONFIG

logger = logging.getLogger("bis_retrieval")


class _BM25Index:
    """Lightweight in-memory BM25 index built using rank_bm25."""

    def __init__(self, docs: List[Document]) -> None:
        from rank_bm25 import BM25Okapi
        self._docs = docs
        tokenized = [self._tokenize(d.page_content) for d in docs]
        self._bm25 = BM25Okapi(tokenized)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return text.lower().split()

    def get_top_k(self, query: str, k: int = 5) -> List[Document]:
        if not self._docs:
            return []
        scores = self._bm25.get_scores(self._tokenize(query))
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [self._docs[i] for i in top_indices if scores[i] > 0]


_bm25_cache: Dict[str, _BM25Index] = {}


def _get_bm25_index(domain: str, chroma_db: Chroma) -> Optional[_BM25Index]:
    """Retrieve or lazily construct a cached BM25 index for a specific domain collection."""
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
                logger.warning("Domain '%s' has 0 documents in collection", domain)
                return None
        except Exception as exc:
            logger.warning("Failed to build BM25 index for '%s': %s", domain, exc)
            return None
    return _bm25_cache[domain]


def reset_bm25_cache() -> None:
    """Clear all in-memory BM25 indices (useful after database re-ingestion)."""
    _bm25_cache.clear()
    logger.info("Cleared BM25 cache.")


def _cosine_rerank(
    docs: List[Document],
    query_embedding: List[float],
    doc_embeddings: List[List[float]],
    top_n: int = 2,
) -> List[Document]:
    """Rerank candidates using cosine similarity to query embedding."""
    if not docs:
        return []

    q = np.array(query_embedding, dtype=np.float32)
    q_norm = q / (np.linalg.norm(q) + 1e-9)

    scored: List[Tuple[float, Document]] = []
    for doc, emb in zip(docs, doc_embeddings):
        d = np.array(emb, dtype=np.float32)
        d_norm = d / (np.linalg.norm(d) + 1e-9)
        score = float(np.dot(q_norm, d_norm))
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_n]]


def hybrid_retrieve(
    query: str,
    chroma_db: Chroma,
    embeddings: Embeddings,
    domain: str,
    dense_k: int = CONFIG.retriever_k,
    bm25_k: int = CONFIG.retriever_k,
    rerank_top_n: int = CONFIG.rerank_top_n,
) -> Tuple[List[Document], str]:
    """
    Retrieve documents using hybrid sparse (BM25) + dense (embeddings) search,
    followed by cosine reranking.

    Returns:
        (top_documents, formatted_context_string)
    """
    # 1. Dense retrieval
    dense_docs: List[Document] = []
    try:
        retriever = chroma_db.as_retriever(search_kwargs={"k": dense_k})
        dense_docs = retriever.invoke(query)
    except Exception as exc:
        logger.warning("Dense retrieval error for domain '%s': %s", domain, exc)

    # 2. Sparse BM25 retrieval
    bm25_docs: List[Document] = []
    bm25_index = _get_bm25_index(domain, chroma_db)
    if bm25_index:
        bm25_docs = bm25_index.get_top_k(query, k=bm25_k)

    # 3. Deduplicate
    seen: set[str] = set()
    merged: List[Document] = []
    for doc in dense_docs + bm25_docs:
        key = doc.page_content[:100]
        if key not in seen:
            seen.add(key)
            merged.append(doc)

    if not merged:
        return [], "No relevant documents found in the knowledge base."

    # 4. Rerank
    try:
        query_emb = embeddings.embed_query(query)
        doc_embs = embeddings.embed_documents([doc.page_content for doc in merged])
        top_docs = _cosine_rerank(merged, query_emb, doc_embs, top_n=rerank_top_n)
    except Exception as exc:
        logger.warning("Reranking failed (%s) - using top candidates directly.", exc)
        top_docs = merged[:rerank_top_n]

    # 5. Format context
    context_parts: List[str] = []
    for i, doc in enumerate(top_docs, 1):
        src = doc.metadata.get("source_filename", "BIS Document")
        page = doc.metadata.get("page", "")
        citation = f"{src} (page {page})" if page else src
        context_parts.append(f"[Source {i}: {citation}]\n{doc.page_content}")

    return top_docs, "\n\n".join(context_parts)
