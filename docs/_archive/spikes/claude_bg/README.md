# `claude_bg` — kalıcı arka plan terminali spike'ı (ARŞİV)

- **Arşive alındı:** 2026-09-11, Faz 13-C · [ADR-0009](../../../adr/ADR-0009-claude-bg-arsivlendi.md)
- **Kaynak karar:** [ADR-0007](../../../adr/ADR-0007-claude-bg-ertelendi.md) madde 4
  ("Faz 13'e kadar üründen çağıran çıkmazsa modül `docs/_archive/spikes/` altına iner")
- **Araştırma:** `docs/reports/2026-09-10_Faz13_Arastirma_Notu.md` §3.5 (seçenek B)
- **Spike raporu:** `docs/reports/2026-09-10_Faz11F_Spike_Kalici_Terminal.md`

## Ne yapıyordu

`claude --bg` bayrağının etrafına yazılmış 739 satırlık bir sarmalayıcı:
uygulama kapansa da yaşayan bir arka plan CLI oturumu (`ClaudeBgSession`),
iş klasörü düzeni (`claude_home()` / `jobs_dir()` / `job_dir(<id>)`), CLI
çıktısı ayrıştırıcıları, `BgAgent` durum makinesi ve gerçek süreç yolu.
Faz 11-F'nin isteğe bağlı spike'ıydı; ölçüldü, çalıştı, **ürüne bağlanmadı**.

## Neden ertelendi ve neden arşivde

Kalıcı süreç yaşam döngüsü (yetim süreç, kilit dosyası, Windows süreç ağacı
temizliği) yeni bir risk sınıfı açıyor; Faz 10'un **etkileşimli kart** kipi
(açık stdin + izleyen turlar) bugünkü ihtiyacı karşılıyor. Arşivleme geri
alınabilir bir karardır, bağlama değildir.

Arşive alındığı andaki ölçüm: üründe içe aktaran **0**
(`git grep -n claude_bg src` → boş), yalnız `tests/test_phase11_claude_bg.py`
(32 test) modülü canlı tutuyordu. `EntropyAI.spec` hiddenimports'ta ise
ADR-0007 madde 2'ye **aykırı olarak** bir girdi vardı (`entropy.core.claude_bg`)
— `test_spec_sync` "her kaynak modülü spec'te olmalı" kuralını uyguladığı için
oraya girmişti; modülle birlikte o satır da kaldırıldı.

## Geri getirme adımları

1. `git mv docs/_archive/spikes/claude_bg/claude_bg.py src/entropy/core/claude_bg.py`
2. `git mv tests/_reference/test_phase11_claude_bg.py tests/test_phase11_claude_bg.py`
   ve `tests/_reference/conftest.py` içindeki `collect_ignore` satırını kaldır
   (dosyanın başındaki ARŞİV notu da silinir).
3. `EntropyAI.spec` hiddenimports listesine `'entropy.core.claude_bg'` satırını
   geri ekle — aksi hâlde `test_spec_sync.py::test_spec_lists_every_entropy_module`
   kırmızıya döner ve modül `.exe`'ye **sessizce** girmez.
4. ADR-0007 madde 3 gereği: üründen ilk çağrı eklenirken bağlama kararı için
   yeni bir ADR yazılır; ölçümler Faz 11-F raporundan alınır.
5. `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_phase11_claude_bg.py tests/contracts/test_spec_sync.py -q -p no:cacheprovider`
   → 32 + 9 test yeşil olmalı.
