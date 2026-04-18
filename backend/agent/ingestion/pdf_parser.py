"""
PDF Parser — Aracı kurum araştırma raporlarını parse eder.

Docling kullanarak yüksek kaliteli PDF metin çıkarımı yapar.
Docling yoksa PyMuPDF fallback devreye girer.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ── Main PDF Parser ───────────────────────────────────────────────────────────
class PDFParser:
    """
    Brokerage araştırma raporu PDF parser'ı.

    Kullanım:
        parser = PDFParser()
        doc = parser.parse("data/raw/brokerage/asels_report.pdf",
                           ticker="ASELS", institution="Garanti BBVA Yatırım")
    """

    def __init__(self, save_dir: str = "data/raw/brokerage"):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self._has_docling = self._check_docling()

    # ── Public API ────────────────────────────────────────────────────────────

    def parse(
        self,
        pdf_path: str,
        ticker: str,
        institution: str = "Aracı Kurum",
        report_date: Optional[str] = None,
    ) -> dict:
        """
        PDF'yi parse edip belge dict'i döndürür.

        Args:
            pdf_path:    PDF dosya yolu
            ticker:      İlgili hisse kodu
            institution: Raporu hazırlayan kurum
            report_date: Rapor tarihi (ISO 8601), None = dosya değişim tarihi

        Returns:
            Document dict with mandatory metadata schema
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(f"Parsing PDF: {path.name} (engine: {'docling' if self._has_docling else 'pymupdf'})")

        if self._has_docling:
            text, pages = self._parse_with_docling(str(path))
        else:
            text, pages = self._parse_with_pymupdf(str(path))

        # Tarihi belirle
        if not report_date:
            mtime = path.stat().st_mtime
            from datetime import datetime
            report_date = datetime.utcfromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%SZ")

        doc = {
            # ── Mandatory metadata schema ──────────────────────────────
            "ticker":      ticker.upper(),
            "source_type": "brokerage",
            "date":        report_date,
            "institution": institution,
            # ── Content ────────────────────────────────────────────────
            "title":    f"{institution} — {ticker} Araştırma Raporu",
            "content":  text,
            "url":      str(path.resolve()),
            "filename": path.name,
            "pages":    pages,
            "engine":   "docling" if self._has_docling else "pymupdf",
        }

        # Kaydet
        out_path = os.path.join(
            self.save_dir,
            f"{ticker.lower()}_{path.stem}_parsed.json",
        )
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved parsed PDF → {out_path}")

        return doc

    def parse_directory(
        self,
        directory: str,
        ticker: str,
        institution: str = "Aracı Kurum",
    ) -> list[dict]:
        """Dizindeki tüm PDF'leri parse eder."""
        docs = []
        for pdf in Path(directory).glob("*.pdf"):
            try:
                doc = self.parse(str(pdf), ticker, institution)
                docs.append(doc)
            except Exception as e:
                logger.error(f"Failed to parse {pdf.name}: {e}")
        return docs

    # ── Docling Engine ────────────────────────────────────────────────────────

    def _parse_with_docling(self, pdf_path: str) -> tuple[str, int]:
        """Docling ile yüksek kaliteli PDF parse."""
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        doc = result.document

        # Markdown olarak eksport
        md_text = doc.export_to_markdown()

        # Sayfa sayısı
        pages = len(doc.pages) if hasattr(doc, "pages") else 0

        return md_text, pages

    # ── PyMuPDF Fallback ──────────────────────────────────────────────────────

    def _parse_with_pymupdf(self, pdf_path: str) -> tuple[str, int]:
        """PyMuPDF (fitz) ile basit PDF text çıkarımı."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            pages = doc.page_count
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            return "\n\n".join(text_parts), pages
        except ImportError:
            logger.warning("Neither docling nor PyMuPDF found. Using pdfplumber fallback.")
            return self._parse_with_pdfplumber(pdf_path)

    def _parse_with_pdfplumber(self, pdf_path: str) -> tuple[str, int]:
        """En basit fallback — pdfplumber."""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                pages = len(pdf.pages)
                texts = [p.extract_text() or "" for p in pdf.pages]
            return "\n\n".join(texts), pages
        except Exception as e:
            logger.error(f"All PDF engines failed: {e}")
            return "", 0

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _check_docling() -> bool:
        try:
            import docling  # noqa: F401
            return True
        except ImportError:
            return False


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = PDFParser()
    if len(sys.argv) > 1:
        doc = parser.parse(sys.argv[1], ticker="TEST", institution="Test Kurum")
        print(f"Parsed {doc['pages']} pages, {len(doc['content'])} chars")
        print(doc["content"][:500])
    else:
        print("Usage: python pdf_parser.py <path_to_pdf>")
