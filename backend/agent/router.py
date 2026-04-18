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
            _store = BISTVectorStore(persist_path=persist_path, embed_provider=embed_provider)
        except Exception as e:
            logger.error(f"VectorStore init failed: {e}")
            raise HTTPException(status_code=503, detail="VectorStore offline")
    return _store

# ── Schemas ──
class QueryRequest(BaseModel):
    question: str
    ticker:   Optional[str] = None

class QueryResponse(BaseModel):
    answer:          str
    sources:         List[dict]
    ticker:          Optional[str] = None
    market_data:     Optional[dict] = None
    disclaimer:      str = DISCLAIMER
    decision:        Optional[dict] = None
    consistency_note: Optional[str] = None
    iterations:      int = 1

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Safe Query Endpoint — Prevents 500 errors if market data fails."""
    
    from backend.agent.engine.bist_agent import BISTAgent
    from backend.agent.ingestion.market_data import MarketDataFetcher
    
    store = get_store()
    agent = BISTAgent(store=store)
    market_fetcher = MarketDataFetcher()
    
    ticker = req.ticker.upper() if req.ticker else None
    market_data = None

    if ticker:
        try:
            # 1. Market Summary (Safe catch)
            market_data = market_fetcher.get_summary(ticker)
            
            # 2. KAP Impact Analysis (Safe catch)
            docs = store.search(ticker, query="", limit=5)
            kap_dates = [d.metadata.get("date") for d in docs if d.metadata.get("source_type") == "kap" and d.metadata.get("date")]
            if kap_dates and market_data:
                latest_kap = sorted(kap_dates, reverse=True)[0]
                impact = market_fetcher.get_price_after_event(ticker, latest_kap)
                if impact:
                    market_data["kap_impact"] = {"date": latest_kap, **impact}
        except Exception as e:
            logger.warning(f"Non-critical Market Data fetch failed for {ticker}: {e}")

    # 3. Context string
    ctx = ""
    if market_data:
        ctx = f"--- MARKET DATA ({ticker}) ---\nPrice: {market_data.get('last_price')}, Change: %{market_data.get('daily_change')}\n"
        if "kap_impact" in market_data:
            ctx += f"Reaction to KAP ({market_data['kap_impact']['date']}): %{market_data['kap_impact']['stock_reaction']}\n"
        ctx += "------------------\n\n"

    try:
        result = agent.run(ctx + req.question, ticker=ticker)
        return QueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            ticker=ticker,
            market_data=market_data,
            decision=result.get("decision"),
            consistency_note=result.get("consistency_note")
        )
    except Exception as e:
        logger.error(f"Agent analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis engine failed")

@router.get("/status")
async def get_agent_status():
    return {"status": "online", "version": "4.2.1-stable"}
