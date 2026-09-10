# ADR-0001 — Agent Desk, Entropy AI'dan tam ayrık bir uygulamadır

- Durum: **kabul edildi** (Faz 6'da uygulandı, Faz 9 ve 10-B'de sıkılaştırıldı)
- Tarih: 2026-09-10 (karar geriye dönük yazıya geçirildi)
- Kaynak: `2026-09-11_Faz9_Arastirma_B_Agent_Desk_Yol_Haritasi.md`,
  `2026-09-10_Faz11_Arastirma_B_Depo_Denetimi.md` §3.4, `src/entropy/core/paths.py` modül başlığı

## Bağlam

Agent Desk, Entropy AI'nin içine gömülü ayrı bir uygulama: kendi ofisleri, orkestratörleri ve
alt ajanlarıyla terminallerde yazılım geliştiriyor. İlk sürümlerde Desk, Entropy'nin kendi
kadrosunu (`Entropy/Agents`) ve kendi kasa köklerini paylaşıyordu. Sonuç üç somut sorundu:

1. Entropy'nin ajanları Desk işleriyle meşgul oluyor, Entropy kendi işine ajan bulamıyordu.
2. Ofis kartları Entropy'nin görev panosunda ve çekirdek çiplerinde görünüyordu — ters yönlü
   bir akış (kullanıcının deyimiyle "çok saçma").
3. Ofis verisi `Entropy/Desk/Offices/...` altındayken doğuş talimatı alt ajanlara **mutlak
   yol** verdiği için "Entropy" adı orkestratörün istemine sızıyordu; testler bunu
   "yol satırlarını ölçme" istisnasıyla geçiştiriyordu.

## Karar

1. **Desk'in kendi kadrosu vardır.** Tohum ofis ve tohum ajan yoktur; kullanıcı ofisi
   yarattığı anda o ofisin **orkestratörü** kendiliğinden oluşur.
2. **Veri kökü ayrıdır:** `<kasa>/Desk/**` (kasa kökünde, `Entropy/` altında değil).
   Entropy'nin kendi verisi `<kasa>/Entropy/**` altında kalır. Geçiş
   (`core/paths.py:migrate_desk_root`) kopyala → doğrula → sil sözleşmesiyle, idempotent.
3. **Bilgi tek yönlüdür.** Entropy Desk'in mimarisini bilir ve Desk'i geliştirebilir; Desk
   Entropy'nin varlığını bilmez. Orkestratör istemlerinde Entropy'nin adı geçmez.
4. **Görev akışı tek yönlüdür.** Entropy orkestratörlere görev/mesaj gönderir ve rapor alır;
   Desk Entropy'nin panosuna kart itemez.
5. **Orkestratör kod yazmaz.** Araştırır, planlar, kendi alt ajanlarını oluşturur/düzenler ve
   raporlar; araç politikası salt okunurdur.

## Gerekçe

İstisna yerine kökü değiştirmek daha temiz bir çözümdür: bir sözleşmeyi testte istisna ile
korumak, sözleşmenin fiilen delik olduğunu gizler. Kadro ayrımı da aynı mantıkla yapısaldır —
"Desk Entropy'nin ajanını çağırmasın" diye bir kontrol eklemek yerine Desk'in görebileceği
defteri Entropy'nin defterinden ayırdık.

## Sonuçlar

- `agents/desk_registry.py` ayrı bir kayıt defteridir; `agents/offices.py` yalnızca eski
  adların takma adıdır.
- Entropy'ye salt okunur bir orkestratör listesi + posta kutusu komutları verilir.
- Her QA turunda bu kural sınanır: `tests/contracts/test_phase9_desk_separation.py`,
  `tests/contracts/test_phase10_desk_root.py`.
- Maliyet: iki kayıt defteri, iki kasa kökü ve bir geçiş yolu bakımı.
