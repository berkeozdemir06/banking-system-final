from backend.agent.ingestion.kap_scraper import KAPScraper
scraper = KAPScraper()
docs = scraper.fetch_disclosures('TRENJ')
print("DOCS:", docs)
