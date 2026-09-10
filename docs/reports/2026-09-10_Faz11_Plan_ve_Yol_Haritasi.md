# Faz 11 Planı ve Yol Haritası — Entropy AI'nın Beyni (onay bekliyor)

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Taban `v0.8.0` · Orkestratör: Claude Fable 5.1 · Uygulayıcılar: 6 alt ajan (Opus 5, low effort): memory-rag-engineer, agy-integration-engineer, ui-engineer, qa-build-engineer, research-scout (yeni), repo-curator (yeni)

Dayanaklar (dördü de salt okunur, kanıtlı ve kaynaklı):
- A — `2026-09-10_Faz11_Arastirma_A_Hafiza_ve_RAG.md` (hafıza literatürü, mem0, mevcut hafızanın denetimi, Brain v2)
- B — `2026-09-10_Faz11_Arastirma_B_Depo_Denetimi.md` (envanter, içe aktarma grafiği, manifest, yeni yapı)
- C — `2026-09-10_Faz11_Arastirma_C_Gorev_Panosu_ve_Ajan_Calisma_Zamani.md` (görev panosu, durum makinesi, olay günlüğü, ajan kalıcılığı, efor)
- D — `2026-09-10_Faz11_Arastirma_D_Arayuz_Tasarim_Denetimi.md` (tasarım denetimi ve tasarım sistemi)

## 0. Neyi nasıl anladım

**Ürün.** Entropy AI, API anahtarı kullanmayan (yalnızca Claude Code ve Antigravity abonelik oturumları), kendi kendini geliştiren kişisel bir yapay zeka. Bir **beyni** var (RAG + hafıza), **öğrenir ve beyinle sentezler**, web'de araştırır, skill ve MCP arar, kullanmayı öğrenir, kendine skill ekler; **kendi ajanları** var ve onlara **görev panosu** üzerinden iş dağıtır, raporlarını alır ve arayüzde gösterir. Üç biçimi var (Chat / Floating / Zen). Entropy Agent Desk içinde kalır, sonra geliştirilir.

**Çekirdek döngü (senin grafiğin).** Kullanıcı girdisi → Entropy Chat → girdi beyinde (profesyonel RAG) ve internette, aktif yeteneklerle araştırılır → gerekiyorsa bir ajan için görev oluşturulur ve **TASKBOARD**'a konur → mevcut ajanlar **tek tek tetiklenir**, panoya bakarlar → görevi alan ajan durumu **TAKEN** yapar → ajan işi bitirince **Entropy için rapor** yazar ve "görev tamamlandı" olayını tetikler → Entropy görevi görür, raporu **sohbete** alır. Ajanlar terminallerde çalışır, görevlerini **Markdown**'dan okur; tetikleyici otomatiktir (durum makinesi + olay mimarisi); her ajanın **kalıcı konuşması** vardır (uygulama kapanıp açılsa da sürer); model ve efor **AGENT.md**'den yönetilir ve arayüzden değiştirilebilir (Entropy'nin kendisi için de). Araçlar "tool yığını" değil, **ajanlara yardımcı** az sayıda güçlü araçtır.

**Öncelik.** Önce depo temizliği ve yeni proje yapısı; sonra beynin (RAG/hafıza) revizyonu; sonra görev panosu döngüsü; sonra tasarım. Hafızayı gerekirse sıfırdan kurma yetkisi verildi.

## 1. Bulguların özü

**Beyin (A).** Okuma tarafı sağlam: kör testte Hit@1 8/10, Hit@5 9/10, 316 ms. Asıl açık **yazma tarafı**: düğüm kimliği içeriğin birebir hash'i olduğu için "bunu zaten biliyorum" denetimi yok → hafızanın %55,7'si fazlalık (1544 düğüm, 684 benzersiz konu), %30'u test fikstürü, 29 uydurma "N katmanlı mimari" adı kendi çıktısını okuyan bir araştırma görevinden (öz-amplifikasyon). Çözüm zaten yazılmış ama yanlış yere bağlı (`reconcile_facts` yalnızca graf katmanında; 7 yazma noktasının hiçbiri oradan geçmiyor). Genel sohbette beyin payı %0 (yetenek eşleşmeyince). Rüya döngüsü fiilen ölü. **mem0 kararı:** kütüphaneyi alma (LLM/API zorunlu; graf belleği açık kaynaktan kaldırıldı; 2026'da yalnızca ADD'e döndü), **algoritmayı al** (SAGE üç bantlı yenilik kapısı, Dual-Layer kaskadı, Hindsight eşikleri 0,92/0,95). CoALA katmanları, HippoRAG 2 (PPR) ve Zep/Graphiti (çift zamanlı) bizde zaten var. Karpathy: "bilgi bir kez derlenir, her sorguda yeniden türetilmez" — en zayıf halkamız (wiki bağlamın %0,8'i).

**Depo (B).** Disk 4,7 GB / 18.700 dosya, git nesneleri 24 MB: ayak izinin %99,5'i üretilmiş çıktı (`dist` 1,8 GB, `dist_check` 1,2 GB, `build` 0,8 GB, kök `EntropyAI.exe` 475 MB). Ürün paketlerinde yetim modül yok; tek ölü ürün modülü `platform/autostart.py`. `tools/autonomous_agent_architecture*` ailesi (60 dosya, 75.578 satır, 3 MB) tamamen prototip; 32 test dosyası (332 test) yalnızca onu sınıyor → birlikte silinebilir. `AGENTS.md` var olmayan bir kadro ilan ediyor; `GEMINI.md` dizin haritası eski; `CLAUDE.md` yok (ve ölçülmeden oluşturulmamalı — `--add-dir` kökleri CLAUDE.md dizini sayılıyor). `.claude/agents/` altında senin 6 geliştirme ajanınla Entropy'nin ürettiği 5 ajan karışık. `docs/STATE.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `adr/` yok. Testlerin %23,5'i sevk edilen hiçbir kodu sınamıyor. Paket taşıma (`memory → brain`) ayrı faza (104 dosya, sessiz PyInstaller riski).

**Görev panosu ve ajanlar (C).** Tarif ettiğin tam zincir deponun **yanlış tarafında** kurulu: Desk ofis harness'ında var, Entropy'nin kendi panosunda yok. Entropy hiçbir zaman kendi kararıyla görev üretmiyor; `/task` kartı oluşturup aynı satırda koşturuyor; `TAKEN`/`assigned`/`canceled` durumları yok; geçişler 6 dosyaya dağılmış; diske yazılan olay günlüğü yok; konuşma kimliği görev başına ve bellekte (ajan başına kalıcılık yok); Claude'da efor AGENT.md'den yürütmeye hiç geçmiyor; kapanışta koşan Entropy kartı sonsuza dek `running` kalıyor; kart raporu sohbete dönmüyor. **En değerli bulgu:** `claude --bg` + `claude agents --json` + `claude attach <id>` üçlüsü "uygulama kapansa da aynı oturum sürsün" isteğini CLI'ın kendisi karşılıyor (bu makinede doğrulandı); `--session-id` ile kimlik önceden atanabiliyor (agy'de yok). C# tetikleyiciye gerek yok: sorun dil değil süreç sahipliğiydi. Claude oturum deposu cwd'ye anahtarlı → kart başına worktree ajanın konuşmasını dağıtır (tasarımda dikkate alındı).

**Tasarım (D).** — D notu gelince bu bölüm ve Faz 11-E tamamlanacak.

## 2. Hedef mimari (tek resim)

```
Kullanıcı ─▶ Entropy Chat ─▶ [Beyin v2: MemoryGate ▸ L1 çalışma / L2 anlamsal (graf+wiki) / L3 yordamsal (skill) / kimlik+kurallar]
                 │                    ▲ Obsidian = soğuk depo + insan arayüzü (raporlar, playbook, wiki, kurallar)
                 ▼                    │
        Araştırma (web + aktif skill) ── rapor ── yenilik kapısı (ADD / NOOP / gri bant → gece CLI turu)
                 │
                 ▼
        Entropy/Board: TASKBOARD.md + tasks/<id>.md + events.jsonl + claims/ + agents/<ad>/session.json
        durum makinesi: backlog → assigned → taken → running → review → done | failed | canceled
        BoardDispatcher (QTimer): her ajan için "panoda sana görev var mı?" → atomik claim → terminal süreci (AGENT.md: provider/model/effort)
                 │
                 ▼
        Ajan araçları (4+1): board_next / checkpoint / finish (kanıtla) / ask  ·  Entropy: board_create
        rapor → Entropy/Reports + Board olayı → sohbete "rapor geldi" kartı → beyne yenilik kapısından
```
Desk (ofisler/orkestratörler) aynı ilkeleri zaten uyguluyor; Entropy tarafı bu fazda ona yetişiyor. Kod paketleri bu fazda taşınmıyor; `memory → brain` yeniden adlandırması Faz 12.

## 3. Fazlar (Faz 11 = beş dilim + Faz 12)

| Dilim | Ne | Ajanlar | Kota (model turu) | Etiket |
|---|---|---|---|---|
| **11-A Temizlik ve iskelet** | B §8'deki 13 adım: `.gitignore`; üretilmiş ikili çıktı (4,5 GB) ve kök artıkları (56 `.py`, `financial-auditor/`) silinir; kullanıcı çıktıları `docs/_archive/customer/`; prototip kaynağı (60 dosya) + prototip testleri (32 dosya) silinir; prototip raporları arşive; `docs/{ARCHITECTURE,STATE,ROADMAP}.md` + `adr/` kurulur (alt ajanların belleği); `AGENTS.md`/`GEMINI.md` gerçekle eşitlenir; `.claude/agents` ayrımı (Entropy derlemesi kendi klasörüne); testler `tests/{contracts,ui,skills}` altında gruplanır; kapanış ölçümü | repo-curator, qa | 0 | `v0.9.0` |
| **11-B Beyin v2 çekirdek** | A 11.1 kategori disiplini + şema v2 · 11.2 `MemoryGate` (tek giriş; LLM'siz üç bantlı yenilik kapısı; `reconcile_facts` bağlantısı) · 11.4 test yalıtımı (7 yazma noktası) · **11.5 hafıza göçü: sıfırdan kur + seçici göç** (1544 → ~668 temiz çekirdek; `.bak` + Obsidian güvencesi; Hit@1 düşerse geri al) · 11.6 öz-amplifikasyon kilidi (açık tespiti, %70 yenilik kotası, kaynak zorunluluğu) · 11.10 okuma eklentileri (kapsam süzgeci, PPR genişletme, "beyinde yok" sinyali) · 11.13 ölçüm paketi (K1–K12 testte) | memory-rag, agy, qa | ~60 | `v0.9.1` |
| **11-C Entropy Board ve ajan çalışma zamanı** | C.1 FSM tablosu (8 durum, 12 geçiş; kütüphane yok) + `events.jsonl` + `TASKBOARD.md` projeksiyonu · C.2 `BoardDispatcher` + atomik claim (`O_CREAT|O_EXCL`) + kapanış uzlaştırıcısı · C.3 ajan başına oturum deposu (`agents/<ad>/session.json`, `uuid5` kimlik; istem/model değişince yeni oturum) · C.4 efor uçtan uca (AGENT.md → argv → `--agents` JSON; Entropy'nin kendi model/eforu ayar + `/model` `/effort`; kart panosu efor alanı gerçek) · C.5 4+1 pano aracı + rapor→sohbet kartı · Entropy'nin kendi kararıyla görev üretmesi (sohbette "bunu X ajanına veriyorum" → `board_create`) | agy, ui, memory-rag, qa | ~120 (uçtan uca doğrulama dahil) | `v0.9.2` |
| **11-D Konsolidasyon, wiki, genel beyin** | A 11.3 gri bant kuyruğu + toplu CLI birleştirme turu · 11.7 rüya v2 (0,95 kümeleme, birleştirme, arşivleme, wiki yükseltme) · 11.8 wiki derleme hattı (financial-auditor 50 rapor, media-agency 16; en pahalı kalem, bölünebilir) · 11.9 genel sohbet beyin paketi (ego + kurallar + wiki + PPR recall; K4 ≥ %60) · 11.12 bellek panosu (yineleme, kategori, kuyruk, K1–K12 canlı) | memory-rag, agy, ui, qa | ~90 | `v0.9.3` |
| **11-E Tasarım sistemi ve arayüz sadeleştirme** | D notundan: token tabanlı tasarım sistemi, bilgi mimarisi sadeleştirme, kabuk/üst çubuk, paneller, "ui-design" skill'i | ui, qa | 0 | `v0.9.4` |
| **11-F (isteğe bağlı spike)** | `claude --bg` / `attach` ile gerçek kalıcı terminal (uygulama kapansa da süreç yaşar) — açık uçlu, ayrı kart | agy | ~20 | — |
| **Faz 12** | `memory → brain` paket taşıması; Desk geliştirmesine dönüş (Faz 10 kalanları: canlı kanıt/makbuz doğrulaması, `gh`, efor uçtan uca) | — | — | `v1.0.0` |

Her dilim sonunda: tam paket + build + ölçüm + kısa rapor + sürüm etiketi. Dilim içinde onay istemem; **dilimler arasında** onayını beklerim (bunu değiştirmek istersen söyle: "11-A→11-B→11-C zincirle" dersen zincirlerim).

## 4. Kota planı
Toplam ~290 model turu (A ~180 + C ~110'un örtüşmeyen kısmı); büyük kalemler 11.8 wiki derleme (~40) ve 11-C uçtan uca doğrulama (~60k token). 11-A ve 11-E sıfır kota. Her dilimde tavan yazılır; ledger ile izlenir.

## 5. Onayına sunduğum kararlar (önerim kalın)
1. **Hafıza:** saf silme değil, **sıfırdan kur + seçici göç** (temiz çekirdek ~668 düğüm; 36 benzersiz finans düğümü korunur; test fikstürleri ve uydurma mimariler atılır). Alternatif: tam sıfırlama (raporlardan yeniden damıtma ~40 tur).
2. **Silme manifesti (11-A):** üretilmiş ikili çıktı 4,5 GB + kök artıkları + prototip kaynağı/testleri (2.374 → 2.042 test) **silinsin**; kullanıcı çıktıları ve prototip raporları **arşive**. `google_flow_files/` (102 MB) depo dışına.
3. **Tetikleyici:** C# değil, uygulama içi Python `BoardDispatcher` (QTimer + olay günlüğü); durum makinesi kütüphanesiz 12 satırlık geçiş tablosu.
4. **Kalıcı terminal:** önce ajan başına oturum kimliği (C.3); `claude --bg` spike'ı **ayrı, sonra**.
5. **Kod paketleri:** Faz 11'de taşınmaz; `memory → brain` Faz 12.
6. **Tasarım kütüphanesi:** D notu gelince (qfluentwidgets / kendi token sistemi / qdarktheme).
7. **Sıra:** 11-A → 11-B → 11-C → 11-D → 11-E (tasarımı öne almak istersen 11-E, 11-C'den önce koşabilir; birbirine bağımlı değiller).

## 6. Alt ajanların belleği ve çalışma mantığı (kontrol edildi)
Altı ajanın tanımı güncellendi: güncel kapsamlar, `git stash` yasağı, marka kuralı, efor semantiği, kota kuralı ve ortak "çalışma belleği" (her iş öncesi `docs/STATE.md` + son faz raporu). `docs/STATE.md` 11-A'da doğar ve her dilim sonunda güncellenir; bu, alt ajanların oturumlar arası hafızasıdır. research-scout salt okunur araştırır; repo-curator yalnızca manifestli ve geri alınabilir değişiklik yapar.
