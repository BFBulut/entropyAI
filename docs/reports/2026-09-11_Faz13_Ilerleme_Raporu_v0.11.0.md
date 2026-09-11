# Faz 13 İlerleme Raporu — Kapanış (v0.11.0): kullanıcı deneyimi, `brain` taşıması, Desk'e dönüş

Tarih: 2026-09-11 · Branch `ai/v0.1.7` · Taban `v0.10.0` (Faz 12) · Etiketler `v0.10.1` (13-A) · `v0.10.2` (13-A2) · `v0.10.3` (13-B) · `v0.10.4` (13-C) · `v0.11.0` (13-D) · Build: `dist\EntropyAI\EntropyAI.exe`

Plan: `2026-09-10_Faz13_Plan_ve_Yol_Haritasi.md` (araştırma: `2026-09-10_Faz13_Arastirma_Notu.md`). Dilim raporları: `…_v0.10.1.md`, `…_v0.10.2.md`, `…_v0.10.3.md`, `…_v0.10.4.md`. Yaşayan belgeler: `docs/ARCHITECTURE.md`, `docs/STATE.md` (sıkıştırıldı; eski dilimler `docs/_archive/state/`), `docs/ROADMAP.md`, `docs/adr/ADR-0008` (brain taşıması), `ADR-0009` (`claude_bg` arşivi).

## Sonuç (özet)
- **13-A — kullanıcının dört şikâyeti (gerçek ekran):** düğmeler görünmüyor (boş metin/ikon + kenarlıksız ghost), tıklamada kasma (her tıklamada tüm kartların yeniden kurulması 139 ms + 143 KB senkron JSON), Rapor Merkezi/okuyucu/Görevler sıkışık (kart 675 px vs panel 240 px; Görevler beyanı 220 px vs gerçek 1.356 px), rapor başlığı kullanıcının kendi mesajı (istem satırı + sohbet turlarını rapora çeviren sezgi), Zen çekirdeği 24 px noktaya inmiş. Sonuç: tıklama **5–8 ms**, okuma kipi (okuyucu ≥ 560 px), beyan = hesaplanan + liste yedeği, başlık gövdedeki H1'den (tek kaynak `core/report_title.py`), **sohbet turu ≠ rapor** (`Entropy/Sessions/`), çekirdek 136 px animasyonlu ve "korunan kimlik öğesi"; `ui-design` 1.2.0'a dört kapı (boş etkileşimli öğe, ghost kontrast, tıklama ≤ 50 ms, okuyucu asgarisi/beyan doğruluğu). Onaylı canlı koşular: wiki 2 tur (K6 %29 → %36), gri tur (kuyruk 0), beceri sentezi → kasaya yükseltildi, 4. kartta oturum devri; gerçek regresyon (claude yolunda kotalı hafıza turları hiç koşamıyordu) düzeltildi.
- **13-A2 — v0.10.1 geri bildirimi (yedi bulgu):** "Etkin" donması 1.961 → 2,4 ms; ikon-only düğmeler (setIcon hiç çağrılmamış; kapı 7 ekranı tarayıp piksel ölçüyor); rapor kartı eylemleri ayrı satır; ajan canlı durumu (`AgentSessionStore.status`, "çalışıyor · süre", "Ajanlar ●1"); çekirdek yalnız Entropy'nin turu; üst çubuk kırpılması; Görevler kalabalığı (9 QA kartı arşivlendi, arka plan görevleri katlı); **~20 hayalet pencere** (`setParent(None)` → üst düzey pencere; 12 çağrı, kapı `orphan_reparents = 0`) + gizli alt süreçler; **beyin kısa devresi varsayılan kapalı** (yalnız `--brain-only`, ≥ 0,75, kaynaklı, kimlik/legacy asla; tazelik ipucunda hiç). Canlı kartta 300 sn / 6.839 örnekte yeni pencere 0.
- **13-B — `entropy.memory` → `entropy.brain`:** 27 dosya `git mv`, 166 dosyada atıf, bir sürüm ömürlü şim (aynı modül nesnesi, `DeprecationWarning`, v0.12.0'da silinir), ADR-0008; test toplamı korundu (2.605), pakette 27/27 modül, canlı exe gerçek `brain` yolunu yükledi; veri göçü gerekmedi.
- **13-C — Desk'e dönüş:** ofis kartı araç bloğu sızıntısı kapandı (alanlar ayrıştırılıyor, harness alanları okuyor); tek yazıcı kontrol noktası; **onaylı `[DESK office_create | agent_edit | task | msg]` araçları** (bekleyen kuyruk + `/desk approve|reject` + Ajanlar sekmesinde onay paneli; `msg` onaysız; ofis istemlerinde `[DESK` yok); **silme = arşiv + olay** (`archive_card`, `/task rm`, FSM T13/`board.archived`; UI'da "Arşivle"); ofis eforu argv'de; `board.stop` süreç ağacı; kırpık eski başlıklar → H1 (28/28); olay veriyolu yıkım hatası; Desk tasarım kapıları (7 ekran, 0 ihlal); `claude_bg` arşivde (ADR-0009); STATE.md 1.685 → 1.032 satır. **Canlı Desk kanıt zinciri** (izole kasa, gerçek Claude): ofis → orkestratör otomatik; görev 2 alt karta bölündü, **orkestratör kod yazmadı**; iki işçi paralel; kontrol noktası + yeşil kanıt; 8 bölümlü makbuz; `--effort` argv'de. Kapanışta iki gerçek kusur (ofis adı ilk sözcükten alınıyordu; ofis kartları kalıcı sahte ayrışma sayılıyordu) düzeltildi.
- **Kapanış QA (13-D, kota 0):** tam süit **2.648 test, 0 hata**; build exit 0 (207 s), `--version` → `Entropy AI 0.11.0`, 2×20 sn canlı, günlükte `Traceback`/`CRITICAL`/`ModuleNotFoundError` 0; pakette 27/27 `brain` modülü, `desk_admin`, `lifecycle`/`agent_run_state`/`desk_approvals_panel`, `platform.proc`, `entropy.memory` şimi; `claude_bg` yok. Gerçek ekran: kart önizlemesi "…" ile bitiyor (48 px ≤ 51), Desk onayları boş durumu, Zen çekirdeği 136×136 görünür. Kapanışta bulunan kusur: hafıza denetçisinin silme yolu var olmayan iki modül adına düşüp hiç bellek katmanından geçmiyor, sessizce ham SQL'e inip graf kenarlarını diskte bırakıyordu → birincil yol `CognitiveMemorySystem.delete_memory`, aday listesi gerçek adlarla, 4 test. Yalıtım: üç durum dosyası ve kasa sayıları değişmedi; marka 0/0.

## Ölçüm tablosu
| Ölçüt | Faz 12 sonu | Faz 13 sonu |
|---|---:|---:|
| Test | 2.456 | 2.644 (+ 13-D) |
| Okundu tıklaması (sessiz bölüm açık) | 139 ms | 5–9 ms |
| Yetenek "Etkin" tıklaması | 1.961 ms | 2,4 ms |
| Boş/adsız etkileşimli öğe (7 ekran) | 8+ (ölçülmüyordu) | 0 |
| Hayalet üst düzey pencere (kart koşusu) | ~20 | 0 |
| Sohbet açılışlı görünen rapor başlığı (gerçek kasa) | 4 | 0 |
| Kırpık frontmatter başlığı | 28 | 0 |
| K6 wiki payı | %29 | %36 |
| Gri kuyruk | 2 | 0 |
| STATE.md satır | 1.685 | 1.032 |
| Paket adı | `entropy.memory` | `entropy.brain` (+ şim) |

## Kota (gerçek Claude)
| Kalem | Onay | Harcanan |
|---|---:|---:|
| 13-A onaylı canlı koşular | 70k | 75,3k |
| 13-A2 hayalet pencere kartı | 20k | (öksüz satır, ölçülemedi) |
| 13-C Desk kanıt zinciri | 60k | **133,5k** (ledger önbellek okumalarını da sayıyor; çıktı 8,4k) |
| Wiki ikinci parti | 30k | **koşulmadı** |
Ders: tahminler ledger ölçüsüyle yapılmalı; harness'ın 60k kapısı doğru çalıştı (üst kartı `failed` yaptı), ama tek turun ölçüsü tavanı geçebiliyor → 13-C+ için tur başına ön tahmin (istem boyutu × önbellek) gerekli.

## Kalanlar / öneriler (Faz 14 adayları)
- F-13D-1: her açılışta `entropy_fault.log`'a düşen COM `0x8001010d` bloğu (uygulama ölmüyor; 13 öncesinden beri var; kök neden bulunamadı).
- LangGraph araştırması (`2026-09-11_Arastirma_LangChain_LangGraph_LangSmith.md`): çalışma zamanı olarak alınmaz; dört desen (yeniden-oynatma güvenliği, interrupt semantiği, kota sınırlı fan-out, trace şeması) Faz 14 adayı — kullanıcı kararı bekliyor (ADR-0010).
- Wiki ikinci parti (~30k, onay bekliyor); K2 Hit@1 8/10 izlemesi.
- Canlı ölçülmeyenler: kanıtsız `board_finish` → `review`, `/desk review` diff + `gh` yokluğu, `agent_stream`'in uygulama içinde sprite/terminal sekmesine ulaşması, `[DESK]` uçtan uca gerçek Entropy sohbetiyle.
- Kullanıcı verisi: iki canivopets kartı kullanıcı kararıyla silinmiş kaldı (artık silme = arşiv + olay).
- Şim `entropy.memory` v0.12.0'da kaldırılacak; `_oneshot` betikleri yeni adla.
- Çökme dayanıklılığı: Claude Code süreci bu fazda iki kez çöktü; alt ajan işleri ağaçta korunuyor, devralma ritüeli (`git diff` ile bitti/yarım/başlanmadı tablosu, sonra tamamlama) `docs/STATE.md`'ye kapanışta eklendi.
