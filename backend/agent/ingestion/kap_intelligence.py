"""
KAP Intelligence Module — Gerçek KAP Bildirimleri + Fiyat Etkisi Analizi

Kaynaklar:
  - KAP bildirimleri: Google News RSS (kap.org.tr bot engeline karşı en güvenilir yol)
  - Fiyat verisi:    Yahoo Finance (yfinance) — gerçek zamanlı + tarihsel
  - PDF üretimi:     ReportLab

Özellikler:
  1. Hisse seçilince son 15 KAP duyurusunu otomatik çeket
  2. Her duyurunun ertesi günündeki fiyat değişimini gösterir
  3. Şirket özeti, fiyat getirisi, hacim, BIST100 karşılaştırması
  4. Tüm bunları PDF raporuna aktarır
"""

import os
import re
import time
import logging
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from io import BytesIO
from typing import Optional

import requests
import yfinance as yf
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}


# ─────────────────────────────────────────────────────────────
#  1. Şirket Verisi  (Yahoo Finance)
# ─────────────────────────────────────────────────────────────

def get_company_data(ticker: str) -> dict:
    """
    Yahoo Finance'ten şirket bilgisi + tarihsel fiyat verisi çeker.
    ticker = BIST kodu (örn. 'ASELS') → Yahoo'da 'ASELS.IS' olarak aranır.
    """
    yf_ticker = ticker.upper() + ".IS"
    bist_ticker = "XU100.IS"  # BIST 100 endeks

    try:
        stock = yf.Ticker(yf_ticker)
        bist  = yf.Ticker(bist_ticker)

        # 1 yıllık tarihsel veri
        hist_1y   = stock.history(period="1y")
        hist_6mo  = stock.history(period="6mo")
        hist_1mo  = stock.history(period="1mo")
        hist_1w   = stock.history(period="5d")
        bist_1y   = bist.history(period="1y")

        if hist_1y.empty:
            raise ValueError(f"Yahoo Finance'te {yf_ticker} için veri bulunamadı")

        info = stock.info or {}

        # Son kapanış fiyatı
        last_close = float(hist_1y["Close"].iloc[-1])
        prev_close = float(hist_1y["Close"].iloc[-2]) if len(hist_1y) > 1 else last_close

        # Getiriler
        def pct_return(hist):
            if len(hist) < 2:
                return None
            return round((hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100, 2)

        ret_1w  = pct_return(hist_1w)
        ret_1mo = pct_return(hist_1mo)
        ret_1y  = pct_return(hist_1y)

        # BIST 100 1 yıllık getiri karşılaştırması
        bist_ret_1y = pct_return(bist_1y) if not bist_1y.empty else None

        # 6 aylık günlük hacim listesi
        volume_data = []
        for dt, row in hist_6mo.iterrows():
            volume_data.append({
                "date":   dt.strftime("%Y-%m-%d"),
                "volume": int(row["Volume"]),
                "close":  round(float(row["Close"]), 2),
            })

        # 1 yıllık geçmiş (istikrar analizi için)
        price_history_1y = []
        for dt, row in hist_1y.iterrows():
            price_history_1y.append({
                "date":  dt.strftime("%Y-%m-%d"),
                "close": round(float(row["Close"]), 2),
                "high":  round(float(row["High"]),  2),
                "low":   round(float(row["Low"]),   2),
                "vol":   int(row["Volume"]),
            })

        # Volatilite (1y std dev of daily returns)
        daily_returns = hist_1y["Close"].pct_change().dropna()
        volatility_1y = round(float(daily_returns.std() * (252 ** 0.5) * 100), 2)  # annualized %

        # 52 haftalık high/low
        high_52w = round(float(hist_1y["High"].max()), 2)
        low_52w  = round(float(hist_1y["Low"].min()),  2)

        # İstikrar skoru (0-100): düşük volatilite + pozitif getiri = daha yüksek skor
        stability_score = max(0, min(100, int(50 - volatility_1y + (ret_1y or 0) * 0.3)))

        return {
            "ticker":           ticker.upper(),
            "yf_ticker":        yf_ticker,
            "company_name":     info.get("longName", ticker.upper()),
            "sector":           info.get("sector", "Bilinmiyor"),
            "industry":         info.get("industry", "Bilinmiyor"),
            "market_cap":       info.get("marketCap"),
            "employees":        info.get("fullTimeEmployees"),
            "description":      info.get("longBusinessSummary", ""),
            "last_close":       last_close,
            "prev_close":       prev_close,
            "day_change_pct":   round((last_close / prev_close - 1) * 100, 2),
            "ret_1w":           ret_1w,
            "ret_1mo":          ret_1mo,
            "ret_1y":           ret_1y,
            "bist_ret_1y":      bist_ret_1y,
            "vs_bist_1y":       round((ret_1y or 0) - (bist_ret_1y or 0), 2),
            "high_52w":         high_52w,
            "low_52w":          low_52w,
            "volatility_1y":    volatility_1y,
            "stability_score":  stability_score,
            "volume_data":      volume_data,
            "price_history_1y": price_history_1y,
            "fetched_at":       datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"get_company_data({ticker}) failed: {e}")
        return {
            "ticker": ticker.upper(),
            "error":  str(e),
            "company_name": ticker.upper(),
            "last_close": None,
        }


# ─────────────────────────────────────────────────────────────
#  2. KAP Bildirimleri (Google News RSS + DDG fallback)
# ─────────────────────────────────────────────────────────────

def _parse_rss_date(raw: str) -> Optional[datetime]:
    """RSS pubDate string → datetime objesi."""
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).replace(tzinfo=None)
    except Exception:
        pass
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(raw.strip()[:19], fmt)
        except ValueError:
            continue
    return None


def fetch_kap_announcements(ticker: str, limit: int = 15) -> list[dict]:
    """
    Google News RSS üzerinden KAP bildirimlerini çeker.
    Her bildirim için:
      - title, date, url, content
    Sonuçlar tarihe göre azalan sırada döner.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    queries = [
        f'"{ticker.upper()}" KAP bildirimi site:kap.org.tr',
        f'"{ticker.upper()}" KAP özel durum',
        f'"{ticker.upper()}" KAP borsa bildirimi',
        f'{ticker.upper()} KAP',
    ]

    seen_titles: set = set()
    docs: list[dict] = []

    for query in queries:
        if len(docs) >= limit * 2:
            break
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://news.google.com/rss/search?q={encoded}&hl=tr&gl=TR&ceid=TR:tr"
            resp = session.get(url, timeout=12)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            items = root.findall("./channel/item")

            for item in items:
                try:
                    title_el = item.find("title")
                    link_el  = item.find("link")
                    pub_el   = item.find("pubDate")
                    desc_el  = item.find("description")

                    title   = title_el.text.strip() if title_el is not None and title_el.text else ""
                    link    = link_el.text.strip()  if link_el  is not None and link_el.text  else ""
                    pub_raw = pub_el.text.strip()   if pub_el   is not None and pub_el.text   else ""
                    desc_raw = desc_el.text         if desc_el  is not None and desc_el.text  else ""

                    if not title or title in seen_titles:
                        continue
                    seen_titles.add(title)

                    desc_clean = re.sub(r"<[^>]+>", " ", desc_raw).strip()
                    content = f"{title}. {desc_clean}" if desc_clean else title
                    dt_obj  = _parse_rss_date(pub_raw)

                    docs.append({
                        "ticker":   ticker.upper(),
                        "title":    title,
                        "content":  content[:3000],
                        "url":      link,
                        "date_str": dt_obj.strftime("%Y-%m-%d") if dt_obj else "Bilinmiyor",
                        "date_obj": dt_obj,
                        "source":   "Google News RSS / KAP",
                    })
                except Exception:
                    continue
            time.sleep(0.4)
        except Exception as e:
            logger.warning(f"RSS fetch failed for query '{query}': {e}")

    # DDG fallback
    if len(docs) < 3:
        docs.extend(_ddg_fallback(ticker, limit, seen_titles))

    # Tarihe göre sırala (en yeni önce)
    docs_with_date = [d for d in docs if d.get("date_obj")]
    docs_no_date   = [d for d in docs if not d.get("date_obj")]
    docs_with_date.sort(key=lambda x: x["date_obj"], reverse=True)
    docs = docs_with_date + docs_no_date

    return docs[:limit]


def _ddg_fallback(ticker: str, limit: int, seen_titles: set) -> list[dict]:
    """DuckDuckGo HTML fallback."""
    result = []
    try:
        query = f"{ticker} KAP bildirimi"
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/109.0"},
            timeout=12,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        for res in soup.select(".result")[:limit * 2]:
            a   = res.select_one(".result__a")
            snp = res.select_one(".result__snippet")
            if not a:
                continue
            title = a.get_text(strip=True)
            if title in seen_titles:
                continue
            combo = (title + " " + (snp.get_text(strip=True) if snp else "")).upper()
            if "KAP" not in combo and "BİLDİRİM" not in combo and ticker.upper() not in combo:
                continue
            seen_titles.add(title)
            result.append({
                "ticker":   ticker.upper(),
                "title":    title,
                "content":  title + (". " + snp.get_text(strip=True) if snp else ""),
                "url":      a.get("href", ""),
                "date_str": "Bilinmiyor",
                "date_obj": None,
                "source":   "DuckDuckGo / KAP",
            })
            time.sleep(0.2)
    except Exception as e:
        logger.error(f"DDG fallback failed: {e}")
    return result


# ─────────────────────────────────────────────────────────────
#  3. Duyuru Sonrası Fiyat Etkisi
# ─────────────────────────────────────────────────────────────

def get_price_impact(ticker: str, announcements: list[dict]) -> list[dict]:
    """
    Her KAP duyurusu için ertesi gün fiyat değişimini hesaplar.
    Yahoo Finance'ten 1 yıllık günlük kapanış fiyatlarını bir kere çeker,
    sonra her duyuru tarihi için lookup yapar.
    """
    yf_ticker = ticker.upper() + ".IS"
    bist_ticker = "XU100.IS"

    try:
        hist  = yf.Ticker(yf_ticker).history(period="1y")
        bist  = yf.Ticker(bist_ticker).history(period="1y")

        # date → close price map
        price_map = {}
        for dt, row in hist.iterrows():
            price_map[dt.strftime("%Y-%m-%d")] = round(float(row["Close"]), 2)

        bist_map = {}
        for dt, row in bist.iterrows():
            bist_map[dt.strftime("%Y-%m-%d")] = round(float(row["Close"]), 2)

        sorted_dates = sorted(price_map.keys())

    except Exception as e:
        logger.error(f"Price history fetch failed: {e}")
        return announcements  # fiyat verisi eklenemedi, olduğu gibi dön

    enriched = []
    for ann in announcements:
        ann = dict(ann)
        date_obj = ann.get("date_obj")

        if date_obj is None:
            ann["price_day0"]    = None
            ann["price_day1"]    = None
            ann["price_change"]  = None
            ann["price_change_pct"] = None
            ann["bist_change_pct"]  = None
            enriched.append(ann)
            continue

        # Duyuru günü ve ertesi gün
        day0_str = date_obj.strftime("%Y-%m-%d")

        # sorted_dates içinde day0'dan küçük veya eşit olan son tarihi bul (T günü)
        day0_actual = None
        for d in sorted_dates:
            if d <= day0_str:
                day0_actual = d

        # T+1: day0_actual'dan sonraki ilk tarih
        day1_actual = None
        if day0_actual:
            idx = sorted_dates.index(day0_actual)
            if idx + 1 < len(sorted_dates):
                day1_actual = sorted_dates[idx + 1]

        p0 = price_map.get(day0_actual) if day0_actual else None
        p1 = price_map.get(day1_actual) if day1_actual else None

        b0 = bist_map.get(day0_actual) if day0_actual else None
        b1 = bist_map.get(day1_actual) if day1_actual else None

        change     = round(p1 - p0, 2)           if (p0 and p1) else None
        change_pct = round((p1/p0 - 1)*100, 2)   if (p0 and p1) else None
        bist_pct   = round((b1/b0 - 1)*100, 2)   if (b0 and b1) else None

        ann["price_day0"]      = p0
        ann["price_day1"]      = p1
        ann["price_change"]    = change
        ann["price_change_pct"] = change_pct
        ann["bist_change_pct"] = bist_pct
        ann["day0_date"]       = day0_actual
        ann["day1_date"]       = day1_actual
        enriched.append(ann)

    return enriched


# ─────────────────────────────────────────────────────────────
#  4. Tam Analiz (tek fonksiyon çağrısı)
# ─────────────────────────────────────────────────────────────

def full_analysis(ticker: str, kap_limit: int = 15) -> dict:
    """
    Belirli bir hisse için tam analiz paketi döner:
    - Şirket verileri
    - KAP duyuruları (son kap_limit adet)
    - Her duyuru için ertesi gün fiyat etkisi
    """
    logger.info(f"Full analysis starting for {ticker}...")

    company = get_company_data(ticker)
    logger.info(f"Company data fetched. Last close: {company.get('last_close')}")

    announcements = fetch_kap_announcements(ticker, limit=kap_limit)
    logger.info(f"Fetched {len(announcements)} KAP announcements")

    enriched = get_price_impact(ticker, announcements)
    logger.info(f"Price impact enrichment done")

    return {
        "ticker":        ticker.upper(),
        "company":       company,
        "announcements": enriched,
        "generated_at":  datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────────────────────
#  5. PDF Raporu (ReportLab)
# ─────────────────────────────────────────────────────────────

def generate_pdf_report(analysis: dict) -> bytes:
    """
    Analiz verisinden PDF rapor üretir ve bytes olarak döner.
    ReportLab kullanır.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Türkçe karakter desteği için Arial Unicode
    _ARIAL_UNICODE = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
    _ARIAL_BOLD    = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    _FONT_REGULAR  = "ArialUnicode"
    _FONT_BOLD     = "ArialUnicodeBold"
    try:
        if _FONT_REGULAR not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(_FONT_REGULAR, _ARIAL_UNICODE))
        if _FONT_BOLD not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(_FONT_BOLD, _ARIAL_BOLD))
    except Exception:
        _FONT_REGULAR = "Helvetica"
        _FONT_BOLD    = "Helvetica-Bold"

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    # ── Renkler
    DARK_BG    = colors.HexColor("#0a0f1e")
    GOLD       = colors.HexColor("#f5c842")
    GOLD_LIGHT = colors.HexColor("#fde68a")
    MUTED      = colors.HexColor("#64748b")
    GREEN      = colors.HexColor("#22c55e")
    RED        = colors.HexColor("#ef4444")
    BLUE       = colors.HexColor("#3b82f6")
    WHITE      = colors.white
    LIGHT_GREY = colors.HexColor("#1e293b")
    TEXT_GREY  = colors.HexColor("#cbd5e1")

    # ── Stiller
    styles = getSampleStyleSheet()

    def make_style(name, **kwargs):
        return ParagraphStyle(name, **kwargs)

    s_title = make_style("Title",
        fontName=_FONT_BOLD, fontSize=22,
        textColor=GOLD, alignment=TA_CENTER, spaceAfter=4)

    s_subtitle = make_style("Sub",
        fontName=_FONT_REGULAR, fontSize=10,
        textColor=MUTED, alignment=TA_CENTER, spaceAfter=12)

    s_section = make_style("Section",
        fontName=_FONT_BOLD, fontSize=13,
        textColor=GOLD, spaceBefore=16, spaceAfter=8)

    s_body = make_style("Body",
        fontName=_FONT_REGULAR, fontSize=9,
        textColor=TEXT_GREY, leading=14)

    s_small = make_style("Small",
        fontName=_FONT_REGULAR, fontSize=8,
        textColor=MUTED, leading=12)

    s_bold = make_style("Bold",
        fontName=_FONT_BOLD, fontSize=9,
        textColor=TEXT_GREY)

    s_ann_title = make_style("AnnTitle",
        fontName=_FONT_BOLD, fontSize=9,
        textColor=WHITE, leading=13)

    s_ann_meta = make_style("AnnMeta",
        fontName=_FONT_REGULAR, fontSize=8,
        textColor=MUTED, leading=12)

    def divider():
        return HRFlowable(width="100%", thickness=0.5,
                          color=colors.HexColor("#1e3a5f"), spaceAfter=8)

    # ── Veri
    company = analysis.get("company", {})
    tk      = analysis.get("ticker", "?")
    anns    = analysis.get("announcements", [])
    gen_at  = analysis.get("generated_at", "")[:10]

    def fmt_price(v):
        if v is None: return "N/A"
        return f"{v:,.2f} TL"

    def fmt_pct(v, arrow=True):
        if v is None: return "N/A"
        sign = "▲" if v >= 0 else "▼"
        color_tag = "#22c55e" if v >= 0 else "#ef4444"
        return f'<font color="{color_tag}">{sign if arrow else ""} %{abs(v):.2f}</font>'

    def fmt_vol(v):
        if v is None: return "N/A"
        if v >= 1_000_000_000: return f"{v/1e9:.2f}B"
        if v >= 1_000_000:     return f"{v/1e6:.2f}M"
        if v >= 1_000:         return f"{v/1e3:.1f}K"
        return str(v)

    story = []

    # ═══════════════════════════════════════
    # BÖLÜM 1: Başlık
    # ═══════════════════════════════════════
    story.append(Paragraph(f"ÖZAS Finance Agent", s_title))
    story.append(Paragraph(
        f"BIST Equity Intelligence Report · {company.get('company_name', tk)} ({tk}) · {gen_at}",
        s_subtitle))
    story.append(Spacer(1, 4))
    story.append(divider())

    # ═══════════════════════════════════════
    # BÖLÜM 2: Şirket Özeti
    # ═══════════════════════════════════════
    story.append(Paragraph("📊 Şirket Özeti", s_section))

    # Bilgi tablosu
    info_data = [
        ["Alan", "Değer"],
        ["Şirket Adı",    company.get("company_name", "–")],
        ["Sektör",        company.get("sector", "–")],
        ["Endüstri",      company.get("industry", "–")],
        ["Piyasa Değeri", fmt_vol(company.get("market_cap"))],
        ["Çalışan Sayısı", str(company.get("employees") or "–")],
    ]
    info_table = Table(info_data, colWidths=[4.5*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), LIGHT_GREY),
        ("TEXTCOLOR",   (0,0), (-1,0), GOLD),
        ("FONTNAME",    (0,0), (-1,0), _FONT_BOLD),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("FONTNAME",    (0,1), (0,-1), _FONT_BOLD),
        ("TEXTCOLOR",   (0,1), (0,-1), TEXT_GREY),
        ("TEXTCOLOR",   (1,1), (1,-1), TEXT_GREY),
        ("BACKGROUND",  (0,1), (-1,-1), colors.HexColor("#0f172a")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1),
         [colors.HexColor("#0f172a"), colors.HexColor("#111827")]),
        ("GRID",        (0,0), (-1,-1), 0.25, colors.HexColor("#1e3a5f")),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",  (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    # Açıklama
    desc = company.get("description", "")
    if desc:
        story.append(Paragraph(desc[:600] + ("..." if len(desc) > 600 else ""), s_small))
        story.append(Spacer(1, 10))

    # ═══════════════════════════════════════
    # BÖLÜM 3: Sayısal Performans
    # ═══════════════════════════════════════
    story.append(divider())
    story.append(Paragraph("📈 Fiyat & Performans", s_section))

    perf_data = [
        ["Metrik", "Değer", "Yorum"],
        ["Son Kapanış",          fmt_price(company.get("last_close")),  ""],
        ["Günlük Değişim",       fmt_pct(company.get("day_change_pct")), ""],
        ["1 Haftalık Getiri",    fmt_pct(company.get("ret_1w")),    ""],
        ["1 Aylık Getiri",       fmt_pct(company.get("ret_1mo")),   ""],
        ["1 Yıllık Getiri",      fmt_pct(company.get("ret_1y")),    ""],
        ["BIST100 1Y Getirisi",  fmt_pct(company.get("bist_ret_1y")), "BIST 100 Endeksi"],
        ["Hisse vs BIST100 (1Y)", fmt_pct(company.get("vs_bist_1y")), "Fazla / Eksik Getiri"],
        ["52H En Yüksek",        fmt_price(company.get("high_52w")), ""],
        ["52H En Düşük",         fmt_price(company.get("low_52w")),  ""],
        ["Yıllık Volatilite",    f"%{company.get('volatility_1y', '?')}", "Std.Dev. × √252"],
        ["İstikrar Skoru",       f"{company.get('stability_score', '?')}/100", "Ajan değerlendirmesi"],
    ]

    perf_table = Table(perf_data, colWidths=[5*cm, 4*cm, 7.5*cm])
    perf_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), LIGHT_GREY),
        ("TEXTCOLOR",    (0,0), (-1,0), GOLD),
        ("FONTNAME",     (0,0), (-1,0), _FONT_BOLD),
        ("FONTSIZE",     (0,0), (-1,-1), 9),
        ("FONTNAME",     (0,1), (0,-1), _FONT_BOLD),
        ("TEXTCOLOR",    (0,1), (0,-1), TEXT_GREY),
        ("TEXTCOLOR",    (1,1), (1,-1), TEXT_GREY),
        ("TEXTCOLOR",    (2,1), (2,-1), MUTED),
        ("ROWBACKGROUNDS", (0,1), (-1,-1),
         [colors.HexColor("#0f172a"), colors.HexColor("#111827")]),
        ("GRID",         (0,0), (-1,-1), 0.25, colors.HexColor("#1e3a5f")),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ("LEFTPADDING",  (0,0), (-1,-1), 10),
        ("FONTSIZE",     (2,1), (2,-1), 8),
    ]))
    story.append(perf_table)

    # BIST100 karşılaştırma yorumu
    vs = company.get("vs_bist_1y")
    ret_1y = company.get("ret_1y")
    bist_ret = company.get("bist_ret_1y")
    if vs is not None and ret_1y is not None and bist_ret is not None:
        if vs > 5:
            verdict = f"{tk} son 1 yılda BIST100'ü %{abs(vs):.1f} outperform etti. Piyasanın üzerinde güçlü bir performans sergiledi."
        elif vs < -5:
            verdict = f"{tk} son 1 yılda BIST100'ün %{abs(vs):.1f} gerisinde kaldı. Endeks düştüğünde hisse daha sert düştü / yükselişi takip edemedi."
        else:
            verdict = f"{tk} son 1 yılda BIST100 ile benzer performans gösterdi (%{vs:+.1f} fark)."
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"🔍 Ajan Yorumu: {verdict}", s_small))

    # ═══════════════════════════════════════
    # BÖLÜM 4: 1 Yıllık İstikrar Analizi
    # ═══════════════════════════════════════
    story.append(Spacer(1, 12))
    story.append(divider())
    story.append(Paragraph("🤖 1 Yıllık Geçmiş — Ajan İstikrar Analizi", s_section))

    ph = company.get("price_history_1y", [])
    stability = company.get("stability_score", 50)
    vol       = company.get("volatility_1y", 0)
    ret_1y    = company.get("ret_1y")

    analysis_text = _stability_analysis(tk, stability, vol, ret_1y, ph)
    story.append(Paragraph(analysis_text, s_body))

    # ═══════════════════════════════════════
    # BÖLÜM 5: 6 Aylık Hacim Özeti
    # ═══════════════════════════════════════
    story.append(Spacer(1, 12))
    story.append(divider())
    story.append(Paragraph("📦 6 Aylık Hacim & Fiyat Özeti", s_section))

    vol_data = company.get("volume_data", [])
    if vol_data:
        monthly_summary = _monthly_volume_summary(vol_data)
        monthly_table_data = [["Ay", "Ort. Günlük Hacim", "Ort. Kapanış"]]
        for row in monthly_summary:
            monthly_table_data.append([
                row["month_label"],
                fmt_vol(row["avg_volume"]),
                fmt_price(row["avg_close"]),
            ])

        monthly_table = Table(monthly_table_data, colWidths=[4*cm, 5*cm, 5*cm])
        monthly_table.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,0), LIGHT_GREY),
            ("TEXTCOLOR",    (0,0), (-1,0), GOLD),
            ("FONTNAME",     (0,0), (-1,0), _FONT_BOLD),
            ("FONTSIZE",     (0,0), (-1,-1), 9),
            ("TEXTCOLOR",    (0,1), (-1,-1), TEXT_GREY),
            ("ROWBACKGROUNDS", (0,1), (-1,-1),
             [colors.HexColor("#0f172a"), colors.HexColor("#111827")]),
            ("GRID",         (0,0), (-1,-1), 0.25, colors.HexColor("#1e3a5f")),
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",   (0,0), (-1,-1), 6),
            ("BOTTOMPADDING",(0,0), (-1,-1), 6),
            ("LEFTPADDING",  (0,0), (-1,-1), 10),
        ]))
        story.append(monthly_table)

    # ═══════════════════════════════════════
    # BÖLÜM 6: KAP Duyuruları + Fiyat Etkisi
    # ═══════════════════════════════════════
    story.append(Spacer(1, 12))
    story.append(divider())
    story.append(Paragraph(
        f"📢 Son {len(anns)} KAP Duyurusu — Ertesi Gün Fiyat Etkisi",
        s_section))

    if not anns:
        story.append(Paragraph("KAP verisi alınamadı.", s_body))
    else:
        ann_table_data = [["#", "Tarih", "Başlık", "Duy. Günü", "Ertesi Gün", "Değişim", "BIST100"]]

        for i, ann in enumerate(anns[:15], 1):
            title_short = ann.get("title", "?")[:55] + ("…" if len(ann.get("title","")) > 55 else "")
            date_str    = ann.get("date_str", "?")[:10]
            p0          = ann.get("price_day0")
            p1          = ann.get("price_day1")
            chg_pct     = ann.get("price_change_pct")
            bist_pct    = ann.get("bist_change_pct")

            chg_str = (
                f'+%{chg_pct:.2f}' if (chg_pct and chg_pct >= 0)
                else f'-%{abs(chg_pct):.2f}' if chg_pct
                else "N/A"
            )
            bist_str = (
                f'+%{bist_pct:.2f}' if (bist_pct and bist_pct >= 0)
                else f'-%{abs(bist_pct):.2f}' if bist_pct
                else "N/A"
            )

            ann_table_data.append([
                str(i),
                date_str,
                title_short,
                fmt_price(p0) if p0 else "–",
                fmt_price(p1) if p1 else "–",
                chg_str,
                bist_str,
            ])

        ann_table = Table(
            ann_table_data,
            colWidths=[0.6*cm, 2.2*cm, 5.5*cm, 2.2*cm, 2.2*cm, 2*cm, 1.8*cm],
        )

        ann_row_colors = []
        for i, ann in enumerate(anns[:15], 1):
            chg_pct = ann.get("price_change_pct")
            if chg_pct is not None:
                bg = colors.HexColor("#0b2a1a") if chg_pct >= 0 else colors.HexColor("#2a0b0b")
            else:
                bg = colors.HexColor("#0f172a") if i % 2 == 0 else colors.HexColor("#111827")
            ann_row_colors.append(bg)

        style_cmds = [
            ("BACKGROUND",   (0,0), (-1,0), LIGHT_GREY),
            ("TEXTCOLOR",    (0,0), (-1,0), GOLD),
            ("FONTNAME",     (0,0), (-1,0), _FONT_BOLD),
            ("FONTSIZE",     (0,0), (-1,-1), 7.5),
            ("TEXTCOLOR",    (0,1), (-1,-1), TEXT_GREY),
            ("GRID",         (0,0), (-1,-1), 0.25, colors.HexColor("#1e3a5f")),
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",   (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",(0,0), (-1,-1), 5),
            ("LEFTPADDING",  (0,0), (-1,-1), 5),
        ]
        for i, bg in enumerate(ann_row_colors, 1):
            style_cmds.append(("BACKGROUND", (0,i), (-1,i), bg))

        ann_table.setStyle(TableStyle(style_cmds))
        story.append(ann_table)

        # Duyuru detayları
        story.append(Spacer(1, 12))
        story.append(Paragraph("📋 Duyuru Detayları", s_section))

        for i, ann in enumerate(anns[:15], 1):
            title   = ann.get("title", "?")
            content = ann.get("content", "")
            date_s  = ann.get("date_str", "?")
            url     = ann.get("url", "")
            chg_pct = ann.get("price_change_pct")
            p0      = ann.get("price_day0")
            p1      = ann.get("price_day1")
            bist_p  = ann.get("bist_change_pct")

            # Fiyat etki yorumu
            if chg_pct is not None and p0 is not None and p1 is not None:
                direction = "yükseldi" if chg_pct >= 0 else "düştü"
                bist_dir  = "yükseldi" if (bist_p or 0) >= 0 else "düştü"
                impact_text = (
                    f"Duyurudan sonraki gün hisse %{abs(chg_pct):.2f} {direction} "
                    f"({p0:.2f} → {p1:.2f} TL). "
                    f"Aynı günde BIST100 %{abs(bist_p):.2f} {bist_dir}."
                    if bist_p is not None else
                    f"Duyurudan sonraki gün hisse %{abs(chg_pct):.2f} {direction} ({p0:.2f} → {p1:.2f} TL)."
                )
            elif chg_pct is None and ann.get("date_str") != "Bilinmiyor":
                impact_text = "Bu duyuru tarihi için fiyat verisi mevcut değil (1 yıl öncesi veya gelecek tarih olabilir)."
            else:
                impact_text = "Duyuru tarihi bilinemediği için fiyat etkisi hesaplanamadı."

            block = KeepTogether([
                Paragraph(f"{i}. {title}", s_ann_title),
                Paragraph(f"📅 {date_s}  |  Kaynak: {ann.get('source','?')}", s_ann_meta),
                Spacer(1, 3),
                Paragraph(content[:400] + ("…" if len(content) > 400 else ""), s_small),
                Spacer(1, 3),
                Paragraph(f"💹 Fiyat Etkisi: {impact_text}", s_bold),
                Spacer(1, 6),
                HRFlowable(width="100%", thickness=0.25,
                           color=colors.HexColor("#1e3a5f"), spaceAfter=6),
            ])
            story.append(block)

    # ═══════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════
    story.append(Spacer(1, 16))
    story.append(divider())
    story.append(Paragraph(
        "⚠️ Bu rapor ÖZAS Finance Agent tarafından yalnızca akademik ve bilgi amaçlı üretilmiştir. "
        "Yatırım tavsiyesi niteliği taşımaz. Al/sat kararları için kullanılamaz. "
        "Veriler Yahoo Finance ve Google News RSS üzerinden otomatik alınmıştır.",
        s_small))

    doc.build(story)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────
#  Yardımcı Fonksiyonlar
# ─────────────────────────────────────────────────────────────

def _stability_analysis(ticker, stability, vol, ret_1y, price_history) -> str:
    """1 yıllık verilerden ajan tarzı istikrar metni üretir."""
    lines = []

    if ret_1y is not None:
        if ret_1y > 50:
            perf_txt = f"son 1 yılda %{ret_1y:.1f} gibi son derece güçlü bir getiri sağladı"
        elif ret_1y > 20:
            perf_txt = f"son 1 yılda %{ret_1y:.1f} ile piyasanın üzerinde performans gösterdi"
        elif ret_1y > 0:
            perf_txt = f"son 1 yılda %{ret_1y:.1f} artı getiri elde etti"
        elif ret_1y > -20:
            perf_txt = f"son 1 yılda %{ret_1y:.1f} kayıp yaşadı"
        else:
            perf_txt = f"son 1 yılda %{ret_1y:.1f} gibi ciddi bir değer kaybetti"
        lines.append(f"{ticker} {perf_txt}.")

    if vol is not None:
        if vol < 20:
            vol_txt = f"Yıllık volatilite %{vol:.1f} ile görece düşük — fiyat hareketleri stabil seyrediyor."
        elif vol < 40:
            vol_txt = f"Yıllık volatilite %{vol:.1f} ile orta seviyede — normal piyasa dalgalanmaları izleniyor."
        else:
            vol_txt = f"Yıllık volatilite %{vol:.1f} ile yüksek — intraday/haftalık fiyat dalgalanmaları önemli."
        lines.append(vol_txt)

    if stability >= 70:
        lines.append(f"İstikrar skoru {stability}/100 — ajan bu hisseyi düşük riskli ve tutarlı performanslı olarak değerlendiriyor.")
    elif stability >= 40:
        lines.append(f"İstikrar skoru {stability}/100 — orta düzey istikrar, piyasa koşullarına göre değişken seyir izleniyor.")
    else:
        lines.append(f"İstikrar skoru {stability}/100 — yüksek oynaklık ve/veya negatif getiri nedeniyle düşük istikrar tespit edildi.")

    # En iyi ve en kötü çeyrek
    if len(price_history) >= 60:
        q_size = len(price_history) // 4
        q1_avg = sum(d["close"] for d in price_history[:q_size]) / q_size
        q4_avg = sum(d["close"] for d in price_history[-q_size:]) / q_size
        trend = "yükseliş" if q4_avg > q1_avg else "düşüş"
        lines.append(
            f"Yıllık trend analizi: yılın başında ortalama {q1_avg:.2f} TL'den "
            f"yılın sonuna {q4_avg:.2f} TL'ye — genel {trend} trendi."
        )

    return " ".join(lines)


def _monthly_volume_summary(vol_data: list[dict]) -> list[dict]:
    """6 aylık hacim verisini ay bazında özetler."""
    from collections import defaultdict
    monthly = defaultdict(list)
    for item in vol_data:
        month_key = item["date"][:7]  # "YYYY-MM"
        monthly[month_key].append(item)

    result = []
    for month_key in sorted(monthly.keys()):
        items = monthly[month_key]
        avg_vol   = int(sum(i["volume"] for i in items) / len(items))
        avg_close = round(sum(i["close"]  for i in items) / len(items), 2)
        # Month label
        try:
            dt = datetime.strptime(month_key, "%Y-%m")
            tr_months = ["","Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"]
            label = f"{tr_months[dt.month]} {dt.year}"
        except Exception:
            label = month_key
        result.append({"month_label": label, "avg_volume": avg_vol, "avg_close": avg_close})

    return result


# ─────────────────────────────────────────────────────────────
#  CLI Test
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ticker = sys.argv[1] if len(sys.argv) > 1 else "ASELS"

    print(f"\n=== {ticker} Tam Analiz ===")
    result = full_analysis(ticker, kap_limit=15)
    company = result["company"]
    anns    = result["announcements"]

    print(f"Şirket: {company.get('company_name')}")
    print(f"Son Kapanış: {company.get('last_close')} TL")
    print(f"1Y Getiri: %{company.get('ret_1y')}")
    print(f"BIST100: %{company.get('bist_ret_1y')}")
    print(f"\nKAP Duyuruları ({len(anns)} adet):")
    for i, ann in enumerate(anns[:5], 1):
        chg = ann.get('price_change_pct')
        chg_str = f"%{chg:+.2f}" if chg is not None else "N/A"
        print(f"  {i}. [{ann.get('date_str')}] {ann.get('title','?')[:60]}")
        print(f"     Ertesi gün değişim: {chg_str}")

    # PDF test
    print("\nPDF üretiliyor...")
    pdf_bytes = generate_pdf_report(result)
    out_path = f"/tmp/{ticker}_report.pdf"
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"PDF kaydedildi: {out_path} ({len(pdf_bytes):,} byte)")
