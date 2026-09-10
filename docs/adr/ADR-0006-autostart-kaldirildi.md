# ADR-0006 — `platform/autostart.py` kaldırıldı

- **Durum:** Kabul edildi (Faz 12-E, 2026-09-10)
- **Bağlam:** `docs/reports/2026-09-10_Faz12_Arastirma_B_Depo_Denetimi.md` §2.2, §7 M5
- **Karar sahibi:** repo-curator (orkestratör zincirli onayı)

## Bağlam

`src/entropy/platform/autostart.py` (2.692 B, `WindowsAutostartManager`) Windows
başlangıç klasörüne `.bat` yazan bir modüldü. **Ölü ürün modülüydü:**

| Kanıt | Ölçüm |
|---|---|
| Üründe içe aktaran | **0** — `grep -rn "autostart" src/entropy --include=*.py` → yalnız modülün kendisi + `config.py` alanı (+ `single_instance.py` yorumunda geçen kelime) |
| Testten içe aktaran | 2 (`tests/test_exe.py`, `tests/test_scheduler.py`) — yani modülü **yalnızca testleri** canlı tutuyordu |
| Arayüz karşılığı | **0** — `grep -rn autostart src/entropy/ui src/entropy/main.py` → boş |
| Ayar | `config.autostart_enabled` okunuyor **ve** diske yazılıyordu; onu uygulayan hiçbir kod yoktu |

Yani: **ayar vardı, davranış yoktu.** Kullanıcı ayarı açtığında hiçbir şey olmuyordu.
Bu, Faz 11 açık işi #4 olarak iki tur açık kaldı ("ya `main.py` açılışına bağla, ya kaldır").

## Karar

**Kaldırıldı.** Bağlamak yerine silmenin gerekçesi:

1. Otomatik başlatma bir **kurulum/dağıtım** kararıdır, uygulama içi bir kip değil;
   bugünkü dağıtım yolu `EntropyAI.spec` → `dist/EntropyAI` klasörü, kurulum yapıcı yok.
   Başlangıç klasörüne `.bat` yazmak, tek örnek kilidiyle (`core/single_instance.py`)
   birlikte sessiz çakışma üretme riski taşıyordu.
2. Yalnız testin canlı tuttuğu kod, **yanlış güvence** üretir: "2.347 test yeşil"
   cümlesine sevk edilmeyen bir modülün 3 testi giriyordu.
3. Geri getirmek ucuzdur: modül 80 satırdı, git geçmişinde duruyor.

## Yapılanlar

| Dosya | Eylem |
|---|---|
| `src/entropy/platform/autostart.py` | `git rm` |
| `src/entropy/core/config.py` | `autostart_enabled` alanı + `save_settings`/`load_settings` içindeki 3 satır kaldırıldı |
| `tests/test_exe.py` | `test_autostart_detects_compiled_exe` ve içe aktarma kaldırıldı (`test_compiled_exe_exists` kaldı) |
| `tests/test_scheduler.py` | `test_windows_autostart_manager` ve içe aktarma kaldırıldı |
| `EntropyAI.spec` | `'entropy.platform.autostart'` hiddenimport girdisi kaldırıldı (yalnız bu satır) |

**Geriye dönük uyum:** eski `settings.json` dosyalarında `autostart_enabled` anahtarı
kalabilir; `load_settings` bilinmeyen anahtarları zaten görmezden gelir → göç gerekmez,
kullanıcı verisi silinmez.

## Geri alma

`git revert <commit>` — modül, ayar alanı ve iki test birlikte geri gelir.
