# ADR-0005 — Kendi belirteç sistemimiz + QtAwesome; hazır Qt tema kütüphaneleri alınmaz

- Durum: **kabul edildi** (Faz 11-E'de uygulanacak)
- Tarih: 2026-09-10
- Kaynak: `docs/reports/2026-09-10_Faz11_Arastirma_D_Arayuz_Tasarim_Denetimi.md`

## Bağlam

"Karmaşık ve modern değil" yargısı sayıyla doğrulandı. **Tasarım sistemi yok; iki yarım sistem
var** (`CYBER_THEME` ve `READING_TOKENS` aynı rolleri farklı değerlerle dolduruyor):

- 99 farklı hex, 223 yerel `setStyleSheet`, 87 sabit boyut, 9 yazı boyutu, 18 font ailesi,
  yazıların %63'ü kalın;
- Zen'de tek ekranda 153 görünür denetim, üst çubukta 18 öğe, sol sekme çubuğunun 7
  sekmesinden 1920 px'te yalnızca 3'ü görünüyor, merkez sütunun %93'ü boş;
- aynı rapor bilgisi 8 yüzeyde tutarsız sayılarla;
- Chat'te 1280×800'de sohbet gövdesi pencerenin %17'si;
- üç erişilebilirlik ihlali: klavye odağı 0 düğmede görünür, panel kenarlığı kontrastı 1,39:1,
  23 denetim 24 px altında;
- "modern görünmeme"nin kaynağı: saf tayf (S=%100) 8 vurgu rengi + tamamen emoji ikonografi
  (376 kullanım, 76 emoji) + BÜYÜK HARF panel başlıkları.

## Karar

1. **Kendi belirteç sistemimiz**: 12 renk belirteci (WCAG oranları hesaplanmış), 4 tipografi
   kademesi + mono, 4 px ızgara, 3 yarıçap, 14 bileşen, çalışır bir `build_qss()`.
2. **İkonlar QtAwesome** (MIT) — emoji ikonografi kaldırılır.
3. Reddedilenler: `qfluentwidgets` (GPLv3 / ücretli ticari lisans), `qt-material` ve
   `qdarktheme` (sorun tema değil, **sistemin yokluğu**).
4. Kurallar 8 kalıcı testle zorlanır (`test_no_hardcoded_hex`, `test_focus_rules_exist`,
   `test_zen_fits_1366` …) ve Entropy'ye bir `ui-design` yeteneği (`SKILL.md`) eklenir:
   7 değişmez, "ölç → planla → uygula → kanıtla" süreci, çalıştırılabilir ölçüm betiği,
   9 kapı eşiği.

## Gerekçe

- Lisans: `qfluentwidgets` GPLv3'tür; ticari lisansı ücretlidir. Kapalı bir kişisel uygulamada
  bu bir yükümlülük doğurur.
- Teşhis: hazır bir tema, 223 yerel `setStyleSheet` çağrısının üstünü örter ama kaldırmaz.
  Sorun paletin çirkinliği değil, **her ekranın kendi paletini uydurması**dır. Belirteç
  sistemi + testler bu kök nedeni kaldırır.
- Emoji ikonografi platformlar arası tutarsızdır ve boyut/hizalama denetimi vermez.

## Sonuçlar

- Tek doğruluk kaynağı: belirteç modülü; `setStyleSheet` çağrıları belirteçlerden türetilir ve
  `test_no_hardcoded_hex` yeni hex sızıntısını engeller.
- Bilgi mimarisi sadeleşir: sekmeler → dikey gezinme, üst çubuk 18 → 4 öğe, rapor yüzeyi
  8 → 2, komut paleti birincil gezinme, "Bildirimler" 6 tıklamadan 1'e.
- Desk zaten daha disiplinli (17 hex); aynı belirteçlere **son adımda** geçirilir.
- Maliyet: 14 bileşenin bir kez yazılması ve widget'ların kademeli geçişi; kazanç, sonraki her
  arayüz işinin ölçülebilir bir kapıdan geçmesi.
