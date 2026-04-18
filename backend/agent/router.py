import os
import logging
from typing import Optional, List, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)

DISCLAIMER = "\n\n⚠️ Bu sistem yatırım tavsiyesi vermez. Sunulan bilgiler yalnızca bilgi amaçlıdır."

_store = None
def get_store():
    global _store
    if _store is None:
        try:
            from backend.agent.vectordb.chroma_store import BISTVectorStore
            _store = BISTVectorStore(
                persist_path=os.getenv("CHROMA_PATH", "./data/chroma_db"),
                embed_provider=os.getenv("EMBED_PROVIDER", "default")
            )
        except Exception as e:
            logger.error(f"DB Init Error: {e}")
            raise HTTPException(status_code=503, detail="Database Offline")
    return _store

class QueryRequest(BaseModel):
    question: str
    ticker:   Optional[str] = None

class QueryResponse(BaseModel):
    answer:          str
    sources:         List[dict]
    ticker:          Optional[str] = None
    market_data:     Optional[dict] = None
    disclaimer:      str = DISCLAIMER
    decision:        Optional[Any] = None
    consistency_note: Optional[str] = None
    iterations:      int = 1

@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    from backend.agent.engine.bist_agent import BISTAgent
    from backend.agent.ingestion.market_data import MarketDataFetcher
    
    store = get_store()
    agent = BISTAgent(store=store)
    market_fetcher = MarketDataFetcher()
    
    ticker = req.ticker.upper() if req.ticker else None
    market_data = None

    if ticker:
        try:
            market_data = market_fetcher.get_summary(ticker)
            if not market_data or 'returns' not in market_data:
                market_data = {
                    "last_price": "N/A", "daily_change": 0, 
                    "returns": {"1w": "N/A", "1m": "N/A", "1y": "N/A"},
                    "bist100_comparison_1y": 0, "avg_volume_6m": "0", "stability": "BİLİNMİYOR", "volatility": 0
                }
            try:
                docs = store.search(ticker, query="", limit=5)
                k_dates = [d.metadata.get("date") for d in docs if d.metadata.get("source_type") == "kap" and d.metadata.get("date")]
                if k_dates and market_data and market_data.get("last_price") != "N/A":
                    latest = sorted(k_dates, reverse=True)[0]
                    impact = market_fetcher.get_price_after_event(ticker, latest)
                    if impact: market_data["kap_impact"] = {"date": latest, **impact}
            except: pass
        except Exception as e:
            logger.warning(f"Market fetch failed: {e}")
            market_data = {
                "last_price": "N/A", "daily_change": 0, 
                "returns": {"1w": "N/A", "1m": "N/A", "1y": "N/A"},
                "bist100_comparison_1y": 0, "avg_volume_6m": "0", "stability": "BİLİNMİYOR", "volatility": 0
            }

    # Step 2: Context Construction
    ctx = ""
    if market_data:
        ctx = f"--- MARKET OVERVIEW ({ticker}) ---\nPrice: {market_data.get('last_price')} TL, Relative: {market_data.get('bist100_comparison_1y')}%\n\n"

    # Step 3: Run Agent with error handling
    try:
        result = agent.run(ctx + req.question, ticker=ticker)
        
        # Ensure result is serializable
        return QueryResponse(
            answer=result.get("answer", "Analiz üretilemedi."),
            sources=result.get("sources", []),
            ticker=ticker,
            market_data=market_data,
            decision=result.get("decision"),
            consistency_note=result.get("consistency_note"),
            iterations=result.get("iterations", 1)
        )
    except Exception as e:
        logger.error(f"Agent analysis crashed: {e}")
        return QueryResponse(
            answer=f"Üzgünüm, analiz sırasında bir hata oluştu: {str(e)}",
            sources=[],
            ticker=ticker,
            market_data=market_data
        )

@router.get("/status")
async def get_status():
    return {"status": "online", "version": "4.2.2-resilient"}
