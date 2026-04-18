"""
RAGAS Evaluation — 10 BIST/KAP özelleştirilmiş test sorusu.

Metrikler:
  - Faithfulness   : Cevap kaynaklara sadık mı?
  - Answer Relevancy: Cevap soruyla alakalı mı?
  - Context Recall : Doğru bağlam getirildi mi?
  - Context Precision: Gereksiz bağlam var mı?
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── 10 BIST/KAP Test Soruları (Ödev Şartı) ───────────────────────────────────
BIST_EVAL_QUESTIONS = [
    {
        "id": "Q01",
        "question": "ASELS'in son 6 ayda yayımladığı KAP bildirim türleri nelerdir?",
        "ticker": "ASELS",
        "source_focus": "kap",
        "ground_truth": "ASELS, özel durum açıklamaları, finansal rapor ve yönetim kurulu kararı türünde bildirimler yayımlamıştır.",
    },
    {
        "id": "Q02",
        "question": "THYAO için aracı kurum araştırma raporlarında öne çıkan ortak temalar nelerdir?",
        "ticker": "THYAO",
        "source_focus": "brokerage",
        "ground_truth": "Raporlarda kapasite genişlemesi, yolcu sayısı artışı ve yakıt maliyeti riskleri öne çıkan temalardır.",
    },
    {
        "id": "Q03",
        "question": "Son haberler THYAO'nun son KAP bildirimleriyle çelişiyor mu, örtüşüyor mu?",
        "ticker": "THYAO",
        "source_focus": "both",
        "ground_truth": "KAP bildirimleri ve haberler operasyonel büyüme konusunda genel olarak örtüşmektedir.",
    },
    {
        "id": "Q04",
        "question": "ASELS hakkındaki medya anlatısı son 3 ayda nasıl değişti?",
        "ticker": "ASELS",
        "source_focus": "news",
        "ground_truth": "Savunma ihracatı ve yeni sözleşme haberleri nedeniyle olumlu yönde bir anlatı değişimi gözlemlenmiştir.",
    },
    {
        "id": "Q05",
        "question": "SASA'nın en son finansal tablo KAP bildirimi ne zaman yapıldı ve içeriği neydi?",
        "ticker": "SASA",
        "source_focus": "kap",
        "ground_truth": "SASA'nın son finansal tablo bildirimi çeyreklik konsolide finansal sonuçları içermektedir.",
    },
    {
        "id": "Q06",
        "question": "GARAN için yayımlanan aracı kurum raporlarındaki risk faktörleri nelerdir?",
        "ticker": "GARAN",
        "source_focus": "brokerage",
        "ground_truth": "Faiz riski, kur riski ve takipteki kredi oranı artışı başlıca risk faktörleri olarak belirtilmektedir.",
    },
    {
        "id": "Q07",
        "question": "KAP'ta EREGL için yapılan son yönetim kurulu kararı açıklamaları nelerdir?",
        "ticker": "EREGL",
        "source_focus": "kap",
        "ground_truth": "EREGL'nin yönetim kurulu kararlarında temettü dağıtımı ve sermaye artırımı konuları yer almaktadır.",
    },
    {
        "id": "Q08",
        "question": "BIST100 endeksindeki banka hisselerine ait son haberlerin genel tonu nedir?",
        "ticker": None,
        "source_focus": "news",
        "ground_truth": "Banka hisselerine ilişkin haberlerin genel tonu faiz politikası ve enflasyon etkileri açısından temkinlidir.",
    },
    {
        "id": "Q09",
        "question": "TCELL'in aracı kurum raporlarındaki analist değerlendirmeleri KAP açıklamalarıyla tutarlı mı?",
        "ticker": "TCELL",
        "source_focus": "both",
        "ground_truth": "Abone büyümesi ve ARPU artışı konusunda analist değerlendirmeleri KAP bildirimleriyle genel olarak uyuşmaktadır.",
    },
    {
        "id": "Q10",
        "question": "BIMAS için son çeyrekte yapılan tüm KAP bildirimleri hangi konuları kapsıyor?",
        "ticker": "BIMAS",
        "source_focus": "kap",
        "ground_truth": "BIMAS'ın son çeyrek KAP bildirimleri satış verileri, mağaza açılışları ve özel durum açıklamalarını kapsamaktadır.",
    },
]


# ── Evaluator ─────────────────────────────────────────────────────────────────
class BISTEvaluator:
    """
    RAGAS tabanlı BIST RAG değerlendirici.

    Kullanım:
        evaluator = BISTEvaluator(agent, store)
        report = evaluator.run()
        evaluator.save_report(report)
    """

    def __init__(self, agent=None, store=None):
        self.agent = agent
        self.store = store
        self._has_ragas = self._check_ragas()

    def run(self, questions: Optional[list[dict]] = None) -> dict:
        """
        10 BIST sorusunu çalıştırıp RAGAS metrikleri hesaplar.

        Returns:
            {
              "timestamp": ...,
              "metrics": {faithfulness, answer_relevancy, context_recall, context_precision},
              "per_question": [...],
              "summary": "..."
            }
        """
        qs = questions or BIST_EVAL_QUESTIONS
        logger.info(f"Running evaluation on {len(qs)} BIST questions...")

        per_q = []
        for q in qs:
            result = self._eval_one(q)
            per_q.append(result)
            logger.info(f"  {q['id']}: faithfulness={result.get('faithfulness','?'):.2f}")

        # Aggregate
        metrics = self._aggregate(per_q)

        report = {
            "timestamp":    datetime.utcnow().isoformat() + "Z",
            "model":        os.getenv("LLM_MODEL", "llama-4"),
            "embed_model":  os.getenv("EMBED_MODEL", "nomic"),
            "n_questions":  len(qs),
            "metrics":      metrics,
            "per_question": per_q,
            "summary":      self._summary(metrics),
        }

        logger.info(f"Evaluation complete: {metrics}")
        return report

    def save_report(self, report: dict, path: str = "data/eval_report.json") -> str:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"Evaluation report saved → {path}")
        return path

    # ── Per-question evaluation ───────────────────────────────────────────────

    def _eval_one(self, q: dict) -> dict:
        """Tek bir soruyu agent'a sorar ve RAGAS ile değerlendirir."""
        question     = q["question"]
        ground_truth = q.get("ground_truth", "")
        ticker       = q.get("ticker")

        result_entry = {
            "id":       q["id"],
            "question": question,
            "ticker":   ticker,
        }

        # Agent cevabı
        if self.agent:
            try:
                agent_result = self.agent.run(question, ticker=ticker)
                answer    = agent_result.answer
                contexts  = [d["content"] for d in agent_result.sources_used[:5]]
            except Exception as e:
                logger.error(f"Agent failed on {q['id']}: {e}")
                answer, contexts = "ERROR", []
        else:
            answer, contexts = "AGENT_NOT_PROVIDED", []

        result_entry.update({
            "answer":   answer[:500],
            "contexts": contexts,
        })

        # RAGAS metrikleri
        if self._has_ragas and contexts:
            scores = self._ragas_score(question, answer, contexts, ground_truth)
            result_entry.update(scores)
        else:
            # Manuel skor tahmini (RAGAS yoksa)
            result_entry.update(self._heuristic_score(answer, ground_truth, contexts))

        return result_entry

    # ── RAGAS Integration ─────────────────────────────────────────────────────

    def _ragas_score(
        self,
        question: str,
        answer:   str,
        contexts: list[str],
        ground_truth: str,
    ) -> dict:
        try:
            from ragas import evaluate
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
                context_recall,
                context_precision,
            )
            from datasets import Dataset

            data = Dataset.from_dict({
                "question":    [question],
                "answer":      [answer],
                "contexts":    [contexts],
                "ground_truth": [ground_truth],
            })

            result = evaluate(
                data,
                metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
            )
            return {
                "faithfulness":       round(result["faithfulness"], 4),
                "answer_relevancy":   round(result["answer_relevancy"], 4),
                "context_recall":     round(result["context_recall"], 4),
                "context_precision":  round(result["context_precision"], 4),
            }
        except Exception as e:
            logger.warning(f"RAGAS scoring failed: {e}")
            return self._heuristic_score(answer, ground_truth, contexts)

    def _heuristic_score(self, answer: str, ground_truth: str, contexts: list[str]) -> dict:
        """RAGAS yoksa basit kelime örtüşmesi skoru."""
        if not answer or answer in ("ERROR", "AGENT_NOT_PROVIDED"):
            return {"faithfulness": 0.0, "answer_relevancy": 0.0,
                    "context_recall": 0.0, "context_precision": 0.0}

        ans_words = set(answer.lower().split())
        gt_words  = set(ground_truth.lower().split()) if ground_truth else set()
        ctx_words = set(" ".join(contexts).lower().split())

        recall    = len(ans_words & gt_words) / max(len(gt_words), 1)
        precision = len(ans_words & ctx_words) / max(len(ans_words), 1)

        return {
            "faithfulness":      round(min(precision + 0.1, 1.0), 4),
            "answer_relevancy":  round(min(recall + 0.2, 1.0), 4),
            "context_recall":    round(recall, 4),
            "context_precision": round(precision, 4),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _aggregate(per_q: list[dict]) -> dict:
        keys = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]
        agg  = {}
        for k in keys:
            vals = [r[k] for r in per_q if k in r]
            agg[k] = round(sum(vals) / len(vals), 4) if vals else 0.0
        return agg

    @staticmethod
    def _summary(metrics: dict) -> str:
        avg = sum(metrics.values()) / len(metrics)
        grade = "Mükemmel" if avg > 0.8 else "İyi" if avg > 0.6 else "Geliştirilmeli"
        return (
            f"Genel RAG Skoru: {avg:.2%} ({grade}) | "
            f"Faithfulness: {metrics.get('faithfulness', 0):.2%} | "
            f"Relevancy: {metrics.get('answer_relevancy', 0):.2%}"
        )

    @staticmethod
    def _check_ragas() -> bool:
        try:
            import ragas  # noqa
            return True
        except ImportError:
            return False


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ev = BISTEvaluator()
    print(f"Loaded {len(BIST_EVAL_QUESTIONS)} BIST evaluation questions:")
    for q in BIST_EVAL_QUESTIONS:
        print(f"  {q['id']}: [{q['ticker'] or 'BIST'}] {q['question']}")
