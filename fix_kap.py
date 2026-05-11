import re

with open('src/ingestion/kap_scraper.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the broken _fetch_via_mkk_api at the bottom
bad_mkk_pattern = r"    def _fetch_via_mkk_api\(self, ticker: str, limit: int\) -> list\[dict\]:.*"
mkk_func = re.search(bad_mkk_pattern, content, flags=re.DOTALL)
if mkk_func:
    content = content.replace(mkk_func.group(0), "")
    
    # Re-insert it right before `def _fetch_google_news_rss`
    insert_target = "    def _fetch_google_news_rss("
    if insert_target in content:
        content = content.replace(insert_target, mkk_func.group(0) + "\n\n" + insert_target)

with open('src/ingestion/kap_scraper.py', 'w', encoding='utf-8') as f:
    f.write(content)
