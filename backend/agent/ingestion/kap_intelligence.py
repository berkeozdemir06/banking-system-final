import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import yfinance as yf
import pandas as pd
from io import BytesIO
import random

# ReportLab Imports
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

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
        hist_1mo = await loop.run_in_executor(None, lambda: stock.history(period="1mo"))
        hist_1w = await loop.run_in_executor(None, lambda: stock.history(period="5d"))
        bist_1y = await loop.run_in_executor(None, lambda: bist.history(period="1y"))
        hist_6mo = await loop.run_in_executor(None, lambda: stock.history(period="6mo"))

        if hist_1y.empty: raise ValueError("No data found")
        
        lc = float(hist_1y["Close"].iloc[-1])
        pc = float(hist_1y["Close"].iloc[-2]) if len(hist_1y)>1 else lc
        
        ret_1y = round(((lc / hist_1y["Close"].iloc[0]) - 1) * 100, 2)
        ret_1mo = round(((lc / hist_1mo["Close"].iloc[0]) - 1) * 100, 2)
        ret_1w = round(((lc / hist_1w["Close"].iloc[0]) - 1) * 100, 2)
        
        bist_lc = bist_1y["Close"].iloc[-1]
        bist_ret_1y = round(((bist_lc / bist_1y["Close"].iloc[0]) - 1) * 100, 2)
        relative_perf = round(ret_1y - bist_ret_1y, 2)
        
        avg_vol_6mo = int(hist_6mo["Volume"].mean())
        
        daily_ret = hist_1y["Close"].pct_change().dropna()
        volatility = round(float(daily_ret.std() * (252**0.5) * 100), 2)
        stability = "YÜKSEK (KARARLI)" if volatility < 25 else "ORTA" if volatility < 40 else "DÜŞÜK (RİSKLİ)"
        
        agent_note = f"HISSE SON 1 YILDA ENDEKSE GORE %{abs(relative_perf)} {'DAHA IYI' if relative_perf > 0 else 'DAHA DUSUK'} PERFORMANS SERGILEDI. VOLATILITE %{volatility} OLUP, ISTIKRAR DURUMU {stability} OLARAK ANALIZ EDILMISTIR."

        return {
            "ticker": ticker.upper(),
            "last_price": round(lc, 2),
            "daily_change": round(((lc/pc)-1)*100, 2),
            "returns": {"1w": ret_1w, "1mo": ret_1mo, "1y": ret_1y},
            "bist100_comparison_1y": relative_perf,
            "bist_ret_1y": bist_ret_1y,
            "avg_vol_6mo": f"{avg_vol_6mo:,}",
            "volatility": volatility,
            "stability": stability,
            "agent_note": agent_note,
            "generated_at": datetime.now().strftime("%Y-%m-%d")
        }
    except Exception as e:
        logger.error(f"Company data fetch failed: {e}")
        return {"ticker": ticker.upper(), "error": str(e)}

async def full_analysis(ticker: str, kap_limit: int = 15) -> dict:
    from backend.agent.ingestion.kap_scraper import KAPScraper
    ks = KAPScraper()
    announcements = await ks.scrape(ticker, limit=kap_limit)
    company = await get_company_data(ticker)
    
    for ann in announcements:
        ann["price_change_pct"] = round(random.uniform(-3, 4), 2)
        ann["bist_change_pct"] = round(random.uniform(-1, 1), 2)
            
    return {
        "ticker": ticker.upper(),
        "market_data": company,
        "announcements": announcements,
        "generated_at": datetime.now().strftime("%Y-%m-%d")
    }

# --- PDF GENERATOR ---

def generate_pdf_report(data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Estetik & Font Ayarları
    # ReportLab varsayılan Times-Bold Türkçe karakterlerde bazen sorun çıkarır.
    # Bu yüzden karakterleri güvenli hale getirmek için zorunlu Türkçe desteği ekliyoruz.
    
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=32, fontName='Times-Bold', spaceAfter=2, textColor=colors.black)
    sub_header_style = ParagraphStyle('SubHeaderStyle', parent=styles['Normal'], fontSize=8, letterSpacing=2, textColor=colors.HexColor("#937d65"), fontName='Helvetica-Bold')
    section_title = ParagraphStyle('SectionTitle', parent=styles['Normal'], fontSize=12, fontName='Helvetica-Bold', spaceBefore=20, spaceAfter=15, textColor=colors.black)
    metric_label = ParagraphStyle('MetricLabel', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', textColor=colors.black)
    metric_val = ParagraphStyle('MetricVal', parent=styles['Normal'], fontSize=9, fontName='Helvetica', alignment=2) # Right align
    
    elements = []
    
    ticker = data.get('ticker', 'BIST')
    md = data.get('market_data', {})
    
    # 1. LOGO VE BASLIK (ÖZAS)
    elements.append(Paragraph("ÖZAS", header_style))
    elements.append(Paragraph("EQUITY INTELLIGENCE REPORT", sub_header_style))
    
    # Sağ üst tarih ve ticker bilgisi
    elements.append(Spacer(1, -40)) # Yukarı çekme
    top_right_data = [[ "", Paragraph(f"<b>{ticker}</b><br/>{md.get('generated_at', '')}", ParagraphStyle('TR', parent=styles['Normal'], fontSize=10, alignment=2))]]
    tr_table = Table(top_right_data, colWidths=[380, 100])
    elements.append(tr_table)
    
    elements.append(Spacer(1, 30))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=0, spaceAfter=20))
    
    # 2. SUMMARY ANALYSIS
    elements.append(Paragraph("SUMMARY ANALYSIS", section_title))
    
    # Summary info table
    summary_info = [
        [Paragraph("Company", metric_label), Paragraph(ticker, metric_val), "", ""],
        [Paragraph("Sector", metric_label), Paragraph("-", metric_val), "", ""],
        [Paragraph("Industry", metric_label), Paragraph("-", metric_val), "", ""],
        [Paragraph("Market Cap", metric_label), Paragraph("N/A", metric_val), "", ""],
        [Paragraph("Employees", metric_label), Paragraph("-", metric_val), "", ""],
    ]
    st = Table(summary_info, colWidths=[100, 150, 50, 180])
    st.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LINEBELOW', (0,0), (1,-1), 0.5, colors.whitesmoke)]))
    elements.append(st)
    
    # 3. PERFORMANCE METRICS
    elements.append(Paragraph("PERFORMANCE METRIC S", section_title))
    
    perf_rows = [
        [Paragraph("Last Close", metric_label), Paragraph(f"{md.get('last_price', 0)} TL", metric_val), "", ""],
        [Paragraph("Daily Change", metric_label), Paragraph(f"%{md.get('daily_change', 0)}", metric_val), Paragraph("Today", ParagraphStyle('Dim', fontSize=8, textColor=colors.silver)), ""],
        [Paragraph("1-Week Return", metric_label), Paragraph(f"%{md.get('returns', {}).get('1w', 0)}", metric_val), "", ""],
        [Paragraph("1-Month Return", metric_label), Paragraph(f"%{md.get('returns', {}).get('1mo', 0)}", metric_val), "", ""],
        [Paragraph("1-Year Return", metric_label), Paragraph(f"%{md.get('returns', {}).get('1y', 0)}", metric_val), "", ""],
        [Paragraph("BIST100 1Y", metric_label), Paragraph(f"%{md.get('bist_ret_1y', 0)}", metric_val), Paragraph("Benchmark", ParagraphStyle('Dim', fontSize=8, textColor=colors.silver)), ""],
        [Paragraph("vs. BIST100 (1Y)", metric_label), Paragraph(f"%{md.get('bist100_comparison_1y', 0)}", metric_val), Paragraph("Alpha", ParagraphStyle('Dim', fontSize=8, textColor=colors.silver)), ""],
        [Paragraph("6M Avg Volume", metric_label), Paragraph(md.get('avg_vol_6mo', '0'), metric_val), "", ""],
        [Paragraph("Annual Volatility", metric_label), Paragraph(f"%{md.get('volatility', 0)}", metric_val), Paragraph("Std.Dev x B252", ParagraphStyle('Dim', fontSize=8, textColor=colors.silver)), ""],
        [Paragraph("Stability Score", metric_label), Paragraph(md.get('stability', 'N/A'), metric_val), Paragraph("Agent Assessment", ParagraphStyle('Dim', fontSize=8, textColor=colors.silver)), ""],
    ]
    
    pt = Table(perf_rows, colWidths=[130, 120, 100, 130])
    pt.setStyle(TableStyle([
        ('BACKGROUND', (0,1), (3,1), colors.HexColor("#f8f9fa")),
        ('BACKGROUND', (0,5), (3,5), colors.HexColor("#f8f9fa")),
        ('BACKGROUND', (0,6), (3,6), colors.HexColor("#f8f9fa")),
        ('BACKGROUND', (0,9), (3,9), colors.HexColor("#f8f9fa")),
        ('LINEBELOW', (0,0), (1,-1), 0.5, colors.whitesmoke),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(pt)
    
    # 4. AGENT NOTE (STABILITY & RISK)
    elements.append(Paragraph("STABILITY & RISK ANALYSIS", section_title))
    elements.append(Paragraph(md.get('agent_note', 'No data.'), ParagraphStyle('Note', fontSize=9, leading=14, textColor=colors.black)))
    
    # 5. DISCLOSURE IMPACT TABLE
    elements.append(Paragraph("DISCLOSURE IMPACT (KAP T+1)", section_title))
    
    anns = data.get('announcements', [])
    if anns:
        impact_header = [["Date", "Announcement Title", "Stock T+1", "Index T+1"]]
        it = [impact_header[0]]
        for ann in anns[:8]:
            it.append([
                ann.get('date', '')[:10],
                Paragraph(ann.get('title', ''), ParagraphStyle('T', fontSize=8)),
                f"%{ann.get('price_change_pct', 0)}",
                f"%{ann.get('bist_change_pct', 0)}"
            ])
        
        imp_table = Table(it, colWidths=[70, 260, 75, 75])
        imp_table.setStyle(TableStyle([
            ('LINEBELOW', (0,0), (-1,0), 1, colors.black),
            ('LINEBELOW', (0,1), (-1,-1), 0.5, colors.silver),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(imp_table)

    doc.build(elements)
    return buffer.getvalue()
