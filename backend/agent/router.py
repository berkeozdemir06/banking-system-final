import os
import logging
import tempfile
import shutil
import time
import re
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ── Router Config ──
router = APIRouter()
logger = logging.getLogger(__name__)

DISCLAIMER = (
    "\n\n⚠️ Bu sistem yatırım tavsiyesi vermez. "
    "Sunulan bilgiler yalnızca bilgi amaçlıdır ve "
    "al/sat kararı için kullanılamaz."
)

# ── Global Store Instance ─────────────────────────────────────────────────────
_store = None

def get_store():
    global _store
    if _store is None:
        try:
            from backend.agent.vectordb.chroma_store import BISTVectorStore
            persist_path   = os.getenv("CHROMA_PATH", "./data/chroma_db")
            embed_provider = os.getenv("EMBED_PROVIDER", "default")
            os.makedirs(persist_path, exist_ok=True)
            _store = BISTVectorStore(
                persist_path=persist_path,
                embed_provider=embed_provider,
            )
        except Exception as e:
            logger.error(f"VectorStore init failed: {e}")
            raise HTTPException(status_code=503, detail=f"VectorStore init failed: {str(e)}")
    return _store

# ── Schemas ───────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., description="Kullanıcı sorusu")
    ticker:   Optional[str] = Field(None, description="Hisse filtresi, örn. 'ASELS'")

class AgentDecisionModel(BaseModel):
    sources_selected: List[str]
    time_horizon: str
    needs_reretrieval: bool
    reasoning: str

class QueryResponse(BaseModel):
    answer:          str
    sources:         List[dict]
    ticker:          Optional[str]
    market_data:     Optional[dict] = None
    disclaimer:      str = DISCLAIMER
    decision:        Optional[AgentDecisionModel] = None
    consistency_note: Optional[str] = None
    iterations:      int = 1

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Ana RAG endpoint — pazar verisi ve KAP etki analizi eklenmiş versiyon."""
    
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return JSONResponse(status_code=500, content={"error": "Sistem hatası: GROQ_API_KEY eksik."})

    from backend.agent.engine.bist_agent import BISTAgent
    from backend.agent.ingestion.market_data import MarketDataFetcher
    
    store = get_store()
    agent = BISTAgent(store=store)
    market_fetcher = MarketDataFetcher()
    
    ticker = req.ticker.upper() if req.ticker else None
    market_data = None

    if ticker:
        # 1. Temel Market Verileri
        market_data = market_fetcher.get_summary(ticker)
        
        # 2. Auto-Ingest
        stats = store.get_stats()
        ticker_count = stats.get("by_ticker", {}).get(ticker, 0)
        if ticker_count == 0:
            from backend.agent.ingestion.kap_scraper import KAPScraper
            from backend.agent.ingestion.rss_scraper import RSSNewsScraper
            from backend.agent.embeddings.embedder import embed_documents
            kap = KAPScraper(); kap_docs = kap.fetch_disclosures(ticker, limit=20)
            if kap_docs: store.add_documents(embed_documents(kap_docs))
            rss = RSSNewsScraper(); news_docs = rss.fetch_news(ticker, limit=15)
            if news_docs: store.add_documents(embed_documents(news_docs))

        # 3. KAP Etki Analizi (Son KAP Tarihini Bul)
        try:
            docs = store.search(ticker, query="", limit=5)
            kap_dates = [d.metadata.get("date") for d in docs if d.metadata.get("source_type") == "kap" and d.metadata.get("date")]
            if kap_dates:
                latest_kap = sorted(kap_dates, reverse=True)[0]
                impact = market_fetcher.get_price_after_event(ticker, latest_kap)
                if impact:
                    market_data["kap_impact"] = {
                        "date": latest_kap,
                        **impact
                    }
        except: pass

    # 4. Context Oluştur
    context_prefix = ""
    if market_data:
        context_prefix = (
            f"--- GÜNCEL PİYASA VERİLERİ ({ticker}) ---\n"
            f"Fiyat: {market_data.get('last_price')} TL, Günlük Değişim: %{market_data.get('daily_change')}\n"
            f"Getiriler: 1H: %{market_data['returns']['1w']}, 1A: %{market_data['returns']['1m']}, 1Y: %{market_data['returns']['1y']}\n"
            f"BIST 100 Karşılaştırması (1Y): %{market_data.get('bist100_comparison_1y')} fark\n"
            f"İstikrar: {market_data.get('stability')}\n"
        )
        if "kap_impact" in market_data:
            ki = market_data["kap_impact"]
            context_prefix += f"Son KAP Bildirimi Etkisi ({ki['date']}): Hisse %{ki['stock_reaction']}, Endeks %{ki['index_reaction']}\n"
        context_prefix += "-------------------------------------------\n\n"

    try:
        result = agent.run(context_prefix + req.question, ticker=ticker)
        return QueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            ticker=ticker,
            market_data=market_data,
            decision=result.get("decision"),
            consistency_note=result.get("consistency_note"),
            iterations=result.get("iterations", 1)
        )
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_agent_status():
    store = get_store()
    stats = store.get_stats()
    return {"status": "online", "vectorstore": stats, "version": "4.2.0-impact-aware"}
