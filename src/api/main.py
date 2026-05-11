"""
BIST RAG — FastAPI uygulaması (Agentic RAG).

Endpoint'ler:
  POST /query                  — soru sor, Agentic RAG yanıtı al
  POST /ingest/kap             — KAP bildirimlerini ingest et
  POST /ingest/news            — Haber ingest et
  POST /ingest/pdf             — PDF rapor ingest et
  GET  /stats                  — veritabanı istatistikleri
  GET  /health                 — sistem durumu
  POST /intelligence/analyze   — KAP + fiyat analizi (JSON)
  GET  /intelligence/report    — KAP + fiyat analizi PDF raporu
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from fastapi.responses import StreamingResponse

from src.vectordb.chroma_store import BISTVectorStore
from src.embeddings.embedder import embed_documents
from src.ingestion.kap_scraper import KAPScraper
from src.ingestion.news_scraper import NewsScraper
from src.ingestion.pdf_parser import PDFParser
from src.agent.bist_agent import BISTAgent
from src.ingestion.kap_intelligence import full_analysis, generate_pdf_report

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DISCLAIMER = (
    "\n\n⚠️ Bu sistem yatırım tavsiyesi vermez. "
    "Sunulan bilgiler yalnızca bilgi amaçlıdır ve "
    "al/sat kararı için kullanılamaz."
)

# ── App Lifecycle ─────────────────────────────────────────────────────────────
store: Optional[BISTVectorStore] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global store
    logger.info("Starting BIST Agentic API...")
    store = BISTVectorStore(
        persist_path=os.getenv("CHROMA_PATH", "./data/chroma_db"),
        embed_provider=os.getenv("EMBED_PROVIDER", "nomic"),
    )
    logger.info("VectorStore ready ✓")
    yield
    logger.info("Shutting down...")

app = FastAPI(
    title="BIST Equity Intelligence Agent API",
    description="Agentic RAG for Turkish Equity Markets (KAP · News · Brokerage)",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ───────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., description="Kullanıcı sorusu")
    ticker:   Optional[str] = Field(None, description="Hisse filtresi, örn. 'ASELS'")

class IngestKAPRequest(BaseModel):
    ticker: str
    limit:  int = Field(30, ge=1, le=100)

class IngestNewsRequest(BaseModel):
    ticker:    str
    limit:     int = Field(30, ge=1, le=100)
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

@app.get("/health")
def health():
    return {"status": "ok", "vectorstore": store.get_stats() if store else None}

@app.get("/stats")
def stats():
    if not store:
        raise HTTPException(503, "VectorStore not ready")
    return store.get_stats()

@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Ana RAG endpoint — soru sor, kaynaklı cevap al. BISTAgent kullanılır."""
    if not store:
        raise HTTPException(503, "VectorStore not ready")

    # Ajanı başlat ve çalıştır
    agent = BISTAgent(store=store)
    try:
        result = agent.run(question=req.question, ticker=req.ticker)
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise HTTPException(500, f"Ajan hatası: {str(e)}")

    # Sonuçları formatla
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


@app.post("/ingest/kap")
def ingest_kap(req: IngestKAPRequest):
    """KAP bildirimlerini çekip VectorDB'ye ekler."""
    if not store:
        raise HTTPException(503, "VectorStore not ready")

    scraper = KAPScraper()
    docs    = scraper.fetch_disclosures(req.ticker, limit=req.limit)
    if not docs:
        raise HTTPException(404, f"No KAP disclosures found for {req.ticker}")

    chunks = embed_documents(docs)
    added  = store.add_documents(chunks)
    return {"ticker": req.ticker, "docs": len(docs), "chunks_added": added}


@app.post("/ingest/news")
def ingest_news(req: IngestNewsRequest):
    """Finansal haberleri çekip VectorDB'ye ekler."""
    if not store:
        raise HTTPException(503, "VectorStore not ready")

    scraper = NewsScraper(firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"))
    docs    = scraper.fetch_news(req.ticker, limit=req.limit, days_back=req.days_back)
    
    # Try embedding, if Nomic fails due to bad key, return gracefully
    added = 0
    try:
        chunks  = embed_documents(docs)
        if chunks: added = store.add_documents(chunks)
    except Exception as e:
        logger.error(f"Embed/Chroma failed: {e}")
        pass
        
    return {"ticker": req.ticker, "docs": len(docs), "chunks_added": added}


@app.post("/ingest/pdf")
async def ingest_pdf(
    file:        UploadFile = File(...),
    ticker:      str = "UNKNOWN",
    institution: str = "Aracı Kurum",
):
    """PDF araştırma raporunu yükleyip VectorDB'ye ekler."""
    if not store:
        raise HTTPException(503, "VectorStore not ready")

    import tempfile, shutil
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        parser = PDFParser()
        doc    = parser.parse(tmp_path, ticker=ticker, institution=institution)
        added = 0
        try:
            chunks = embed_documents([doc])
            if chunks: added  = store.add_documents(chunks)
        except Exception as e:
            logger.error(f"Embed/Chroma failed for PDF: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return {
        "ticker":      ticker,
        "institution": institution,
        "pages":       doc.get("pages", 0),
        "chunks_added": added,
    }


# ─────────────────────────────────────────────────────────────
#  KAP Intelligence Endpoints
# ─────────────────────────────────────────────────────────────

class IntelligenceRequest(BaseModel):
    ticker:    str = Field(..., description="BIST hisse kodu (örn. 'ASELS')")
    kap_limit: int = Field(15, ge=1, le=30)


@app.post("/intelligence/analyze")
async def intelligence_analyze(req: IntelligenceRequest):
    """
    Belirtilen hisse için:
    - Yahoo Finance'ten şirket bilgisi + fiyat getirileri
    - Google News RSS'ten son KAP duyuruları
    - Her duyuru için ertesi gün fiyat etkisi
    JSON olarak döner.
    """
    try:
        result = full_analysis(req.ticker, kap_limit=req.kap_limit)
        # date_obj serialize edilemez, sil
        for ann in result.get("announcements", []):
            ann.pop("date_obj", None)
        return result
    except Exception as e:
        logger.error(f"intelligence_analyze failed: {e}")
        raise HTTPException(500, f"Analiz hatası: {str(e)}")


@app.get("/intelligence/report")
async def intelligence_report(ticker: str = "ASELS", kap_limit: int = 15):
    """
    Belirtilen hisse için tam analiz yapıp PDF rapor olarak döner.
    Tarayıcıda doğrudan indirilir.
    """
    try:
        result = full_analysis(ticker.upper(), kap_limit=kap_limit)
        pdf_bytes = generate_pdf_report(result)
        filename = f"{ticker.upper()}_OZAS_Report_{result['generated_at'][:10]}.pdf"
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.error(f"intelligence_report failed: {e}")
        raise HTTPException(500, f"Rapor hatası: {str(e)}")
