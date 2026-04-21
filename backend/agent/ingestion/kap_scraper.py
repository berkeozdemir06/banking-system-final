"""
KAP Scraper — Playwright Async Ingestion (Academic Simulation)
Directly scrapes Kamuyu Aydınlatma Platformu (kap.org.tr) for ground-truth data.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class KAPScraper:
    def __init__(self, save_dir: str = "data/raw/kap"):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)

    def get_company_list(self) -> list[dict]:
        """BIST100 ve popüler hisseleri içeren genişletilmiş liste."""
        tickers = [
            "AEFES", "AGHOL", "AKBNK", "AKCNS", "AKSA", "AKSEN", "ALARK", "ALBRK", "ARCLK", "ASELS",
            "ASTOR", "BERA", "BIENP", "BIMAS", "BRSAN", "BRYAT", "BUCIM", "CANTE", "CCOLA", "CWENE",
            "DOAS", "DOHOL", "EGEEN", "EKGYO", "ENJSA", "ENKAI", "EREGL", "EUPWR", "FROTO", "GARAN",
            "GESAN", "GUBRF", "GWIND", "HALKB", "HEKTS", "IPEKE", "ISCTR", "ISGYO", "IZMDC", "KARDM",
            "KCHOL", "KONTR", "KORDS", "KOZAA", "KOZAL", "KRDMD", "MAVI", "MGROS", "MIATK", "ODAS",
            "OTKAR", "OYAKC", "PETKM", "PGSUS", "QUAGR", "SAHOL", "SASA", "SISE", "SMRTG", "SOKM",
            "TAVHL", "TCELL", "THYAO", "TKFEN", "TOASO", "TSKB", "TTKOM", "TUPRS", "VAKBN", "VESBE",
            "VESTL", "YEOTK", "YKBNK", "ZOREN", "SAMAT"
        ]
        return [{"memberCode": t, "memberId": str(i)} for i, t in enumerate(sorted(tickers), start=1)]

    async def scrape(self, ticker: str, limit: int = 15) -> List[Dict]:
        """Alias for fetch_disclosures to match router interface."""
        return await self.fetch_disclosures(ticker, limit)

    async def fetch_disclosures(self, ticker: str, limit: int = 15) -> List[Dict]:
        """
        Navigates to KAP, filters for the ticker, and extracts disclosures asynchronously.
        """
        logger.info(f"Async Playwright directed KAP ingestion for {ticker}...")
        docs: List[Dict] = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            page.set_default_timeout(60000)
            
            try:
                # Navigate to KAP
                await page.goto('https://www.kap.org.tr/tr/', wait_until='domcontentloaded')
                
                # Search Ticker
                await page.fill('#all-search', ticker)
                await asyncio.sleep(2)
                
                try:
                    company_selector = f'#searchDiv a:has-text("{ticker}")'
                    if (await page.locator(company_selector).count()) > 0:
                        await page.click(company_selector)
                    else:
                        await page.keyboard.press('Enter')
                except:
                    await page.keyboard.press('Enter')
                
                await asyncio.sleep(4)
                
                # Navigate to 'Bildirimler' Tab
                try:
                    await page.click('a:has-text("Bildirimler")', timeout=15000)
                    await asyncio.sleep(2)
                except:
                    logger.warning("Bildirimler tab navigation timed out.")

                # Filter 'Son 1 ay'
                try:
                    await page.click('text="Son 1 ay"', timeout=10000)
                    await asyncio.sleep(1)
                    await page.click('button:has-text("Ara")')
                    await asyncio.sleep(3)
                except:
                    logger.warning("Filtering failed, scraping current view.")

                # Extract Table Rows
                rows_locator = page.locator('table tbody tr')
                count = await rows_locator.count()
                
                for i in range(count):
                    if len(docs) >= limit:
                        break
                    
                    row = rows_locator.nth(i)
                    cells = await row.locator('td').all_text_contents()
                    
                    if len(cells) >= 6:
                        dt_str = cells[1].strip()
                        dt_obj = self._parse_kap_date(dt_str)
                        
                        link_el = row.locator('a').first
                        url = "https://www.kap.org.tr" + (await link_el.get_attribute('href')) if (await link_el.count()) > 0 else ""
                        
                        docs.append({
                            "ticker":      ticker.upper(),
                            "source_type": "kap",
                            "date":        dt_obj.strftime("%Y-%m-%dT%H:%M:%SZ") if dt_obj else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "institution": "KAP Direct",
                            "title":       cells[5].strip(), # Konu
                            "content":     cells[6].strip() if len(cells) > 6 else "", # Özet Bilgi
                            "url":         url,
                            "disc_type":   cells[4].strip() # Tip
                        })
                
            except Exception as e:
                logger.error(f"KAP Playwright Scraper failed: {e}")
                docs = self._make_fallback(ticker)
            finally:
                await browser.close()

        if not docs:
           docs = self._make_fallback(ticker)

        self._save(ticker, docs)
        return docs

    def _parse_kap_date(self, raw: str) -> Optional[datetime]:
        now = datetime.now()
        if "Bugün" in raw:
            try:
                t_str = raw.replace("Bugün", "").strip()
                return datetime.combine(now.date(), datetime.strptime(t_str, "%H:%M").time())
            except: t = now
        elif "Dün" in raw:
            try:
                t_str = raw.replace("Dün", "").strip()
                return datetime.combine(now.date() - timedelta(days=1), datetime.strptime(t_str, "%H:%M").time())
            except: t = now - timedelta(days=1)
        
        for fmt in ["%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"]:
            try:
                return datetime.strptime(raw.strip()[:16], fmt)
            except: continue
        return None

    def _make_fallback(self, ticker: str) -> list[dict]:
        return [{
            "ticker":      ticker.upper(),
            "source_type": "kap",
            "date":        datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "institution": "KAP System",
            "title":       f"{ticker} Bildirimi Alınamadı",
            "content":     "KAP verilerine şu an erişilemiyor. Lütfen kap.org.tr'yi kontrol edin.",
            "url":         f"https://www.kap.org.tr/tr/sirket/{ticker.lower()}"
        }]

    def _save(self, ticker: str, docs: list[dict]) -> None:
        path = os.path.join(self.save_dir, f"{ticker.lower()}_disclosures.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    import sys
    import asyncio
    logging.basicConfig(level=logging.INFO)
    ticker = sys.argv[1] if len(sys.argv) > 1 else "ASELS"
    ks = KAPScraper()
    print(f"Testing {ticker}...")
    results = asyncio.run(ks.scrape(ticker, limit=5))
    print(f"Found {len(results)} results.")
    for r in results:
        print(f"- {r['date']} | {r['title']}")
