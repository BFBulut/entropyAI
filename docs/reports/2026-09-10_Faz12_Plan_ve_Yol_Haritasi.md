# Faz 12 Planı — Beynin kapanışı, otonom pano, tasarım köprüsü (zincirli; onay alındı)

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Taban `v0.9.4` (Faz 11) · Orkestratör: Claude Fable 5.1 · Uygulayıcılar: 6 alt ajan (Opus 5, low)

Dayanaklar (Faz 11 sonrası aynı dört istemle yeniden tur, hepsi salt okunur ve kanıtlı):
- A — `2026-09-10_Faz12_Arastirma_A_Hafiza_ve_RAG.md`
- B — `2026-09-10_Faz12_Arastirma_B_Depo_Denetimi.md`
- C — `2026-09-10_Faz12_Arastirma_C_Gorev_Panosu_ve_Ajan_Calisma_Zamani.md`
- D — `2026-09-10_Faz12_Arastirma_D_Arayuz_Tasarim_Denetimi.md`

## 0. Faz 11 ne verdi, ne bıraktı (araştırmanın özü)
- **Hafıza:** ölçümler tuttu (729 düğüm, K1 %5,5, Hit@1 9/10, gürültü %0, K4 %77, K5 %42). Ama üç konsolidasyon modülü üretimde köprüsüz: `/memory merge` yanlış sembol adıyla hiç çalışmıyor (hata yutuluyor), `/wiki compile` köprüyü almıyor, `/memory dream` köprü varken `None` geçiyor → K6 (wiki payı) tek FAIL. CRAG eşiği 0,45 çok yüksek (sistem ilgili paket üretebilirken "beynimde yok" diyor). K12'nin kalan 2'si kimlik düğümü (ölçüm tanımı). Literatürde yeni: beceri sentezi ailesi (SKILLFOUNDRY şeması) ve derlenmiş wikinin ROI'si (%84,6 kümülatif token tasarrufu).
- **Pano:** taşıyıcı parçalar kurulu ve canlı kanıtlı; döngünün başı kapalı: Entropy kendi kararıyla görev üretmiyor (`board_create` bağlı değil), beş araçtan yalnızca `board_finish` tüketiliyor (`[KONTROL NOKTASI]` Entropy kartında dosyaya yazılmıyor), araç bloğu metinleri özete/olaya/hafızaya ham sızıyor, oturum bütçesi politikası yok (24k → 39k → 67k), projeksiyon karması üretimde yazılmıyor; `claude --bg` kararı değişmedi.
- **Depo:** temizlik tuttu (untracked 1.262 → 10). Kalan: 59 tek seferlik betik, çürük `EntropyAI_OneFile.spec`, `EntropyAI.spec`'te 15 eksik modül (exe'de sessiz kırılma riski), `ARCHITECTURE.md` bir faz geride, `skills/` üçüzlemesi, sürüm üç yerde farklı, kullanılmayan `pillow`. `memory → brain` taşıması yine ertelenmeli (ön koşullar karşılanmadı).
- **Tasarım:** kapılar yeşil ama yoğunluk kötüleşti (153 → 156; kapı listede yoktu), gömülü SVG/HTML gövdelerinde neon palet (kontrast 2,8:1), graf tuvali `viz.*` belirteçlerini kullanmıyor, üst çubuk "4 öğe" beyanı canlı sayımda 12, rapor sayacı iki kaynak, bölücü kalıcılığı ve tema/yoğunluk seçicisi ölü.

## 1. Dilimler (zincirli; her dilim sonunda test + build + rapor + etiket)

| Dilim | İş | Ajan | Kota | Etiket |
|---|---|---|---|---|
| **12-A Köprü ve sözleşme onarımı** | `/memory merge` → `run_merge_round(memory, send_prompt=köprü)`, `/wiki compile <yetenek> --turns N` → `compile_skill(skill, bridge=köprü, budget_turns=N)`, `/memory dream` köprüyle; **sembol sözleşme testi** (slash → modül bağlantıları import anında doğrulanır); CRAG eşiği 0,45 → ölçümle kalibrasyon (5 sorguda 0,30 civarı; `brain_has_answer` doğruluğu); K12 tanımı kimlik dışlar; `EntropyAI.spec` 15 eksik modül + kalıcı spec-eşleme testi; sürüm tek kaynak (pyproject/`__init__`/etiket); `pillow` kaldır | agy, qa | ~5 | `v0.10.0` |
| **12-B Otonom pano** | araç yürütücüsü: beş pano aracının tamamı tüketilir (`board_checkpoint` → dosya, `board_ask` → posta, `board_next` → sonraki kart ya da sözleşmeden çıkar); özet temizleyici (`[PANO]/[KANIT]/[KURAL]` blokları özet/olay/hafızaya sızmaz); **Entropy'nin kendi kararıyla görev üretmesi**: sistem istemine `board_create` sözleşmesi, sohbet yanıtındaki blok ayrıştırılır → kart `assigned` → dispatcher; oturum bütçesi politikası (ajan başına 3 kart ya da 60k token → `handoff.md` özeti + taze oturum; `--autocompact` bayrağı varsa), `projection.json` + ayrışma uyarısı; slash 34 → 31 birleştirme; ofis↔Entropy birleşik salt okunur pano görünümü | agy, memory-rag, ui | ~40 (canlı doğrulama dahil) | `v0.10.1` |
| **12-C Beynin kapanışı ve beceri sentezi v1** | gerçek wiki derlemesi: financial-auditor (50 rapor, 2×25 tur), media-agency (16), autonomous-agent; gerçek gri birleştirme turu; K6 ≥ %15, K9 ölçümü; `WIKI.state.json` artımlılık canlı; **beceri sentezi döngüsü v1** (SKILLFOUNDRY şeması: ortam varsayımı, provenance, sonlandırma ölçütü, testler): araştırma raporları → skill taslağı (`skills/<ad>/SKILL.md` + betik iskeleti) → öz-doğrulama (kotasız kontrol listesi + isteğe bağlı tek tur) → **kullanıcı onayı** (kural onay paneli ile aynı yüzey; onaysız etkinleşmez) | memory-rag, agy, ui | ~110 (wiki 68 + sentez 30 + doğrulama) | `v0.10.2` |
| **12-D Tasarım köprüsü ve yoğunluk** | gömülü belge tema köprüsü (`markdown_renderer` SVG'leri + rapor kartları + sohbet balonları → `viz.*`/belirteç CSS değişkenleri), graf tuvali `viz.*` (yalnız renk sabitleri), telemetri şeridi kaldırma + rapor sayacı tek kaynak, üst çubuk yaprak sayımı ≤ 6, yoğunluk kapısı (1366'da etkileşimli ≤ 90) nihai listede, tema/yoğunluk seçicisi + bölücü kalıcılığı (QSettings), `ui-design` 1.1.0 (11 yeni kapı + gerçek ekran kontrol listesi) | ui, qa | 0 | `v0.10.3` |
| **12-E Depo bakımı** | 59 tek seferlik betik → `scripts/_oneshot/`; `EntropyAI_OneFile.spec` + 5 eski spec → `docs/_archive/`; `ARCHITECTURE.md` 11-C/D/E sözleşmeleriyle; `GEMINI.md` çift sağlayıcı; 563 "kendi kendine yeten" test → `tests/_reference/`; `skills/` üçüzlemesi kararı (Entropy için `skills/<ad>/SKILL.md` kanonik; Python paketi testler için; `scripts/` kopyası arşiv); `platform/autostart.py` kaldır (ADR); `claude_bg.py` "ertelenmiş" etiketiyle kalır | repo-curator, qa | 0 | `v0.10.4` |
| **12-F Kapanış** | tam süit, spec eşleme, build, gerçek ekran, uçtan uca (otonom görev üretimi + beş araç + oturum bütçesi; tavan 100k), Faz 12 raporu | qa | ~40 | `v0.10.5` |
| **Faz 13 (sonra)** | `memory → brain` taşıması (ön koşullar: 12-E sonrası yüzey ≤ 100 dosya, spec eşleme testi, tam süit yeşil), Desk'e dönüş (Faz 10 kalanları) | — | — | `v1.0.0` |

Sıra: 12-A → 12-B → (12-C ‖ 12-D ‖ 12-E paralel, ayrık kapsam) → 12-F. Dilim içinde onay yok; kullanıcı zincirlemeyi onayladı.

## 2. Kota planı
~195 model turu; en büyük kalem 12-C wiki derlemesi (68 tur, ROI literatürde kanıtlı). Her dilimde tavan; ledger ile izleme.

## 3. Kabul ölçütleri (özet)
K6 ≥ %15 (wiki payı), K9 ölçülmüş, CRAG doğruluk ≥ 4/5, `board_create` canlı (Entropy sohbette bir görevi ajana verip raporunu sohbete alıyor), beş araç tüketiliyor, özetlerde blok sızıntısı 0, oturum bütçesi: 4. kart taze oturumda ve ≤ 30k, `projection_hash` dolu, spec eşleme testi yeşil, yoğunluk ≤ 90, gömülü belge kontrastı ≥ 4,5:1, üst çubuk yaprak ≤ 6, tam süit 0 hata, build smoke temiz.
