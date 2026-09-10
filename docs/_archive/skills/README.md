# `docs/_archive/skills/` — tekilleştirmede ayrılan yetenek kopyaları

## `media-agency-soldier-root-proxies/` (Faz 12-E)

`skills/media-agency-soldier/` **kökünde** duran 6 dosya (`__init__.py`,
`campaign_architect.py`, `media_calculator.py`, `seo_analyzer.py`, `soldier.py`,
`url_analyzer.py`, toplam 1.107 satır) buraya alındı.

**Kanıt — neden ölüydüler:**

- Dizin adı tireli (`media-agency-soldier`) → Python paketi olarak **içe aktarılamaz**.
- Hiçbir dosya bunları yol üzerinden yüklemiyordu:
  `grep -rn "spec_from_file_location" src tests` → yalnız `perf_bench`, `memory_migrate_v2`,
  `brain_metrics`; çıplak `import campaign_architect|url_analyzer|…` → **0 sonuç**.
- Üç test dosyası `SKILL_DIR`'i `sys.path`'e ekliyor ama içe aktarımı
  `skills.media_agency_soldier.*` (alt çizgili paket) üzerinden yapıyor.
- Beşi de `scripts/` altındaki gerçek koda yönlendiren **proxy**'ydi
  (`importlib.util.spec_from_file_location(... / "scripts" / ...)`); `url_analyzer.py`
  ise alt çizgili paketteki 949 satırlık kopyanın **birebir aynısıydı** (`diff` → SAME).

**Üçüzlemeden sonra kalan iki katman (kanonik):**

| Yol | Rol | Kim kullanıyor |
|---|---|---|
| `skills/media-agency-soldier/SKILL.md` + `scripts/` (4.928 satır) | **tek gerçek kaynak** | `src/entropy/skills/media_agency_soldier_engine.py:33` (`root/"skills"/"media-agency-soldier"/"scripts"`), `SKILL.md:43-53` CLI |
| `skills/media_agency_soldier/` (alt çizgili, 8 dosya) | testlerin içe aktardığı proxy paketi | `tests/skills/test_media_agency_{soldier,advanced,enhancements,deep_capabilities}.py` |

Doğrulama: `pytest tests/skills -q` → **111 passed** (taşımadan önce de sonra da).
