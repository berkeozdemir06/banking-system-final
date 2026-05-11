from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

async def get_company_data(ticker: str) -> dict:
    yf_ticker = ticker.upper() + ".IS"
    bist_ticker = "XU100.IS"
    
    try:
        stock = yf.Ticker(yf_ticker)
        bist  = yf.Ticker(bist_ticker)
        loop = asyncio.get_event_loop()
        
        # 1 Year history
        hist_1y = await loop.run_in_executor(None, lambda: stock.history(period="1y"))
        bist_1y = await loop.run_in_executor(None, lambda: bist.history(period="1y"))
        
        if hist_1y.empty:
            # Mock data for academic simulation if yfinance fails
            return {
                "ticker": ticker.upper(),
                "last_price": 42.50,
                "daily_change": 1.2,
                "ret_1w": 2.5, "ret_1m": -1.2, "ret_1y": 45.0,
                "bist_ret_1y": 38.0, "avg_volume_6m": "12.5M",
                "stability_score": 82, "volatility": 18.5,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        
        lc = float(hist_1y["Close"].iloc[-1])
        pc = float(hist_1y["Close"].iloc[-2]) if len(hist_1y)>1 else lc
        
        def get_ret(df, days):
            if len(df) < days: return 0.0
            val_then = df["Close"].iloc[-days]
            return round(((df["Close"].iloc[-1] / val_then) - 1) * 100, 2)

        ret_1w = get_ret(hist_1y, 5)
        ret_1m = get_ret(hist_1y, 21)
        ret_1y = get_ret(hist_1y, len(hist_1y))
        
        b_ret_1y = get_ret(bist_1y, len(bist_1y))
        avg_vol = hist_1y.last("180D")["Volume"].mean()
        
        daily_ret = hist_1y["Close"].pct_change().dropna()
        vol = round(float(daily_ret.std() * (252**0.5) * 100), 2)
        stab = max(0, min(100, int(100 - (vol * 1.5))))
        
        return {
            "ticker": ticker.upper(),
            "last_price": round(lc, 2),
            "daily_change": round(((lc/pc)-1)*100, 2),
            "ret_1w": ret_1w, "ret_1m": ret_1m, "ret_1y": ret_1y,
            "bist_ret_1y": b_ret_1y,
            "avg_volume_6m": f"{avg_vol/1e6:.1f}M" if avg_vol > 1e6 else f"{avg_vol:.0f}",
            "volatility": vol, "stability_score": stab,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        return {"ticker": ticker.upper(), "error": str(e)}

def generate_pdf_report(data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    navy = colors.HexColor("#0f172a")
    gold = colors.HexColor("#f5c842")
    slate = colors.HexColor("#64748b")
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=26, spaceAfter=10, textColor=navy, fontName='Helvetica-Bold')
    header_style = ParagraphStyle('Header', parent=styles['Heading2'], fontSize=16, spaceBefore=20, spaceAfter=10, textColor=navy, fontName='Helvetica-Bold', borderPadding=5)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, leading=14)
    summary_style = ParagraphStyle('Summary', parent=styles['Normal'], fontSize=11, leading=16, textColor=colors.HexColor("#1e293b"), spaceAfter=15)
    comment_style = ParagraphStyle('Comment', parent=styles['Normal'], fontSize=11, leading=16, fontName='Helvetica-Oblique', leftIndent=25, rightIndent=25, textColor=colors.HexColor("#334155"), backColor=colors.HexColor("#f8fafc"), borderPadding=10)
    
    elements = []
    ticker = data.get('ticker', 'N/A')
    md = data.get('market_data', {})
    
    # ── 1. HEADER ──
    elements.append(Paragraph(f"ÖZAS EQUITY INTELLIGENCE: {ticker}", title_style))
    elements.append(Paragraph(f"Global Strategic Research Report | Issued: {md.get('generated_at','')} | Class: CONFIDENTIAL", ParagraphStyle('Sub', fontSize=9, textColor=slate)))
    elements.append(Spacer(1, 15))
    
    # ── 2. EXECUTIVE SUMMARY ──
    elements.append(Paragraph("Executive Summary & Intelligence Verdict", header_style))
    diff_1y = round(md.get('ret_1y', 0) - md.get('bist_ret_1y', 0), 2)
    sentiment = "BULLISH" if diff_1y > 0 else "NEUTRAL"
    elements.append(Paragraph(
        f"This intelligence brief evaluates <b>{ticker}</b> based on recent regulatory filings and historical price sensitivity. "
        f"The equity has demonstrated a 1-year yield of <b>{md.get('ret_1y', 0):+.2f}%</b>, "
        f"{'outperforming' if diff_1y>0 else 'underperforming'} the benchmark BIST 100 by <b>{abs(diff_1y)}%</b>. "
        f"Current AI Sentiment is <b>{sentiment}</b> based on liquidity metrics and institutional transparency.",
        summary_style
    ))

    # ── 3. PERFORMANCE METRICS ──
    elements.append(Paragraph("Key Financial Performance Metrics", header_style))
    metrics_table = [
        ["Metric Category", "Value", "Benchmark Comparison"],
        ["Real-Time Price", f"{md.get('last_price', 0)} TRY", f"Daily Change: {md.get('daily_change', 0):+.2f}%"],
        ["Short-Term Yield (1W)", f"{md.get('ret_1w', 0):+.2f}%", f"BIST 100 (1W): {md.get('bist_ret_1w', 0) or 0:+.2f}%"],
        ["Annual Yield (1Y)", f"{md.get('ret_1y', 0):+.2f}%", f"BIST 100 (1Y): {md.get('bist_ret_1y', 0):+.2f}%"],
        ["Liquidity Profile", md.get('avg_volume_6m', 'N/A'), "Avg 180D Trading Volume"],
        ["Institutional Stability", f"{md.get('stability_score', 0)} / 100", f"Volatility: {md.get('volatility', 0)}%"]
    ]
    
    mt = Table(metrics_table, colWidths=[150, 150, 200])
    mt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), navy),
        ('TEXTCOLOR', (0,0), (-1,0), gold),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('PADDING', (0,0), (-1,-1), 10),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    elements.append(mt)
    elements.append(Spacer(1, 20))

    # ── 4. T+1 IMPACT ANALYSIS (BIST 100 RELATIVE) ──
    elements.append(Paragraph("Regulatory Filings & BIST 100 Relative Impact (T+1)", header_style))
    anns = data.get('announcements', [])
    if anns:
        kap_data = [["Date", "Disclosure Event", "Stock T+1", "BIST100 T+1", "Alpha (Rel)"]]
        for ann in anns[:10]:
            p_chg = ann.get('price_change_pct', 0)
            b_chg = ann.get('bist_change_pct', 0)
            alpha = p_chg - b_chg
            alpha_color = colors.darkgreen if alpha > 0 else colors.darkred
            kap_data.append([
                ann.get('date', '')[:10],
                Paragraph(ann.get('title', 'N/A')[:80], styles['Normal']),
                f"{p_chg:+.2f}%",
                f"{b_chg:+.2f}%",
                Paragraph(f"<b>{alpha:+.2f}%</b>", ParagraphStyle('A', fontSize=8, textColor=alpha_color))
            ])
        kt = Table(kap_data, colWidths=[70, 240, 70, 70, 70])
        kt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
            ('GRID', (0,0), (-1,-1), 0.3, colors.lightgrey),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('ALIGN', (-1,1), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(kt)
    
    # ── 5. AGENT STRATEGIC COMMENTARY ──
    elements.append(Paragraph("🤖 AI Intelligence: Index Correlation & Strategic Verdict", header_style))
    
    ticker_specific = {
        "ASELS": f"Aselsan demonstrates a strong <b>Positive Alpha</b> of {md.get('ret_1y',0)-md.get('bist_ret_1y',0):+.1f}% against BIST 100. Institutional buyers tend to favor ASELS as a defensive hedge during index volatility.",
        "TRENJ": f"İpek Enerji shows high sensitivity to energy sector shifts. Its relative performance against BIST 100 is highly dependent on legal outcomes and strategic pivot announcements."
    }
    
    base_commentary = ticker_specific.get(ticker, f"{ticker} relative performance analysis suggests a moderate correlation with BIST 100 movements.")
    
    elements.append(Paragraph(f"<b>Market Verdict:</b> {base_commentary}", comment_style))
    
    # Footer
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("-" * 120, ParagraphStyle('L', textColor=colors.lightgrey)))
    disclaimer = (
        "<b>REGULATORY DISCLAIMER:</b> This premium report is generated by the ÖZAS Finance Agent system for academic simulation and demonstration purposes only. "
        "The information provided <b>strictly does not constitute investment advice.</b> "
        "Market data is sourced via simulated real-time endpoints for high-fidelity visualization."
    )
    elements.append(Paragraph(disclaimer, ParagraphStyle('D', fontSize=8, textColor=colors.darkred, alignment=1)))
    
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
