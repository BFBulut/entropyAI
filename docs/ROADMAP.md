# Entropy AI — Yol Haritası

> `docs/PHASED_ROADMAP.md`'nin yerini alır (Faz 11-A, `git mv` + yeniden yazım).
> Eski dosya kendi kendini "eskimiş" ilan ediyor ve atıf yaptığı prototip serisi silindi.
> Mimari için [`ARCHITECTURE.md`](ARCHITECTURE.md), güncel durum için [`STATE.md`](STATE.md).

Çalışma biçimi: iş **fazlara** bölünür. Her faz sonunda commit + build + testler + kısa rapor
(`docs/reports/`) + sürüm etiketi; **fazlar arasında kullanıcı onayı beklenir**, faz içinde
onay istenmez.

---

## 1. Tamamlanan fazlar

| Faz | Ne getirdi | Sürüm | Rapor |
|---|---|---|---|
| 1 | Kablolama, açılış ve temel kip iskeleti | v0.1.8 | `2026-09-10_Faz1_Ilerleme_Raporu_v0.1.8.md` |
| 2 | Çekirdek akış ve arayüz düzeltmeleri | v0.1.9 | `..._Faz2_..._v0.1.9.md` |
| 3 | Agent Desk tasarımı ve ilk sürümü | v0.2.0 | `..._Faz3_Agent_Desk_Tasarim_Raporu.md`, `..._Faz3_..._v0.2.0.md` |
| 4 | Cilalama, rapor gelen kutusu | v0.2.1 | `..._Faz4_..._v0.2.1.md` |
| 5 | Bilgi grafı, komut paleti, rapor merkezi | v0.3.0 | `..._Faz5_Tasarim_Raporu.md` (koddan atıflı) |
| 6 | Desk veri kökü, CLI sınırları ve efor | v0.4.0 | `..._Faz6_..._v0.4.0.md` |
| 7 | Bütçe, orkestratör, panel minimumları | v0.5.0 | `..._Faz7_..._v0.5.0.md` |
| 8 | Hiyerarşik graf, graf verisi ve pencereler | v0.6.0 | `..._Faz8_..._v0.6.0.md` |
| 9 | Entropy Saf Kip, sağlayıcı/model kimliği, Desk ayrımı | v0.7.0 | `2026-09-11_Faz9_Ilerleme_Raporu_v0.7.0.md` |
| 9.1 | Efor = model varyantı, proje kökü düzeltmesi, skill enjeksiyon bütçesi | v0.7.1 | `2026-09-10_Faz10_Ara_Rapor_v0.7.1.md` |
| 10 | Ofis çalışma alanı dosyaları, denetim noktaları, kanıtla kapat, etkileşimli kartlar, worktree + PR akışı, ekip şablonları, makbuz | v0.8.0 | `2026-09-10_Faz10_Ilerleme_Raporu_v0.8.0.md` |

---

## 2. Faz 11 — "Entropy AI'nın Beyni" (yürürlükte)

Dayanak dört salt okunur araştırma raporu: A (hafıza ve RAG), B (depo denetimi),
C (görev panosu ve ajan çalışma zamanı), D (arayüz tasarım denetimi) +
`2026-09-10_Faz11_Plan_ve_Yol_Haritasi.md`.

| Dilim | Ne | Kota (model turu) | Etiket | Durum |
|---|---|---:|---|---|
| **11-A Temizlik ve iskelet** | B §8: `.gitignore`; üretilmiş ikili çıktı (4,5 GB) ve kök artıkları silinir; kullanıcı çıktıları arşive/depo dışına; prototip kaynağı (60 dosya) + testleri (32 dosya) silinir; `docs/{ARCHITECTURE,STATE,ROADMAP}.md` + `adr/` kurulur; `AGENTS.md`/`GEMINI.md` gerçekle eşitlenir; `.claude/agents` ayrımı; testler `tests/{contracts,ui,desk,skills}` altında gruplanır | 0 | v0.9.0 | **uygulandı** (build/ölçüm QA'da) |
| **11-B Beyin v2 çekirdek** | Kategori disiplini + şema v2, `MemoryGate` (tek giriş, LLM'siz üç bantlı yenilik kapısı, `reconcile_facts` bağlantısı), test yalıtımı (7 yazma noktası), hafıza göçü (1544 → ~668), öz-amplifikasyon kilidi, okuma eklentileri, K1–K12 ölçüm paketi | ~60 | v0.9.1 | sırada |
| **11-C Entropy Board ve ajan çalışma zamanı** | 8 durumlu FSM + `events.jsonl` + `TASKBOARD.md` projeksiyonu; `BoardDispatcher` + atomik claim + kapanış uzlaştırıcısı; ajan başına oturum deposu; efor uçtan uca; 4+1 pano aracı; rapor → sohbet kartı; Entropy'nin kendi kararıyla görev üretmesi | ~120 | v0.9.2 | planlandı |
| **11-D Konsolidasyon, wiki, genel beyin** | Gri bant kuyruğu + toplu birleştirme turu; rüya v2; wiki derleme hattı; genel sohbet beyin paketi (K4 ≥ %60); bellek panosu | ~90 | v0.9.3 | planlandı |
| **11-E Tasarım sistemi ve arayüz sadeleştirme** | Belirteç sistemi + `build_qss()` + QtAwesome + 8 tasarım testi; kabuk sadeleştirme; Zen panelleri; Chat krom ≤ %25; erişilebilirlik kapıları; Desk'e aynı belirteçler; `ui-design` yeteneği | 0 | v0.9.4 | planlandı ([ADR-0005](adr/ADR-0005-tasarim-sistemi-kendi-belirtecler.md)) |
| **11-F (isteğe bağlı spike)** | Gerçek kalıcı arka plan terminali (uygulama kapansa da süreç yaşar) | ~20 | — | açık uçlu |

Sıra: 11-A → 11-B → 11-C → 11-D → 11-E. 11-E ile 11-C birbirine bağımlı değildir; istenirse
tasarım öne alınabilir.

---

## 3. Faz 12 (tamamlandı, v0.10.0) ve Faz 13 (yürürlükte)

Faz 12: beynin kapanışı, otonom pano, tasarım köprüsü, depo bakımı — `docs/reports/2026-09-10_Faz12_Ilerleme_Raporu_v0.10.0.md`.

Faz 13 planı: `docs/reports/2026-09-10_Faz13_Plan_ve_Yol_Haritasi.md` (araştırma: `…_Faz13_Arastirma_Notu.md`).

| Dilim | Durum | Not |
|---|---|---|
| 13-A UX ve çekirdek + onaylı canlı koşular | **tamamlandı, v0.10.1** | `docs/reports/2026-09-10_Faz13_Ilerleme_Raporu_v0.10.1.md` |
| 13-A2 v0.10.1 geri bildirimi (donma, görünmeyen düğmeler, ajan durumu, pencere yanıp sönmesi, beyin kısa devresi kapalı) | **tamamlandı, v0.10.2** | tam süit 2.596 passed, `ui_audit --gate --final` exit 0; **açık regresyon R-13A2-1** (kullanıcının iki kart dosyası kayıp) `STATE.md` §2.10'da |
| 13-B eski bellek paketi → `entropy.brain` taşıması | **tamamlandı, v0.10.3** | kota 0; 27 modül `git mv`; 166 dosyada dizgi; uyumluluk şimi (v0.12.0'da silinir); [ADR-0008](adr/ADR-0008-brain-paket-tasimasi.md); toplama 2.596 → 2.596, QA tam süit **2.605 passed / 0 failed**, build exit 0, `Entropy AI 0.10.3` |
| 13-C Desk kanıt zinciri ve temizlik | **tamamlandı, v0.10.4** (wiki ikinci parti kota aşımı nedeniyle koşulmadı) | `docs/reports/2026-09-11_Faz13_Ilerleme_Raporu_v0.10.4.md` |
| 13-D Kapanış | **tamamlandı, v0.11.0** | `docs/reports/2026-09-11_Faz13_Ilerleme_Raporu_v0.11.0.md` |

---

**Faz 13 kapandı** (v0.11.0, 2026-09-11): tam süit 2.648 passed / 0 failed, build exit 0,
`--version` → `Entropy AI 0.11.0`, `ui_audit --gate --final` exit 0.

---

## 3.1 Faz 14 — "Geçici ajan, gerçek onay, süreklilik" (yürürlükte)

Dayanak: `docs/reports/2026-09-11_Faz14_Analiz_ve_Plan.md` (kullanıcı 2026-09-11'de onayladı)
+ iki salt okunur araştırma notu (A: mevcut mimari ve hata izi, B: istenen mimari ve fark)
+ `2026-09-11_Arastirma_LangChain_LangGraph_LangSmith.md`.
Mimari karar: [ADR-0010](adr/ADR-0010-gecici-ajan-mimarisi-langgraph-alinmadi.md)
(geçici ajan mimarisi; LangGraph alınmaz, dört desen alınır).

**Kabul ölçütü test sayısı değil, kullanıcının senaryosudur.**

| # | Senaryo | Geçti sayılması için |
|---|---|---|
| **S1** | İki ardışık sohbet turu | ikinci tur birincinin konusunu doğru anar; argv'de `--resume` görünür |
| **S2** | "google-flow ile video üret" | onay kartı (araç / komut / risk) çıkar → "onaylıyorum" → komut koşar; reddet yolu da çalışır |
| **S3** | "media-agency-soldier ile canivopets.com'u sıfırdan araştır" | canlı akış satırı → rapor → **tek** bildirim; `agent.md` ve oturum diskte **yok**, ledger satırı **var** |
| **S4** | S3'ten sonra yeni sohbet | Entropy bulguyu **kaynaklı** hatırlar; K3 ≤ %5, K12 artmaz |
| **S5** | Yeni düzen | 7 düğme üstte, sağda tam panel (Sohbet/Hafıza); `ui_audit --gate --final` exit 0 |

| Dilim | İş | Senaryo | Ajan | Etiket | Durum |
|---|---|---|---|---|---|
| **14-A** Sohbet sürekliliği | sabit sistem istemi, bağlam kullanıcı mesajına iner, imza yalnız sabit bölümlerden, tek oturum kimliği, ledger `model`/`effort`, sohbette proje kökü salt okunur | S1 | agy-integration-engineer | **v0.11.1** | **tamamlandı** (canlı S1 GEÇTİ) |
| **14-B** Gerçek onay | stdio MCP onay sunucusu + `--permission-prompt-tool`; skip bayrağı koşullu; tek bekleyen işler kuyruğu (`core/pending.py`) + onay kartı; CLI keşif yedekleri | S2 | agy + ui | **v0.11.2** | **tamamlandı** (canlı S2 GEÇTİ: onay/ret) |
| **14-C** Geçici ajan döngüsü | `agents/ephemeral.py`: `agent.md` üretici, tek seferlik oturum, canlı akış satırı, yeteneğe göre adım tavanı (aşınca `review`), kendini silme, tek bildirim; kalıcı kadro **gizlendi** | S3 | agy + ui | **v0.11.3** | **tamamlandı** (canlı S3 iki koşum GEÇTİ) |
| **14-D** Hafıza yazarı alt ajan | kapıda hata/günlük/yığın izi reddi bandı; 16 artık düğüm **arşive** (silme yok); alt ajan `[HAFIZA]` JSON → kapı | S4 | memory-rag-engineer | v0.11.4 (ayrı etiket atılmadı) | **offline tamamlandı**; **canlı S4 kapanışta doğrulanacak** |
| **14-E** Yeni düzen | 7 düğme üstte (`navStrip`), sağ tam panel Sohbet/Hafıza, çekirdek sohbetin üstünde, tek durum satırı; `ui-design` G14-1 / G14-1b kapıları | S5 | ui-engineer + repo-curator | v0.11.5 (ayrı etiket atılmadı) | **tamamlandı**; **gerçek ekranda S5 kapanışta doğrulanacak** |
| **14-F** Kapanış | tam süit, build, **`dist/` kullanıcının ikilisi**, veri kökü tek kaynak (`core/paths.py`), `entropy.memory` şiminin kaldırılması, R-13A2-1 drift döngüsü, ARCHITECTURE ölçümle eşit, S1–S5 gerçek ekranda birlikte | tümü canlı | qa-build-engineer + repo-curator | **v0.12.0** | **yürürlükte** (belge kapanışı yapıldı; QA açık) |

**Ölçüm (14-E sonu):** kaynak **167 dosya / 85.520 satır** (Faz 14 farkı +9 modül /
+4.327 satır), test dosyası **209**; toplanan test sayısı ve `dist/` ölçümü kapanış
QA'sındadır. Kanıtlar: `docs/reports/_evidence_2026-09-11_s{1,2,3}_live.json`,
`scratch/phase14/s3_live.json`, `scratch/phase14/permission_spike/README.md`.
Faz 14 raporu: `docs/reports/2026-09-11_Faz14_Ilerleme_Raporu_v0.12.0.md`.

Sıra: 14-A → 14-B → 14-C → 14-D → 14-E → 14-F (14-E, 14-A ile paralel koştu).
**Kota tavanı 150k**; 14-A…14-E'de harcanan **ham ≈ 194k / taze ≈ 6k** — ham sayı
CLI'ın önbellek okumalarını da sayar, abonelik penceresini yakan **taze** sayıdır
(ayrıntı: faz raporu §3). 14-C'nin koşum başına 60k'lık ham tavanı iki koşumun
toplamında 3.272 token aşıldı.

### Faz 14 sonrası aday işler (sıralanmadı, kota onayı gerekir)

| # | İş | Neden | Dayanak |
|---|---|---|---|
| 1 | **agy kolunun canlı doğrulaması** | geçici ajan agy yolunda yalnız birim testiyle ölçüldü (`agent.md` yazılır/silinir) | STATE §2.15-C açık (c) |
| 2 | **"Güvenli komut" sınıfının onay kapsamına alınması** | `echo`/`ls` izin kancasından önce koşuyor; "her araç sorulur" garantisi yok. Önce **belge/bayrak araştırması** (`--permission-prompts none` + beyaz liste maliyeti) | ARCHITECTURE §6.6, spike README §1 |
| 3 | **Rapor yolu kararı** | geçici ajan raporu `Entropy/Skills/<yetenek>/Reports/` altına düşüyor, yeteneksiz koşuda `Entropy/Reports/`; tek yol mu, iki yol mu — ADR gerekir | STATE §2.15-C açık (b) |
| 4 | **Wiki ikinci partisi** (~30k) | 13-C'de kota nedeniyle koşulmadı | Faz 13 kalanı |
| 5 | **Veri kökü tekleştirmesinin kalanı** | 7 modül hâlâ `Path.home()` sabit yazıyor; yenileri `paths.data_root()` kullanıyor | ARCHITECTURE §3.0 |
| 6 | **Desk — Faz 10 kalanları** | ofis/orkestratör yüzeyi Faz 13'ten beri beklemede | ADR-0001, Faz 10 raporu |
| 7 | **F-13D-1** açılışta fault günlüğüne COM istisnası · **R-13A2-1** drift döngüsü | açık bulgular | STATE §2.14, §2.10 |
| 8 | **LangGraph — parkta** | yeniden açılırsa izole venv'de ~10k'lık spike; `pyproject.toml` değişmez | ADR-0010 "Geri alma" |

Faz 14'e devreden eski açık işler: wiki ikinci partisi (~30k, kota onayı), F-13D-1 kök
nedeni, R-13A2-1 drift döngüsü, `entropy.memory` şiminin v0.12.0'da kaldırılması
(**yapıldı, 14-F** — [ADR-0008](adr/ADR-0008-brain-paket-tasimasi.md)); kalanlar
yukarıdaki aday iş tablosuna taşındı.

**Hafıza sıfırlanmaz (şimdilik):** şema Faz 11-B'de temizlendi, değişen **yazar**dır.
Tetik ölçütü 14-D sonrası K3 > %5 ya da K12 artışı → önce `dream.forget_stale` + gri tur.

---

## 4. Değişmezler (her fazda geçerli)

1. **API anahtarı yok.** Yalnızca abonelik oturumlu iki CLI köprüsü.
2. **Kullanıcı verisine dokunulmaz.** Obsidian kasası ve `~/.entropy` hiçbir temizlikte
   silinmez.
3. **Ölç, iddia etme.** Her rapor sayı verir: test sayısı, dosya/MB önce-sonra, süre.
4. **Silme iki aşamalıdır:** manifest + kuru koşum, sonra yalnızca onaylı liste.
5. **`git stash` / `git checkout --` / `git reset --hard` yasaktır.**
6. **Marka kuralı:** ticari referans ürünün ve üreticisinin adı hiçbir dosyaya yazılmaz.
7. **Bilgi ve görev akışı tek yönlüdür** (Entropy → Desk) — [ADR-0001](adr/ADR-0001-desk-ayrimi.md).
8. **Silme = arşiv + olay.** Ürüne bağlanmamış kod `docs/_archive/spikes/`, eskiyen ölçüm
   `docs/_archive/state/`, kullanıcı çıktısı `docs/_archive/customer/` altına **taşınır**;
   kart arşivlenmesi FSM'de T13'tür ve **gerekçesiz yapılamaz**. Kayıt bırakmayan silme
   yoktur: her taşımanın bir ADR'si ya da olay satırı olur (R-13A2-1 tam olarak bu kural
   çiğnendiği için doğdu — iki kart dosyası olay yazılmadan kayboldu).
9. **Faz kapanışı = kullanıcının koşturduğu `dist/` ikilisi son sürümdür.** "Build exit 0"
   kapanış ölçütü değildir: 13-A2'nin düzeltmesi `dist_check/`te kaldı ve kullanıcı
   düzeltilmiş sanılan hatayı üç kez yaşadı. Kapanış raporuna `EntropyAI.exe --version`
   çıktısı ve `dist/` ikilisinin mtime'ı yazılır (Faz 14, A notu §3 madde 2).
10. **Başarısız turun hata metni hafızaya girmez.** Hata, yığın izi, günlük satırı ve
   `[Otonom Görev Hata]` içerikleri `MemoryGate` tarafından reddedilir (reddedilenler gri
   kuyruğa düşer, sessizce yutulmaz); yazma `success` bayrağına bağlıdır. Test artığı
   düğümler silinmez, **arşivlenir**. Gerekçe: `'list_iterator'` hata metni ve 12 pytest
   izli düğüm gerçek hafızaya bu yoldan girdi (Faz 14, A notu §1 madde 3c).
11. **Araştırma kartları beyinden kısa devre yapmaz.** "Araştır" dendiğinde araştırma
   **canlı** koşar; beyin ajana bağlamdır, yanıtın yerine geçmez
   (`config.brain_shortcut_enabled` varsayılan **False**; tek meşru kapı kullanıcının
   açık `brain_only` tercihidir).
