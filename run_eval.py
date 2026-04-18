import os
from dotenv import load_dotenv

# dotenv'yi backend dizininden yükle
load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))

from backend.agent.ingestion.kap_scraper import KAPScraper
from backend.agent.ingestion.news_scraper import NewsScraper
from backend.agent.embeddings.embedder import embed_documents
from backend.agent.vectordb.chroma_store import BISTVectorStore

def run():
    print("Agent Ingestion Başlıyor...")
    store = BISTVectorStore(persist_path="./data/chroma_db", embed_provider="default")
    
    # 1. KAP Ingestion
    print("\n--- KAP Ingestion (ASELS) ---")
    kap = KAPScraper()
    docs = kap.fetch_disclosures("ASELS", limit=5)
    chunks = embed_documents(docs, provider="default")
    added = store.add_documents(chunks)
    print(f"KAP eklendi: {added} chunk")
    
    # 2. RAGAS Eval Testini Başlat
    print("\n--- RAGAS Evaluation Başlıyor ---")
    os.system("python3 backend/agent/evaluation/ragas_eval.py")

if __name__ == "__main__":
    run()
