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

## 3. Faz 12 ve sonrası

| İş | Ön koşul | Not |
|---|---|---|
| `entropy.memory` → `entropy.brain` paket taşıması | Faz 11 kapanış ölçümü yeşil, `.exe` bir kez sorunsuz derlenmiş | ~104 dosya; tek commit; spec hiddenimports riski ([ADR-0004](adr/ADR-0004-faz11-paket-tasima-yok.md)) |
| Agent Desk geliştirmesine dönüş | aynı | Faz 10 kalanları: canlı kanıt/makbuz doğrulaması, `gh` ile PR, efor uçtan uca |
| Sürüm | — | v1.0.0 |

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
