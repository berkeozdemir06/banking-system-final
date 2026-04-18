"""
Embedder — ChromaDB için varsayılan embedding fonksiyonu.

Python 3.9 uyumlu: Nomic yerine ChromaDB'nin built-in sentence-transformers kullanır.
Fallback: OpenAI text-embedding-3-small (OPENAI_API_KEY gerekli)
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CHUNK_SIZE    = 800
CHUNK_OVERLAP = 120


# ── Factory ───────────────────────────────────────────────────────────────────
def get_embedder(provider: str = "default"):
    """
    Embedding provider döndürür.
    provider: "openai" | "default" (chromadb built-in)
    """
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        logger.info("Using OpenAI text-embedding-3-small")
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=openai_key,
        )
    # ChromaDB'nin default embedding'i (sentence-transformers, ücretsiz, offline)
    logger.info("Using ChromaDB default embedding (offline, no API key needed)")
    from langchain_community.embeddings import SentenceTransformerEmbeddings
    return SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")


# ── Text Splitter ─────────────────────────────────────────────────────────────
def get_text_splitter():
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""],
    )


# ── Pipeline ──────────────────────────────────────────────────────────────────
def embed_documents(docs: list, provider: str = "default") -> list:
    """
    Belge listesini chunk'lara böler ve embedding üretir.
    """
    embedder = get_embedder(provider)
    splitter = get_text_splitter()

    chunks = []
    for doc in docs:
        content = doc.get("content", "")
        if not content.strip():
            logger.warning(f"Skipping empty doc: {doc.get('title','?')}")
            continue

        texts = splitter.split_text(content)
        logger.info(f"  {doc.get('ticker','?')} | {doc.get('source_type','?')} → {len(texts)} chunks")

        for i, text in enumerate(texts):
            chunk = {
                "ticker":       doc["ticker"],
                "source_type":  doc["source_type"],
                "date":         doc["date"],
                "institution":  doc["institution"],
                "title":        doc.get("title", ""),
                "content":      text,
                "url":          doc.get("url", ""),
                "chunk_index":  i,
                "total_chunks": len(texts),
            }
            chunks.append(chunk)

    if not chunks:
        logger.warning("No chunks produced")
        return []

    logger.info(f"Embedding {len(chunks)} chunks...")
    texts_only = [c["content"] for c in chunks]
    embeddings = embedder.embed_documents(texts_only)

    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb

    logger.info(f"Done — {len(chunks)} embeddings ready")
    return chunks
