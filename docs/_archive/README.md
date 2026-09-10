# `docs/_archive/` — arşiv

Burası **çöp kutusu değil, soğuk depodur**. İçindeki hiçbir dosya silinmez; taşınırlar.
Kural (repo-curator): depo içi kullanıcı raporları (`*_audit.md/json`) ve müşteri çıktıları
asla silinmez, buraya taşınır.

| Klasör | İçerik | Neden burada |
|---|---|---|
| `customer/` | Kullanıcının denetim çıktıları (`*_financial_audit.md`, `*_audit.json`, `CanivoPets_Media_Agency_Audit.md`) ve `customer/slides/` altındaki sunumlar | Ürün belgesi değil, ürünle **üretilmiş** çıktı. Depo kökünü ve `docs/`'u kirletiyordu. |
| `prototype/` | `2026_Kapsamli_Otonom_Ajan_Mimarisi_…Faz1XX.md` (21), `2026_Otonom_Ajan_Ortamlari_*` (3), `AUTONOMOUS_AGENT_ARCHITECTURE_FAZ126.md` | Anlattıkları kod (`src/entropy/tools/autonomous_agent_architecture*`, 60 dosya / 75.578 satır) Faz 11-A'da silindi. Notlar tarihsel kayıt olarak duruyor. |

## Ne buraya taşınmaz

- **Koddan atıf yapılan raporlar** yerinde kalır. Bugün üç tanesi var:
  `docs/reports/2026-09-10_Faz5_Tasarim_Raporu.md`,
  `docs/reports/2026-09-11_Faz9_Teshis_Notu.md`,
  `docs/reports/2026-09-11_Faz10_Teshis_ve_Mimari_Bosluk_Notu.md`.
  Taşımadan önce doğrulama:
  `grep -rhoE "docs/(reports|specifications)/[A-Za-z0-9_.-]+\.md" src/entropy tests`
- **Kullanıcı verisi** (Obsidian kasası, `~/.entropy`) zaten depoda değildir ve hiçbir koşulda
  buraya kopyalanmaz.
- Depoda tutulması için teknik gerekçesi olmayan **büyük ikili çıktılar** arşive değil, depo
  **dışına** taşınır: `~/.entropy/external/`
  (Faz 11-A'da `google_flow_files/` 102 MB ve `scratch/pixel-agents-main/` oraya gitti).
