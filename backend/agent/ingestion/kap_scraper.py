\"\"\"
KAP Scraper — Playwright Direct Ingestion (Academic Simulation)
Directly scrapes Kamuyu Aydınlatma Platformu (kap.org.tr) for ground-truth data.
\"\"\"

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

class KAPScraper:
    def __init__(self, save_dir: str = "data/raw/kap"):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)

    def scrape(self, ticker: str, limit: int = 15) -> list[dict]:
        \"\"\"Alias for fetch_disclosures to match router interface.\"\"\"
        return self.fetch_disclosures(ticker, limit)

    def fetch_disclosures(self, ticker: str, limit: int = 15) -> list[dict]:
        \"\"\"
        Navigates to KAP, filters for the ticker, and extracts disclosures.
        \"\"\"
        logger.info(f"Playwright directed KAP ingestion for {ticker}...")
        docs: list[dict] = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                )
                page = context.new_page()
                page.set_default_timeout(60000)
                
                # Navigate to KAP
                page.goto('https://www.kap.org.tr/tr/', wait_until='domcontentloaded')
                
                # Step 1: Search Ticker
                page.fill('#all-search', ticker)
                page.wait_for_timeout(2000)
                
                # Select from dropdown
                try:
                    company_selector = f'#searchDiv a:has-text(\"{ticker}\")'
                    if page.locator(company_selector).count() > 0:
                        page.click(company_selector)
                    else:
                        page.keyboard.press('Enter')
                except:
                    page.keyboard.press('Enter')
                
                page.wait_for_timeout(4000)
                
                # Navigate to 'Bildirimler' Tab
                try:
                    page.click('a:has-text(\"Bildirimler\")', timeout=15000)
                    page.wait_for_timeout(2000)
                except:
                    logger.warning(\"Bildirimler tab navigation timed out.\")

                # Filter 'Son 1 ay'
                try:
                    page.click('text=\"Son 1 ay\"', timeout=10000)
                    page.wait_for_timeout(500)
                    page.click('button:has-text(\"Ara\")')
                    page.wait_for_timeout(3000)
                except:
                    logger.warning(\"Filtering failed, scraping current view.\")

                # Extract Table Rows
                rows = page.locator('table tbody tr').all()
                for row in rows:
                    if len(docs) >= limit:
                        break
                    cells = row.locator('td').all_text_contents()
                    if len(cells) >= 6:
                        dt_str = cells[1].strip()
                        dt_obj = self._parse_kap_date(dt_str)
                        
                        link_el = row.locator('a').first
                        url = \"https://www.kap.org.tr\" + link_el.get_attribute('href') if link_el.count() > 0 else \"\"
                        
                        docs.append({
                            \"ticker\":      ticker.upper(),
                            \"source_type\": \"kap\",
                            \"date\":        dt_obj.strftime(\"%Y-%m-%dT%H:%M:%SZ\") if dt_obj else datetime.utcnow().strftime(\"%Y-%m-%dT%H:%M:%SZ\"),
                            \"institution\": \"KAP Direct\",
                            \"title\":       cells[5].strip(), # Konu
                            \"content\":     cells[6].strip() if len(cells) > 6 else \"\", # Özet Bilgi
                            \"url\":         url,
                            \"disc_type\":   cells[4].strip() # Tip
                        })
                
                browser.close()
        except Exception as e:
            logger.error(f"KAP Playwright Scraper failed: {e}")
            return self._make_fallback(ticker)

        if not docs:
            return self._make_fallback(ticker)

        self._save(ticker, docs)
        return docs

    def _parse_kap_date(self, raw: str) -> Optional[datetime]:
        now = datetime.now()
        if \"Bugün\" in raw:
            try:
                t_str = raw.replace(\"Bugün\", \"\").strip()
                return datetime.combine(now.date(), datetime.strptime(t_str, \"%H:%M\").time())
            except: t = now
        elif \"Dün\" in raw:
            try:
                t_str = raw.replace(\"Dün\", \"\").strip()
                return datetime.combine(now.date() - timedelta(days=1), datetime.strptime(t_str, \"%H:%M\").time())
            except: t = now - timedelta(days=1)
        
        for fmt in [\"%d.%m.%Y %H:%M\", \"%d.%m.%Y\", \"%Y-%m-%d\"]:
            try:
                return datetime.strptime(raw.strip()[:16], fmt)
            except: continue
        return None

    def _make_fallback(self, ticker: str) -> list[dict]:
        return [{
            \"ticker\":      ticker.upper(),
            \"source_type\": \"kap\",
            \"date\":        datetime.utcnow().strftime(\"%Y-%m-%dT%H:%M:%SZ\"),
            \"institution\": \"KAP System\",
            \"title\":       f\"{ticker} Bildirimi Alınamadı\",
            \"content\":     f\"KAP verilerine şu an erişilemiyor. Lütfen kap.org.tr'yi kontrol edin.\",
            \"url\":         f\"https://www.kap.org.tr/tr/sirket/{ticker.lower()}\"
        }]

    def _save(self, ticker: str, docs: list[dict]) -> None:
        path = os.path.join(self.save_dir, f\"{ticker.lower()}_disclosures.json\")
        with open(path, \"w\", encoding=\"utf-8\") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
