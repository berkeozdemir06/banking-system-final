# 🧠 BIST Agent — Bellek Yönetim Politikası (Memory Policy)

Bu döküman, **RAG Assignment v2 (Madde 172-177)** gereksinimleri uyarınca sistemin bellek (hafıza) yönetim stratejisini tanımlar.

---

### 1. Bellek Katmanları (Memory Layers)

Sistem, kullanıcının finansal ilgi alanlarını ve konuşma akışını takip etmek için üç katmanlı bir hiyerarşi kullanır:

| Katman | Amaç | Teknoloji | Kapasite |
| :--- | :--- | :--- | :--- |
| **Short-Term** | Mevcut konuşmanın akışını ve bağlamını korumak. | `In-memory list` | Son 5 Soru-Cevap Çifti |
| **Long-Term** | Kullanıcının geçmiş ilgi duyduğu hisseleri (ticker) ve tercihlerini hatırlamak. | `Mem0 (Cloud)` veya `Local JSON` | Süresiz |
| **Archival** | Geçmiş analiz sonuçlarını ve raporları depolamak. | `Vector Database` | Proje Süresince |

---

### 2. Veri İşleme ve Gizlilik (Data Handling)

*   **Toplanan Veriler:** Kullanıcının sorguladığı hisse kodları, sorduğu soru tipleri (KAP odaklı mı, haber odaklı mı?) ve tercih ettiği dil/derinlik seviyesi.
*   **Gizlilik:** Kullanıcı belleği sadece ilgili `user_id` ile eşleşen oturumlarda yüklenir. Çapraz kullanıcı verisi erişimi engellenmiştir.

---

### 3. Temizlik ve Silme Politikası (Purge Policy)

*   **Otomatik Purge:** 30 günden eski kullanıcı anıları, bulut tabanlı bellek (Mem0) veya yerel fallback üzerinden otomatik olarak silinecek şekilde konfigüre edilmiştir.
*   **Manuel Silme:** Kullanıcı istediği zaman veritabanı üzerinden "Hafızayı Sıfırla" (`mem.clear()`) fonksiyonunu tetikleyebilir.

---

### 4. Agentic Kullanım Senaryosu

Ajan, her sorgu öncesinde `BISTMemory.get_context()` metodunu çağırarak şu verileri sistem prompt'una enjekte eder:
1.  *"Kullanıcı daha önce ASELS ile ilgilenmişti."*
2.  *"Kullanıcı genellikle KAP bildirimlerindeki çelişkilere odaklanıyor."*
3.  *"Son sorusunda bir önceki analizi yetersiz bulmuştu (Follow-up desteği)."*

---

> [!NOTE]
> Bu politika, finansal analizlerde tutarlılığı artırmak ve kullanıcıya özel bir deneyim sunmak amacıyla **Agentic Market Intelligence** mimarisinin bir parçası olarak uygulanmaktadır.
