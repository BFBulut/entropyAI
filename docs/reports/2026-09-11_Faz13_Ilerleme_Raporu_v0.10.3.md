# Faz 13 İlerleme Raporu — 13-B (v0.10.3): `entropy.memory` → `entropy.brain`

Tarih: 2026-09-11 · Branch `ai/v0.1.7` · Taban `v0.10.2` · Etiket `v0.10.3` (commit'ler `c0d865f` yeniden adlandırma + `d126bf8` atıf değişimi) · Build: `dist\EntropyAI\EntropyAI.exe`

Dayanak: araştırma notu §2 (ADR-0004'ün beş gerçek ön koşulu yeşil; yüzey 113 dosya), kullanıcı onayı 2026-09-10. Karar: `docs/adr/ADR-0008-brain-paket-tasimasi.md` (ADR-0004 yerine geçildi).

## Yapılan
- `git mv src/entropy/memory src/entropy/brain` (27 dosya, yalnız R satırları); 166 dosyada `entropy.memory` → `entropy.brain` (src 48/183 satır, tests 57, scripts 5 + `_oneshot` 55, spec 27 satır); dizgi hâlindeki üç modül adı elle (hafıza denetçisi diyaloğu, günlükçü adı `entropy.brain.cognitive`); göreli import 0.
- Uyumluluk şimi `src/entropy/memory/__init__.py`: `sys.meta_path` bulucusu hedef modülün **aynı nesnesini** yayınlar (`entropy.memory.gate is entropy.brain.gate` True, derin yollar dahil), import anında `DeprecationWarning`; ömür bir sürüm, **v0.12.0'da silinecek**.
- Spec: 27 girdi yeni adla + şim; canlı belgeler (`ARCHITECTURE.md`, `STATE.md` §2.11 + §3, `ROADMAP.md`, `GEMINI.md`, ajan tanımları) güncellendi; 31 tarihsel rapor dokunulmadı.
- Veri: `~/.entropy` ve kasa durum dosyalarında paket adına bağlı anahtar yok → **veri göçü gerekmedi**; veri yolları (`~/.entropy/memory/`, `Entropy/Memory`) değişmedi.

## Doğrulama (B4, qa-build-engineer)
| Kontrol | Sonuç |
|---|---|
| Test toplama | 2.596 + 9 yeni = **2.605** (hiçbir test kaybolmadı) |
| Tam süit | **2.605 passed / 0 failed** (681 s) |
| Kaynakta eski atıf | 0 (şim ve spec'in bilinçli girdisi hariç) |
| Build | exit 0 (467 s); `--version` → `Entropy AI 0.10.3` |
| Paket | `entropy.brain*` 30 girdi; kaynaktaki **27/27** modül pakette; şim var, `entropy.memory.<alt modül>` yok |
| Canlı koşum | 20 sn ayakta; exe gerçek `entropy.brain` yolunu yükledi (günlükte `brain\supabase\cognitive_memory.py`); `Traceback`/`CRITICAL`/`ModuleNotFoundError` 0 |
| Yalıtım / marka | üç durum dosyası değişmedi, kasa 423/1 sabit; marka 0/0 |

## Notlar
- İlk commit yalnız yeniden adlandırmaları içerdi (`git add` var olmayan bir yol adı yüzünden hiçbir şey eklememişti); kalan 176 dosya ikinci commit'le eklendi ve etiket ona taşındı.
- `memory_inspector_dialog.py`'deki yedek aday adı `entropy.brain.cognitive_memory` gerçekte `brain.supabase.cognitive_memory` (taşımadan önce de böyleydi; zararsız yedek listesi) — 13-D temizliği.
- Sıradaki: 13-C (Desk'e dönüş: ofis kartı blok sızıntısı, tek yazıcı kontrol noktası, onaylı `[DESK …]` araçları, silme = arşiv + olay, ofis eforu argv, `claude_bg` arşivi, Desk tasarım kalanları) + canlı Desk kanıt zinciri (~60k) + wiki ikinci parti (~30k) → `v0.10.4`; 13-D → `v0.11.0`.
