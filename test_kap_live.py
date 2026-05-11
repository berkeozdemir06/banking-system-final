import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # KAP search for SAMAT
        url = "https://www.kap.org.tr/tr/sirket-bilgileri/genel/1552-saray-matbaacilik-kagitcilik-kirtasiyecilik-ticaret-ve-sanayi-a-s"
        await page.goto(url, timeout=30000)
        await page.wait_for_selector(".disclosure-list", timeout=10000)
        
        items = await page.query_selector_all(".disclosure-row")
        print(f"Found {len(items)} disclosures on page")
        for item in items[:3]:
            title = await item.query_selector(".disclosure-title")
            date = await item.query_selector(".disclosure-date")
            if title and date:
                print(f"[{await date.inner_text()}] {await title.inner_text()}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
