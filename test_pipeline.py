import os
import sys
import asyncio
os.environ["CHROMA_PATH"] = "./data/test_chroma"
from backend.agent.vectordb.chroma_store import BISTVectorStore
from backend.agent.embeddings.embedder import embed_documents
from backend.agent.ingestion.kap_scraper import KAPScraper

def main():
    print("1. KAP Scraper")
    scraper = KAPScraper()
    docs = scraper.fetch_disclosures("TRENJ", limit=2)
    print(f"Got {len(docs)} docs")

    print("\n2. Embedder")
    chunks = embed_documents(docs)
    print(f"Got {len(chunks)} embedded chunks")
    
    print("\n3. Chroma Store")
    store = BISTVectorStore()
    added = store.add_documents(chunks)
    print(f"Added {added} items cleanly!")

if __name__ == "__main__":
    main()
