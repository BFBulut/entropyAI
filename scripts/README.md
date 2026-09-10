# `scripts/` — canlı geliştirici araçları

Kökteki betikler **canlı**dır: testler ya da ürün kodu bunlara atıf yapar.
Tek seferlik faz betikleri `_oneshot/` altındadır (bkz. `_oneshot/README.md`).

| Betik | Kullanan |
|---|---|
| `brain_metrics.py` | `tests/contracts/test_phase11_brain_metrics.py` (K1–K12 ölçüm paketi) |
| `memory_blind_test.py` | aynı test (K2/K3 kör testi) |
| `memory_migrate_v2.py` | `tests/contracts/test_phase11_brain_metrics.py`, `tests/test_phase11_migration.py` |
| `perf_bench.py` | `tests/test_perf_harness.py`, `src/entropy/core/perf_history.py` |
| `routing_eval.py` | `src/entropy/skills/manager.py` (karar eşiği kaynağı) |
| `ui_audit.py` | `tests/ui/test_design_system.py`, `tests/ui/test_phase11_design_gates.py`, `ui/design/*` |
| `graph_metrics.py` | graf ölçümü (elle koşulur) |
| `phase5_ui_screenshots.py` | ekran görüntüsü üretici (elle koşulur) |
| finans/denetim ailesi (`audit_*`, `sahol_*`, `atatp_*`, `froto_*`, `leverage_*`, `earnings_*`) | `tests/_reference/` altındaki ispat defterleri |
| `generate_canivopets_slides.py` | `tests/skills/test_slide_deck_architect.py` |
