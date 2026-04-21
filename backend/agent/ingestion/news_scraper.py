"""
News Scraper — Async Playwright & Firecrawl Ingestion
Türk finansal haber sitelerinden haber çeker.
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class NewsScraper:
    def __init__(self, firecrawl_api_key: Optional[str] = None, save_dir: str = "data/raw/news"):
        self.firecrawl_key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY", "")
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)

    async def fetch_news(self, ticker: str, limit: int = 15, days_back: int = 90) -> List[Dict]:
        """Ticker ile ilgili haberleri asenkron olarak çeker."""
        logger.info(f"Async news fetching for {ticker} (limit={limit})...")
        docs = []

        if self.firecrawl_key:
            docs = await self._fetch_via_firecrawl(ticker, limit)
        
        # Fallback to Google News RSS if no firecrawl or no results
        if not docs:
            docs = await self._fetch_via_rss(ticker, limit)

        cutoff = datetime.utcnow() - timedelta(days=days_back)
        docs = [d for d in docs if self._parse_date(d.get("date", "")) >= cutoff]

        self._save(ticker, docs)
        return docs[:limit]

    async def _fetch_via_firecrawl(self, ticker: str, limit: int) -> List[Dict]:
        docs = []
        queries = [f"{ticker} hisse haberleri", f"{ticker} KAP bildirimi", f"{ticker} borsa yorum"]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for q in queries[:2]:
                try:
                    resp = await client.post(
                        "https://api.firecrawl.dev/v1/search",
                        headers={"Authorization": f"Bearer {self.firecrawl_key.strip()}"},
                        json={
                            "query": q,
                            "limit": 5,
                            "lang": "tr",
                            "country": "tr",
                            "searchOptions": {"excludeDomains": ["twitter.com", "youtube.com"]}
                        }
                    )
                    if resp.status_code == 200:
                        results = resp.json().get("data", [])
                        for r in results:
                            docs.append({
                                "ticker": ticker.upper(),
                                "source_type": "news",
                                "date": r.get("publishedDate") or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "institution": r.get("siteName") or "News",
                                "title": r.get("title", "Haber"),
                                "content": r.get("markdown") or r.get("description", ""),
                                "url": r.get("url", ""),
                                "sentiment": None
                            })
                except Exception as e:
                    logger.warning(f"Firecrawl query '{q}' failed: {e}")
        return docs

    async def _fetch_via_rss(self, ticker: str, limit: int) -> List[Dict]:
        docs = []
        rss_url = f"https://news.google.com/rss/search?q={ticker}+hisse+borsa&hl=tr&gl=TR&ceid=TR:tr"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(rss_url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "xml")
                    for item in soup.find_all("item")[:limit]:
                        title = item.title.text if item.title else "Haber"
                        docs.append({
                            "ticker": ticker.upper(),
                            "source_type": "news",
                            "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), # Placeholder
                            "institution": "BIST News",
                            "title": title,
                            "content": title,
                            "url": item.link.text if item.link else ""
                        })
            except Exception as e:
                logger.warning(f"RSS fallback failed: {e}")
        return docs

    def _parse_date(self, ds: str) -> datetime:
        try: return datetime.strptime(ds[:19], "%Y-%m-%dT%H:%M:%S")
        except: return datetime.utcnow()

    def _save(self, ticker: str, docs: List[Dict]):
        path = os.path.join(self.save_dir, f"{ticker.lower()}_news.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = NewsScraper()
    asyncio.run(scraper.fetch_news("ASELS", limit=5))
