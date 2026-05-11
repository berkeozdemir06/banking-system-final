import streamlit as st
import requests
import time
import os

st.set_page_config(
    page_title="BIST Equity Intelligence Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = os.getenv("API_URL", "http://localhost:8080")

# ── Premium CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Reset & Base ── */
*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp {
    background: #070d1f !important;
    font-family: 'Inter', sans-serif !important;
    color: #e2e8f0 !important;
}

/* ── Animated Background ── */
.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    background:
        radial-gradient(ellipse 80% 50% at 20% 10%, rgba(245,200,66,0.06) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 80% 80%, rgba(59,130,246,0.06) 0%, transparent 60%),
        radial-gradient(ellipse 40% 60% at 60% 30%, rgba(168,85,247,0.04) 0%, transparent 50%);
    pointer-events: none;
    z-index: 0;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
.block-container { padding: 0 !important; max-width: 100% !important; }
section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0c1428 0%, #0a1020 100%) !important;
    border-right: 1px solid rgba(245,200,66,0.12) !important;
}
section[data-testid="stSidebar"] .block-container {
    padding: 0 !important;
}

/* ── Main content area ── */
.main .block-container {
    padding: 2rem 2.5rem 4rem !important;
    max-width: 100% !important;
}

/* ── Hero Header ── */
.hero {
    background: linear-gradient(135deg, #0c1428 0%, #111827 50%, #0c1428 100%);
    border: 1px solid rgba(245,200,66,0.15);
    border-radius: 20px;
    padding: 36px 48px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
        radial-gradient(ellipse at 15% 50%, rgba(245,200,66,0.08) 0%, transparent 55%),
        radial-gradient(ellipse at 85% 20%, rgba(59,130,246,0.06) 0%, transparent 50%);
    pointer-events: none;
}
.hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(245,200,66,0.08);
    border: 1px solid rgba(245,200,66,0.25);
    border-radius: 99px;
    padding: 5px 14px;
    font-size: 0.72rem;
    font-weight: 600;
    color: #f5c842;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 14px;
}
.hero-title {
    font-size: 2.4rem;
    font-weight: 900;
    background: linear-gradient(90deg, #f5c842 0%, #fde68a 50%, #f5c842 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.15;
    margin: 0 0 8px;
    letter-spacing: -0.02em;
}
.hero-sub {
    color: #64748b;
    font-size: 0.92rem;
    margin: 0;
}
.hero-stats {
    display: flex;
    gap: 16px;
    margin-top: 24px;
}
.stat-pill {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 12px 20px;
    text-align: center;
    min-width: 110px;
}
.stat-pill .val {
    font-size: 1.3rem;
    font-weight: 800;
    color: #f5c842;
    font-family: 'JetBrains Mono', monospace;
    display: block;
}
.stat-pill .lbl {
    font-size: 0.65rem;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    display: block;
    margin-top: 2px;
}

/* ── Sidebar panel ── */
.sidebar-section {
    padding: 20px 18px;
}
.sidebar-title {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #475569;
    margin-bottom: 14px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
.sidebar-logo {
    background: linear-gradient(135deg, #f5c842, #f97316);
    border-radius: 14px;
    width: 48px; height: 48px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px;
    margin-bottom: 12px;
    box-shadow: 0 0 24px rgba(245,200,66,0.25);
}

/* ── Cards ── */
.glass-card {
    background: rgba(17,24,39,0.8);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s;
}
.glass-card:hover { border-color: rgba(245,200,66,0.15); }
.glass-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(245,200,66,0.2), transparent);
}

/* ── Answer card ── */
.answer-card {
    background: linear-gradient(135deg, rgba(17,24,39,0.95) 0%, rgba(12,20,40,0.95) 100%);
    border: 1px solid rgba(245,200,66,0.2);
    border-radius: 16px;
    padding: 28px 32px;
    margin-top: 20px;
    position: relative;
    overflow: hidden;
}
.answer-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 3px; height: 100%;
    background: linear-gradient(180deg, #f5c842, #f97316);
    border-radius: 3px 0 0 3px;
}
.answer-card::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: radial-gradient(ellipse at 90% 10%, rgba(245,200,66,0.04) 0%, transparent 60%);
    pointer-events: none;
}
.answer-label {
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #f5c842;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.answer-text {
    font-size: 0.95rem;
    line-height: 1.75;
    color: #cbd5e1;
}

/* ── Decision pills ── */
.decision-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin: 12px 0;
}
.d-pill {
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 0.75rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}
.d-pill.sources { background: rgba(59,130,246,0.12); border: 1px solid rgba(59,130,246,0.25); color: #60a5fa; }
.d-pill.horizon  { background: rgba(168,85,247,0.12); border: 1px solid rgba(168,85,247,0.25); color: #c084fc; }
.d-pill.iter     { background: rgba(245,200,66,0.10); border: 1px solid rgba(245,200,66,0.25); color: #f5c842; }

/* ── Consistency box ── */
.consistency-box {
    background: rgba(34,197,94,0.05);
    border: 1px solid rgba(34,197,94,0.2);
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 0.85rem;
    color: #86efac;
    margin: 12px 0;
}
.consistency-box.warn {
    background: rgba(251,191,36,0.05);
    border-color: rgba(251,191,36,0.2);
    color: #fcd34d;
}

/* ── Disclaimer ── */
.disclaimer-bar {
    background: rgba(239,68,68,0.06);
    border: 1px solid rgba(239,68,68,0.2);
    border-radius: 10px;
    padding: 10px 16px;
    font-size: 0.8rem;
    color: #f87171;
    margin-top: 20px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* ── Source item ── */
.src-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.src-item:last-child { border-bottom: none; }
.src-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-top: 6px;
    flex-shrink: 0;
}
.src-info { flex: 1; min-width: 0; }
.src-type { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }
.src-meta { font-size: 0.75rem; color: #475569; margin-top: 2px; font-family: 'JetBrains Mono', monospace; }
.src-link { font-size: 0.72rem; color: #3b82f6; text-decoration: none; display: inline-block; margin-top: 4px; }
.src-link:hover { color: #60a5fa; }

/* ── Streamlit widget overrides ── */
div[data-testid="stTextInput"] > div > div > input,
div[data-testid="stTextArea"] > div > div > textarea {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
}
div[data-testid="stTextInput"] > div > div > input:focus,
div[data-testid="stTextArea"] > div > div > textarea:focus {
    border-color: rgba(245,200,66,0.4) !important;
    box-shadow: 0 0 0 3px rgba(245,200,66,0.08) !important;
}

div[data-testid="stButton"] > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.2s !important;
}
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #f5c842, #f97316) !important;
    border: none !important;
    color: #0a0f1e !important;
    font-weight: 700 !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(245,200,66,0.3) !important;
}
div[data-testid="stButton"] > button[kind="secondary"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #94a3b8 !important;
}
div[data-testid="stButton"] > button[kind="secondary"]:hover {
    border-color: rgba(245,200,66,0.3) !important;
    color: #f5c842 !important;
    background: rgba(245,200,66,0.05) !important;
}

div[data-testid="stSelectbox"] > div > div {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
}

.stSpinner > div { border-top-color: #f5c842 !important; }

div[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.02) !important;
    border: 1px dashed rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
}

div[data-testid="stExpander"] {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 12px !important;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
    padding: 12px 16px !important;
}
div[data-testid="stMetricValue"] { color: #f5c842 !important; font-family: 'JetBrains Mono', monospace !important; }
div[data-testid="stMetricLabel"] { color: #475569 !important; font-size: 0.72rem !important; }

div[data-testid="stAlert"] {
    border-radius: 10px !important;
    border: 1px solid rgba(245,200,66,0.2) !important;
    background: rgba(245,200,66,0.05) !important;
}
div[data-testid="stSuccess"] {
    border-color: rgba(34,197,94,0.3) !important;
    background: rgba(34,197,94,0.05) !important;
}
div[data-testid="stError"] {
    border-color: rgba(239,68,68,0.3) !important;
    background: rgba(239,68,68,0.05) !important;
}

/* Divider */
hr { border-color: rgba(255,255,255,0.06) !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(245,200,66,0.2); border-radius: 99px; }

/* Label overrides */
label, .stLabel { color: #94a3b8 !important; font-size: 0.82rem !important; font-weight: 500 !important; }

</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sidebar-section">
        <div class="sidebar-logo">📈</div>
        <div style="font-size:1rem;font-weight:800;color:#f5c842;margin-bottom:2px;">BIST Agent</div>
        <div style="font-size:0.72rem;color:#475569;margin-bottom:24px;">Agentic RAG · Turkish Equity Markets</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">🎯 Hedef Hisse</div>', unsafe_allow_html=True)
    ingest_ticker = st.text_input("", value="ASELS", placeholder="THYAO, GARAN, SASA...", label_visibility="collapsed").upper()

    st.markdown('<div class="sidebar-title" style="margin-top:20px;">🗄️ Veri Tabanı</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📡 KAP Çek", use_container_width=True):
            with st.spinner(f"KAP verisi alınıyor..."):
                try:
                    res = requests.post(f"{API_URL}/ingest/kap", json={"ticker": ingest_ticker, "limit": 20}, timeout=30)
                    if res.status_code == 200:
                        d = res.json()
                        st.success(f"✅ {d['docs']} bildirim, {d['chunks_added']} chunk")
                    else:
                        st.error(res.text[:120])
                except Exception as e:
                    st.error(f"Bağlantı hatası: {e}")

    with col2:
        if st.button("📰 Haber Çek", use_container_width=True):
            with st.spinner("Haberler alınıyor..."):
                try:
                    res = requests.post(f"{API_URL}/ingest/news", json={"ticker": ingest_ticker, "limit": 15, "days_back": 60}, timeout=30)
                    if res.status_code == 200:
                        d = res.json()
                        st.success(f"✅ {d['docs']} haber eklendi")
                    else:
                        st.error(res.text[:120])
                except Exception as e:
                    st.error(f"Bağlantı hatası: {e}")

    st.markdown("---")
    st.markdown('<div class="sidebar-title">📄 Brokerage Raporu (PDF)</div>', unsafe_allow_html=True)
    uploaded_pdf = st.file_uploader("", type=["pdf"], label_visibility="collapsed")
    if uploaded_pdf:
        if st.button("📤 PDF Yükle & İşle", use_container_width=True, type="primary"):
            with st.spinner("PDF işleniyor..."):
                try:
                    files = {"file": (uploaded_pdf.name, uploaded_pdf.getvalue(), "application/pdf")}
                    data  = {"ticker": ingest_ticker, "institution": "Aracı Kurum"}
                    res   = requests.post(f"{API_URL}/ingest/pdf", files=files, data=data, timeout=60)
                    if res.status_code == 200:
                        d = res.json()
                        st.success(f"✅ {d['pages']} sayfa, {d['chunks_added']} chunk işlendi")
                    else:
                        st.error(res.text[:120])
                except Exception as e:
                    st.error(f"Bağlantı hatası: {e}")

    st.markdown("---")
    st.markdown('<div class="sidebar-title">📊 Sistem</div>', unsafe_allow_html=True)
    if st.button("VectorDB Durumu", use_container_width=True):
        try:
            res = requests.get(f"{API_URL}/stats", timeout=5)
            st.json(res.json())
        except:
            st.error("API'ye ulaşılamıyor")

    st.markdown('</div>', unsafe_allow_html=True)

# ── Main ──────────────────────────────────────────────────────────────────────

# Hero
st.markdown("""
<div class="hero">
  <div class="hero-badge">🇹🇷 &nbsp; FinTech 2025-2026 · Agentic RAG</div>
  <div class="hero-title">BIST Equity Intelligence Agent</div>
  <p class="hero-sub">KAP bildirimleri · Finansal haberler · Aracı kurum raporları → Kaynaklı &amp; zaman farkındalıklı analiz</p>
  <div class="hero-stats">
    <div class="stat-pill"><span class="val">3</span><span class="lbl">Veri Kaynağı</span></div>
    <div class="stat-pill"><span class="val">8</span><span class="lbl">Stack Katmanı</span></div>
    <div class="stat-pill"><span class="val">10</span><span class="lbl">Eval Sorusu</span></div>
    <div class="stat-pill"><span class="val">∞</span><span class="lbl">Non-Trading</span></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Intelligence Dashboard ────────────────────────────────────────────────────
st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.markdown('<div class="sidebar-title">🧠 KAP Intelligence Dashboard — Otomatik Analiz</div>', unsafe_allow_html=True)

intel_col1, intel_col2, intel_col3 = st.columns([2, 1, 1])
with intel_col1:
    intel_ticker = st.text_input(
        "", value="ASELS",
        placeholder="Hisse kodu girin (ASELS, THYAO, GARAN...)",
        label_visibility="collapsed",
        key="intel_ticker"
    ).upper()
with intel_col2:
    analyze_btn = st.button("📊 Analiz Et", type="primary", use_container_width=True, key="analyze_btn")
with intel_col3:
    report_btn = st.button("📥 PDF İndir", use_container_width=True, key="report_btn")

st.markdown('</div>', unsafe_allow_html=True)

if analyze_btn and intel_ticker:
    with st.spinner(f"📡 {intel_ticker} için KAP bildirimleri ve piyasa verisi çekiliyor..."):
        try:
            t0  = time.time()
            res = requests.post(
                f"{API_URL}/intelligence/analyze",
                json={"ticker": intel_ticker, "kap_limit": 15},
                timeout=120
            )
            elapsed = time.time() - t0

            if res.status_code == 200:
                idata   = res.json()
                company = idata.get("company", {})
                anns    = idata.get("announcements", [])

                st.success(f"✅ {intel_ticker} analizi tamamlandı — {len(anns)} KAP duyurusu, {elapsed:.1f}s")

                # ── Şirket Kartı
                st.markdown(f"""
                <div class="glass-card" style="margin-top:12px;">
                  <div class="sidebar-title">🏢 {company.get('company_name', intel_ticker)}</div>
                  <div style="font-size:0.8rem;color:#64748b;margin-bottom:16px;">
                    {company.get('sector','–')} · {company.get('industry','–')} · Piyasa Değeri: {company.get('market_cap') and str(round(company['market_cap']/1e9,1))+'B TL' or '–'}
                  </div>
                </div>
                """, unsafe_allow_html=True)

                # Metrik sütunları
                lc   = company.get("last_close")
                dc   = company.get("day_change_pct")
                r1w  = company.get("ret_1w")
                r1m  = company.get("ret_1mo")
                r1y  = company.get("ret_1y")
                vs   = company.get("vs_bist_1y")

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Son Kapanış",     f"{lc:.2f} TL" if lc else "N/A",     f"%{dc:+.2f}" if dc is not None else None)
                m2.metric("1 Hafta",         f"%{r1w:+.2f}" if r1w is not None else "N/A")
                m3.metric("1 Ay",            f"%{r1m:+.2f}" if r1m is not None else "N/A")
                m4.metric("1 Yıl",           f"%{r1y:+.2f}" if r1y is not None else "N/A")
                m5.metric("vs BIST100 (1Y)", f"%{vs:+.2f}" if vs is not None else "N/A")

                # İstikrar
                stab = company.get("stability_score", 50)
                vol  = company.get("volatility_1y", 0)
                stab_color = "#22c55e" if stab >= 70 else ("#f59e0b" if stab >= 40 else "#ef4444")

                st.markdown(f"""
                <div class="glass-card" style="margin-top:8px;">
                  <div class="sidebar-title">🤖 Ajan İstikrar Değerlendirmesi</div>
                  <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;">
                    <div style="text-align:center;">
                      <div style="font-size:2rem;font-weight:900;color:{stab_color};font-family:'JetBrains Mono',monospace;">{stab}</div>
                      <div style="font-size:0.65rem;color:#475569;text-transform:uppercase;letter-spacing:.07em;">İstikrar Skoru / 100</div>
                    </div>
                    <div style="font-size:0.85rem;color:#cbd5e1;line-height:1.7;flex:1;">
                      Yıllık Volatilite: <strong style="color:#f5c842;">%{vol:.1f}</strong> &nbsp;|&nbsp;
                      52H En Yüksek: <strong style="color:#22c55e;">{company.get('high_52w','?')} TL</strong> &nbsp;|&nbsp;
                      52H En Düşük: <strong style="color:#ef4444;">{company.get('low_52w','?')} TL</strong><br/>
                      BIST100 1Y: <strong style="color:#3b82f6;">%{company.get('bist_ret_1y','?')}</strong> &nbsp;|&nbsp;
                      {intel_ticker} 1Y: <strong style="color:{('#22c55e' if (r1y or 0)>=0 else '#ef4444')};">%{f'{r1y:+.2f}' if r1y is not None else '?'}</strong>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                # KAP Tablosu
                if anns:
                    st.markdown(f'<div class="glass-card" style="margin-top:8px;"><div class="sidebar-title">📢 Son {len(anns)} KAP Duyurusu — Ertesi Gün Fiyat Etkisi</div>', unsafe_allow_html=True)

                    import pandas as pd
                    rows = []
                    for ann in anns:
                        chg_pct  = ann.get("price_change_pct")
                        bist_pct = ann.get("bist_change_pct")
                        p0 = ann.get("price_day0")
                        p1 = ann.get("price_day1")
                        rows.append({
                            "Tarih":      ann.get("date_str","?")[:10],
                            "Başlık":     ann.get("title","?")[:60] + ("…" if len(ann.get("title",""))>60 else ""),
                            "Duy.Günü":   f"{p0:.2f} TL" if p0 else "–",
                            "Ertesi Gün": f"{p1:.2f} TL" if p1 else "–",
                            "Değişim":    f"%{chg_pct:+.2f}" if chg_pct is not None else "–",
                            "BIST100":    f"%{bist_pct:+.2f}" if bist_pct is not None else "–",
                        })
                    df = pd.DataFrame(rows)

                    def color_val(val):
                        if val == "–": return "color:#475569"
                        try:
                            v = float(val.replace("%","").replace("+",""))
                            return f"color:{'#22c55e' if v>=0 else '#ef4444'}"
                        except: return "color:#475569"

                    styled = df.style.applymap(color_val, subset=["Değişim","BIST100"])
                    st.dataframe(styled, use_container_width=True, height=430)
                    st.markdown('</div>', unsafe_allow_html=True)

                # PDF indirme linki
                pdf_url = f"{API_URL}/intelligence/report?ticker={intel_ticker}&kap_limit=15"
                st.markdown(f"""
                <div style="margin-top:16px;">
                  <a href="{pdf_url}" target="_blank" style="
                    display:inline-flex;align-items:center;gap:8px;
                    background:linear-gradient(135deg,#f5c842,#f97316);
                    color:#0a0f1e;font-weight:700;font-size:0.9rem;
                    padding:12px 28px;border-radius:10px;text-decoration:none;
                    box-shadow:0 4px 16px rgba(245,200,66,0.3);
                  ">📥 {intel_ticker} Tam PDF Raporunu İndir</a>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.error(f"Analiz hatası ({res.status_code}): {res.text[:300]}")
        except Exception as e:
            st.error(f"Bağlantı hatası: {e}")
elif analyze_btn:
    st.warning("Lütfen bir hisse kodu girin.")

# PDF direkt indir butonu
if report_btn and intel_ticker:
    with st.spinner(f"📄 {intel_ticker} PDF raporu hazırlanıyor..."):
        try:
            res = requests.get(
                f"{API_URL}/intelligence/report",
                params={"ticker": intel_ticker, "kap_limit": 15},
                timeout=120
            )
            if res.status_code == 200:
                st.download_button(
                    label=f"⬇️ {intel_ticker}_OZAS_Report.pdf indir",
                    data=res.content,
                    file_name=f"{intel_ticker}_OZAS_Report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.error(f"PDF hatası ({res.status_code}): {res.text[:200]}")
        except Exception as e:
            st.error(f"PDF hatası: {e}")

st.markdown("---")

# Query section
st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.markdown('<div class="sidebar-title">🤖 Agentic RAG Sorgusu</div>', unsafe_allow_html=True)

query = st.text_area(
    "",
    value="ASELS'ın son KAP bildirimleri ile basında çıkan haberler birbiriyle örtüşüyor mu? Çelişen noktalar var mı?",
    height=110,
    label_visibility="collapsed",
    placeholder="'THYAO için son 3 ayda brokerage raporları ne söylüyor?' gibi bir soru sorun..."
)

col_q1, col_q2, col_q3 = st.columns([2, 1, 1])
with col_q1:
    ticker_filter = st.text_input("", value="ASELS", placeholder="Hisse filtresi (opsiyonel)", label_visibility="collapsed")
with col_q2:
    run_btn = st.button("🚀 Ajanı Başlat", type="primary", use_container_width=True)
with col_q3:
    st.button("🗑️ Temizle", use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

# Run agent
if run_btn and query:
    ticker = ticker_filter.upper().strip() if ticker_filter else None
    
    with st.spinner(f"🔍 {ticker or 'Piyasa'} için internet araştırması yapılıyor... (KAP + Haberler)") if ticker else st.spinner("🧠 Ajan düşünüyor..."):
        try:
            # ── 1. OTOMATİK İNTERNET ARAŞTIRMASI (INGESTION) ──────────────────
            if ticker:
                # Paralel değil, sıralı yapıyoruz ki kullanıcı ilerlemeyi görsün (veya toplu spinner)
                try:
                    # KAP Ingest
                    requests.post(f"{API_URL}/ingest/kap", json={"ticker": ticker, "limit": 15}, timeout=60)
                    # Haber Ingest
                    requests.post(f"{API_URL}/ingest/news", json={"ticker": ticker, "limit": 15}, timeout=60)
                except Exception as ingest_err:
                    logger.warning(f"Otomatik araştırma hatası: {ingest_err}")
            
            # ── 2. RAG SORGUSU ────────────────────────────────────────────────
            payload  = {"question": query, "ticker": ticker}
            t0       = time.time()
            res      = requests.post(f"{API_URL}/query", json=payload, timeout=120)
            elapsed  = time.time() - t0

            if res.status_code == 200:
                data     = res.json()
                answer   = data.get("answer", "")
                decision = data.get("decision") or {}
                sources  = data.get("sources", [])
                consist  = data.get("consistency_note", "")
                iters    = data.get("iterations", 1)

                # ── Decision strip ──────────────────────────────────────
                src_list = ", ".join(decision.get("sources_selected", [])).upper() if decision else "–"
                horizon  = decision.get("time_horizon", "–")
                reasoning = decision.get("reasoning", "")

                st.markdown(f"""
                <div style="margin:16px 0 6px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
                  <span style="font-size:0.72rem;color:#475569;font-weight:600;">Ajan Kararı:</span>
                  <span class="d-pill sources">📡 {src_list}</span>
                  <span class="d-pill horizon">⏱ {horizon}</span>
                  <span class="d-pill iter">🔄 {iters} iterasyon</span>
                  <span style="font-size:0.72rem;color:#475569;margin-left:auto;">{elapsed:.2f}s</span>
                </div>
                """, unsafe_allow_html=True)

                if reasoning:
                    st.markdown(f'<div style="font-size:0.78rem;color:#475569;margin-bottom:12px;font-style:italic;">💡 {reasoning}</div>', unsafe_allow_html=True)

                # ── Consistency ─────────────────────────────────────────
                if consist:
                    cls = "warn" if "⚠️" in consist or "Tutarsız" in consist else ""
                    st.markdown(f'<div class="consistency-box {cls}">🔍 <strong>Çapraz Doğrulama:</strong> {consist}</div>', unsafe_allow_html=True)

                # ── Answer ──────────────────────────────────────────────
                clean = answer.replace("⚠️ Bu sistem yatırım tavsiyesi vermez. Sunulan bilgiler yalnızca bilgi amaçlıdır ve al/sat kararı için kullanılamaz.", "").strip()
                clean = clean.replace("⚠️ **Bu sistem yatırım tavsiyesi vermez.** Sunulan bilgiler yalnızca bilgi ve analiz amaçlıdır.", "").strip()

                st.markdown(f"""
                <div class="answer-card">
                  <div class="answer-label">🧠 &nbsp; Nihai Analiz</div>
                  <div class="answer-text">{clean.replace(chr(10), '<br>')}</div>
                </div>
                """, unsafe_allow_html=True)

                # ── Disclaimer ──────────────────────────────────────────
                st.markdown('<div class="disclaimer-bar">⚠️ <strong>Bu sistem yatırım tavsiyesi vermez.</strong> Sunulan bilgiler yalnızca bilgi ve analiz amaçlıdır. Al/sat kararı için kullanılamaz.</div>', unsafe_allow_html=True)

                # ── Sources ─────────────────────────────────────────────
                if sources:
                    with st.expander(f"📚 Kullanılan Kaynaklar ({len(sources)} belge)"):
                        for src in sources:
                            s_type = (src.get("source_type") or "").lower()
                            color  = "#22c55e" if s_type == "kap" else ("#a855f7" if s_type == "news" else "#f59e0b")
                            label  = s_type.upper()
                            url    = src.get("url", "")
                            link   = f'<a class="src-link" href="{url}" target="_blank">🔗 Kaynağa git</a>' if url else ""
                            st.markdown(f"""
                            <div class="src-item">
                              <div class="src-dot" style="background:{color};box-shadow:0 0 6px {color}44;"></div>
                              <div class="src-info">
                                <div class="src-type" style="color:{color};">{label}</div>
                                <div class="src-meta">{src.get('ticker','?')} · {src.get('date','?')} · {src.get('institution','?')}</div>
                                {link}
                              </div>
                            </div>
                            """, unsafe_allow_html=True)

            else:
                st.error(f"API hatası ({res.status_code}): {res.text[:300]}")

        except Exception as e:
            st.error(f"Bağlantı hatası: {e}")

elif run_btn:
    st.warning("Lütfen bir soru girin.")

# ── How it works ──────────────────────────────────────────────────────────────
with st.expander("⚙️ Sistem Nasıl Çalışır?"):
    st.markdown("""
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:8px;">
    """ + "".join([f"""
      <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px;">
        <div style="font-size:1.3rem;margin-bottom:8px;">{icon}</div>
        <div style="font-size:0.82rem;font-weight:700;color:#e2e8f0;margin-bottom:4px;">{title}</div>
        <div style="font-size:0.75rem;color:#475569;">{desc}</div>
      </div>
    """ for icon, title, desc in [
        ("🧠", "Source Selection", "LLM hangi kaynağa bakacağına otomatik karar verir: KAP, Haber veya Brokerage Raporu"),
        ("⏱️", "Temporal Reasoning", "Sorgunun 'son 90 gün' mü yoksa 'tarihi veri' mi gerektirdiğini anlar"),
        ("📡", "Iterative Retrieval", "Yeterli kaynak bulunamazsa filtresiz ikinci bir arama turu başlatır"),
        ("🔍", "Cross-Source Verify", "KAP resmi bildirimi ile haber içeriklerini karşılaştırır, çelişki varsa raporlar"),
        ("🛡️", "Guardrails", "18 regex + LLM kontrolü ile yatırım tavsiyesi verilmesini engeller"),
        ("📊", "RAGAS Evaluation", "10 BIST sorusuyla Faithfulness, Relevancy, Recall ve Precision ölçülür"),
    ]]) + "</div>", unsafe_allow_html=True)
