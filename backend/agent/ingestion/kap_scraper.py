"""
KAP Scraper — Google News RSS Proxy Modu
kap.org.tr API'si bot koruması nedeniyle erişimi engellediğinden,
Google News RSS üzerinden "{TICKER} KAP bildirimi" araması yaparak
gerçek zamanlı KAP haberlerini çeker.

Yedek: DuckDuckGo HTML scraping
"""

import os
import json
import time
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
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
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


class KAPScraper:
    """
    KAP (Kamuyu Aydınlatma Platformu) scraper — Google News RSS Modu.

    kap.org.tr doğrudan API erişimini engellediğinden Google News RSS kullanılır.
    Kullanım:
        scraper = KAPScraper()
        docs = scraper.fetch_disclosures(ticker="ASELS", limit=30)
    """

    def __init__(self, save_dir: str = "data/raw/kap"):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def fetch_disclosures(
        self,
        ticker: str,
        limit: int = 40,
        disc_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Belirtilen ticker için KAP bildirimlerini Google News RSS üzerinden çeker.
        Depth artırıldı ve spesifik atama sorguları eklendi.
        """
        logger.info(f"Targeted KAP search for {ticker} (Depth: {limit})...")
        t_up = ticker.upper()
        
        # Çok açılı arama sorguları — kritik haberleri kaçırmamak için
        queries = [
            f'"{t_up}" KAP bildirimi',
            f'"{t_up}" atama müdür KAP',
            f'"{t_up}" yönetim kurulu değişikliği KAP',
            f'"{t_up}" özel durum açıklaması atama'
        ]

        docs = []
        seen_titles = set()
        seen_urls = set()

        for query in queries:
            if len(docs) >= limit:
                break
            fetched = self._fetch_google_news_rss(query, ticker, seen_titles)
            for f in fetched:
                if f['url'] not in seen_urls:
                    docs.append(f)
                    seen_urls.add(f['url'])

        # Sonuçlar azsa DuckDuckGo yedeği
        if len(docs) < 5:
            logger.warning(f"Low results for {ticker}, trying DDG fallback")
            ddg_docs = self._fetch_via_ddg(ticker, limit - len(docs), seen_titles)
            for d in ddg_docs:
                if d['url'] not in seen_urls:
                    docs.append(d)
                    seen_urls.add(d['url'])

        # Tarihe göre sırala (En yeni en üstte)
        docs.sort(key=lambda x: x.get('date', '0000-00-00'), reverse=True)
        docs = docs[:limit]

        if not docs:
            logger.warning(f"All sources failed for {ticker}, generating structural mock")
            docs = self._make_fallback(ticker)

        self._save(ticker, docs)
        return docs

    def get_company_list(self) -> list[dict]:
        """BIST şirketleri listesi — Google News'ten çekilemez, statik liste döner."""
        return [
            {"memberCode": t, "memberId": str(i)}
            for i, t in enumerate([
                "ASELS", "THYAO", "GARAN", "AKBNK", "ISCTR", "HALKB",
                "VAKBN", "TUPRS", "EREGL", "KCHOL", "SAHOL", "BIMAS",
                "TCELL", "FROTO", "TOASO", "PETKM", "SASA", "EKGYO",
            ], start=1)
        ]

    # ── Internal Methods ──────────────────────────────────────────────────────

    def _fetch_google_news_rss(
        self, query: str, ticker: str, seen_titles: set
    ) -> list[dict]:
        """Google News RSS'ten belirtilen sorgu için haberleri çeker."""
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=tr&gl=TR&ceid=TR:tr"

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            items = root.findall("./channel/item")
        except Exception as e:
            logger.warning(f"Google News RSS failed for query '{query}': {e}")
            return []

        docs = []
        for item in items:
            try:
                title_el = item.find("title")
                link_el = item.find("link")
                pub_el = item.find("pubDate")
                desc_el = item.find("description")

                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                link = link_el.text.strip() if link_el is not None and link_el.text else ""
                pub_raw = pub_el.text.strip() if pub_el is not None and pub_el.text else ""
                desc_raw = desc_el.text if desc_el is not None and desc_el.text else ""

                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                # HTML temizle
                desc_clean = re.sub(r"<[^>]+>", " ", desc_raw).strip()
                content = f"{title}. {desc_clean}" if desc_clean else title

                date_str = self._parse_rss_date(pub_raw)

                docs.append({
                    "ticker":      ticker.upper(),
                    "source_type": "kap",
                    "date":        date_str,
                    "institution": "KAP / BIST (Google News RSS)",
                    "title":       title,
                    "content":     content[:4000],
                    "url":         link,
                    "disc_type":   "KAP Bildirimi",
                })
                time.sleep(0.1)
            except Exception as e:
                logger.debug(f"Item parse error: {e}")
                continue

        return docs

    def _fetch_via_ddg(
        self, ticker: str, limit: int, seen_titles: set
    ) -> list[dict]:
        """DuckDuckGo HTML scraping ile KAP haberlerini çeker."""
        docs = []
        try:
            query = f"{ticker} KAP bildirimi özel durum"
            url = "https://html.duckduckgo.com/html/"
            ddg_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0"
            }
            resp = self.session.post(
                url, data={"q": query}, headers=ddg_headers, timeout=15
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            results = soup.select(".result")

            for res in results[:limit * 3]:
                a_tag = res.select_one(".result__a")
                snip_tag = res.select_one(".result__snippet")
                if not a_tag:
                    continue

                title = a_tag.get_text(strip=True)
                snippet = snip_tag.get_text(strip=True) if snip_tag else ""

                # KAP/borsa ile ilgili olanları filtrele
                combined = (title + " " + snippet).upper()
                if "KAP" not in combined and "BİLDİRİM" not in combined and ticker.upper() not in combined:
                    continue

                if title in seen_titles:
                    continue
                seen_titles.add(title)

                content = f"{title}. {snippet}" if snippet else title
                docs.append({
                    "ticker":      ticker.upper(),
                    "source_type": "kap",
                    "date":        datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "institution": "KAP / BIST (DuckDuckGo Proxy)",
                    "title":       title,
                    "content":     content[:4000],
                    "url":         a_tag.get("href", ""),
                    "disc_type":   "KAP Bildirimi",
                })
                if len(docs) >= limit:
                    break
                time.sleep(0.3)
        except Exception as e:
            logger.error(f"DDG fallback failed: {e}")
        return docs

    def _make_fallback(self, ticker: str) -> list[dict]:
        """Tüm kaynaklar başarısız olursa yapısal placeholder döner."""
        now = datetime.utcnow()
        return [
            {
                "ticker":      ticker.upper(),
                "source_type": "kap",
                "date":        (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "institution": "KAP (Fallback)",
                "title":       f"{ticker.upper()} — KAP Bildirimi (Veri Alınamadı)",
                "content": (
                    f"{ticker.upper()} için KAP bildirimleri şu an çekilemiyor. "
                    "Lütfen kap.org.tr adresini manuel ziyaret edin ya da daha sonra tekrar deneyin."
                ),
                "url":         f"https://www.kap.org.tr/tr/sirket/{ticker.lower()}",
                "disc_type":   "KAP Fallback",
            }
        ]

    @staticmethod
    def _parse_rss_date(raw: str) -> str:
        """RSS pubDate'i ISO 8601 formatına çevirir."""
        if not raw:
            return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            dt = parsedate_to_datetime(raw)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"]:
            try:
                return datetime.strptime(raw.strip()[:19], fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    def _save(self, ticker: str, docs: list[dict]) -> None:
        """Çekilen bildirimleri JSON olarak kaydeder."""
        path = os.path.join(self.save_dir, f"{ticker.lower()}_disclosures.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(docs)} disclosures → {path}")


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    scraper = KAPScraper()
    docs = scraper.fetch_disclosures("ASELS", limit=10)
    print(f"\nTotal: {len(docs)} docs")
    for d in docs:
        print(f"[{d['date'][:10]}] {d['title'][:90]}")
        print(f"  → {d['url'][:80]}")
