# ADR-0009 — `claude_bg` arşivlendi

- **Durum:** Kabul edildi (Faz 13-C, 2026-09-11)
- **Yerine geçtiği karar:** [ADR-0007](ADR-0007-claude-bg-ertelendi.md) (sonuçlandı — arşiv)
- **Bağlam:** `docs/reports/2026-09-10_Faz13_Arastirma_Notu.md` §3.5 (seçenek B),
  `docs/reports/2026-09-10_Faz11F_Spike_Kalici_Terminal.md`

## Bağlam

ADR-0007 madde 4 bir son tarih koymuştu: **"Faz 13'e kadar üründen çağıran
çıkmazsa modül `docs/_archive/spikes/` altına iner."** Faz 13-C'de ölçüm:

| Ölçüm | Sonuç |
|---|---|
| `git grep -n claude_bg src` | **0** — üründe içe aktaran yok |
| `EntropyAI.spec` hiddenimports | `'entropy.core.claude_bg'` **vardı** (ADR-0007 madde 2'ye aykırı) |
| Modülü canlı tutan | yalnız `tests/test_phase11_claude_bg.py` — **32 test** |
| Modül boyutu | 739 satır |

Spec girdisi bir karar değil bir yan etkiydi: `tests/contracts/test_spec_sync.py`
"`src/entropy/**` altındaki her modül hiddenimports'ta olmalı" kuralını uyguluyor,
modül orada durduğu sürece satırı da orada olmak zorundaydı. Yani ADR-0007'nin
"`.exe`'ye girmez" güvencesi **fiilen bozulmuştu**.

## Karar

**Arşivlendi (geri alınabilir).**

1. `src/entropy/core/claude_bg.py` → `docs/_archive/spikes/claude_bg/claude_bg.py`
   (`git mv`, geçmiş korundu) + geri getirme adımlarını yazan `README.md`.
2. `tests/test_phase11_claude_bg.py` → `tests/_reference/test_phase11_claude_bg.py`,
   ispat defteri olarak saklanır ama **toplanmaz**
   (`tests/_reference/conftest.py` → `collect_ignore`). Toplama **2.605 → 2.573**.
3. `EntropyAI.spec` hiddenimports'tan `'entropy.core.claude_bg'` satırı kaldırıldı;
   modül kaynakta olmadığı için `test_spec_sync.py` yeşil kalır (9 passed).
4. `docs/ARCHITECTURE.md` §2'deki "deneysel, ürüne bağlı değil" satırı kalktı.

Silme **değildir**: kod da testleri de depoda, tek `git mv` ile geri gelir.

## Gerekçe

Kalıcı süreç yaşam döngüsü (yetim süreç, kilit, Windows süreç ağacı temizliği)
yeni bir risk sınıfıdır; Faz 10'un **etkileşimli kart** kipi (açık stdin +
izleyen turlar) bugünkü ihtiyacı karşılıyor. Arşivleme geri alınabilir,
ürüne bağlama değildir.

## Sonuçlar

- Ürün yüzeyi 739 satır küçüldü; `.exe` artık gerçekten bu modülü içermiyor.
- Süit ölçümü dürüstleşti: koşan 32 test sevk edilen hiçbir kodu sınamıyordu.
- Bedel: spike yeniden canlandırılırsa testleri toplamaya geri almak gerekir
  (adımlar arşiv README'sinde, beş madde).

## Geri alma

`docs/_archive/spikes/claude_bg/README.md` → "Geri getirme adımları".
