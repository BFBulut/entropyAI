# ADR-0007 — `core/claude_bg.py` "ertelendi" etiketiyle kalıyor

- **Durum:** **Sonuçlandı (arşiv)** — Faz 13-C, 2026-09-11. Madde 4'ün koşulu
  gerçekleşti (üründen çağıran çıkmadı) ve modül arşive indi:
  [ADR-0009](ADR-0009-claude-bg-arsivlendi.md). Aşağıdaki metin tarihsel kayıttır.
- **Özgün durum:** Kabul edildi (Faz 12-E, 2026-09-10)
- **Bağlam:** `docs/reports/2026-09-10_Faz11F_Spike_Kalici_Terminal.md`,
  `docs/reports/2026-09-10_Faz12_Arastirma_B_Depo_Denetimi.md` §2.2, §7 M4

## Bağlam

`src/entropy/core/claude_bg.py` (741 satır) Faz 11-F "kalıcı terminal" spike'ının
çıktısıdır. Ölçüm: üründe **içe aktaran yok**, `EntropyAI.spec` hiddenimports'ta
**yok** → `.exe`'ye girmiyor; yalnız `tests/test_phase11_claude_bg.py` (32 test)
canlı tutuyor.

## Karar

**Silinmiyor, "deneysel — bağlı değil" olarak etiketleniyor.** `autostart.py`'den
farkı: autostart'ın ürün karşılığı vardı ama davranışı yoktu (ölü ayar);
`claude_bg` ise **ölçülmüş bir spike** — 32 testi çalışan bir davranışı doğruluyor
ve Faz 11-F raporu ertelemeyi bilinçli bir karar olarak yazıyor.

Kural (sessiz kalmasını önlemek için):

1. `docs/ARCHITECTURE.md` §2 paket tablosunda **"deneysel, ürüne bağlı değil"** satırı bulunur.
2. `EntropyAI.spec` hiddenimports'a **eklenmez** — bağlanana kadar `.exe`'ye girmez.
3. Bağlama kararı Faz 11-F raporunun ölçümleriyle birlikte ayrı bir ADR'de verilir;
   üründen ilk çağrı eklendiği commit'te spec girdisi de eklenir.
4. Faz 13'e kadar üründen çağıran çıkmazsa modül `docs/_archive/spikes/` altına iner.

## Geri alma

Etiket kararıdır, kod değişikliği içermez.
