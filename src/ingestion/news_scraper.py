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
    "googlenews": {
        "url": "https://news.google.com/rss/search?q={ticker}+hisse&hl=tr&gl=TR&ceid=TR:tr",
    },
    "mynet": {
        "search_url": "https://finans.mynet.com/borsa/hisseler/{ticker}/",
        "link_sel": "ul.mb-6 li a",
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
    RSS (Google News) ve HTML Fallback (Mynet) kullanır.
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
        Ticker ile ilgili haberleri çeker. prioritize highly current RSS data.
        """
        logger.info(f"Fetching news for {ticker} (limit={limit}, days_back={days_back})")
        docs = []

        # 1. Google News RSS (Reliable & Current)
        docs.extend(self._fetch_via_rss(ticker, limit // 2))

        # 2. Mynet / HTML Fallback
        if len(docs) < limit:
            docs.extend(self._fetch_via_html(ticker, limit - len(docs)))
    def fetch_news(self, ticker: str, limit: int = 15, days_back: int = 30) -> list[dict]:
        """Haberleri çeker - Önce Yerel Demo Verisi (Altın Paket) kontrol edilir."""
        ticker_up = ticker.upper().strip()
        logger.info(f"Checking for demo news for {ticker_up}")

        # 1. Altın Paket (Demo Haber) Kontrolü
        demo_path = f"data/demo_data/news/{ticker_up.lower()}.json"
        if os.path.exists(demo_path):
            try:
                with open(demo_path, "r", encoding="utf-8") as f:
                    logger.info(f"Loading GOLDEN PACK demo news for {ticker_up}")
                    return json.load(f)
            except Exception as e:
                logger.error(f"Demo news load failed for {ticker_up}: {e}")

        # 2. Eğer demo haberi yoksa, Normal Google News RSS kullanılır.
        logger.info(f"Fetching live news for {ticker_up}")
        news = self._fetch_via_rss(ticker_up, limit)
        
        if not news:
            logger.warning(f"Live news failed for {ticker_up}, using minimal fallback")
            news = self._make_fallback(ticker_up)

        logger.info(f"Fetched {len(news)} news articles for {ticker_up}")
        self._save(ticker_up, news)
        return news[:limit]

    # ── RSS Integration ────────────────────────────────────────────────────────

    def _fetch_via_rss(self, ticker: str, limit: int) -> list[dict]:
        """Google News RSS üzerinden güncel haber çeker."""
        docs = []
        url = NEWS_SOURCES["googlenews"]["url"].format(ticker=ticker)
        try:
            resp = self.session.get(url, timeout=15)
            # RSS is XML, but we use html.parser as a fallback if lxml is missing
            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("item")[:limit]
            for item in items:
                title = item.title.text if item.title else "Haber"
                link = item.link.text if item.link else ""
                date_str = item.pubdate.text if item.pubdate else "" # case insensitive in soup
                
                doc = {
                    "ticker":      ticker.upper(),
                    "source_type": "news",
                    "date":        self._normalize_date(date_str),
                    "institution": "Google News / " + (item.source.text if item.source else "Media"),
                    "title":       title,
                    "content":     title, # RSS results usually just titles, use as base
                    "url":         link,
                    "sentiment":   None,
                }
                docs.append(doc)
        except Exception as e:
            logger.warning(f"Google News RSS failed: {e}")
        return docs

    # ── Firecrawl Integration ─────────────────────────────────────────────────

    def _fetch_via_firecrawl(self, ticker: str, limit: int) -> list[dict]:
        """Firecrawl API kullanarak haber çeker."""
        docs = []
        search_queries = [ticker, f"{ticker} hisse news", f"{ticker} son durum"]

        for query in search_queries[:2]:
            try:
                resp = requests.post(
                    "https://api.firecrawl.dev/v1/search",
                    headers={
                        "Authorization": f"Bearer {self.firecrawl_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": query,
                        "limit": max(5, limit // 2),
                        "lang": "tr",
                        "country": "tr",
                        "searchOptions": {"excludeDomains": ["twitter.com","youtube.com"]},
                    },
                    timeout=20,
                )
                if resp.status_code == 200:
                    results = resp.json().get("data", [])
                    for r in results:
                        doc = self._build_doc(r, ticker, source="firecrawl")
                        if doc: docs.append(doc)
            except Exception as e:
                logger.warning(f"Firecrawl search failed for '{query}': {e}")
            time.sleep(0.5)

        return docs[:limit]

    # ── HTML Fallback ─────────────────────────────────────────────────────────

    def _fetch_via_html(self, ticker: str, limit: int) -> list[dict]:
        """Mynet ve Investing üzerinden doğrudan HTML scraping yapar."""
        docs = []
        
        # 1. Mynet Finans (Stable local source)
        url = NEWS_SOURCES["mynet"]["search_url"].format(ticker=ticker.lower())
        try:
            resp = self.session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select(NEWS_SOURCES["mynet"]["link_sel"])[:limit]
            for it in items:
                href = it.get("href", "")
                if not href.startswith("http"): href = "https://finans.mynet.com" + href
                doc = {
                    "ticker":      ticker.upper(),
                    "source_type": "news",
                    "date":        datetime.utcnow().isoformat() + "Z", # placeholder
                    "institution": "Mynet Finans",
                    "title":       it.get_text(strip=True),
                    "content":     "", 
                    "url":         href,
                    "sentiment":   None,
                }
                # Optional: deep fetch text
                doc["content"] = self._get_article_text(href)
                docs.append(doc)
                if len(docs) >= limit: break
                time.sleep(0.3)
        except Exception as e:
            logger.warning(f"Mynet scraping failed: {e}")

        # 2. Investing.com TR Fallback
        if len(docs) < limit:
            url = f"https://tr.investing.com/search/?q={ticker}&tab=news"
            try:
                resp = self.session.get(url, timeout=15)
                soup = BeautifulSoup(resp.text, "html.parser")
                articles = soup.select(".articleItem")[:limit]
                for art in articles:
                    link = art.select_one("a")
                    title_el = art.select_one(".articleTitle")
                    if not link: continue
                    href = link.get("href", "")
                    if href.startswith("/"): href = "https://tr.investing.com" + href
                    doc = {
                        "ticker":      ticker.upper(),
                        "source_type": "news",
                        "date":        datetime.utcnow().isoformat() + "Z",
                        "institution": "Investing.com TR",
                        "title":       title_el.get_text(strip=True) if title_el else "Haber",
                        "content":     self._get_article_text(href),
                        "url":         href,
                        "sentiment":   None,
                    }
                    docs.append(doc)
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
            resp = self.session.get(url, timeout=12)
            soup = BeautifulSoup(resp.text, "html.parser")
            # Multiple aggressive selectors for Turkish news portals
            for sel in ["article", ".article-content", ".news-content", ".content-article", ".WYSIWYG", "main"]:
                el = soup.select_one(sel)
                if el:
                    # Remove ads/related widgets
                    for bad in el.select(".ad, .recom-box, .social-share"): bad.decompose()
                    txt = el.get_text(separator="\n", strip=True)
                    if len(txt) > 200: return txt[:5000]
        except Exception:
            pass
        return ""

    @staticmethod
    def _normalize_date(raw: str) -> str:
        if not raw:
            return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        # Handle RSS Date format (e.g. Fri, 17 Apr 2026 12:00:00 GMT)
        for fmt in ["%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(raw.strip() if "%a" not in fmt else raw.strip(), fmt)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                continue
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

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
    docs = scraper.fetch_news("ASELS", limit=5)
    for d in docs[:5]:
        print(f"[{d['date']}] {d['title']}")
        print(f"  Url: {d['url'][:60]}...")
