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

        # Handle missing info gracefully
        company_full_name = info.get("longName") or info.get("shortName") or ticker.upper()
        sector = info.get("sector") or "-"
        industry = info.get("industry") or "-"
        mkt_cap = info.get("marketCap")
        
        # If info is completely missing, try to get at least the name from ticker
        if not info and not hist_1y.empty:
            logger.warning(f"Stock info is empty for {yf_ticker}, using history only.")

        return {
            "ticker":           ticker.upper(),
            "yf_ticker":        yf_ticker,
            "company_name":     company_full_name,
            "sector":           sector,
            "industry":         industry,
            "market_cap":       mkt_cap,
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


# ─────────────────────────────────────────────────────────────
#  2. KAP Bildirimleri (Playwright Direct Scraping)
# ─────────────────────────────────────────────────────────────

def fetch_kap_announcements(ticker: str, limit: int = 15) -> list[dict]:
    """
    KAP üzerinden doğrudan bildirimleri çeker (Playwright kullanarak).
    Adımlar:
      1. kap.org.tr'ye gir
      2. Arama kutusuna ticker yaz
      3. Dropdown'dan şirketi seç
      4. Bildirimler sekmesine git
      5. Son 1 ay filtresini uygula
      6. Verileri çek
    """
    from playwright.sync_api import sync_playwright
    
    docs: list[dict] = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Use a slightly longer timeout and less strict wait condition
            context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            page = context.new_page()
            page.set_default_timeout(45000)
            
            logger.info(f"Navigating to KAP for {ticker}...")
            page.goto('https://www.kap.org.tr/tr/', wait_until='domcontentloaded')
            
            # Step 1: Type ticker
            # Using the #all-search ID found in previous analysis
            page.fill('#all-search', ticker)
            page.wait_for_timeout(2000)
            
            # Step 2: Select company from dropdown/results
            # We try to click the first reasonable result matching the ticker
            try:
                # The dropdown results are in #searchDiv
                company_selector = f'#searchDiv a:has-text("{ticker}")'
                if page.locator(company_selector).count() > 0:
                    page.click(company_selector)
                else:
                    page.keyboard.press('Enter')
            except:
                page.keyboard.press('Enter')
            
            page.wait_for_timeout(4000)
            
            # Step 3: Navigate to 'Bildirimler' tab
            try:
                # Look for the tab. It might be an <a> or <div>
                page.click('a:has-text("Bildirimler")', timeout=10000)
                page.wait_for_timeout(2000)
            except:
                logger.warning("Bildirimler tab not found via text match.")

            # Step 4: Filter 'Son 1 ay' and search
            try:
                page.click('text="Son 1 ay"', timeout=10000)
                page.wait_for_timeout(1000)
                page.click('button:has-text("Ara")')
                page.wait_for_timeout(3000)
            except:
                logger.warning("Filtering for 'Son 1 ay' failed.")

            # Step 5: Scrape Table
            rows = page.locator('table tbody tr').all()
            for row in rows:
                if len(docs) >= limit:
                    break
                cells = row.locator('td').all_text_contents()
                if len(cells) >= 6:
                    # Tarih, Kod, Şirket, Tip, Konu, Özet Bilgi
                    dt_str = cells[1].strip()
                    # Parse date (Bugün HH:mm or DD.MM.YYYY HH:mm)
                    dt_obj = _parse_kap_date(dt_str)
                    
                    link_el = row.locator('a').first
                    url = "https://www.kap.org.tr" + link_el.get_attribute('href') if link_el.count() > 0 else ""
                    
                    docs.append({
                        "ticker":   ticker.upper(),
                        "title":    cells[5].strip(), # Konu
                        "content":  cells[6].strip() if len(cells) > 6 else "", # Özet Bilgi
                        "url":      url,
                        "date_str": dt_obj.strftime("%Y-%m-%d") if dt_obj else dt_str,
                        "date_obj": dt_obj,
                        "source":   "KAP Direct",
                        "type":     cells[4].strip() # Tip (ÖDA, DG vb.)
                    })
            
            browser.close()
    except Exception as e:
        logger.error(f"fetch_kap_announcements({ticker}) failed: {e}")
        # In case of failure, we might want to fallback to RSS or return empty
        return []

    return docs

def _parse_kap_date(raw: str) -> Optional[datetime]:
    """KAP tarih formatını (örn: 'Bugün 14:15' veya '15.04.2024 10:00') datetime'a çevirir."""
    now = datetime.now()
    if "Bugün" in raw:
        try:
            t_str = raw.replace("Bugün", "").strip()
            return datetime.combine(now.date(), datetime.strptime(t_str, "%H:%M").time())
        except: return now
    if "Dün" in raw:
        try:
            t_str = raw.replace("Dün", "").strip()
            return datetime.combine(now.date() - timedelta(days=1), datetime.strptime(t_str, "%H:%M").time())
        except: return now - timedelta(days=1)
    
    for fmt in ["%d.%m.%Y %H:%M", "%d.%m.%Y"]:
        try:
            return datetime.strptime(raw.strip()[:16], fmt)
        except: continue
    return None


# ─────────────────────────────────────────────────────────────
#  6. AI Commentary (ÖZAS Agent Yorumu)
# ─────────────────────────────────────────────────────────────

def generate_agent_commentary(announcement: dict, price_impact: Optional[float] = None) -> str:
    """
    KAP bildirimine binaen 'ÖZAS Agent' yorumu üretir.
    Gerçek uygulamada bir LLM (Gemini/OpenAI) çağrısı yapılır.
    """
    title = announcement.get('title', '')
    content = announcement.get('content', '')
    impact = f"Bu bildirim sonrası hisse fiyatı %{price_impact:+.2f} değişim gösterdi." if price_impact is not None else "Fiyat verisi henüz işlenmedi."
    
    # Simple logic-based commentary generation if no LLM
    comment = ""
    if "Kar Payı" in title or "Temettü" in title:
        comment = "Şirketin nakit temettü dağıtım kararı hissedar bağlılığı açısından pozitif bir sinyaldir. Dağıtım oranı sektör ortalamalarıyla kıyaslanmalıdır."
    elif "İhale" in title or "Yeni İş İlişkisi" in title:
        comment = "Yeni alınan iş/ihale, şirketin iş hacmini ve gelecekteki nakit akışlarını doğrudan olumlu etkileyecektir. Operasyonel karlılık üzerindeki marj etkisi takip edilmelidir."
    elif "Kredi" in title or "Borçlanma" in title:
        comment = "Borçlanma araçları ihracı veya kredi kullanımı, şirketin finansman yapısını ve likidite yönetimini etkiler. Borç/Özsermaye rasyosu kritik öneme sahiptir."
    else:
        comment = f"Bu bildirim, şirketin genel operasyonel akışını ve şeffaflık ilkelerini yansıtmaktadır. Yatırımcıların bildirim içeriğindeki detaylara (eklere) odaklanması önerilir."

    return f"{comment} {impact}"


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
        HRFlowable, KeepTogether, Frame, PageTemplate
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping
    import os

    # ── Font Kayıt (Playfair Display + Outfit) ────────────────────────────────
    # _BASE: Try multiple locations to find fonts
    possibilities = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "fonts"),
        os.path.join(os.getcwd(), "assets", "fonts"),
        os.path.join(os.getcwd(), "backend", "assets", "fonts"),
        "/app/assets/fonts",
        "./assets/fonts"
    ]
    _BASE = None
    for p in possibilities:
        if os.path.isdir(p):
            _BASE = p
            break
    
    if not _BASE:
        logger.error("CRITICAL: Assets/fonts directory not found in any expected location.")
        _BASE = "assets/fonts" # Fallback to relative

    def _reg(name, path):
        """TTF dosyasını ReportLab'a kaydeder. Başarılı ise True döner."""
        if name in pdfmetrics.getRegisteredFontNames():
            return True
        try:
            full_path = os.path.abspath(path)
            if not os.path.isfile(full_path):
                logger.warning(f"Font dosyası bulunamadı: {full_path}")
                return False
            if os.path.getsize(full_path) < 1000:
                logger.warning(f"Font dosyası çok küçük (bozuk olabilir): {full_path}")
                return False
            pdfmetrics.registerFont(TTFont(name, full_path))
            logger.info(f"Font yüklendi: {name} ({os.path.getsize(full_path)//1024}KB)")
            return True
        except Exception as exc:
            logger.warning(f"Font kaydedilemedi [{name}]: {exc}")
            return False

    # Playfair Display – ÖZAS logo ve başlıklar
    pf_ok  = _reg("Playfair",     os.path.join(_BASE, "PlayfairDisplay.ttf"))
    pfb_ok = _reg("PlayfairBold", os.path.join(_BASE, "PlayfairDisplay-Bold.ttf"))
    # Outfit – body, tablolar, meta
    ot_ok  = _reg("Outfit",       os.path.join(_BASE, "Outfit.ttf"))
    otb_ok = _reg("OutfitBold",   os.path.join(_BASE, "Outfit-Bold.ttf"))

    if pf_ok and pfb_ok:
        addMapping("Playfair", 0, 0, "Playfair")
        addMapping("Playfair", 1, 0, "PlayfairBold")

    if ot_ok and otb_ok:
        addMapping("Outfit", 0, 0, "Outfit")
        addMapping("Outfit", 1, 0, "OutfitBold")

    # Aktif font adları (ReportLab built-in fallback — platformdan bağımsız)
    F_SERIF      = "Playfair"     if pf_ok  else "Times-Roman"
    F_SERIF_BOLD = "PlayfairBold" if pfb_ok else "Times-Bold"
    F_SANS       = "Outfit"       if ot_ok  else "Helvetica"
    F_SANS_BOLD  = "OutfitBold"   if otb_ok else "Helvetica-Bold"

    logger.info(f"PDF Fontlar: SERIF={F_SERIF}/{F_SERIF_BOLD}  SANS={F_SANS}/{F_SANS_BOLD}")

    # ── Renk Paleti (ekrandaki beyaz premium tasarım) ─────────────────────────
    BLACK      = colors.HexColor("#000000")
    DARK       = colors.HexColor("#111111")
    MID        = colors.HexColor("#333333")
    MUTED      = colors.HexColor("#777777")
    VERY_MUTED = colors.HexColor("#aaaaaa")
    LIGHT_LINE = colors.HexColor("#e0e0e0")
    LIGHT_BG   = colors.HexColor("#f8f8f8")
    GOLD_ACC   = colors.HexColor("#937d65")   # logo alt yazı altın tonu
    GREEN      = colors.HexColor("#1a7a3c")
    RED        = colors.HexColor("#b91c1c")
    WHITE      = colors.white
    BLUE       = colors.HexColor("#1d4ed8")

    # ── Sayfa Yapısı ──────────────────────────────────────────────────────────
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2.2*cm,
        rightMargin=2.2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )
    W = A4[0] - 4.4*cm   # kullanılabilir genişlik

    # ── Stil Tanımları ────────────────────────────────────────────────────────
    def P(name, **kw):
        return ParagraphStyle(name, **kw)

    # ÖZAS büyük logosu (Playfair Display, Bold)
    s_logo = P("Logo",
        fontName=F_SERIF_BOLD, fontSize=28,
        textColor=BLACK, leading=30, spaceAfter=0)

    # "EQUITY INTELLIGENCE REPORT" — küçük spaced üst yazı
    s_sub_logo = P("SubLogo",
        fontName=F_SANS, fontSize=9,
        textColor=GOLD_ACC, letterSpacing=2.5,
        alignment=TA_LEFT, spaceAfter=2)

    # Bölüm başlıkları (Summary Analysis, Performance vs.)
    s_section = P("Section",
        fontName=F_SANS_BOLD, fontSize=10,
        textColor=BLACK, letterSpacing=1.5,
        spaceBefore=18, spaceAfter=8,
        textTransform="uppercase" if hasattr(ParagraphStyle, 'textTransform') else None)

    # Tablo başlık etiketi
    s_label = P("Label",
        fontName=F_SANS, fontSize=8,
        textColor=MUTED, letterSpacing=1.2,
        spaceBefore=14, spaceAfter=4)

    # Body metin
    s_body = P("Body",
        fontName=F_SANS, fontSize=10,
        textColor=MID, leading=16, spaceAfter=4)

    # Küçük açıklama
    s_small = P("Small",
        fontName=F_SANS, fontSize=8.5,
        textColor=MUTED, leading=13)

    # Duyuru başlığı (Türkçe karakterlerin hatasız çıkması için Outfit Bold kullanıyoruz)
    s_ann_title = P("AnnTitle",
        fontName=F_SANS_BOLD, fontSize=10,
        textColor=DARK, leading=14, spaceAfter=2)

    # Duyuru meta (tarih, kaynak)
    s_ann_meta = P("AnnMeta",
        fontName=F_SANS, fontSize=8,
        textColor=MUTED, leading=12)

    # Fiyat etkisi satırı
    s_impact = P("Impact",
        fontName=F_SANS_BOLD, fontSize=9,
        textColor=MID, leading=13, spaceAfter=4)

    # Sağ hizalı (ticker, tarih)
    s_right = P("Right",
        fontName=F_SANS, fontSize=9,
        textColor=MID, alignment=TA_RIGHT)

    # Disclaimer
    s_disclaimer = P("Disc",
        fontName=F_SANS, fontSize=8,
        textColor=VERY_MUTED, leading=12)

    def divider(thick=0.5, color=LIGHT_LINE, before=6, after=8):
        return HRFlowable(width="100%", thickness=thick,
                          color=color, spaceAfter=after, spaceBefore=before)

    def section_title(text):
        # Büyük harf + ince çizgi
        return [
            Spacer(1, 4),
            Paragraph(f"<b>{text.upper()}</b>", s_section),
            divider(thick=0.5, color=LIGHT_LINE, before=0, after=6),
        ]

    # ── Veri ──────────────────────────────────────────────────────────────────
    company = analysis.get("company", {})
    tk      = analysis.get("ticker", "?")
    anns    = analysis.get("announcements", [])
    gen_at  = analysis.get("generated_at", "")[:10]

    def fmt_pct(v, plain=False):
        if v is None: return "N/A"
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.2f}%"

    def fmt_price(v):
        if v is None: return "N/A"
        return f"{v:,.2f} TL"

    def fmt_vol(v):
        if v is None: return "N/A"
        if v >= 1_000_000_000: return f"{v/1e9:.2f}B"
        if v >= 1_000_000:     return f"{v/1e6:.2f}M"
        if v >= 1_000:         return f"{v/1e3:.1f}K"
        return str(v)

    story = []

    # ═══════════════════════════════════════════════════════════════════════════
    # HEADER — ÖZAS / Equity Intelligence Report / Ticker / Date
    # ═══════════════════════════════════════════════════════════════════════════
    hdr_data = [[
        [
            Paragraph("ÖZAS", s_logo),
            Paragraph("EQUITY INTELLIGENCE REPORT", s_sub_logo),
        ],
        [
            Paragraph(f"<b>{tk}</b>", P("TKR", fontName=F_SERIF_BOLD, fontSize=12,
                       textColor=BLACK, alignment=TA_RIGHT)),
            Paragraph(gen_at, P("DT", fontName=F_SANS, fontSize=9,
                       textColor=MUTED, alignment=TA_RIGHT)),
        ]
    ]]
    hdr_table = Table(hdr_data, colWidths=[W*0.65, W*0.35])
    hdr_table.setStyle(TableStyle([
        ("VALIGN",  (0,0), (-1,-1), "BOTTOM"),
        ("LEFTPADDING",  (0,0), (0,0), 0),
        ("RIGHTPADDING", (1,0), (1,0), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 0),
        ("BOTTOMPADDING",(0,0), (-1,-1), 0),
    ]))
    story.append(hdr_table)
    story.append(Spacer(1, 8))
    story.append(divider(thick=1.2, color=BLACK, before=0, after=16))

    # ═══════════════════════════════════════════════════════════════════════════
    # BÖLÜM 1 — Şirket Özeti
    # ═══════════════════════════════════════════════════════════════════════════
    story += section_title("Summary Analysis")

    # Şirket bilgi tablosu
    co_name = company.get("company_name", tk)
    sector  = company.get("sector", "–")
    ind     = company.get("industry", "–")
    mktcap  = fmt_vol(company.get("market_cap"))
    emps    = str(company.get("employees") or "–")

    info_rows = [
        ["Company", co_name],
        ["Sector",  sector],
        ["Industry", ind],
        ["Market Cap", mktcap],
        ["Employees", emps],
    ]
    info_t = Table(info_rows, colWidths=[3.5*cm, W - 3.5*cm])
    info_t.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (0,-1), F_SANS_BOLD),
        ("FONTNAME",  (1,0), (1,-1), F_SANS),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1), MUTED),
        ("TEXTCOLOR", (1,0), (1,-1), DARK),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LINEBELOW", (0,-1), (-1,-1), 0.3, LIGHT_LINE),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(info_t)

    desc = company.get("description", "")
    if desc:
        story.append(Spacer(1, 10))
        story.append(Paragraph(desc[:500] + ("..." if len(desc) > 500 else ""), s_small))

    # ═══════════════════════════════════════════════════════════════════════════
    # BÖLÜM 2 — Performance Metrics (tablo)
    # ═══════════════════════════════════════════════════════════════════════════
    story += section_title("Performance Metrics")

    lc   = company.get("last_close")
    dc   = company.get("day_change_pct")
    r1w  = company.get("ret_1w")
    r1m  = company.get("ret_1mo")
    r1y  = company.get("ret_1y")
    bist = company.get("bist_ret_1y")
    vs   = company.get("vs_bist_1y")
    h52  = company.get("high_52w")
    l52  = company.get("low_52w")
    vol  = company.get("volatility_1y")
    stab = company.get("stability_score")

    def colored_pct(v):
        if v is None: return "N/A"
        sign = "+" if v >= 0 else ""
        col = "#1a7a3c" if v >= 0 else "#b91c1c"
        return Paragraph(f'<font color="{col}"><b>{sign}{v:.2f}%</b></font>', P("Pct", fontName=F_SANS, fontSize=9, leading=10))

    perf_rows = [
        ["Last Close",          fmt_price(lc),                ""],
        ["Daily Change",        colored_pct(dc),              "Today"],
        ["1-Week Return",       colored_pct(r1w),             ""],
        ["1-Month Return",      colored_pct(r1m),             ""],
        ["1-Year Return",       colored_pct(r1y),             ""],
        ["BIST100 1Y",          colored_pct(bist),            "Benchmark"],
        ["vs. BIST100 (1Y)",    colored_pct(vs),              "Alpha"],
        ["52W High",            fmt_price(h52),               ""],
        ["52W Low",             fmt_price(l52),               ""],
        ["Annual Volatility",   f"{vol:.1f}%" if vol else "N/A", "Std.Dev × √252"],
        ["Stability Score",     f"{stab}/100" if stab else "N/A", "Agent Assessment"],
    ]

    perf_t = Table(perf_rows, colWidths=[4*cm, 3.5*cm, W - 7.5*cm])
    perf_t.setStyle(TableStyle([
        ("FONTNAME",   (0,0), (0,-1), F_SANS_BOLD),
        ("FONTNAME",   (1,0), (-1,-1), F_SANS),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("TEXTCOLOR",  (0,0), (0,-1), MUTED),
        ("TEXTCOLOR",  (2,0), (2,-1), VERY_MUTED),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, LIGHT_BG]),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("LINEBELOW", (0,-1), (-1,-1), 0.5, LIGHT_LINE),
    ]))
    story.append(perf_t)

    # Yorum satırı
    if vs is not None and r1y is not None and bist is not None:
        if vs > 5:
            verdict = f"{tk} outperformed BIST100 by {vs:.1f}% over the past year — strong alpha generation."
        elif vs < -5:
            verdict = f"{tk} underperformed BIST100 by {abs(vs):.1f}% — lagged the index materially."
        else:
            verdict = f"{tk} tracked BIST100 closely with a {vs:+.1f}% differential over 12 months."
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<i>Agent view: {verdict}</i>", s_small))

    # ═══════════════════════════════════════════════════════════════════════════
    # BÖLÜM 3 — Stability Analysis
    # ═══════════════════════════════════════════════════════════════════════════
    story += section_title("Stability & Risk Analysis")
    ph = company.get("price_history_1y", [])
    analysis_text = _stability_analysis(tk, stab or 50, vol or 0, r1y, ph)
    story.append(Paragraph(analysis_text, s_body))

    # ═══════════════════════════════════════════════════════════════════════════
    # BÖLÜM 4 — 6 Aylık Hacim Özeti
    # ═══════════════════════════════════════════════════════════════════════════
    vol_data = company.get("volume_data", [])
    if vol_data:
        story += section_title("6-Month Volume Summary")
        monthly = _monthly_volume_summary(vol_data)
        mv_rows = [["Month", "Avg Daily Volume", "Avg Close"]]
        for row in monthly:
            mv_rows.append([row["month_label"], fmt_vol(row["avg_volume"]), fmt_price(row["avg_close"])])

        mv_t = Table(mv_rows, colWidths=[4*cm, 4.5*cm, 4.5*cm])
        mv_t.setStyle(TableStyle([
            ("FONTNAME",   (0,0), (-1,0), F_SANS_BOLD),
            ("FONTNAME",   (0,1), (-1,-1), F_SANS),
            ("FONTSIZE",   (0,0), (-1,-1), 9),
            ("TEXTCOLOR",  (0,0), (-1,0), MUTED),
            ("TEXTCOLOR",  (0,1), (-1,-1), DARK),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LIGHT_BG]),
            ("LINEBELOW",  (0,0), (-1,0), 0.5, LIGHT_LINE),
            ("LINEBELOW",  (0,-1), (-1,-1), 0.5, LIGHT_LINE),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 0),
        ]))
        story.append(mv_t)

    # ═══════════════════════════════════════════════════════════════════════════
    # BÖLÜM 5 — KAP Duyuruları Özet Tablo
    # ═══════════════════════════════════════════════════════════════════════════
    story += section_title(f"KAP Disclosures — Next-Day Price Reaction ({len(anns)} events)")

    if not anns:
        story.append(Paragraph("No KAP disclosure data available.", s_body))
    else:
        kap_rows = [["#", "Date", "Headline", "T+0", "T+1", "Change", "BIST100"]]
        for i, ann in enumerate(anns[:15], 1):
            title_s  = ann.get("title", "?")[:52] + ("…" if len(ann.get("title","")) > 52 else "")
            date_s   = ann.get("date_str", "?")[:10]
            p0       = ann.get("price_day0")
            p1       = ann.get("price_day1")
            chg      = ann.get("price_change_pct")
            bist_c   = ann.get("bist_change_pct")

            chg_str = (
                f'<font color="#1a7a3c"><b>+{chg:.2f}%</b></font>' if (chg is not None and chg >= 0)
                else f'<font color="#b91c1c"><b>{chg:.2f}%</b></font>'  if chg is not None
                else "–"
            )
            bist_str = (
                f'<font color="#1a7a3c">+{bist_c:.2f}%</font>' if (bist_c is not None and bist_c >= 0)
                else f'<font color="#b91c1c">{bist_c:.2f}%</font>' if bist_c is not None
                else "–"
            )
            kap_rows.append([
                str(i), date_s,
                Paragraph(title_s, P("TS", fontName=F_SANS, fontSize=8, textColor=DARK, leading=11)),
                f"{p0:.2f}" if p0 else "–",
                f"{p1:.2f}" if p1 else "–",
                Paragraph(chg_str, P("CS", fontName=F_SANS, fontSize=9, textColor=DARK, leading=11)),
                Paragraph(bist_str, P("BS", fontName=F_SANS, fontSize=9, textColor=DARK, leading=11)),
            ])

        kap_t = Table(
            kap_rows,
            colWidths=[0.5*cm, 1.9*cm, W - 9.4*cm, 1.8*cm, 1.8*cm, 1.7*cm, 1.7*cm]
        )

        row_colors = []
        for i, ann in enumerate(anns[:15], 1):
            chg = ann.get("price_change_pct")
            if chg is not None:
                bg = colors.HexColor("#f0faf4") if chg >= 0 else colors.HexColor("#fef2f2")
            else:
                bg = WHITE if i % 2 == 0 else LIGHT_BG
            row_colors.append(bg)

        kap_style = [
            ("FONTNAME",   (0,0), (-1,0), F_SANS_BOLD),
            ("FONTSIZE",   (0,0), (-1,-1), 8.5),
            ("FONTNAME",   (0,1), (-1,-1), F_SANS),
            ("TEXTCOLOR",  (0,0), (-1,0), MUTED),
            ("TEXTCOLOR",  (0,1), (-1,-1), DARK),
            ("LINEBELOW",  (0,0), (-1,0), 0.5, LIGHT_LINE),
            ("LINEBELOW",  (0,-1), (-1,-1), 0.5, LIGHT_LINE),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 3),
            ("VALIGN",     (0,0), (-1,-1), "TOP"),
        ]
        for i, bg in enumerate(row_colors, 1):
            kap_style.append(("BACKGROUND", (0,i), (-1,i), bg))
        kap_t.setStyle(TableStyle(kap_style))
        story.append(kap_t)

    # ═══════════════════════════════════════════════════════════════════════════
    # BÖLÜM 6 — Duyuru Detayları
    # ═══════════════════════════════════════════════════════════════════════════
    story += section_title("Disclosure Details & Price Impact")

    for i, ann in enumerate(anns[:15], 1):
        title   = ann.get("title", "?")
        content = ann.get("content", "")
        date_s  = ann.get("date_str", "?")[:10]
        chg     = ann.get("price_change_pct")
        p0      = ann.get("price_day0")
        p1      = ann.get("price_day1")
        bist_c  = ann.get("bist_change_pct")

        if chg is not None and p0 and p1:
            direction = "advanced" if chg >= 0 else "declined"
            bist_dir  = "rose" if (bist_c or 0) >= 0 else "fell"
            impact_line = (
                f"Post-announcement: stock {direction} {abs(chg):.2f}% "
                f"({p0:.2f} → {p1:.2f} TL). "
                f"BIST100 {bist_dir} {abs(bist_c):.2f}% on the same day."
                if bist_c is not None else
                f"Post-announcement: stock {direction} {abs(chg):.2f}% ({p0:.2f} → {p1:.2f} TL)."
            )
        else:
            impact_line = "Price impact data unavailable for this date."

        # Get AI Commentary
        ai_comment = generate_agent_commentary(ann, chg)

        blk = KeepTogether([
            Paragraph(f"<b>{i}. {title}</b>", s_ann_title),
            Paragraph(f"{date_s}  ·  {ann.get('source','?')}", s_ann_meta),
            Spacer(1, 3),
            Paragraph(f"<b>Bildirim Metni:</b> {content[:500]}...", s_small),
            Spacer(1, 6),
            Paragraph(f"<b>ÖZAS Agent Yorumu:</b>", s_ann_title), # Using same style for sub-header
            Paragraph(ai_comment, s_body),
            Spacer(1, 6),
            Paragraph(f"<b>Fiyat Etkisi:</b> {impact_line}", s_impact),
            Spacer(1, 6),
            divider(thick=0.25, color=LIGHT_LINE, before=0, after=4),
        ])
        story.append(blk)

    # ═══════════════════════════════════════════════════════════════════════════
    # FOOTER — Disclaimer
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 20))
    story.append(divider(thick=0.5, color=LIGHT_LINE, before=0, after=10))
    story.append(Paragraph(
        "REGULATORY DISCLAIMER: This report is generated by the ÖZAS Finance Agent for "
        "academic simulation purposes only. The information does not constitute investment "
        "advice, financial guidance, or any buy/sell recommendation. All data sourced from "
        "Yahoo Finance and KAP Direct (Public Disclosure Platform). Consult a licensed financial advisor before "
        "making any investment decisions.",
        s_disclaimer
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Page 1 of 1  ·  ÖZAS Finance Intelligent Systems  ·  Generated {gen_at}",
        P("Footer2", fontName=F_SANS, fontSize=7.5, textColor=VERY_MUTED, alignment=TA_CENTER)
    ))

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
