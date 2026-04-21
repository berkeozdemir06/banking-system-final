"""
KAP Scraper — Firecrawl & Async Ingestion
Directly scrapes Kamuyu Aydınlatma Platformu (kap.org.tr) using Firecrawl for maximum stability.
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import httpx

logger = logging.getLogger(__name__)

class KAPScraper:
    def __init__(self, firecrawl_api_key: Optional[str] = None, save_dir: str = "data/raw/kap"):
        self.firecrawl_key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY", "")
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)

    async def scrape(self, ticker: str, limit: int = 15) -> List[Dict]:
        """Firecrawl kullanarak KAP bildirimlerini çeker."""
        logger.info(f"Firecrawl-powered KAP ingestion for {ticker}...")
        docs = []

        if not self.firecrawl_key:
            logger.warning("No Firecrawl key found, falling back to empty list.")
            return self._make_fallback(ticker)

        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                # KAP arama sayfasını Firecrawl ile "crawl" ediyoruz
                # Search query: ticker site:kap.org.tr
                resp = await client.post(
                    "https://api.firecrawl.dev/v1/search",
                    headers={"Authorization": f"Bearer {self.firecrawl_key.strip()}"},
                    json={
                        "query": f"{ticker} site:kap.org.tr son bildirimler",
                        "limit": limit,
                        "lang": "tr",
                        "country": "tr"
                    }
                )
                
                if resp.status_code == 200:
                    results = resp.json().get("data", [])
                    for r in results:
                        docs.append({
                            "ticker":      ticker.upper(),
                            "source_type": "kap",
                            "date":        datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "institution": "KAP Direct (Firecrawl)",
                            "title":       r.get("title", f"{ticker} Bildirimi"),
                            "content":     r.get("markdown") or r.get("description", ""),
                            "url":         r.get("url", ""),
                            "sentiment":   None
                        })
                else:
                    logger.error(f"Firecrawl KAP search failed: {resp.status_code}")
                    docs = self._make_fallback(ticker)
            except Exception as e:
                logger.error(f"KAP Ingestion error: {e}")
                docs = self._make_fallback(ticker)

        self._save(ticker, docs)
        return docs

    def _make_fallback(self, ticker: str) -> list[dict]:
        return [{
            "ticker":      ticker.upper(),
            "source_type": "kap",
            "date":        datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "institution": "KAP System",
            "title":       f"{ticker} Bildirimi Alınamadı",
            "content":     f"KAP verilerine şu an erişilemiyor. Lütfen https://www.kap.org.tr/tr/sirket-bilgileri/ozet/{ticker.upper()} adresini kontrol edin.",
            "url":         f"https://www.kap.org.tr/tr/sirket-bilgileri/ozet/{ticker.lower()}"
        }]

    def _save(self, ticker: str, docs: list[dict]) -> None:
        path = os.path.join(self.save_dir, f"{ticker.lower()}_disclosures.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
