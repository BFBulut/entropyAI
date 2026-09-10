# Faz 13 Planı — Kullanıcı deneyimi, `brain` taşıması, Desk'e dönüş

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Taban `v0.10.0` (Faz 12) · Orkestratör: Claude Fable 5.1 · Uygulayıcılar: 6 alt ajan (Opus 5, low)

Dayanak: `2026-09-10_Faz13_Arastirma_Notu.md` (salt okunur, kanıtlı; kota 0). Kullanıcının v0.10.0 geri bildirimi (gerçek ekran, 4 görsel): rapor başlığı garip, Rapor Merkezi/okuyucu/Görevler sıkışık, düğmeler görünmüyor ve tıklamada kasma var, Zen'de çekirdek görseli yok; kararlar: canlı kota onaylandı (1), Faz 13 araştırma+plan istendi (2), küçük açık kalemler Faz 13'e (3).

## 0. Araştırmanın özü (kök nedenler, ölçülmüş)
- **Düğmeler görünmüyor:** digest kartındaki iki eylem düğmesi boş metinle kuruluyor (`report_center.py:802-807`) ve `ghost` varyantı kenarlıksız + sönük metin → görünmez dikdörtgen. 12-F'nin kapıları boş etkileşimli öğeyi ölçmüyordu (kapı boşluğu).
- **Kasma:** her okundu/pin tıklaması bütün kart widget'larını yok edip yeniden kuruyor (`report_center.py:1146-1160`): sessiz bölüm açıkken **139 ms** (bütçe 50 ms, 2,8× aşım) + tıklama başına 143 KB senkron JSON yazımı.
- **Sıkışıklık:** kart 675 px istiyor, panel 240 px'e sıkıştırılabiliyor; okuyucu 380 px ≈ 50 karakter/satır (okunabilirlik alt sınırı). Görevler kanbanı gerçekte 1.356 px istiyor, beyanı 220 px (6× sapma).
- **Rapor başlığı:** kullanıcının kendi mesajının ilk 40 karakteri başlık oluyor (`agy_bridge.py:2383`); daha derini, 8 anahtar kelimeli sezgi serbest sohbet turlarını rapora çeviriyor (`:2360-2368`) — bu yüzden 674 "rapor" var.
- **Çekirdek:** modül sağlam; 11-E onu 24 px durum noktasına indirmişti. Kalıcı ilke: çekirdek kimlik + durum göstergesidir, sadeleştirme turları onu kaldıramaz.
- **`memory → brain`:** ADR-0004'ün beş gerçek ön koşulu yeşil; yalnız sayısal "≤ 100 dosya" hedefi 113 ile aşılıyor → uyumluluk shim'iyle, tek başına koşan bir dilimde **yapılsın**.
- **Desk kalanları:** ofis kartı araç bloğu sızıntısı tek satır (`tasks.py:1693`, harness `summary`den ayrıştırıyor); `/desk` yüzeyi geniş, eksik olan Entropy'nin kendi kararıyla Desk'i düzenleyeceği onaylı `[DESK …]` araçları; Desk kanıt zinciri hiç canlı koşulmadı; `claude_bg` ADR-0007 koşuluyla arşive.

## 1. Dilimler
| Dilim | İş | Ajan | Kota | Etiket | Durum |
|---|---|---|---|---|---|
| **13-A UX ve çekirdek** | A1 boş düğmeler (metin/ikon + erişilebilir ad) · A2 `refresh()` fark uygular (okundu tıklaması ≤ 50 ms, 158 kartta) · A3 `set_many` yazımı tıklama yolundan çıkar (debounce + kapanış kancası, veri kaybı testi) · A4 Rapor Merkezi bilgi mimarisi: aynı anda en çok iki bölge, okuyucu ≥ 560 px, kart ≥ 520 px · A5 Görevler: `failed/canceled` varsayılan katlı, < 1.020 px'te liste+detay, beyan = hesaplanan · A6 `derive_report_title` (H1 → ilk cümle → dosya adı; istem satırı asla) · A7 **sohbet turu ≠ rapor** (8 kelime sezgisi kalkar; serbest sohbet çıktısı `Entropy/Sessions/` altına `type: session`; eski dosyalar taşınmaz, görüntü katmanı yeniden başlıklar) · A8 Zen çekirdeği geri (kompakt animasyonlu, ≥ 48 px, `prefs` anahtarı, sözleşme testi) · A9 `ui-design` 1.2.0: G13-1 boş etkileşimli öğe = 0, G13-2 düğme kontrastı (ghost dâhil), G13-3 tıklama ≤ 50 ms, G13-4 okuyucu asgarisi + beyan doğruluğu | ui-engineer (A1–A5, A8, A9), agy-integration-engineer (A6–A7 yazma tarafı) | 0 | `v0.10.1` | **koşuyor** (kullanıcının açık isteği) |
| **Onaylı canlı koşular** | wiki derlemesi financial-auditor 2×25 tur, gri birleştirme turu, 4. kartta oturum devri, `/skill synth` + onay; K4/K5/K6/K9 önce/sonra | qa-build-engineer | ≤ 70k | — | **koşuyor** (karar 1) |
| **13-B `brain` taşıması** | B1 `git mv memory → brain` + 181 satır + 3 dizgi · B2 uyumluluk shim'i (`entropy.memory.*` → `entropy.brain.*`, `DeprecationWarning`, bir sürüm) · B3 spec + canlı belgeler + ADR-0008 (31 tarihsel rapor dokunulmaz) · B4 doğrulama zinciri: import → tam süit (sayı değişmez) → build → `--version` → 20 sn canlı → `_internal/entropy/brain/` pakette | memory-rag-engineer, qa-build-engineer | 0 | `v0.10.2` | **onay bekliyor** |
| **13-C Desk kanıt zinciri ve temizlik** | C1 ofis kartı `summary` koşulsuz temizlenir, harness `card.checkpoint/proof` okur · C2 Entropy kontrol noktası tek yazıcı, `task_board_widget.py:110` kartın mutlak yolunu okur · C3 Entropy'ye onaylı `[DESK office_create/agent_edit/task]` araçları (yalnız claude sohbet yolu) · C4 tek yön sözleşme testleri (orkestratör isteminde Entropy yok; Desk → Entropy panosuna yazamaz) · C5 **canlı Desk kanıt zinciri** (ofis + orkestratör + 2 işçi; orkestratör kod yazmaz; kanıtsız bitiş reddedilir; makbuz + diff; `gh` yoksa atlanır) · C6 ofis eforu argv kanıtı · C7 `claude_bg` arşive, Desk tasarım kalanları | agy-integration-engineer, qa-build-engineer, repo-curator | ~60k | `v0.10.3` | **onay bekliyor** |
| **13-D Kapanış** | tam süit, spec eşleme, build, `ui_audit --gate --final` (G13-3 canlı ölçülür), gerçek ekran (LG %200: 4/4 şikâyet görsel kanıtla kapanır), yalıtım kanıtı, marka taraması, `STATE.md`/`ROADMAP.md`, Faz 13 raporu | qa-build-engineer, orkestratör | 0 | `v0.11.0` | 13-A/B/C sonrası |

Sıra: 13-A (ve canlı koşular) → **13-B tek başına** (koşarken hiçbir ajan `src/entropy/memory`, `EntropyAI.spec`, `tests/` altına yazmaz) → 13-C → 13-D. 13-A ile 13-C kapsamları ayrık (`ui/` vs `agents/`+`desk/`), gerekirse paralel.

## 2. Kota planı
| Kalem | Tavan | Onay |
|---|---:|---|
| Onaylı canlı koşular (wiki, gri tur, devir, sentez) | 70k | verildi |
| Desk kanıt zinciri (C5) | 60k | bekliyor |
| 13-A, 13-B, 13-D | 0 | — |
Kural: ledger'da sohbet + görev toplamı dilim tavanını geçince canlı koşu durur, kalan adımlar rapora yazılır (12-F'de görülen aşım artık `record_chat_turn` ile erken görülür).

## 3. Kabul ölçütleri (özet)
G13-1 boş etkileşimli öğe 0 · okundu tıklaması ≤ 50 ms (158 kartta) · tıklamada JSON yazımı yok · okuyucu ≥ 560 px · Görevler beyan ≥ hesaplanan, 1.020 px'te 5 sütun taşmasız · "Tamamdır, şimdi senden…" başlık olarak üretilmez · serbest sohbet turu rapor sayılmaz · çekirdek Zen'de görünür ve ≥ 48 px · `ui_audit` yeni kapılar bilerek bozulmuş düğmeyle kırmızıya döner · taşıma sonrası test sayısı değişmez, `entropy.memory.gate is entropy.brain.gate`, build'de `brain` klasörü · ofis kartı `summary`sinde `[PANO` 0 · orkestratör kod yazmaz, kanıtsız `board_finish` reddedilir · tam süit 0 hata, marka taraması 0.

## 4. Riskler
- A2 kart imzası eşlemesi (küme sırası değişince) → imza testi zorunlu. A3 çökmede son tıklama kaybı → kapanış kancası + testi.
- A7 Rapor Merkezi sayacı düşer (beklenen; veri silinmez, sohbet turları `Sessions/` süzgeciyle görünür).
- 13-B PyInstaller sessiz eksik paketleme → kalıcı spec testi + paket klasörü kontrolü + 20 sn canlı koşum; paralel ajan çakışması → dilim tek başına.
- C5 kota → 100k'da durdur. C3 kalıcı yapı değişikliği → yalnız kullanıcı onayıyla uygulanır (kural onay paneli deseni).

## 5. Kararlar (araştırma K1–K10 → plan)
K1–K5 ve K7 13-A/13-C'ye alındı; K6 (taşıma yapılsın) 13-B olarak onaya sunuldu; K8 (`claude_bg` arşive) 13-C'de; K9 (`[DESK …]` araçları, onaylı) 13-C'de; K10 tavan 120k → iki ayrı tavan (70k verildi + 60k onay bekliyor).

## 6. Güncelleme (2026-09-10, v0.10.1 sonrası kullanıcı geri bildirimi ve onaylar)
Kullanıcı üç kararı da onayladı: **13-B yapılacak**, **13-C ve ~60k Desk kanıt zinciri onaylı**, **wiki ikinci parti (~30k) onaylı**. v0.10.1'i gerçek ekranda denedikten sonra yedi yeni bulgu bildirdi; bunlar 13-B'den önce **13-A2** dilimi olarak kapatılır (etiket `v0.10.2`), çünkü 13-B tek başına koşar ve başka iş beklemez:

| # | Bulgu (kullanıcı) | Ajan |
|---|---|---|
| 1 | Yetenekler'de "Etkin" kutusu donma yaratıyor ("EntropyAI.exe is not responding") | ui-engineer |
| 2 | Bazı düğmeler hâlâ görünmüyor (yetenek satırlarında ikon-only boş kareler) → G13-1 bütün ekranları tarar, boş ikon nesnesi kapıdan geçmez | ui-engineer |
| 3 | Sohbet rapor kartında "Raporu açSohbete al" bitişik | ui-engineer |
| 4 | Ajanlar sekmesinde araştırmacının çalıştığı görünmüyor ("2 sa önce" derken kart çalışıyor); çekirdek Entropy yerine ajanın işini yansıtıyor | ui-engineer (görünüm) + agy-integration-engineer (`AgentSessionStore.status()` sözleşmesi) |
| 5 | Görevler ekranı kalabalık; QA canlı koşularının artık kartları duruyor | ui-engineer (düzen) + agy-integration-engineer (QA kartlarını arşivle, kullanıcı kartlarına dokunma) |
| 6 | Bir görev koşarken ~20 pencere açılıp kapanıyor | ui-engineer (ebeveynsiz Qt pencereleri) + agy-integration-engineer (alt süreç `CREATE_NO_WINDOW`) |
| 7 | "Araştır" deyince her şey beyinden çekildi ("Beyinden yanıtlandı … CLI turu açılmadı", yanıt kimlik düğümü) → otomatik kısa devre varsayılan kapalı, beyin yalnız `[BEYİN]` bağlamı, kimlik/legacy düğümleri asla yanıt değil, `brain_only` açık tercih | memory-rag-engineer |
| + | Üst çubuk durum kümesi kırpılıyor; "Oturumu yenile" sohbete otonom görev kartı düşürüyor | ui-engineer · agy-integration-engineer |

Sıra: 13-A2 (`v0.10.2`) → 13-B tek başına (`v0.10.3`) → 13-C + wiki ikinci parti + Desk kanıt zinciri (`v0.10.4`) → 13-D (`v0.11.0`).
