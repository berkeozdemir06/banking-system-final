# 🎙️ BIST RAG — Teknik Tartışma ve Tercihler (Technical Discussion)

Bu döküman, **RAG Assignment v2 (Madde 6.2.5 ve 6.5.5)** gereksinimleri uyarınca sistem tasarımındaki tercihleri ve teknik ödünleşimleri (trade-offs) açıklar.

---

### 1. LLM Tercihi ve Ödünleşimler (Madde 134)

Sistemimizde **Groq (Llama-3)** kullanımı tercih edilmiştir. Diğer modellerle karşılaştırması aşağıdadır:

| Model | Avantaj | Dezavantaj | Neden Groq? |
| :--- | :--- | :--- | :--- |
| **GPT-4o** | Yüksek akıl yürütme. | Pahalı ve Latency yüksek. | - |
| **Gemini 2.5** | Büyük bağlam penceresi. | API hız limitleri. | - |
| **Llama-3 (Groq)** | **Ultra-düşük gecikme (LPU).** | Bazen Türkçe gramer hataları. | Finansal analizlerde "hız" ve "ajan tepkisi" önceliklidir. |

---

### 2. Türkçe Finansal Dil Performansı (Madde 163)

Türkçe, eklemeli bir dil olduğu için finansal terminolojide (örn: *"temettü verimliliği"*, *"bedelsiz sermaye artırımı"*) yerel bir embedding modeli kritik önem taşır.

*   **Embedder Seçimi:** Nomic-Embed-v1 ve sentence-transformers (all-MiniLM-L6-v2) kullanılmıştır.
*   **Gözlem:** Standart modeller "KAP" veya "BIST" gibi kısaltmaları anlamakta başarılı olsa da, kompleks finansal cümle yapılarında `RecursiveCharacterTextSplitter` separatörleri Türkçe cümle yapısına (noktalama işaretleri) göre optimize edilmiştir.

---

### 3. Veri Çıkarımı (Docling & Firecrawl)

*   **Docling:** Brokerage raporlarındaki (PDF) tablo verilerini (Table extraction) standart PDF kütüphanelerine göre %40 daha başarılı bir şekilde metne dönüştürdüğü için seçilmiştir.
*   **Firecrawl:** Dinamik haber sitelerindeki "Infinite Scroll" veya "Lazy Load" bariyerlerini aşarak temiz Markdown verisi sağladığı için tercih edilmiştir.

---

### 4. Ajan Mimarisi Tercihi (Madde 89)

Sistemde neden "Simple RAG" değil de "Agentic RAG" kullanıldı?
*   Haberlerdeki "spekülatif" anlatımları KAP'taki "resmi" verilerle doğrulama (Verification) ihtiyacı, bir ajanın (Reasoning Step) devreye girmesini zorunlu kılmaktadır. Bu sayede sistem hatalı bilgi verme riskini minimize eder.
