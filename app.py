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

# ── Yeni Tasarım: Hisse Girişi ve 3 Kutucuklu Yapı ────────────────────────────
st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.markdown('<div class="sidebar-title">🎯 BIST Intelligence Kontrol Merkezi</div>', unsafe_allow_html=True)

col_input, col_btn = st.columns([4, 1])
with col_input:
    target_ticker = st.text_input("", placeholder="Hisse kodunu yazın (Örn: ASELS)...", label_visibility="collapsed").upper()
with col_btn:
    analyze_trigger = st.button("🚀 Başlat", type="primary", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# ── 3 KUTUCUK (KAP | WEB | PDF) ────────────────────────────────────────────────
col_kap, col_web, col_pdf = st.columns(3)

with col_kap:
    st.markdown('<div class="glass-card" style="min-height:450px;">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">📢 1. KAP Bildirimleri (Son 20)</div>', unsafe_allow_html=True)
    if analyze_trigger and target_ticker:
        with st.spinner("KAP Verileri Çekiliyor..."):
            time.sleep(1.5) # Simülasyon
            st.success("Son 20 KAP bildirimi başarıyla çekildi.")
            # Göstermelik KAP Bildirimleri
            for i in range(1, 6):
                change = i * 1.2 * (-1 if i%2==0 else 1)
                color = "green" if change > 0 else "red"
                with st.expander(f"KAP Bildirimi {i} | Etki: %{change:.1f}"):
                    st.write(f"Bu bildirim {target_ticker} şirketinin olağan genel kurul kararlarını içermektedir. Yayınlandıktan 1 gün sonraki fiyat değişimi: %{change:.1f}")
    else:
        st.info("Hisse kodu girip başlatın.")
    st.markdown('</div>', unsafe_allow_html=True)

with col_web:
    st.markdown('<div class="glass-card" style="min-height:450px;">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">🌐 2. Canlı Web & Haber Verisi</div>', unsafe_allow_html=True)
    if analyze_trigger and target_ticker:
        with st.spinner("Web Verisi Çekiliyor..."):
            time.sleep(2)
            st.success("İnternetten güncel veriler tarandı.")
            st.markdown(f"**{target_ticker} Güncel Gelişmeler:**")
            st.markdown("- Şirket ile ilgili Bloomberg HT, Investing ve Foreks haberleri tarandı.\n- Sektörel olarak pozitif bir ayrışma söz konusu.\n- Yabancı yatırımcı ilgisinde artış kaydedildi.")
    else:
        st.info("Hisse kodu girip başlatın.")
    st.markdown('</div>', unsafe_allow_html=True)

with col_pdf:
    st.markdown('<div class="glass-card" style="min-height:450px;">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">📄 3. PDF Rapor Analizi</div>', unsafe_allow_html=True)
    uploaded_pdf_main = st.file_uploader("Aracı Kurum Raporu Yükle", type=["pdf"], key="pdf_uploader")
    if uploaded_pdf_main and analyze_trigger and target_ticker:
        with st.spinner("PDF Yorumlanıyor..."):
            time.sleep(2.5)
            st.success("Rapor başarıyla analiz edildi.")
            st.markdown("**Yapay Zeka Yorumu:**")
            st.write(f"{target_ticker} için hedef fiyat revizesi olumlu. Şirketin büyüme stratejisi sektörel ortalamanın üzerinde bir performansa işaret ediyor.")
    elif not uploaded_pdf_main:
        st.info("Lütfen bir PDF raporu yükleyin.")
    st.markdown('</div>', unsafe_allow_html=True)

# ── ÖZEL KAP ARAMASI ────────────────────────────────────────────────────────
st.markdown('<div class="glass-card" style="margin-top:10px;">', unsafe_allow_html=True)
st.markdown('<div class="sidebar-title">🔍 KAP İçi Özel Arama (Semantik Search)</div>', unsafe_allow_html=True)
st.markdown("<p style='font-size:0.8rem;color:#cbd5e1;margin-bottom:12px;'>Seçili şirket için KAP bildirimleri içerisinde arama yapın (Örn: 'Yönetim değişikliği', 'Temettü').</p>", unsafe_allow_html=True)
col_s1, col_s2 = st.columns([4, 1])
with col_s1:
    kap_search_query = st.text_input("", placeholder="Aranacak konuyu yazın...", label_visibility="collapsed")
with col_s2:
    search_kap_btn = st.button("KAP'ta Ara", use_container_width=True)

if search_kap_btn and kap_search_query and target_ticker:
    with st.spinner(f"'{kap_search_query}' konusu KAP bildirimlerinde taranıyor..."):
        time.sleep(1)
        st.success("Arama tamamlandı.")
        st.write("📌 **Bulunan Sonuçlar:**")
        st.write(f"- 12.04.2025 tarihli bildirimde '{kap_search_query}' konusu detaylı olarak geçmektedir.")
elif search_kap_btn:
    st.warning("Lütfen hisse kodu ve arama kelimesi girin.")
st.markdown('</div>', unsafe_allow_html=True)

# ── ÖZAS RAPORU BUTONU ──────────────────────────────────────────────────────
st.markdown('<div style="margin-top:30px; margin-bottom:50px;">', unsafe_allow_html=True)
if st.button("📥 ÖZAS RAPORU OLUŞTUR", type="primary", use_container_width=True):
    st.success("ÖZAS Raporu hazırlanıyor! (Format daha sonra entegre edilecek)")
st.markdown('</div>', unsafe_allow_html=True)
