"""
BIST Equity Intelligence Agent — Agentic RAG core.

retrieve → verify → re-retrieve → answer döngüsü.

Özellikler:
  - Source Selection: KAP vs News vs Brokerage otomatik seçimi
  - Temporal Reasoning: Güncel vs tarihi bilgi farkındalığı
  - Cross-Source Verification: Kaynak çelişkisi saptama
  - Iterative Retrieval: Yeterli bilgi yoksa ikinci tur
"""

import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from backend.agent.vectordb.chroma_store import BISTVectorStore

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "\n\n⚠️ **Bu sistem yatırım tavsiyesi vermez.** "
    "Sunulan bilgiler yalnızca bilgi ve analiz amaçlıdır."
)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class AgentDecision:
    """Agent'ın her adımdaki kararı."""
    sources_selected: list[str]         # ["kap", "news", "brokerage"]
    time_horizon:     str               # "recent" | "historical" | "both"
    needs_reretrieval: bool = False
    reasoning:        str  = ""


@dataclass
class AgentResult:
    """Agent yanıtı."""
    answer:            str
    sources_used:      list[dict]
    decision:          AgentDecision
    consistency_note:  str  = ""       # kaynak çelişkisi varsa not
    disclaimer:        str  = DISCLAIMER
    iterations:        int  = 1


# ── Main Agent ────────────────────────────────────────────────────────────────

class BISTAgent:
    """
    BIST Equity Intelligence Agent.

    Kullanım:
        agent = BISTAgent(store)
        result = agent.run("ASELS için son KAP bildirimleri haberlerle örtüşüyor mu?")
        print(result.answer)
    """

    MAX_ITERATIONS = 2
    MIN_DOCS       = 3      # yeterli kaynak eşiği

    def __init__(self, store: BISTVectorStore, user_id: str = "default_user"):
        self.store = store
        self._callbacks = self._build_callbacks()
        self.llm   = ChatGroq(
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0.1,
            callbacks=self._callbacks,
        )
        self.conversation: list = []
        from backend.agent.engine.memory import BISTMemory
        self.memory = BISTMemory(user_id=user_id)

        from backend.agent.guardrails.guardrails import BISTGuardrails
        self.guardrails = BISTGuardrails(strict=True)

    def _build_callbacks(self) -> list:
        """LangSmith ve Langfuse callback'lerini kurar. API key yoksa atlar."""
        callbacks = []

        # ── LangSmith ─────────────────────────────────────────────────────────
        ls_key = os.getenv("LANGCHAIN_API_KEY", "")
        if ls_key:
            os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
            os.environ.setdefault("LANGCHAIN_PROJECT", "BIST-Equity-Agent")
            try:
                from langsmith.run_helpers import LangSmithTracer  # noqa
                logger.info("LangSmith tracing enabled")
            except Exception:
                pass  # langsmith paket yüklü değilse sessizce geç

        # ── Langfuse ──────────────────────────────────────────────────────────
        lf_key    = os.getenv("LANGFUSE_SECRET_KEY", "")
        lf_pub    = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        lf_host   = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        if lf_key and lf_pub:
            try:
                from langfuse.callback import CallbackHandler as LangfuseCallback
                cb = LangfuseCallback(
                    secret_key=lf_key,
                    public_key=lf_pub,
                    host=lf_host,
                    session_id="bist-agent-session",
                )
                callbacks.append(cb)
                logger.info("Langfuse callback enabled")
            except Exception as e:
                logger.warning(f"Langfuse callback failed to init: {e}")

        return callbacks


    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(
        self,
        question: str,
        ticker:   Optional[str] = None,
    ) -> AgentResult:
        """
        Agentic RAG döngüsü:
          1. Soruyu analiz et → kaynak ve zaman kararı
          2. İlk retrieval
          3. Yeterli mi? Hayırsa → re-retrieval
          4. Cross-source verification
          5. Cevap üret
        """
        logger.info(f"Agent started: '{question[:60]}' | ticker={ticker}")

        # ── Step 0: Input Guardrails ─────────────────────────────────────────
        guard_in = self.guardrails.check_input(question)
        if not guard_in.passed:
            logger.warning(f"Guardrail blocked input: {guard_in.violations}")
            return AgentResult(
                answer=guard_in.response,
                sources_used=[],
                decision=AgentDecision(reasoning="Blocked by Guardrails"),
                iterations=0
            )

        # ── Step 1: Kaynak ve zaman kararı ───────────────────────────────────
        decision = self._decide_sources(question, ticker)
        logger.info(
            f"Decision: sources={decision.sources_selected}, "
            f"horizon={decision.time_horizon}"
        )

        # ── Step 2: İlk retrieval ─────────────────────────────────────────────
        all_docs = []
        for src in decision.sources_selected:
            docs = self._retrieve(
                question   = question,
                ticker     = ticker,
                source_type= src,
                time_horizon= decision.time_horizon,
                k          = 5,
            )
            all_docs.extend(docs)

        iteration = 1

        # ── Step 3: Iterative retrieval ───────────────────────────────────────
        if len(all_docs) < self.MIN_DOCS and iteration < self.MAX_ITERATIONS:
            logger.info(
                f"Only {len(all_docs)} docs found — re-retrieving without filters"
            )
            iteration += 1
            extra = self._retrieve(
                question    = question,
                ticker      = ticker,
                source_type = None,    # filtresiz
                time_horizon= "both",
                k           = 8,
            )
            all_docs = self._merge_dedupe(all_docs, extra)

        # ── Step 4: Cross-source verification ────────────────────────────────
        consistency_note = self._verify_consistency(all_docs, question)

        # ── Step 5: Cevap üret ───────────────────────────────────────────────
        raw_answer = self._generate_answer(question, all_docs, consistency_note, ticker)

        # ── Step 6: Output Guardrails ────────────────────────────────────────
        # We use strict=False for output to allow the response even with small cautions
        guard_out = self.guardrails.check_output(raw_answer, strict=False)
        final_answer = guard_out.response

        self.memory.add_turn(question, final_answer)
        if ticker:
            self.memory.add(f"Kullanıcı {ticker} hissesini sorguladı", ticker=ticker)

        return AgentResult(
            answer           = final_answer,
            sources_used     = all_docs,
            decision         = decision,
            consistency_note = consistency_note,
            iterations       = iteration,
        )

    # ── Step 1: Source & Temporal Decision ───────────────────────────────────

    def _decide_sources(self, question: str, ticker: Optional[str]) -> AgentDecision:
        """
        LLM kullanarak hangi kaynakları ve hangi zaman aralığını
        kullanması gerektiğine karar verir.
        """
        prompt = f"""Bir BIST equity soru analiz aracısısın.
Aşağıdaki soruyu analiz et ve JSON ile yanıtla:

SORU: "{question}"
TICKER: {ticker or 'belirtilmedi'}

Yanıt SADECE şu JSON formatında olsun:
{{
  "sources": ["kap", "news", "brokerage"],   // en uygun kaynaklar (1-3 arası)
  "time_horizon": "recent",                  // "recent" (<90 gün) | "historical" | "both"
  "reasoning": "kısa açıklama"
}}

Kural: KAP = resmi bildirimler, news = haberler, brokerage = araştırma raporları."""

        try:
            resp = self.llm.invoke([HumanMessage(content=prompt)])
            import json, re
            match = re.search(r'\{.*\}', resp.content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return AgentDecision(
                    sources_selected = data.get("sources", ["kap", "news"]),
                    time_horizon     = data.get("time_horizon", "recent"),
                    reasoning        = data.get("reasoning", ""),
                )
        except Exception as e:
            logger.warning(f"Source decision LLM failed ({e}) — using defaults")

        # Fallback: heuristic
        q_lower = question.lower()
        sources = []
        if any(w in q_lower for w in ["kap", "bildiri", "açıklama", "resmi"]):
            sources.append("kap")
        if any(w in q_lower for w in ["haber", "gazete", "medya", "söylüyor"]):
            sources.append("news")
        if any(w in q_lower for w in ["rapor", "hedef", "araştırma", "analist"]):
            sources.append("brokerage")
        if not sources:
            sources = ["kap", "news"]

        horizon = "recent" if any(
            w in q_lower for w in ["son", "güncel", "bu hafta", "bu ay", "latest"]
        ) else "both"

        return AgentDecision(sources_selected=sources, time_horizon=horizon)

    # ── Step 2 & 3: Retrieval ─────────────────────────────────────────────────

    def _retrieve(
        self,
        question:     str,
        ticker:       Optional[str],
        source_type:  Optional[str],
        time_horizon: str,
        k:            int,
    ) -> list[dict]:
        """ChromaDB'den semantik arama yapar, zaman filtresi uygular."""
        from datetime import datetime
        date_from_ts = None
        if time_horizon == "recent":
            # Son 120 gün
            dt = datetime.utcnow() - timedelta(days=120)
            date_from_ts = int(dt.timestamp())

        return self.store.search(
            query       = question,
            k           = k,
            ticker      = ticker,
            source_type = source_type,
            date_from   = date_from_ts, # Geçerli timestamp gönderiyoruz
        )

    # ── Step 4: Cross-Source Verification ────────────────────────────────────

    def _verify_consistency(self, docs: list[dict], question: str) -> str:
        """
        KAP bildirimleri ile haberleri karşılaştırır.
        Çelişki varsa bunu raporlar.
        """
        kap_docs  = [d for d in docs if d["metadata"].get("source_type") == "kap"]
        news_docs = [d for d in docs if d["metadata"].get("source_type") == "news"]

        if not kap_docs or not news_docs:
            return ""  # Karşılaştırmak için iki kaynak yok

        kap_text  = " ".join(d["content"][:300] for d in kap_docs[:2])
        news_text = " ".join(d["content"][:300] for d in news_docs[:2])

        prompt = f"""İki metin arasındaki tutarsızlıkları bul.

KAP BİLDİRİMİ: {kap_text}
HABERLER: {news_text}

Eğer çelişki varsa: "⚠️ Tutarsızlık: [açıklama]"
Eğer uyuşuyorsa: "✅ KAP bildirimleri haberlerle örtüşüyor."
Maksimum 2 cümle."""

        try:
            resp = self.llm.invoke([HumanMessage(content=prompt)])
            return resp.content.strip()
        except Exception as e:
            logger.warning(f"Consistency check failed: {e}")
            return ""

    # ── Step 5: Answer Generation ─────────────────────────────────────────────

    def _generate_answer(
        self,
        question:         str,
        docs:             list[dict],
        consistency_note: str,
        ticker:           Optional[str] = None,
    ) -> str:
        """RAG bağlamıyla nihai cevabı üretir."""
        if not docs:
            return (
                "Veritabanında bu konuya ilişkin yeterli bilgi bulunamadı. "
                "Lütfen önce ilgili hisseyi ingest edin." + DISCLAIMER
            )

        context_parts = []
        for i, d in enumerate(docs[:8], 1):
            m = d["metadata"]
            context_parts.append(
                f"[{i}] {m.get('source_type','?').upper()} | "
                f"{m.get('ticker','?')} | {m.get('date','')[:10]}\n"
                f"Kaynak: {m.get('url','')}\n"
                f"{d['content'][:500]}"
            )
        context = "\n\n".join(context_parts)

        consistency_section = f"\n\nKAYNAK TUTARLILIK NOTU:\n{consistency_note}" if consistency_note else ""

        mem_context = self.memory.get_context(ticker=ticker)
        mem_section = f"\n\nBELLEK (GEÇMİŞ İLGİ VE SORULAR):\n{mem_context}" if mem_context else ""

        system = f"""Sen BIST Equity Intelligence Agent'sın.{mem_section}
KURALLAR:
- Yalnızca verilen kaynaklara dayan, [N] notasyonu ile kaynak göster
- Yatırım tavsiyesi, al/sat sinyali, fiyat tahmini YASAK
- Net, özlü, Türkçe yanıt ver"""

        human = f"""BAĞLAM:
{context}{consistency_section}

SORU: {question}"""

        messages = [SystemMessage(content=system), HumanMessage(content=human)]

        try:
            resp = self.llm.invoke(messages)
            return resp.content + DISCLAIMER
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return f"Yanıt üretilirken hata oluştu: {e}" + DISCLAIMER

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _merge_dedupe(a: list[dict], b: list[dict]) -> list[dict]:
        seen  = {d["content"][:80] for d in a}
        extra = [d for d in b if d["content"][:80] not in seen]
        return a + extra


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    store = BISTVectorStore(persist_path="./data/chroma_db")
    agent = BISTAgent(store)

    q = sys.argv[1] if len(sys.argv) > 1 else "ASELS için son KAP bildirimleri neler?"
    result = agent.run(q, ticker="ASELS")

    print(f"\n{'='*60}")
    print(f"SORU: {q}")
    print(f"KAYNAKLAR: {result.decision.sources_selected}")
    print(f"ZAMAN: {result.decision.time_horizon}")
    print(f"İTERASYON: {result.iterations}")
    if result.consistency_note:
        print(f"TUTARLILIK: {result.consistency_note}")
    print(f"\nCEVAP:\n{result.answer}")
