# Faz 10 İlerleme Raporu — v0.8.0

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Etiket `v0.8.0` · Build: `dist\EntropyAI\EntropyAI.exe` (doğrudan dist, `--help` 0, canlı koşum temiz)

Dayanaklar: `2026-09-11_Faz10_Arastirma_Notu.md`, `2026-09-11_Faz10_Teshis_ve_Mimari_Bosluk_Notu.md`, `2026-09-10_Faz10_Ara_Rapor_v0.7.1.md`.

## Sonuç
Tam paket **2371+ test geçti, 0 hata** (v0.7.1: 2283). Kota: hotfix doğrulaması 2 kısa agy turu + uçtan uca ofis koşusu 76,6k token (Claude).

## Senin Desk çekirdek mantığın — ne kadarı oturdu
| Tarifin | Durum | Nasıl |
|---|---|---|
| Ajanlar dosyalarla konuşur; doğunca önce BOARD ve ARCHITECTURE'ı okur | ✅ canlı doğrulandı | `Desk/Offices/<ofis>/workspace/{BOARD.md, ARCHITECTURE.md, RULES.md}`; her ajan istemi `[DOĞUŞ TALİMATI — önce oku]` ile başlıyor, yollarda "Entropy" yok |
| Kontrol noktası disiplini; çökünce özetten sür | ✅ testlerle (gerçek köprü + sahte süreç) | `[KONTROL NOKTASI]` → `workspace/checkpoints/<kart>.md`; yeniden koşuda `[KALDIĞIN YER]` |
| Kural keşfi → kullanıcı onayı → sistem istemine | ✅ testlerle | `[KURAL]` adayları → Desk Bellek sekmesi ve Zen'de "Kalıcı yap / Reddet"; onaylılar istemde |
| Gizli terminaller, köprü, sprite durumları, tıkla → terminal | ✅ canlı: ajan etiketli akış (19 olay, 3 ajan); bölme ve balonlar testlerle | `agent_stream`; Desk "Terminaller" sekmesi; düşünüyor balon / çalışıyor tuşlama / boşta volta / hata |
| Terminale mesaj yazma (koşan ajana) | ✅ testlerle | etkileşimli kart kipi: ilk sonuçtan sonra süreç bekler, mesaj yeni tur açar, 10 dk boşta kapanır |
| Lider kod yazmaz, panoya böler; işçiler paralel, kendi alanında | ✅ canlı: plan 2 alt kart, iki paralel worktree (`desk/<kart>` dalları) | kart başına git worktree, proje = depo + dal |
| Kanıtla kapatma (testsiz "bitti" yok) | ✅ testlerle | `[KANIT]` yeşil değilse `done` olmaz, `review` + "kanıt eksik" |
| Makbuz, diff, PR | ✅ testlerle | ofis raporu = makbuz (8 bölüm), Desk "Değişiklikler" ve "Makbuz" sekmeleri, onaylı push, `gh` yoksa dal + diff |
| Ekip şablonları | ✅ canlı | 4 şablon (araştırma, refaktör, QA, medya); canlı koşuda `refaktor` şablonundan 5 ajanlı ofis doğdu |

## Uçtan uca canlı koşu (dilim E)
Geçici ofis `dogrulama-10` (refaktör şablonu), küçük bir git deposu bağlı proje, kart "Selamlama fonksiyonu". Doğrulanan: ofis doğuşu (orkestratör Entropy'yi bilmiyor, klasörde 0 "entropy"), proje bağlama, orkestratör planı (kod yok, 2 alt kart), doğuş talimatı, iki alt kartın kendi worktree'lerinde gerçek `hello.py` yazması, ajan etiketli akış. **Ölçülemeyen:** kanıt/kontrol noktası/kural/makbuz/etkileşimli takip/ingest aşamaları — koşu 70k token tavanına takıldı (plan 38k + iki alt kartın ilk çağrıları). Bu aşamalar gerçek köprü + sahte süreç testleriyle doğrulandı. Geçici ofis arşivlendi, worktree'ler temizlendi, senin ofisine dokunulmadı.

Canlı koşunun bulduğu ve düzeltilen kusurlar: gerçek ofis arşivlenemiyordu (hayalet koruması künyeli her ofisi atlıyordu); şablon sözleşmesi içe aktarma sırasına bağlıydı; skill durumu testlerden sızıyordu; **orkestratör CLI düzeyinde yazma araçlarına sahipti** (istemle yasaklıydı ama `Bash` çağırdı) → plan/değerlendirme çağrıları artık `--tools Read,Glob,Grep,WebFetch,WebSearch` ile sınırlı; şablon ofislerin modeli boş kalıyordu → kota dostu varsayılan (`claude-sonnet-5` / `gemini-3.8-flash-high`), plan istemi bölüm bütçeleriyle kısaltıldı.

## Bildirdiklerin (hotfix, v0.7.1'de)
agy efor = model varyantı (`--effort` yok), efor kutusu sağlayıcı/modele göre, Claude `low` geçiyor, 175k açıklaması, proje kökü exe klasörü değil, `AGENTS.md` paketten çıktı, "Supabase" = bilişsel bellek modülü (çift depo sapması ve sessiz hatalar giderildi), marka adları hiçbir dosyada yok.

## Güvenlik notu
Arka plan kartları Faz 1'den beri Claude Code'u `--dangerously-skip-permissions` ile koşturur (başsız koşuda izin istemi mümkün değil). Faz 10'da bunun sınırı daraldı: orkestratör/değerlendirici çağrıları yalnızca salt okunur araç listesiyle (`Read, Glob, Grep, WebFetch, WebSearch`) koşar; işçi kartları yazma araçlarını yalnızca kendi worktree'lerinde kullanır; agy'de CLI düzeyinde araç kısıtı olmadığı için orkestratör yasağı çıktı denetimiyle (kod üreten plan reddedilir) sürer.

## Kalanlar / kararın
- Kanıt-makbuz-etkileşimli akışın canlı doğrulaması için ~40–60k tokenlik ikinci bir ofis koşusu (istersen).
- `gh` kurulu değil; taslak PR yolu yalnızca taklitle doğrulandı.
- Ofis eforu kartlara uçtan uca geçmiyor (ajan tanımı üzerinden geçiyor).
- Depo kökündeki 41 test artığı (`module_task_*`, `schema_task_*`) için silme onayı.
- Faz 11 (öğrenen Entropy: MCP/skill kayıt defteri keşfi, kendi skill'ini yazma döngüsü, onaylanabilir bellek kuralları Entropy tarafı, ajanlarıyla çok taraflı tartışma) için araştırma notu + onayın.
