"""
Guardrails — BIST Agent için yatırım tavsiyesi filtresi.

Zorunlu kurallar (ödev şartı):
  1. Al/sat sinyali → engelle
  2. Fiyat tahmini  → engelle
  3. Yatırım tavsiyesi → engelle
  4. Tüm çıktılara disclaimer ekle
"""

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "\n\n---\n"
    "⚠️ **Bu sistem yatırım tavsiyesi vermez.** "
    "Bu bilgiler yalnızca bilgi ve analiz amaçlıdır; "
    "al/sat kararı için kullanılamaz. "
    "Yatırım kararlarınızda lisanslı bir finansal danışmana başvurun."
)

# ── Yasak ifadeler ─────────────────────────────────────────────────────────────
INVESTMENT_ADVICE_PATTERNS = [
    r"\bal[ıi]n\b",          # "alın"
    r"\bsat[ıi]n\b",         # "satın"
    r"\bal\s*sinyali\b",
    r"\bsat\s*sinyali\b",
    r"\byatırım\s*tavsiye",
    r"\bhedef\s*fiyat[ıi]?\s*\d",
    r"\bfiyat\s*tahmin",
    r"\bkâr\s*elde\s*ed",
    r"\byükselecek\b",
    r"\bdüşecek\b",
    r"\bkesinlikle\s*al\b",
    r"\bkesinlikle\s*sat\b",
    r"should\s+buy",
    r"should\s+sell",
    r"price\s+target\s*[\$₺]?\s*\d",
    r"will\s+rise",
    r"will\s+fall",
    r"strong\s+buy",
    r"strong\s+sell",
]

_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INVESTMENT_ADVICE_PATTERNS]

# ── Replacement messages ─────────────────────────────────────────────────────
BLOCKED_RESPONSE = (
    "🚫 **Bu talep yanıtlanamaz.** "
    "Sistem, yatırım tavsiyesi, al/sat sinyali veya fiyat tahmini üretmez. "
    "Şirket hakkında olgusal bilgi (KAP bildirimleri, haber özeti) almak için "
    "sorunuzu yeniden çerçeveleyebilirsiniz."
    + DISCLAIMER
)


# ── Dataclass ─────────────────────────────────────────────────────────────────
@dataclass
class GuardrailResult:
    passed:      bool
    response:    str       # düzeltilmiş veya orijinal yanıt
    violations:  list[str] # bulunan ihlaller


# ── Main Guardrail ─────────────────────────────────────────────────────────────
class BISTGuardrails:
    """
    BIST Agent guardrail motoru.

    Kullanım:
        guard = BISTGuardrails()

        # Giriş (kullanıcı sorusu) kontrolü
        result = guard.check_input("ASELS almalı mıyım?")
        if not result.passed:
            return result.response

        # Çıkış (LLM cevabı) kontrolü
        result = guard.check_output(llm_answer)
        return result.response  # disclaimer eklenmiş, ihlaller varsa bloke
    """

    def __init__(self, strict: bool = True):
        """
        Args:
            strict: True → ihlal varsa cevabı tamamen bloke et
                    False → uyarı ekle ama cevabı geçir
        """
        self.strict = strict
        logger.info(f"BISTGuardrails loaded (strict={strict}, patterns={len(_PATTERNS)})")

    # ── Input Check ───────────────────────────────────────────────────────────

    def check_input(self, question: str) -> GuardrailResult:
        """Kullanıcı sorusunu filtreler."""
        violations = self._find_violations(question)
        if violations:
            logger.warning(f"Input violation: {violations}")
            return GuardrailResult(
                passed=False,
                response=BLOCKED_RESPONSE,
                violations=violations,
            )
        return GuardrailResult(passed=True, response=question, violations=[])

    # ── Output Check ──────────────────────────────────────────────────────────

    def check_output(self, response: str) -> GuardrailResult:
        """LLM çıktısını filterler ve disclaimer ekler."""
        violations = self._find_violations(response)

        if violations and self.strict:
            logger.warning(f"Output violation (strict block): {violations}")
            return GuardrailResult(
                passed=False,
                response=BLOCKED_RESPONSE,
                violations=violations,
            )

        # Disclaimer zaten yoksa ekle
        cleaned = self._ensure_disclaimer(response)

        if violations:
            # Soft mode: uyarı ekle ama geç
            warning = (
                f"\n\n⚠️ **Not:** Bu yanıtta tespit edilen ifadeler "
                f"({', '.join(violations[:2])}) yatırım tavsiyesi niteliği "
                f"taşıyabilir. Lütfen bu bilgileri yatırım kararlarınızda "
                f"tek başına kullanmayın."
            )
            cleaned += warning
            logger.warning(f"Output soft-warning appended: {violations}")

        return GuardrailResult(passed=True, response=cleaned, violations=violations)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _find_violations(text: str) -> list[str]:
        found = []
        for pat in _PATTERNS:
            match = pat.search(text)
            if match:
                found.append(match.group(0))
        return found

    @staticmethod
    def _ensure_disclaimer(text: str) -> str:
        if "yatırım tavsiyesi vermez" in text or "investment advice" in text.lower():
            return text
        return text + DISCLAIMER


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    guard = BISTGuardrails(strict=True)

    tests = [
        "ASELS hakkında son KAP bildirimleri neler?",           # geçmeli
        "ASELS almalı mıyım?",                                   # bloklenmeli
        "THYAO'nun hedef fiyatı 200 TL'ye yükselecek mi?",      # bloklenmeli
        "Son 3 aydaki KAP bildirimleri haberlerle uyuşuyor mu?", # geçmeli
    ]
    for q in tests:
        r = guard.check_input(q)
        status = "✅ PASS" if r.passed else "🚫 BLOCK"
        print(f"{status}: {q[:60]}")
        if not r.passed:
            print(f"  → Violations: {r.violations}")
