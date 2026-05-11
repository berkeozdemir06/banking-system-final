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
        limit: int = 30,
        disc_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Belirtilen ticker için KAP bildirimlerini Google News RSS üzerinden çeker.

        Args:
            ticker:    Hisse kodu (örn. "ASELS", "THYAO")
            limit:     Maksimum bildirim sayısı
            disc_type: Şu an kullanılmıyor (ilerleyen versiyonlar için)

        Returns:
            List of document dicts with mandatory metadata schema
        """
        logger.info(f"Fetching KAP disclosures for {ticker} via Google News RSS (limit={limit})")
        t_up = ticker.upper()

        # Birden fazla arama sorgusu ile kapsamlı veri çek
        queries = [
            f'"{t_up}" KAP bildirimi',
            f'"{t_up}" KAP özel durum',
            f'"{t_up}" borsa bildirim',
        ]

        docs = []
        seen_titles = set()

        # Try MKK API first!
        mkk_docs = self._fetch_via_mkk_api(ticker, limit)
        if mkk_docs:
            docs.extend(mkk_docs)
        else:
            for query in queries:
                if len(docs) >= limit:
                    break
                fetched = self._fetch_google_news_rss(query, ticker, seen_titles)
                docs.extend(fetched)

        # Google News yeterli sonuç vermediyse DuckDuckGo'ya düş
        if len(docs) < 3:
            logger.warning(f"Google News returned only {len(docs)} results for {ticker}, trying DDG fallback")
            ddg_docs = self._fetch_via_ddg(ticker, limit - len(docs), seen_titles)
            docs.extend(ddg_docs)

        docs = docs[:limit]

        if not docs:
            logger.warning(f"All sources failed for {ticker}, generating structural mock")
            docs = self._make_fallback(ticker)

        logger.info(f"Fetched {len(docs)} KAP disclosures for {ticker}")
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

    def _fetch_via_mkk_api(self, ticker: str, limit: int) -> list[dict]:
        import base64
        api_key = os.getenv("KAP_API_KEY", "917b1aeb-5b01-437e-b5af-c2866c1b09dc")
        api_secret = os.getenv("KAP_API_SECRET", "2aefda15-da34-4fdb-9a58-fc9904d51ba6")
        
        b64_auth = base64.b64encode(f"{api_key}:{api_secret}".encode('utf-8')).decode('utf-8')
        headers = {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}
        base_url = "https://apigwdev.mkk.com.tr/api/vyk"
        
        try:
            # Handle MKK test API delayed ticker updates
            mkk_ticker = "IPEKE" if ticker.upper() == "TRENJ" else ticker.upper()
            
            # 0. Get companyId
            members_res = self.session.get(f"{base_url}/members", headers=headers, timeout=10)
            if members_res.status_code != 200: return []
            company_id = None
            for m in members_res.json():
                if m.get("stockCode") == mkk_ticker:
                    company_id = m.get("id")
                    break
            if not company_id: return []

            # 1. Get last index
            res_idx = self.session.get(f"{base_url}/lastDisclosureIndex", headers=headers, timeout=10)
            if res_idx.status_code != 200: return []
            last_idx = int(res_idx.json().get("lastDisclosureIndex", 0))
            if not last_idx: return []
            
            # 2. Get recent disclosures (approx last 20000 index values)
            start_idx = max(0, last_idx - 100000)
            res_disc = self.session.get(f"{base_url}/disclosures", headers=headers, params={"disclosureIndex": str(start_idx), "companyId": str(company_id)}, timeout=15)
            if res_disc.status_code != 200: return []
            
            disclosures = res_disc.json()
            data_list = disclosures if isinstance(disclosures, list) else disclosures.get("data", [])
            if not data_list: return []
            
            docs = []
            # Reversed to get newest first
            for item in reversed(data_list):
                d_idx = item.get("disclosureIndex")
                if not d_idx: continue
                
                detail_res = self.session.get(f"{base_url}/disclosureDetail/{d_idx}", headers=headers, params={"fileType": "html"})
                if detail_res.status_code == 200:
                    detail = detail_res.json()
                    html_msgs = detail.get("htmlMessages", [{}])
                    content_str = html_msgs[0].get("tr", "") if html_msgs else ""
                    
                    docs.append({
                        "ticker": ticker.upper(),
                        "source_type": "kap",
                        "date": detail.get("time", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")),
                        "institution": "MKK KAP API",
                        "title": item.get("title", ""),
                        "content": content_str[:4000],
                        "url": detail.get("link", ""),
                        "disc_type": item.get("disclosureType", "KAP Bildirimi")
                    })
                    if len(docs) >= limit: break
            return docs
        except Exception as e:
            logger.error(f"MKK API Error: {e}")
            return []


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


