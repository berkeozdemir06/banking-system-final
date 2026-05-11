import re

with open('backend/agent/ingestion/kap_scraper.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_content = """import os
import json
import logging
import asyncio
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class KAPScraper:
    def __init__(self, firecrawl_api_key: Optional[str] = None, save_dir: str = "data/raw/kap"):
        pass

    async def scrape(self, ticker: str, limit: int = 20) -> List[Dict]:
        from src.ingestion.kap_scraper import KAPScraper as RealKAPScraper
        scraper = RealKAPScraper()
        # run synchronous fetch in thread
        docs = await asyncio.to_thread(scraper.fetch_disclosures, ticker, limit)
        return docs
"""

with open('backend/agent/ingestion/kap_scraper.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
