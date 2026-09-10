# `scripts/_oneshot/` — tek seferlik betik arşivi

Bu klasördeki 59 betik **koşulmaz**. Geçmiş fazlarda bir kez çalıştırılmış,
Obsidian kasasına rapor/hafıza yazmış tek seferlik araçlardır; kod değeri değil
**tarih değeri** taşırlar (hangi fazda kasaya ne yazıldığının kaydı).

Kurallar:

- Buradan hiçbir modül içe aktarılmaz; hiçbir test bu klasöre bağlı değildir
  (kanıt: `grep -rlE "record_faz|save_faz|sync_faz|process_phase" tests` → 0).
- Altı betik makineye çakılı mutlak yol (`C:\EntropiAI\...`) içerir;
  `sync_faz150_obsidian.py` Faz 11-A'da arşive taşınmış bir rapora bakar →
  **bugün çalışmaz**. Onarılmaz, olduğu gibi bırakılır.
- Yeni tek seferlik betik yazılırsa doğrudan buraya yazılır, `scripts/` köküne değil.
- Silme kararı ayrı bir ADR gerektirir; kasadaki çıktıları zaten yazılmış durumdadır,
  taşıma kasaya dokunmaz.

Taşıma: Faz 12-E, `git mv` (geçmiş korunur). Manifest: `docs/reports/2026-09-10_Faz12_Arastirma_B_Depo_Denetimi.md` §7 M1.
