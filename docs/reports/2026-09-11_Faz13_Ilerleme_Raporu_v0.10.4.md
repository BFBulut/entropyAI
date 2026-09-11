# Faz 13 İlerleme Raporu — 13-C (v0.10.4): Desk'e dönüş, onaylı Desk araçları, canlı kanıt zinciri

Tarih: 2026-09-11 · Branch `ai/v0.1.7` · Taban `v0.10.3` · Etiket `v0.10.4` · Build: `dist\EntropyAI\EntropyAI.exe`

Dayanak: araştırma notu §3–§5, plan §1/§6 (kullanıcı onayı: 13-C + ~60k Desk zinciri + ~30k wiki ikinci parti). Bu dilim sırasında Claude Code süreci iki kez çöktü; ajanların yarım işi ağaçta korundu ve kaldıkları yerden devralındı (commit/etiket kaybı yok).

## Yapılan (üç kol)
**Köprü/pano (agy-integration-engineer)**
- **C1** Ofis kartlarında araç bloğu sızıntısı kapandı: `summary` artık ofis kartında da koşulsuz temizleniyor; `[PANO board_checkpoint/board_finish]`, `[KANIT]`, `[KURAL]` blokları `card.checkpoint` / `card.proof` / kural adaylarına ayrıştırılıyor ve harness bu alanları okuyor (fikstür harness testi: `summary`de `[PANO` 0, `checkpoint` dolu, `proof.green` doğru).
- **C2** Entropy kontrol noktası tek yazıcıya indi; Görevler kart detayı kartın mutlak `checkpoint` yolunu okuyor (Desk kökü kuralı testi korunuyor).
- **C3** Entropy → Desk düzenleme araçları: `[DESK office_create | agent_edit | task | msg]` blokları (`[PANO]` ile aynı taşıma; gösterilen metinden silinir; yalnız claude sohbet yolu). Yapısal olanlar **kullanıcı onayı** ister: `Entropy/Desk/_pending/<id>.json` + sohbet satırı → `/desk approve <id>` ya da panel; `/desk reject <id>`. `msg` onaysız. API: `agents/desk_admin.list_pending / apply_pending / reject_pending`. Sistem istemi `[DESK]` bölümü +597 karakter (≈149 jeton); ofis/orkestratör isteminde `[DESK` yok (tek yön makinede doğrulandı).
- **C4** Silme = arşiv + olay: `tasks.archive_card(card_id, reason)` (dosya `Entropy/_archive/<tarih>/cards/`, FSM T13 `canceled` gerekçeyle; `done` kartlar `board.archived` bilgi olayıyla terminalde kalır), `/task rm <id> :: <gerekçe>` (gerekçesiz hiçbir şeye dokunmaz); doğrudan dosya silme yolu kalmadı. `board_fsm.EVENTS` 13 → 14, `INFO_EVENTS = (board.drift, board.archived)`.
- **C6** Ofis kartı `effort` → işçi argv (claude `--effort`, agy model son eki), iki sağlayıcı için `Popen` stub testi.
- `board.stop` alt süreç ağacını gizli `taskkill /T` ile kapatıyor, ledger satırını `canceled` yapıyor.
- Hedefli koşum: `tests/contracts` + `tests/desk` + ajan/rapor/amplifikasyon/slash testleri **875 passed / 0**.

**Arayüz (ui-engineer)**
- Desk onayları paneli (Ajanlar sekmesi, kural/beceri adaylarıyla aynı yüzey; Onayla/Reddet; roster yenileme; sohbet satırından bağlantı).
- Görevler "Sil" → "Arşivle" (onay diyaloğu, `archive_card` sözleşmesi; sözleşme yoksa pasif); hafıza denetçisinde de `unlink` kalktı (`archive_report_file`).
- Dar pencerede detay paneli önce asgarisine iniyor, pano taşmıyor; kart önizlemesi "…" ile bitiyor.
- Eski kırpık frontmatter başlıkları (≥ 38 karakter, H1 onunla başlıyor / sözcük ortasında bitiyor) H1'in ilk tam yan tümcesine çözülüyor: gerçek kasada **28/28** (salt okunur sayım).
- `ui_audit` kapanışındaki `EntropyEventBus already deleted` yıkım sırası hatası kapandı (`shiboken6.isValid` koruması).
- Desk tasarım denetimi: `ui_audit` Desk penceresinin 7 ekranını tarıyor — boş etkileşimli 0, adsız ikon 0, ghost/düğme kontrastı 0, hex 0, yerel stil 0; asgari beyan 760 ≥ hesaplanan 701.
- `tests/ui` + `tests/desk` **677 passed / 0**.

**Depo bakımı (repo-curator)**
- `claude_bg` arşivlendi (ADR-0009; ADR-0007 sonuçlandı): modül `docs/_archive/spikes/claude_bg/`, 32 test `tests/_reference/` (toplama dışı), spec girdisi kaldırıldı; kaynakta atıf 0.
- `docs/STATE.md` 1.685 → 1.032 satır: eski dilim ayrıntıları `docs/_archive/state/STATE_2026-09-10_faz11-13A.md`'de, sözleşmeler (§3) yerinde.
- `ARCHITECTURE.md` 13-A/13-A2/13-B sözleşmeleriyle eşitlendi; `ROADMAP.md` değişmezlerine "silme = arşiv + olay" ve "araştırma kartları beyinden kısa devre yapmaz" eklendi.

## Kapanış QA (v0.10.4)
- **Tek yön sözleşmesi (C4):** 15 yeni test (orkestratör/işçi istemlerinde Entropy kimliği ve `[DESK` yok; Desk hiçbir yoldan Entropy panosuna kart yazamaz) — mimari ve spec kapılarıyla 33 passed.
- **Tam süit 2.644 test, 0 hata** (520 s); `ui_audit --gate --final` exit 0, traceback yok, Desk kapıları 7 ekran / 0 ihlal, tıklama 9 ms.
- **Canlı Desk kanıt zinciri (izole kasa, gerçek Claude):** `/desk office add` → orkestratör otomatik doğdu, `BOARD/ARCHITECTURE/RULES` yazıldı, 2 işçi; orkestratör görevi **2 alt karta böldü ve kod yazmadı**; iki kartta da kontrol noktası + `proof_green: true`; paralel koştu (ledger ve zaman damgaları); makbuz 8 bölüm; `--effort low` argv'de; ofis kartı özetinde `[PANO`/`[DESK` yok (C1 canlı). Kanıt: `scratch/desk_chain_13c/`.
- **Kapanışta bulunan iki gerçek kusur (düzeltildi + 5 test):** `/desk office add QA Ofisi 13C :: …` diskte "QA" ofisi açıyordu (ad ilk sözcükten alınıyordu; onay panelinin "Onayla"sı bu yüzden ofisi bulamıyordu) → `_desk_office_name()`; pano ayrışması yalnız Entropy köküyle hesaplandığı için **her ofis kartı kalıcı "dosya yok" ayrışması** sayılıyordu (dakikada bir sahte uyarı) → `office=ALL_CARDS`. Bu ikincisi, kullanıcının iki canivopets kartındaki ayrışmanın en olası açıklaması.
- **Build** exit 0 (372 s), `--version` → `Entropy AI 0.10.4`, pakette `desk_admin` ve `desk_approvals_panel` var, `claude_bg` yok; 20 sn canlı, günlükte `Traceback`/`CRITICAL`/`ModuleNotFoundError` 0.
- **Gerçek ekran (%100 ölçek):** onay paneli — bekleyen öğe → Onayla → ofis + orkestratör doğdu; bölücü 442 px'te pano taşması 0; Desk penceresi 1100×700'de çerçeveyle 1100×731 sığıyor; "Arşivle" onay diyaloğuyla kartı `_archive/` altına taşıdı.
- **Yalıtım:** kullanıcının ofisi, `Entropy/Tasks` (1) ve `Entropy/Reports` (423) değişmedi; `skills_state.json` aynı; marka 0/0.
- **Kota — tavan aşıldı:** Desk zinciri ledger'da **133,5k token** (plan 30,8k + iki alt kart 51,9k / 50,8k; çıktı jetonu yalnız 8,4k, kalan önbellek okuması) — tavan 100k tek turda aşıldı, canlı çağrılar durduruldu; harness'ın kendi 60k kapısı üst kartı `failed` yaptı (alt kartlar kanıtlarını yazmıştı). **Wiki ikinci parti bu yüzden koşulmadı** (yeni onay gerektirir). Ders: ledger önbellek okumalarını da sayıyor; kota tahminleri çıktı+giriş yerine ledger ölçüsüyle yapılmalı (harness bütçe kapısı zaten bunu yapıyor).

## Kalanlar
- Wiki ikinci parti (~30k; kota onayı bekliyor) — K6 %36'da sabit, `WIKI.state.json processed` 2.
- Canlı ölçülmeyenler: kanıtsız `board_finish` → `review` (fikstürle kapalı), `/desk review` yerel dal + diff ve `gh` yokluğu, `agent_stream` sinyalinin ayrı süreçten dinlenmesi (uygulama içinde aynı süreç).
- R-13A2-1 (iki canivopets kartı) kullanıcı kararıyla silinmiş kalıyor; R-13C-2 en olası neden.
- 13-D kapanış (`v0.11.0`): tam süit + build + gerçek ekran + yalıtım + marka + Faz 13 nihai raporu; `memory_inspector_dialog` yedek aday adı temizliği; wiki kalan raporlar (kota).
