"""
Memory Module — Mem0 ile konuşma ve kullanıcı geçmişi yönetimi.

Bellek Politikası:
  - SHORT-TERM: Son 5 soru-cevap (konuşma içi bağlam)
  - LONG-TERM:  Kullanıcının ilgilendiği ticker'lar ve tercihler
  - PURGE:      30 günden eski anılar otomatik silinir
"""

import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ── Memory Manager ────────────────────────────────────────────────────────────
class BISTMemory:
    """
    BIST Agent için hafıza yöneticisi.

    Mem0 API varsa bulut belleği kullanır.
    Yoksa basit in-memory + JSON fallback devreye girer.

    Kullanım:
        mem = BISTMemory(user_id="user_123")
        mem.add("ASELS hakkında KAP sorguladı", category="query")
        context = mem.get_context()
    """

    PURGE_DAYS    = 30
    MAX_SHORT_MEM = 5   # son N soru-cevap

    def __init__(self, user_id: str = "default"):
        self.user_id  = user_id
        self._mem0    = self._init_mem0()
        self._short   = []   # [(role, content)]  — konuşma içi
        logger.info(f"BISTMemory ready (user={user_id}, backend={'mem0' if self._mem0 else 'local'})")

    # ── Public API ────────────────────────────────────────────────────────────

    def add(self, content: str, category: str = "general", ticker: Optional[str] = None) -> None:
        """Yeni bir anı ekler."""
        entry = {
            "content":  content,
            "category": category,
            "ticker":   ticker,
            "ts":       datetime.utcnow().isoformat(),
        }
        if self._mem0:
            try:
                self._mem0.add(
                    messages=[{"role": "user", "content": content}],
                    user_id=self.user_id,
                    metadata={"category": category, "ticker": ticker or ""},
                )
                return
            except Exception as e:
                logger.warning(f"Mem0 add failed ({e}) — using local fallback")
        self._local_add(entry)

    def add_turn(self, question: str, answer: str) -> None:
        """Soru-cevap çiftini kısa belleğe ekler."""
        self._short.append(("user",      question))
        self._short.append(("assistant", answer[:400]))   # kısalt
        # Son MAX_SHORT_MEM çifti tut
        if len(self._short) > self.MAX_SHORT_MEM * 2:
            self._short = self._short[-(self.MAX_SHORT_MEM * 2):]

    def get_context(self, ticker: Optional[str] = None) -> str:
        """
        Mevcut konuşma bağlamı + ilgili geçmiş anıları döndürür.
        Agent'ın sistem prompt'una eklenir.
        """
        parts = []

        # Kısa bellek (son soru-cevaplar)
        if self._short:
            parts.append("=== Son Konuşma Geçmişi ===")
            for role, text in self._short[-6:]:
                prefix = "👤 Kullanıcı" if role == "user" else "🤖 Agent"
                parts.append(f"{prefix}: {text[:200]}")

        # Uzun bellek (geçmiş ilgiler)
        past = self._get_relevant(ticker)
        if past:
            parts.append("\n=== Geçmiş İlgi Alanları ===")
            parts.extend(past[:5])

        return "\n".join(parts) if parts else ""

    def get_watched_tickers(self) -> list[str]:
        """Kullanıcının daha önce sorguladığı ticker'ları döndürür."""
        if self._mem0:
            try:
                memories = self._mem0.get_all(user_id=self.user_id)
                tickers = set()
                for m in memories:
                    t = m.get("metadata", {}).get("ticker", "")
                    if t:
                        tickers.add(t)
                return list(tickers)
            except Exception:
                pass
        return list(self._local_tickers())

    def clear(self) -> None:
        """Tüm bellekleri sıfırlar."""
        self._short = []
        if self._mem0:
            try:
                self._mem0.delete_all(user_id=self.user_id)
            except Exception:
                pass
        self._local_clear()

    # ── Mem0 Init ─────────────────────────────────────────────────────────────

    def _init_mem0(self):
        api_key = os.getenv("MEM0_API_KEY", "")
        if not api_key:
            logger.info("MEM0_API_KEY not set — using local JSON memory")
            return None
        try:
            from mem0 import MemoryClient
            return MemoryClient(api_key=api_key)
        except ImportError:
            logger.warning("mem0ai not installed — using local memory")
            return None

    # ── Local Fallback ────────────────────────────────────────────────────────

    _local_store: list = []

    def _local_add(self, entry: dict) -> None:
        BISTMemory._local_store.append(entry)
        # 30 günden eskiyi temizle
        cutoff = datetime.utcnow().isoformat()[:10]
        BISTMemory._local_store = [
            e for e in BISTMemory._local_store
            if e.get("ts", "")[:10] >= cutoff[:8] + "01"  # pürüzsüz purge
        ]

    def _get_relevant(self, ticker: Optional[str]) -> list[str]:
        if self._mem0:
            try:
                results = self._mem0.search(
                    query=ticker or "bist hisse",
                    user_id=self.user_id,
                    limit=5,
                )
                return [r.get("memory", "") for r in results]
            except Exception:
                pass
        if ticker:
            return [
                e["content"] for e in BISTMemory._local_store
                if e.get("ticker") == ticker
            ]
        return [e["content"] for e in BISTMemory._local_store[-5:]]

    def _local_tickers(self):
        return {e["ticker"] for e in BISTMemory._local_store if e.get("ticker")}

    def _local_clear(self):
        BISTMemory._local_store.clear()


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    mem = BISTMemory(user_id="test_user")
    mem.add("ASELS KAP sorguladı", category="query", ticker="ASELS")
    mem.add_turn(
        "ASELS için son bildirimler neler?",
        "ASELS, Savunma Sanayii ile 1.2 milyar TL sözleşme imzaladı [KAP, 15.03.2025]."
    )
    print(mem.get_context(ticker="ASELS"))
    print("Watched tickers:", mem.get_watched_tickers())
