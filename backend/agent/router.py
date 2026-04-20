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
            # Auto-ingest latest news/KAP for this ticker on-the-fly to ensure DB is populated
            try:
                from backend.agent.ingestion.news_scraper import NewsScraper
                from backend.agent.ingestion.kap_scraper import KAPScraper
                
                # Sınırları düşük tutarak hızlıca son 15-20 haberi çekip DB'ye atalım
                if store.collection.count() < 100 or len(store.search(ticker, query="", limit=1)) == 0:
                    ns = NewsScraper()
                    ks = KAPScraper()
                    n_docs = ns.scrape(ticker, limit=10, days_back=30)
                    k_docs = ks.scrape(ticker, limit=15)
                    # VectorStore'a yükle
                    store.add_documents(n_docs + k_docs)
            except Exception as e:
                logger.warning(f"On-the-fly ingest failed: {e}")

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
        
        return QueryResponse(
            answer=getattr(result, "answer", "Analiz üretilemedi."),
            sources=getattr(result, "sources_used", []),
            ticker=ticker,
            market_data=market_data,
            decision=getattr(result, "decision", None),
            consistency_note=getattr(result, "consistency_note", ""),
            iterations=getattr(result, "iterations", 1)
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
    store = None
    total_chunks = 0
    try:
        store = get_store()
        total_chunks = store.collection.count()
    except: pass

    groq_key = bool(os.getenv("GROQ_API_KEY"))
    return {
        "status": "online",
        "version": "4.2.2-resilient",
        "database": {"total_chunks": total_chunks},
        "environment": {"groq_api_key": groq_key}
    }


# ─── Intelligence Endpoints (Analytical Dashboards) ───────────────────────────

class IntelligenceReq(BaseModel):
    ticker:    str
    kap_limit: int = 15

@router.post("/intelligence/analyze")
async def intelligence_analyze(req: IntelligenceReq):
    try:
        from backend.agent.ingestion.kap_intelligence import full_analysis
        result = full_analysis(req.ticker.upper(), kap_limit=req.kap_limit)
        for ann in result.get("announcements", []):
            ann.pop("date_obj", None)
        return result
    except Exception as e:
        logger.error(f"intelligence_analyze failed: {e}")
        raise HTTPException(500, f"Analiz hatası: {str(e)}")

@router.get("/intelligence/report")
async def intelligence_report(ticker: str = "ASELS", kap_limit: int = 15):
    from fastapi.responses import StreamingResponse
    try:
        from backend.agent.ingestion.kap_intelligence import full_analysis, generate_pdf_report
        result = full_analysis(ticker.upper(), kap_limit=kap_limit)
        pdf_bytes = generate_pdf_report(result)
        fname = f"OZAS_{ticker.upper()}_Report_{result['generated_at'][:10]}.pdf"
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={fname}"}
        )
    except Exception as e:
        logger.error(f"intelligence_report failed: {e}")
        raise HTTPException(500, f"Rapor hatası: {str(e)}")

# ─── Ingestion Endpoints (Populating ChromaDB) ────────────────────────────────

class IngestReq(BaseModel):
    ticker: str
    limit:  int = 15
    days_back: int = 30

@router.post("/ingest/kap")
async def ingest_kap(req: IngestReq):
    from backend.agent.ingestion.kap_scraper import KAPScraper
    store = get_store()
    try:
        ks = KAPScraper()
        docs = ks.scrape(req.ticker, limit=req.limit)
        store.add_documents(docs)
        return {"status": "success", "docs": len(docs), "chunks_added": len(docs)}
    except Exception as e:
        logger.error(f"KAP Ingest failed: {e}")
        raise HTTPException(500, str(e))

@router.post("/ingest/news")
async def ingest_news(req: IngestReq):
    from backend.agent.ingestion.news_scraper import NewsScraper
    store = get_store()
    try:
        ns = NewsScraper()
        docs = ns.fetch_news(req.ticker, limit=req.limit, days_back=req.days_back)
        store.add_documents(docs)
        return {"status": "success", "count": len(docs), "docs": docs}
    except Exception as e:
        logger.error(f"News Ingest failed: {e}")
        raise HTTPException(500, str(e))

from fastapi import UploadFile, File, Form
@router.post("/ingest/pdf")
async def ingest_pdf(file: UploadFile = File(...), ticker: str = Form(...), institution: str = Form("Report")):
    from backend.agent.ingestion.pdf_parser import BISTPDFParser
    store = get_store()
    try:
        # Save temp file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
        
        parser = BISTPDFParser()
        docs = parser.parse(tmp_path, ticker=ticker, institution=institution)
        store.add_documents(docs)
        os.unlink(tmp_path)
        return {"status": "success", "pages": 1, "chunks_added": len(docs)}
    except Exception as e:
        logger.error(f"PDF Ingest failed: {e}")
        raise HTTPException(500, str(e))
