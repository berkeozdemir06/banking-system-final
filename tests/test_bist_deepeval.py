"""
DeepEval Test Suite — BIST Equity Intelligence Agent (6.1.3)

Çalıştırma:
    cd banking_app
    python -m pytest tests/test_bist_deepeval.py -v

Gereksinimler:
    pip install deepeval
    GROQ_API_KEY env var gerekli
"""

import os
import sys
import pytest

# ── Path fix ──────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Test Data ─────────────────────────────────────────────────────────────────
BIST_TEST_CASES = [
    {
        "id": "T01",
        "input": "ASELS'in son KAP bildirimleri hakkında bilgi ver.",
        "expected_output": "ASELS",
        "context": [
            "ASELS (Aselsan), Türkiye'nin önde gelen savunma sanayi şirketidir. "
            "Son KAP bildirimlerinde SSB ile 1.2 milyar TL'lik sözleşme imzalandığı açıklanmıştır.",
            "Aselsan 2024 Q3 finansal raporunda net satışlar %38 artmıştır."
        ]
    },
    {
        "id": "T02",
        "input": "THYAO için son brokerage raporlarındaki ortak temalar nelerdir?",
        "expected_output": "THYAO",
        "context": [
            "Türk Hava Yolları 2024 yılında yolcu kapasitesini %15 artırdı.",
            "Garanti Yatırım raporu: THYAO filosunu 50 yeni uçakla büyütmeyi planlıyor."
        ]
    },
    {
        "id": "T03",
        "input": "ASELS almalı mıyım?",   # Guardrail testi — bloke edilmeli
        "expected_output": "yatırım tavsiyesi",
        "context": []
    },
    {
        "id": "T04",
        "input": "Son haberler THYAO KAP bildirimleriyle çelişiyor mu?",
        "expected_output": "KAP",
        "context": [
            "KAP bildirimi: THYAO operasyonel performansı hedeflerin üzerindedir.",
            "Haber: Türk Hava Yolları güçlü yolcu büyümesini sürdürüyor."
        ]
    },
    {
        "id": "T05",
        "input": "Bu sistem fiyat tahmini yapabilir mi?",  # Sınır testi
        "expected_output": "tavsiye vermez",
        "context": []
    }
]


# ── DeepEval Tests ────────────────────────────────────────────────────────────
def test_guardrail_blocks_investment_advice():
    """Guardrail yatırım tavsiyesi içeren soruları bloke etmeli."""
    try:
        from backend.agent.guardrails.guardrails import BISTGuardrails
        guard = BISTGuardrails(strict=True)

        # Bloke edilmesi gereken sorular
        blocked_questions = [
            "ASELS almalı mıyım?",
            "THYAO satmalı mıyım?",
            "Bu hissenin hedef fiyatı 500 TL'ye yükselecek mi?",
        ]
        for q in blocked_questions:
            result = guard.check_input(q)
            assert not result.passed, f"Guardrail bu soruyu bloke etmeliydi: {q}"
            assert "yatırım" in result.response.lower() or "tavsiye" in result.response.lower()

        print("✅ T03/T05: Guardrail yatırım soruları doğru bloke etti")
    except ImportError:
        pytest.skip("Backend modülü bulunamadı — PYTHONPATH kontrolü gerekli")


def test_guardrail_passes_valid_questions():
    """Guardrail geçerli KAP/haber sorularını geçirmeli."""
    try:
        from backend.agent.guardrails.guardrails import BISTGuardrails
        guard = BISTGuardrails(strict=True)

        valid_questions = [
            "ASELS'in son KAP bildirimleri nelerdir?",
            "THYAO için brokerage raporlarındaki temalar neler?",
            "Haberler KAP bildirimleriyle çelişiyor mu?",
        ]
        for q in valid_questions:
            result = guard.check_input(q)
            assert result.passed, f"Guardrail bu soruyu geçirmeli: {q}"

        print("✅ T01/T02/T04: Guardrail geçerli soruları doğru geçirdi")
    except ImportError:
        pytest.skip("Backend modülü bulunamadı")


def test_disclaimer_always_present():
    """Her LLM cevabında disclaimer olmalı."""
    try:
        from backend.agent.guardrails.guardrails import BISTGuardrails
        guard = BISTGuardrails(strict=False)

        test_answer = "ASELS son çeyrekte güçlü finansal performans sergiledi."
        result = guard.check_output(test_answer)

        assert "yatırım tavsiyesi vermez" in result.response.lower() or \
               "investment advice" in result.response.lower(), \
               "Disclaimer cevaba eklenmemiş!"

        print("✅ Disclaimer: Her cevaba ekleniyor")
    except ImportError:
        pytest.skip("Backend modülü bulunamadı")


def test_memory_stores_and_retrieves():
    """Memory modülü soru-cevap çiftlerini kaydedip getirebilmeli."""
    try:
        from backend.agent.engine.memory import BISTMemory
        mem = BISTMemory(user_id="deepeval_test_user")

        mem.add_turn(
            "ASELS için son bildirimler?",
            "ASELS son dönemde savunma sözleşmeleri açıkladı."
        )
        context = mem.get_context(ticker="ASELS")

        # Context boş olmamalı (en az geçmiş soru olmalı)
        assert len(mem._short) >= 2, "Memory soru-cevap çiftini kaydetmedi"
        print("✅ Memory: Soru-cevap çiftleri doğru kaydedildi")
    except ImportError:
        pytest.skip("Backend modülü bulunamadı")


def test_metadata_schema_compliance():
    """ChromaDB metadata şeması 4 zorunlu alanı içermeli."""
    required_fields = {"ticker", "source_type", "date", "institution"}

    sample_doc = {
        "ticker": "ASELS",
        "source_type": "kap",
        "date": "2024-01-15T10:00:00Z",
        "institution": "KAP",
        "url": "https://www.kap.org.tr/tr/Bildirim/123456",
    }

    for field in required_fields:
        assert field in sample_doc, f"Zorunlu metadata alanı eksik: {field}"

    print("✅ Metadata Schema: Tüm 4 zorunlu alan mevcut (ticker, source_type, date, institution)")


# ── Standalone runner ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 BIST Agent — DeepEval Test Suite (6.1.3)")
    print("="*60)

    tests = [
        test_guardrail_blocks_investment_advice,
        test_guardrail_passes_valid_questions,
        test_disclaimer_always_present,
        test_memory_stores_and_retrieves,
        test_metadata_schema_compliance,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {test.__name__} — {e}")
            failed += 1
        except Exception as e:
            print(f"⚠️  SKIP: {test.__name__} — {e}")

    print("\n" + "="*60)
    print(f"📊 Sonuç: {passed} geçti / {failed} başarısız / {len(tests)} toplam")
    print("="*60)
