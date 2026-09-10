# ADR-0003 — Hafızada kütüphane değil algoritma alınır (mem0 bağımlılığı reddedildi)

- Durum: **kabul edildi** (Faz 11-B'de uygulanacak)
- Tarih: 2026-09-10
- Kaynak: `docs/reports/2026-09-10_Faz11_Arastirma_A_Hafiza_ve_RAG.md`

## Bağlam

Entropy'nin beyninde okuma tarafı ölçülebilir biçimde sağlam: kör testte Hit@1 8/10,
Hit@5 9/10, 316 ms. Asıl açık **yazma tarafındadır**. Düğüm kimliği içeriğin birebir hash'i
olduğu için "bunu zaten biliyorum" denetimi yoktur:

- hafızanın **%55,7'si fazlalık** (1544 düğüm, 684 benzersiz konu),
- **%30'u test fikstürü**,
- 29 uydurma "N katmanlı mimari" adı, kendi çıktısını okuyan bir araştırma görevinden doğmuş
  (**öz-amplifikasyon**),
- genel sohbette beyin payı **%0** (yetenek eşleşmeyince bağlam hiç kurulmuyor),
- rüya (konsolidasyon) döngüsü fiilen ölü,
- çözüm zaten yazılmış ama yanlış yere bağlı: `reconcile_facts` yalnızca graf katmanında;
  **7 yazma noktasının hiçbiri oradan geçmiyor**.

Hazır bir hafıza kütüphanesi (mem0) değerlendirildi.

## Karar

**Kütüphane alınmaz, algoritma alınır.**

- Reddedilen: mem0 paketi bir bağımlılık olarak.
- Alınan fikirler: SAGE üç bantlı yenilik kapısı (ADD / NOOP / gri bant), Dual-Layer kaskadı,
  Hindsight eşikleri (0,92 / 0,95).
- Zaten bizde olan ve korunacak olanlar: CoALA katmanları, HippoRAG 2 tarzı PPR genişletme,
  Zep/Graphiti tarzı çift zamanlı kayıt.
- Uygulama: **tek giriş kapısı** (`MemoryGate`) — 7 yazma noktasının tamamı buradan geçer;
  `reconcile_facts` bu kapıya bağlanır.
- Göç: saf silme değil, **sıfırdan kur + seçici göç** (1544 → ~668 temiz çekirdek);
  `.bak` + Obsidian kasası güvence; Hit@1 düşerse geri alınır.

## Gerekçe

1. mem0 çalışmak için **LLM/API çağrısı** gerektirir; ürünün temel kısıtı "API anahtarı yok,
   yalnızca abonelik oturumu"dur. Her yazmada model çağırmak kotayı hafızaya harcamak demektir.
2. Kütüphanenin graf belleği açık kaynaktan kaldırılmıştır; 2026'da yalnızca ADD işlemine
   dönmektedir — yani asıl ihtiyacımız olan yenilik kapısı zaten dışarıda kalıyor.
3. Yenilik kapısının kendisi **LLM'siz** kurulabilir (gömme benzerliği + üç bant + gri bandın
   gece toplu CLI turuna kuyruklanması). Karpathy'nin ilkesi burada belirleyici:
   *bilgi bir kez derlenir, her sorguda yeniden türetilmez* — bizim en zayıf halkamız
   (wiki, bağlamın yalnızca %0,8'i).

## Sonuçlar

- Yeni bir çalışma zamanı bağımlılığı yok; hafıza yerel SQLite (+ isteğe bağlı pgvector) ile
  çalışmaya devam eder.
- Öz-amplifikasyon kilidi zorunlu hale gelir: açık tespiti, %70 yenilik kotası, kaynak zorunluluğu.
- Test yalıtımı 7 yazma noktasının tamamında sağlanmalıdır; aksi halde fikstürler yeniden
  gerçek hafızaya sızar (bugünkü %30'un kaynağı).
- Ölçüm paketi K1–K12 testte tutulur; kapı eşikleri değiştirilirse bu ADR güncellenir.
