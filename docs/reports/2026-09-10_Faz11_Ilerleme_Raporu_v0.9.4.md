# Faz 11 İlerleme Raporu — v0.9.4 (Entropy AI'nın beyni)

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Etiketler `v0.9.0` (11-A) · `v0.9.1` (11-B/D) · `v0.9.2` (11-C) · `v0.9.3` (kapanış) · `v0.9.4` (11-E) · Build: `dist\EntropyAI\EntropyAI.exe`

Plan: `2026-09-10_Faz11_Plan_ve_Yol_Haritasi.md` (onayladığın plan; A→E zincirlendi). Yaşayan belgeler: `docs/ARCHITECTURE.md`, `docs/STATE.md` (alt ajanların belleği), `docs/ROADMAP.md`, `docs/adr/`.

## Sonuç (özet)
- **Depo:** 4.685 MB / 18.700 dosya → 69 MB / 1.657 dosya; prototip kaynağı (60 dosya, 75.578 satır) ve 332 testi silindi; kök artıkları (56 `.py`), üretilmiş ikili çıktı, kullanıcı çıktıları arşive; `AGENTS.md`/`GEMINI.md` gerçekle eşitlendi; testler `tests/{contracts,ui,desk,skills}` altında.
- **Beyin v2:** hafıza sıfırdan kuruldu + seçici göç: 1.544 → 711 düğüm; yineleme %52,5 → %4,8; kategori 17 → 4 kapalı küme; kör test Hit@1 8 → 9/10, gürültü %2 → %0; `MemoryGate` tek giriş (üç bantlı yenilik kapısı, LLM'siz, medyan 82 ms); test fikstürü sızıntısı 531 → 0; 256 eski kaynaksız düğüm `legacy:pre-v2` (K12 258 → 2, kalan 2 kimlik düğümü); rüya döngüsü v2 (23 birleştirme, 0 hata), gri bant birleştirme turu, wiki derleme hattı (rapor başına 1 tur, artımlı), genel sohbet beyin paketi (damıtılmış pay %0 → %38).
- **Entropy Board:** durum makinesi (8 durum, 12 geçiş, tek kaynak), `events.jsonl` + `TASKBOARD.md`, `BoardDispatcher` (atomik claim, açılış uzlaştırması), ajan başına kalıcı oturum (`--session-id`/`--resume`, agy `--conversation`), efor uçtan uca (Claude `--effort`, agy model son eki), 4+1 pano aracı, kanıtsız bitiş → `review`, rapor → sohbet kartı, `/task` yalnızca kart oluşturur; öz-amplifikasyon kilidi (beyinden yanıt, yenilik kotası, kaynak zorunluluğu); `/board`, `/memory merge|dream`, `/wiki compile`, `/model`, `/agent effort|model`, `/lock`.
- **Canlı doğrulama (gerçek Claude, 129k token):** kart → claim → koşu → kanıtlı bitiş → rapor sinyali; ikinci/üçüncü kartta `--resume` ile aynı oturum; üç gerçek regresyon bulunup düzeltildi (kullanılmış oturum kimliği, `--resume` hiç kullanılmıyordu, araştırma raporları hafızaya girmiyordu).
- **Tasarım sistemi (11-E):** 12 belirteç (24 kontrast kontrolü, 0 ihlal), tek QSS girişi + odak halkası, QtAwesome ikonlar (exe'de çizildiği gerçek ekranda doğrulandı), `ui-design` yeteneği, `scripts/ui_audit.py` 9 kapı yeşil: yerel stil 222 → 1, sabit boyut 87 → 17, yazı kademesi 9 → 4, emoji 358 → 7, erişilebilir ad 0 → 110, kısayol 2 → 8; üst çubuk 18 → 4 öğe, dikey gezinme (1366'da 7/7), rapor yüzeyi 8 → 2, katlanır terminal, Chat kromu %75 → %11 (gerçek ekran), Desk hex 17 → 0. Gerçek ekran: Zen 1920×1080'de 4 öğe/7 gezinme/0 taşma, Tab ile 6/6 odak durağı adlı, üst çubuktan sürükleme çalışıyor.
- **Kapanış QA'sında bulunan:** tam süit 2.352/2.353 (tek kalan Desk asgari boyut sözleşmesi, aşağıda), 11-E'nin iki ürün regresyonu (slash paleti işaretleri, terminal düğmesi etiketi) düzeltildi, zamanlanmış rüya görevi v2'ye bağlandı, kilit/otomatik dağıtım anahtarları komut paletinde, testlere uyarlanabilir zaman bütçesi (yük altındaki sahte zaman aşımları bitti).
- **11-F spike (`claude --bg`):** ertelendi, modül korundu (uygulama kapansa da yaşıyor ama yapılandırılmış akış yok, `--resume` kopya açıp izolasyonu düşürüyor).

## Ölçüm tablosu (gerçek DB, `scripts/brain_metrics.py`)
| Ölçüt | Önce | Sonra |
|---|---:|---:|
| Düğüm | 1.544 | 729 |
| K1 yineleme | %52,5 | %4,8 |
| K2 Hit@1 / Hit@5 | 8/10 · 10/10 | 9/10 · 10/10 |
| K3 gürültü | %2,0 | %0,0 |
| K7 kategori | 17 | 4 |
| K10 fikstür | 531 | 0 |
| K11 kapı gecikmesi | — | 82–134 ms |
| K12 kaynaksız L2 | 1.276 | 2 (kimlik düğümleri) |

## Alt ajanlar
Altı ajan (Opus 5, low): dört mevcut tanım güncellendi; `research-scout` ve `repo-curator` eklendi; ortak bellek `docs/STATE.md`.

## Açık kalanlar
- **Zen, %200 ölçekli LG monitörde ekrana sığmıyor (Faz 6'dan beri):** pencere mantıksal 1920×1032 açılıyor ama Zen'in asgari yüksekliği (845 mantıksal) o monitörün mantıksal yüksekliğini aşıyor; arayüzün bir kısmı ekran dışında. Faz 12-D'nin ilk işi (asgari yükseklik ve kaydırılabilir yan paneller + ekrana kenetleme).
- **Desk'in bildirilen asgari boyutları gerçek değil:** bildirilen 800×540, gerçek 1.205×620 (Projeler sayfası 852 px darboğaz). Faz 12-D.
- Gerçek wiki derleme (financial-auditor ~50 tur) ve gerçek gri birleştirme turu kota tavanı nedeniyle koşulmadı; K6 (wiki payı) bu yüzden FAIL; `/memory merge`, `/wiki compile`, `/memory dream` köprüye bağlı değil (Faz 12-A'nın ilk işi).
- `claude --bg` ertelendi; agy'de kalıcı terminal karşılığı yok.
- Faz 12: `memory → brain` paket taşıması, Desk'e dönüş; ayrıca aynı dört araştırma istemiyle yeni tur ve yeni plan (senin talimatın).
