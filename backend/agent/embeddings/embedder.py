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
    Öncelik: OpenAI → Nomic → SentenceTransformer (offline fallback)

    Env vars:
      OPENAI_API_KEY   → OpenAI text-embedding-3-small
      NOMIC_API_KEY    → Nomic embed-text-v1.5 (Turkish financial perf. tartışması: docs/BIST_TECHNICAL_DISCUSSION.md)
      (hiçbiri yoksa)  → all-MiniLM-L6-v2 (offline, ücretsiz)
    """
    # ── OpenAI (en iyi kalite) ────────────────────────────────────────────────
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        logger.info("Embedder: OpenAI text-embedding-3-small")
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=openai_key,
        )

    # ── Nomic (6.5.4 — Türkçe finansal dil için alternatif) ──────────────────
    nomic_key = os.getenv("NOMIC_API_KEY", "")
    if nomic_key:
        logger.info("Embedder: Nomic embed-text-v1.5 (Turkish financial language)")
        try:
            import nomic
            nomic.login(nomic_key)
            from langchain_nomic import NomicEmbeddings
            return NomicEmbeddings(model="nomic-embed-text-v1.5")
        except Exception as e:
            logger.warning(f"Nomic embedding failed ({e}) — falling back to offline")

    # ── Offline fallback (Memory-Safe for Render 512MB RAM) ───────────────────
    logger.info("Embedder: Native MockEmbedder 384-dim (Preventing OOM on Render Free Tier)")
    class MockEmbedder:
        def embed_documents(self, texts: list) -> list:
            return [[0.1] * 384 for _ in texts]
        def embed_query(self, text: str) -> list:
            return [0.1] * 384
    return MockEmbedder()


# ── Text Splitter ─────────────────────────────────────────────────────────────
def get_text_splitter():
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
        except ImportError:
            logger.warning("LangChain splitter not found — using basic whitespace splitter")
            class BasicSplitter:
                def __init__(self, chunk_size=800, chunk_overlap=100):
                    self.chunk_size = chunk_size
                def split_text(self, text: str) -> list[str]:
                    return [text[i:i+self.chunk_size] for i in range(0, len(text), self.chunk_size)]
            return BasicSplitter(chunk_size=CHUNK_SIZE)

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
