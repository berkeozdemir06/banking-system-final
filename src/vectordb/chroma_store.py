"""
ChromaDB Store — BIST belgelerinin vektör veritabanı.

Zorunlu metadata şeması:
  ticker · source_type · date · institution
"""

import os
import logging
from typing import Optional
import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from src.embeddings.embedder import get_embedder

logger = logging.getLogger(__name__)

COLLECTION_NAME = "bist_documents"
CHROMA_PATH     = os.getenv("CHROMA_PATH", "./data/chroma_db")


# ── Store class ───────────────────────────────────────────────────────────────
class BISTVectorStore:
    """
    BIST Equity Intelligence — ChromaDB vektör deposu.

    Kullanım:
        store = BISTVectorStore()
        store.add_documents(chunks)
        results = store.search("ASELS KAP bildirimi", ticker="ASELS", k=5)
    """

    def __init__(
        self,
        persist_path: str = CHROMA_PATH,
        embed_provider: str = "nomic",
    ):
        self.persist_path   = persist_path
        self.embed_provider = embed_provider
        os.makedirs(persist_path, exist_ok=True)

        self._client     = self._build_client()
        self._embedder   = get_embedder(embed_provider)
        self._collection = self._get_or_create_collection()

        logger.info(
            f"BISTVectorStore ready — path={persist_path}, "
            f"collection={COLLECTION_NAME}, "
            f"docs={self._collection.count()}"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def add_documents(self, chunks: list[dict]) -> int:
        """
        Chunk listesini ChromaDB'ye ekler.

        Args:
            chunks: embed_documents() çıktısı — embedding field içermeli

        Returns:
            Eklenen chunk sayısı
        """
        if not chunks:
            logger.warning("add_documents: empty chunk list")
            return 0

        ids       = []
        texts     = []
        metadatas = []
        embeddings = []

        for i, chunk in enumerate(chunks):
            doc_id = (
                f"{chunk['ticker']}_{chunk['source_type']}_"
                f"{chunk['date'][:10]}_{chunk.get('chunk_index', i)}"
            )
            ids.append(doc_id)
            texts.append(chunk["content"])
            embeddings.append(chunk.get("embedding", []))
            metadatas.append({
                # ── Mandatory metadata schema ──────────────────────
                "ticker":      chunk["ticker"],
                "source_type": chunk["source_type"],
                "date":        chunk["date"],
                "institution": chunk["institution"],
                # ── Extra ──────────────────────────────────────────
                "title":       chunk.get("title", ""),
                "url":         chunk.get("url", ""),
                "chunk_index": chunk.get("chunk_index", i),
            })

        # Batch upsert (duplicate-safe)
        self._collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings if embeddings[0] else None,
            metadatas=metadatas,
        )

        logger.info(f"Added {len(chunks)} chunks to ChromaDB "
                    f"(total: {self._collection.count()})")
        return len(chunks)

    def search(
        self,
        query: str,
        k: int = 5,
        ticker: Optional[str] = None,
        source_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        """
        Semantik arama + metadata filtresi.

        Args:
            query:       Kullanıcı sorusu
            k:           Döndürülecek sonuç sayısı
            ticker:      Hisse filtresi (örn. "ASELS")
            source_type: Kaynak filtresi ("kap" | "news" | "brokerage")
            date_from:   Başlangıç tarihi (ISO 8601, örn. "2025-01-01")
            date_to:     Bitiş tarihi (ISO 8601)

        Returns:
            List of result dicts with content, metadata, distance
        """
        where_clauses = []
        if ticker:
            where_clauses.append({"ticker": {"$eq": ticker.upper()}})
        if source_type:
            where_clauses.append({"source_type": {"$eq": source_type}})
        if date_from:
            where_clauses.append({"date": {"$gte": date_from}})
        if date_to:
            where_clauses.append({"date": {"$lte": date_to}})

        where = None
        if len(where_clauses) == 1:
            where = where_clauses[0]
        elif len(where_clauses) > 1:
            where = {"$and": where_clauses}

        # Sorgu embedding'i üret
        query_embedding = self._embedder.embed_query(query)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, max(1, self._collection.count())),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        docs = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            docs.append({
                "content":     doc,
                "metadata":    meta,
                "distance":    dist,
                "score":       1 - dist,  # 0→1, 1 = en alakalı
            })

        logger.info(
            f"Search '{query[:40]}...' → {len(docs)} results "
            f"(ticker={ticker}, src={source_type})"
        )
        return docs

    def get_stats(self) -> dict:
        """Koleksiyon istatistiklerini döndürür."""
        count = self._collection.count()
        # Benzersiz ticker'ları bul
        try:
            all_meta = self._collection.get(include=["metadatas"])["metadatas"]
            tickers = list({m["ticker"] for m in all_meta})
            sources = list({m["source_type"] for m in all_meta})
        except Exception:
            tickers, sources = [], []

        return {
            "total_chunks": count,
            "tickers":      tickers,
            "source_types": sources,
            "path":         self.persist_path,
        }

    def delete_ticker(self, ticker: str) -> None:
        """Bir hisseye ait tüm chunk'ları siler."""
        self._collection.delete(where={"ticker": {"$eq": ticker.upper()}})
        logger.info(f"Deleted all chunks for {ticker}")

    # ── Internals ─────────────────────────────────────────────────────────────

    def _build_client(self) -> chromadb.PersistentClient:
        return chromadb.PersistentClient(
            path=self.persist_path,
            settings=Settings(anonymized_telemetry=False),
        )

    def _get_or_create_collection(self):
        return self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    store = BISTVectorStore(persist_path="./data/chroma_db")

    # Örnek chunk ekle
    sample = {
        "ticker":      "ASELS",
        "source_type": "kap",
        "date":        "2025-03-15T10:00:00Z",
        "institution": "KAP / SPK",
        "title":       "ASELS Özel Durum",
        "content":     "Aselsan, Savunma Sanayii Başkanlığı ile 1.2 milyar TL sözleşme imzaladı.",
        "url":         "https://www.kap.org.tr/123",
        "chunk_index": 0,
        "embedding":   [],  # boş → Chroma kendi üretir
    }
    store.add_documents([sample])

    # Arama
    results = store.search("Aselsan sözleşme", ticker="ASELS", k=3)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:80]}")

    print("\nStats:", store.get_stats())
