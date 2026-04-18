# 🇹🇷 BIST Equity Intelligence Agent
> **2025-2026 FinTech Ödevi** — Agentic RAG for Turkish Equity Markets  
> Department of International Trade And Business

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-green)](https://langchain.com)
[![Groq](https://img.shields.io/badge/LLM-Llama%204%20on%20Groq-orange)](https://groq.com)
[![ChromaDB](https://img.shields.io/badge/VectorDB-ChromaDB-purple)](https://trychroma.com)

---

## 📌 Proje Özeti

KAP bildirimleri, finansal haberler ve aracı kurum araştırma raporlarını birleştirerek
Türk borsasındaki şirketler hakkında **kaynaklı, zaman farkındalıklı ve etik** sorgu-cevap sistemi.

> ⚠️ **Bu sistem yatırım tavsiyesi vermez.** Tüm çıktılar yalnızca bilgi amaçlıdır.

---

## 🏗️ Teknoloji Stack

| Katman | Teknoloji | Seçim Gerekçesi |
|--------|-----------|-----------------|
| Deployment | Groq | Ücretsiz, ultra-düşük gecikme |
| LLM | Llama 4 Scout 17B | Hız + Türkçe kalitesi |
| Framework | LangChain | Geniş ekosistem |
| Vector DB | ChromaDB | Lokal, ücretsiz, cosine sim |
| Embeddings | Nomic embed-text-v1.5 | Çok dilli, Türkçe dostu |
| Data Extraction | Firecrawl + Docling | HTML + PDF |
| Memory | Mem0 + Local fallback | Kısa/uzun vadeli bellek |
| Guardrails | Regex + LLM | Yatırım tavsiyesi engeli |
| Evaluation | RAGAS | Faithfulness, Relevancy metrikleri |

---

## 🚀 Kurulum

### 1. Bağımlılıklar
```bash
pip install -r requirements.txt
```

### 2. API Anahtarları
```bash
cp .env.example .env
# .env dosyasını düzenleyin
```

### 3. Başlatma
```bash
uvicorn src.api.main:app --reload --port 8000
```

### 4. Docker ile
```bash
cd docker
docker compose up -d
```

---

## 📡 API Kullanımı

### Soru Sor
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "ASELS için son KAP bildirimleri neler?",
    "ticker": "ASELS",
    "k": 5
  }'
```

### KAP Verisi İngest Et
```bash
curl -X POST http://localhost:8000/ingest/kap \
  -H "Content-Type: application/json" \
  -d '{"ticker": "ASELS", "limit": 30}'
```

### PDF Rapor Yükle
```bash
curl -X POST http://localhost:8000/ingest/pdf \
  -F "file=@rapor.pdf" \
  -F "ticker=ASELS" \
  -F "institution=Garanti BBVA Yatırım"
```

---

## 🤖 Agentic Döngü

```
Kullanıcı sorusu
       ↓
[1] Source Selection  ─── LLM: KAP? News? Brokerage?
       ↓
[2] Temporal Reasoning ── recent (<90 gün) / historical / both
       ↓
[3] ChromaDB Retrieval ── semantik arama + metadata filtre
       ↓
[4] Yeterli mi? (≥3 doc) ── Hayır → re-retrieval (filtresiz)
       ↓
[5] Cross-Source Verify ── KAP vs haberler çelişkisi var mı?
       ↓
[6] Guardrails check ──── yatırım tavsiyesi var mı?
       ↓
[7] LLM Answer + Disclaimer
```

---

## 📊 Değerlendirme (RAGAS)

10 BIST/KAP özelleştirilmiş soru ile değerlendirme:

```bash
python -m src.evaluation.ragas_eval
```

Metrikler: Faithfulness · Answer Relevancy · Context Recall · Context Precision

---

## 📁 Proje Yapısı

```
bist-rag-project/
├── src/
│   ├── ingestion/       # KAP + News + PDF scrapers
│   ├── embeddings/      # Nomic embedding pipeline
│   ├── vectordb/        # ChromaDB store
│   ├── agent/           # Agentic RAG core + Memory
│   ├── guardrails/      # Investment advice filter
│   ├── evaluation/      # RAGAS evaluation suite
│   └── api/             # FastAPI endpoints
├── data/                # Raw + processed data
├── docker/              # Dockerfile + Compose
├── index.html           # İlerleme takip paneli
└── requirements.txt
```

---

## ⚖️ Etik Kural

Bu sistem **YASAK**:
- ❌ Yatırım tavsiyesi
- ❌ Al/Sat sinyali
- ❌ Fiyat tahmini

Bu sistem **YAPABILIR**:
- ✅ KAP bildirimlerini özetleme
- ✅ Haber-KAP tutarlılık analizi  
- ✅ Narratif değişim takibi
- ✅ Çapraz kaynak doğrulama

---

*2025-2026 FinTech · Uluslararası Ticaret ve İşletme Bölümü*
