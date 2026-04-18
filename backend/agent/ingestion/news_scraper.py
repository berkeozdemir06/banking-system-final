"""
News Scraper — Türk finansal haber sitelerinden haber çeker.

Hedef siteler:
  - Hürriyet Ekonomi  (hurriyet.com.tr/ekonomi)
  - Mynet Finans       (finans.mynet.com)
  - Investing.com TR   (tr.investing.com/news)
  - Bloomberg HT       (bloomberght.com)

Firecrawl API kullanılarak HTML → temiz metin dönüşümü yapılır.
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# ── News sources ──────────────────────────────────────────────────────────────
NEWS_SOURCES = {
    "hurriyet": {
        "search_url": "https://www.hurriyet.com.tr/ekonomi/",
        "article_sel": "a.card-title-link",
        "content_sel": ".content-article",
        "date_sel": "time",
    },
    "bloomberght": {
        "search_url": "https://www.bloomberght.com/hisseler/{ticker}",
        "article_sel": ".news-list a",
        "content_sel": ".news-detail",
        "date_sel": ".news-date",
    },
}


# ── Main Scraper ──────────────────────────────────────────────────────────────
class NewsScraper:
    """
    Türk finansal haber scraper'ı.

    Kullanım:
        scraper = NewsScraper(firecrawl_api_key="...")
        docs = scraper.fetch_news(ticker="ASELS", limit=20)
    """

    def __init__(
        self,
        firecrawl_api_key: Optional[str] = None,
        save_dir: str = "data/raw/news",
    ):
        self.firecrawl_key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY", "")
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ── Public API ────────────────────────────────────────────────────────────

    def fetch_news(
        self,
        ticker: str,
        limit: int = 30,
        days_back: int = 90,
    ) -> list[dict]:
        """
        Ticker ile ilgili haberleri çeker.

        Args:
            ticker:    Hisse kodu (örn. "ASELS")
            limit:     Maksimum haber sayısı
            days_back: Kaç gün geriye bakılacak

        Returns:
            List of document dicts with mandatory metadata schema
        """
        logger.info(f"Fetching news for {ticker} (limit={limit}, days_back={days_back})")
        docs = []

        # Firecrawl varsa kullan
        if self.firecrawl_key:
            docs = self._fetch_via_firecrawl(ticker, limit)
        else:
            # Fallback: doğrudan HTML parse
            docs = self._fetch_via_html(ticker, limit)

        cutoff = datetime.utcnow() - timedelta(days=days_back)
        docs = [d for d in docs if self._parse_date(d["date"]) >= cutoff]

        logger.info(f"Fetched {len(docs)} news articles for {ticker}")
        self._save(ticker, docs)
        return docs

    # ── Firecrawl Integration ─────────────────────────────────────────────────

    def _fetch_via_firecrawl(self, ticker: str, limit: int) -> list[dict]:
        """Firecrawl API kullanarak haber çeker."""
        docs = []
        search_queries = [
            f"{ticker} yönetim kurulu değişikliği",
            f"{ticker} hisse haberleri",
            f"{ticker} istifa atama",
            f"{ticker} KAP bildirimleri"
        ]

        for query in search_queries[:3]:
            try:
                resp = requests.post(
                    "https://api.firecrawl.dev/v1/search",
                    headers={
                        "Authorization": f"Bearer {self.firecrawl_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": query,
                        "limit": limit // 2,
                        "lang": "tr",
                        "country": "tr",
                        "searchOptions": {"excludeDomains": ["twitter.com","youtube.com"]},
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    results = resp.json().get("data", [])
                    for r in results:
                        doc = self._build_doc(r, ticker, source="firecrawl")
                        if doc:
                            docs.append(doc)
            except Exception as e:
                logger.warning(f"Firecrawl search failed for '{query}': {e}")
            time.sleep(0.5)

        return docs[:limit]

    # ── HTML Fallback ─────────────────────────────────────────────────────────

    def _fetch_via_html(self, ticker: str, limit: int) -> list[dict]:
        """Firecrawl olmadan doğrudan HTML scraping yapar."""
        docs = []

        # Investing.com TR arama
        url = f"https://tr.investing.com/search/?q={ticker}&tab=news"
        try:
            resp = self.session.get(url, timeout=20)
            soup = BeautifulSoup(resp.text, "lxml")
            articles = soup.select(".articleItem")[:limit]
            for art in articles:
                link = art.select_one("a")
                title_el = art.select_one(".articleTitle")
                date_el = art.select_one(".date")
                if not link:
                    continue
                href = link.get("href", "")
                href = "https://tr.investing.com" + href if href.startswith("/") else href
                doc = {
                    "ticker":      ticker.upper(),
                    "source_type": "news",
                    "date":        self._normalize_date(date_el.text if date_el else ""),
                    "institution": "Investing.com TR",
                    "title":       title_el.get_text(strip=True) if title_el else "Haber",
                    "content":     self._get_article_text(href),
                    "url":         href,
                    "sentiment":   None,
                }
                docs.append(doc)
                time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Investing.com scraping failed: {e}")

        return docs[:limit]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_doc(self, raw: dict, ticker: str, source: str) -> Optional[dict]:
        try:
            return {
                "ticker":      ticker.upper(),
                "source_type": "news",
                "date":        self._normalize_date(raw.get("publishedDate") or raw.get("date", "")),
                "institution": raw.get("siteName") or raw.get("source", source),
                "title":       raw.get("title", ""),
                "content":     raw.get("markdown") or raw.get("description") or raw.get("content", ""),
                "url":         raw.get("url", ""),
                "sentiment":   None,
            }
        except Exception:
            return None

    def _get_article_text(self, url: str) -> str:
        try:
            resp = self.session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for sel in ["article", ".articlePage", ".WYSIWYG", "main"]:
                el = soup.select_one(sel)
                if el:
                    return el.get_text(separator="\n", strip=True)[:5000]
        except Exception:
            pass
        return ""

    @staticmethod
    def _normalize_date(raw: str) -> str:
        if not raw:
            return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d", "%b %d, %Y"]:
            try:
                return datetime.strptime(raw.strip()[:19], fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue
        return raw

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        try:
            return datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return datetime.min

    def _save(self, ticker: str, docs: list[dict]) -> None:
        path = os.path.join(self.save_dir, f"{ticker.lower()}_news.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(docs)} news articles → {path}")


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    scraper = NewsScraper()
    docs = scraper.fetch_news("THYAO", limit=5)
    for d in docs[:3]:
        print(f"[{d['date']}] {d['title'][:80]}")
        print(f"  source: {d['institution']}")
        print()
