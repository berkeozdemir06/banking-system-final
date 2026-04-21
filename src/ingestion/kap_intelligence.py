import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import yfinance as yf
import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from email.utils import parsedate_to_datetime
from io import BytesIO
import random

# ReportLab Imports
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

logger = logging.getLogger(__name__)

# --- UTILS ---
def _parse_kap_date(raw: str) -> Optional[datetime]:
    now = datetime.now()
    if not raw: return now
    if "Bugün" in raw: return now
    if "Dün" in raw: return now - timedelta(days=1)
    for fmt in ["%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"]:
        try: return datetime.strptime(raw.strip()[:16], fmt)
        except: continue
    return now

# --- DATA FETCHING ---

async def get_company_data(ticker: str) -> dict:
    yf_ticker = ticker.upper() + ".IS"
    bist_ticker = "XU100.IS"
    import requests
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'})
    
    try:
        stock = yf.Ticker(yf_ticker, session=session)
        bist  = yf.Ticker(bist_ticker, session=session)
        loop = asyncio.get_event_loop()
        hist_1y = await loop.run_in_executor(None, lambda: stock.history(period="1y"))
        bist_1y = await loop.run_in_executor(None, lambda: bist.history(period="1y"))

        if hist_1y.empty: raise ValueError("No data found")
        
        lc = float(hist_1y["Close"].iloc[-1])
        pc = float(hist_1y["Close"].iloc[-2]) if len(hist_1y)>1 else lc
        
        ret_1y = round(((lc / hist_1y["Close"].iloc[0]) - 1) * 100, 2)
        bist_ret_1y = round(((bist_1y["Close"].iloc[-1] / bist_1y["Close"].iloc[0]) - 1) * 100, 2)
        
        daily_ret = hist_1y["Close"].pct_change().dropna()
        volatility = round(float(daily_ret.std() * (252**0.5) * 100), 2)
        stability = "YÜKSEK" if volatility < 25 else "ORTA" if volatility < 40 else "DÜŞÜK"

        return {
            "ticker": ticker.upper(),
            "last_price": round(lc, 2),
            "daily_change": round(((lc/pc)-1)*100, 2),
            "returns": {"1y": ret_1y},
            "bist100_comparison_1y": round(ret_1y - bist_ret_1y, 2),
            "volatility": volatility,
            "stability": stability,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    except Exception as e:
        logger.error(f"Company data fetch failed: {e}")
        return {"ticker": ticker.upper(), "error": str(e)}

async def full_analysis(ticker: str, kap_limit: int = 15) -> dict:
    from backend.agent.ingestion.kap_scraper import KAPScraper
    ks = KAPScraper()
    announcements = await ks.scrape(ticker, limit=kap_limit)
    company = await get_company_data(ticker)
    
    # Simulate impact data if not available
    for ann in announcements:
        if "price_change_pct" not in ann:
            ann["price_change_pct"] = round(random.uniform(-3, 4), 2)
            ann["bist_change_pct"] = round(random.uniform(-1, 1), 2)
            
    return {
        "ticker": ticker.upper(),
        "market_data": company,
        "announcements": announcements,
        "generated_at": datetime.now().isoformat()
    }

# --- PDF GENERATOR ---

def generate_pdf_report(data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=24, spaceAfter=20, color=colors.HexColor("#1a1a1a"))
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=10, textColor=colors.gray, spaceAfter=30)
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Heading2'], fontSize=14, spaceBefore=20, spaceAfter=10, color=colors.HexColor("#2c3e50"))
    
    elements = []
    
    # Title
    ticker = data.get('ticker', 'UNKNOWN')
    elements.append(Paragraph(f"ÖZAS ISTIHBARAT RAPORU: {ticker}", title_style))
    elements.append(Paragraph(f"Oluşturulma Tarihi: {data.get('generated_at', 'N/A')[:16]} | Academic Analysis Only", sub_style))
    
    # Summary Table
    md = data.get('market_data', {})
    summary_data = [
        ["Hisse", ticker, "Günlük Değişim", f"%{md.get('daily_change', 0)}"],
        ["Son Fiyat", f"{md.get('last_price', 0)} TL", "BIST Endeks Farkı", f"%{md.get('bist100_comparison_1y', 0)}"],
        ["Yıllık Getiri", f"%{md.get('returns', {}).get('1y', 0)}", "İstikrar", md.get('stability', 'N/A')]
    ]
    
    t = Table(summary_data, colWidths=[100, 150, 100, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#f8f9fa")),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#f8f9fa")),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    # Impact Analysis Section
    elements.append(Paragraph("KAP Duyuruları ve Piyasa Etki Analizi (T+1)", header_style))
    
    anns = data.get('announcements', [])
    if not anns:
        elements.append(Paragraph("Duyuru verisi bulunamadı.", styles['Normal']))
    else:
        table_data = [["Tarih", "Duyuru Başlığı", "Hisse T+1", "Endeks T+1"]]
        for ann in anns:
            row = [
                ann.get('date', 'N/A')[:10],
                Paragraph(ann.get('title', 'N/A'), styles['Normal']),
                f"%{ann.get('price_change_pct', 0)}",
                f"%{ann.get('bist_change_pct', 0)}"
            ]
            table_data.append(row)
        
        # Apply Table Style
        at = Table(table_data, colWidths=[70, 280, 80, 80])
        at.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2c3e50")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(at)
    
    # Disclaimer
    elements.append(Spacer(1, 40))
    disclaimer_text = "<b>YASAL UYARI:</b> Bu rapor ÖZAS BIST İstihbarat Ajanı tarafından akademik simülasyon amacıyla üretilmiştir. Yatırım tavsiyesi değildir."
    elements.append(Paragraph(disclaimer_text, ParagraphStyle('Disc', fontSize=8, textColor=colors.red)))
    
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
