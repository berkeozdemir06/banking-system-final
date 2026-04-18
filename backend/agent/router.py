import os
import logging
import tempfile
import shutil
import time
from typing import Optional
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

class IngestKAPRequest(BaseModel):
    ticker: str
    limit:  int = Field(5, ge=1, le=100)

class IngestNewsRequest(BaseModel):
    ticker:    str
    limit:     int = Field(20, ge=1, le=100)
    days_back: int = Field(90, ge=1, le=365)

class AgentDecisionModel(BaseModel):
    sources_selected: list[str]
    time_horizon: str
    needs_reretrieval: bool
    reasoning: str

class QueryResponse(BaseModel):
    answer:    str
    sources:   list[dict]
    ticker:    Optional[str]
    disclaimer: str = DISCLAIMER
    decision: Optional[AgentDecisionModel] = None
    consistency_note: Optional[str] = None
    iterations: int = 1

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_agent_status():
    try:
        store = get_store()
        stats = store.get_stats()
    except Exception as e:
        return {"status": "degraded", "error": str(e), "vectorstore": {}}
    return {
        "status": "online",
        "message": "OZAS Finance Agent is operational.",
        "vectorstore": stats
    }


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Ana RAG endpoint — soru sor, kaynaklı cevap al. BISTAgent kullanılır."""
    from backend.agent.engine.bist_agent import BISTAgent
    store = get_store()
    agent = BISTAgent(store=store)
    try:
        result = agent.run(question=req.question, ticker=req.ticker)
    except Exception as e:
        import traceback
        logger.error(f"Agent execution failed: {e}\n{traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": f"Ajan hatası: {str(e)}", "trace": traceback.format_exc()})

    sources = [
        {
            "ticker":      r["metadata"].get("ticker"),
            "source_type": r["metadata"].get("source_type"),
            "date":        r["metadata"].get("date", "")[:10],
            "institution": r["metadata"].get("institution"),
            "url":         r["metadata"].get("url"),
        }
        for r in result.sources_used
    ]

    decision_data = None
    if result.decision:
        decision_data = AgentDecisionModel(
            sources_selected=result.decision.sources_selected,
            time_horizon=result.decision.time_horizon,
            needs_reretrieval=result.decision.needs_reretrieval,
            reasoning=result.decision.reasoning,
        )

    return QueryResponse(
        answer=result.answer,
        sources=sources,
        ticker=req.ticker,
        disclaimer=DISCLAIMER,
        decision=decision_data,
        consistency_note=result.consistency_note,
        iterations=result.iterations,
    )

@router.post("/ingest/kap")
def ingest_kap(req: IngestKAPRequest):
    try:
        """KAP bildirimlerini çekip VectorDB'ye ekler."""
        from backend.agent.ingestion.kap_scraper import KAPScraper
        from backend.agent.embeddings.embedder import embed_documents
        store = get_store()
        
        scraper = KAPScraper()
        docs    = scraper.fetch_disclosures(req.ticker, limit=req.limit)
        if not docs:
            raise HTTPException(404, f"No KAP disclosures found for {req.ticker}")
    
        chunks = embed_documents(docs)
        added  = store.add_documents(chunks)
        return {"ticker": req.ticker, "docs": len(docs), "chunks_added": added}
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}

@router.post("/ingest/news")
def ingest_news(req: IngestNewsRequest):
    """Finansal haberleri çekip VectorDB'ye ekler.
    Birincil: RSS (ücretsiz, API key gerekmez)
    İkincil:  Firecrawl (varsa)
    """
    try:
        from backend.agent.ingestion.rss_scraper import RSSNewsScraper
        from backend.agent.embeddings.embedder import embed_documents
        store = get_store()

        # 1. RSS ile çek (birincil — API key gerektirmez)
        rss = RSSNewsScraper()
        docs = rss.fetch_news(req.ticker, limit=req.limit, days_back=req.days_back)

        # 2. Firecrawl varsa ekstra haber ekle
        firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "")
        if firecrawl_key and len(docs) < req.limit:
            try:
                from backend.agent.ingestion.news_scraper import NewsScraper
                scraper = NewsScraper(firecrawl_api_key=firecrawl_key)
                extra = scraper.fetch_news(req.ticker, limit=req.limit - len(docs), days_back=req.days_back)
                docs.extend(extra)
            except Exception as fc_err:
                logger.warning(f"Firecrawl fallback failed: {fc_err}")

        chunks = embed_documents(docs)
        added  = store.add_documents(chunks)
        return {"ticker": req.ticker, "docs": len(docs), "chunks_added": added, "source": "rss+firecrawl"}
    except Exception as e:
        import traceback
        logger.error(f"INGEST NEWS CRASH: {e}\n{traceback.format_exc()}")
        return {"error": str(e), "traceback": traceback.format_exc()}

@router.post("/ingest/pdf")
async def ingest_pdf(
    ticker:      str,
    institution: str = "Aracı Kurum",
    file:        UploadFile = File(...)
):
    try:
        """PDF araştırma raporunu yükleyip VectorDB'ye ekler."""
        from backend.agent.ingestion.pdf_parser import PDFParser
        from backend.agent.embeddings.embedder import embed_documents
        store = get_store()
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
    
        try:
            parser = PDFParser()
            doc    = parser.parse(tmp_path, ticker=ticker, institution=institution)
            chunks = embed_documents([doc])
            added  = store.add_documents(chunks)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
        return {
            "ticker":      ticker,
            "institution": institution,
            "pages":       doc.get("pages", 0),
            "chunks_added": added,
        }
    except Exception as e:
        import traceback
        logger.error(f"INGEST PDF CRASH: {e}\n{traceback.format_exc()}")
        return {"error": str(e), "traceback": traceback.format_exc()}


@router.post("/evaluate")
async def evaluate_agent():
    """RAGAS Evaluation testini Render üzerinde çalıştırır ve JSON rapor döndürür."""
    from backend.agent.evaluation.ragas_eval import BISTEvaluator
    from backend.agent.engine.bist_agent import BISTAgent
    
    try:
        store = get_store()
        agent = BISTAgent(store)
        evaluator = BISTEvaluator(agent=agent, store=store)
        
        # Testleri çalıştır (limitli data olabileceği için hata vermesin diye)
        report = evaluator.run()
        
        return report
    except Exception as e:
        logger.error(f"Evaluation crash: {e}")
        raise HTTPException(500, f"RAGAS Evaluation failed: {e}")

