# Faz 13 Araştırma Notu — "Kullanıcı deneyimi, paket taşıması, Desk'e dönüş"

Tarih: 2026-09-10 · Dal `ai/v0.1.7` · Taban **v0.10.0** · Kapsam **SALT OKUNUR**
(hiçbir kaynak/test/kasa/ayar dosyasına dokunulmadı; tek yazılan dosya budur).
Model çağrısı yapılmadı — kota harcaması **0**.

Okunan taban: `docs/STATE.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`,
`docs/adr/ADR-0004`, `ADR-0007`, `docs/reports/2026-09-10_Faz12_Ilerleme_Raporu_v0.10.0.md`,
`…Faz12_Arastirma_B_Depo_Denetimi.md` §6, `…Faz12_Arastirma_D_Arayuz_Tasarim_Denetimi.md`,
`2026-09-11_Faz10_Arastirma_Notu.md`.

> **Not:** kullanıcının bildirdiği dört yüzey hatası (rapor başlığı, sıkışıklık, düğme
> görünürlüğü/kasma, Zen çekirdek görseli) paralel bir `ui-engineer` ajanı tarafından
> **şu anda düzeltiliyor** (kodda Faz 13 damgalı yorumlar mevcut:
> `src/entropy/ui/design/prefs.py:91-95`, `src/entropy/ui/modes/zen_mode.py:156-158,473`).
> Bu not o düzeltmeleri **tekrarlamaz**; kök nedenleri ölçer ve **tekrar etmemesi için
> kalıcı kapıları** tanımlar.

---

## 1. UX denetimi — kök nedenler (ölçülmüş)

### 1.1 "Düğmeler görünmüyor" → iki kök neden, biri kesin kanıtlı

**KN-1 (kesin): iki eylem düğmesinin metni boş.**
`src/entropy/ui/widgets/report_center.py:802-807` — digest kartının beş eylem
düğmesinden ikisi **boş dizeyle** kuruluyor:

```python
self.pin_btn = self._action_btn("", "Sabitle / sabitlemeyi kaldır")
self.archive_btn = self._action_btn("", "Kümeyi arşivle")
```

Ölçüm (offscreen, gerçek kasa, 663 künye):

```
btn texts: ['Detayı aç', 'Orkestratöre sor', 'Okundu', '', '']
```

`_action_btn` (`:811-817`) her düğmeye `variant="ghost"` veriyor; `ghost` QSS'te
**`border-color: transparent` + `color: text.muted`** (`src/entropy/ui/design/qss.py:116-117`).
Metin de boş olunca düğme fiilen **görünmez bir dikdörtgen**: kenarlığı yok, yazısı yok,
yalnızca ipucu (tooltip) var. Bu, Faz 11-E emoji temizliğinin artığıdır (📌/🗄 silinmiş,
yerine metin/ikon konmamış) — 11-E'de aynı sınıftan iki hata daha bulunmuştu
(`STATE.md` §2.4 satır 278-279: slash paleti `[✓]`, terminal düğmesi etiketi).

**KN-2 (ikincil): `ghost` varyantı tek başına düşük kontrast.**
`ghost` = kenarlıksız + `text.muted`. `scripts/ui_audit.py` kontrast kapısı
`contrast_failures` **metin/zemin** çiftlerini ölçüyor (`:257-282`), ama
**bir düğmenin metninin boş olup olmadığını** ya da **kenarlığı şeffafken görünürlüğünü**
ölçen kapı **yok**. 12-F'de `ui_audit --gate --final` **exit 0** verdiği hâlde bu hata
canlıydı. **Kapı boşluğu.**

### 1.2 "Tıklamada kasma" → kesin ölçüm

Profil (offscreen, gerçek kasa `…\Obsidian Vault`, **713 rapor `.md`**):

| Adım | Süre | Not |
|---|---:|---|
| `collect_recent_entries(limit=5000)` | **324 ms** | 663 künye (açılış + `reports_updated` debounce) |
| `set_entries(...)` (ilk `refresh`) | **237 ms** | 10 öne çıkan + 148 sessiz küme |
| `refresh()` — **sessiz bölüm kapalı** | **10–13 ms** | 10 kart widget'ı |
| `toggle_quiet()` (sessiz bölüm açılır) | **125 ms** | 158 kart widget'ı |
| `refresh()` — **sessiz bölüm açık** | **139 ms** | her tıklamada 158 widget yok edilip yeniden kuruluyor |

Kök neden `report_center.py:1146-1160`: `refresh()` **her çağrıda** düzendeki bütün
kart widget'larını `deleteLater()` ile yok edip `DigestCardWidget`'ları **sıfırdan**
kuruyor. Okundu/pin/arşiv tıklamalarının hepsi `refresh()`e gidiyor
(`:1199,1209,1233,1239,1244,1253,1262,1276`). Faz 9'da **veri** katmanı önbelleğe
alınmış (`_HEAD_CACHE`, `_enrich_cache`, `_cluster_signature` — `:234-238,1076-1098`)
ama **widget katmanı alınmamış**; ölçüm bunu doğruluyor: 10 kartta 11 ms, 158 kartta
139 ms → maliyet neredeyse tamamen widget kurulumu (kart başına ≈ 0,88 ms).

**İkinci kalem — senkron disk yazımı.** Her okundu/pin tıklaması
`ReportInboxStore.set_many()` → `save()` → **tam JSON yeniden yazımı**
(`report_inbox.py:78-83`). Bugünkü dosya `C:\EntropiAI\.entropy\report_inbox.json`
= **143.612 bayt**. Yani tıklama başına 143 KB senkron `write_text` **+** 139 ms
widget kurulumu, ana iş parçacığında.

**Kabul edilen hedef:** [RAIL modeli](https://web.dev/rail/) girdi yanıtı için
**≤ 100 ms görünür tepki**, uygulamanın kendi bütçesi **≤ 50 ms** (kalan 50 ms
çerçeve/kuyruk payı). Bugün sessiz bölüm açıkken **139 ms ≈ 2,8×** bütçe.

**Çözüm yönü:** (a) `refresh()` **fark uygular** (kart imzası → widget eşlemesi,
yalnızca değişen kart tazelenir); (b) `set_many` yazımı ertelenir/toplanır;
(c) `repolish` yalnızca `variant`/`tone` gerçekten değişen widget'a uygulanır.

### 1.3 "Rapor Merkezi ve okuyucu çok sıkışık" → bilgi mimarisi

| Öğe | Değer | Kanıt |
|---|---:|---|
| `DigestCardWidget.sizeHint()` genişliği | **675 px** | offscreen ölçüm |
| `ReportCenterWidget.minimumWidth()` | **240 px** | `report_center.py:867` |
| Okuyucu (`content_browser`) asgari | **200 px** | `reports_viewer.py:385` |
| Okuyucu bölücü varsayılanı | **[200, 380]** | `reports_viewer.py:396` |
| Sessiz küme sayısı (gerçek kasa) | **148** | ölçüm |

Kart **675 px istiyor**, panel **240 px'e kadar sıkıştırılabiliyor** → 2,8× fark,
kartın iç düzeninin ezilmesi demek. Okuyucuda 380 px'lik gövde 13 px yazıyla satır
başına ≈ **50–54 karakter**; okunabilirlik aralığının (45–75) alt sınırı
([Baymard](https://baymard.com/blog/line-length-readability)).

**Üçlü aynı ekranda yaşayamaz.** Önerilen bilgi mimarisi (progressive disclosure —
[UXPin 2026](https://www.uxpin.com/studio/blog/what-is-progressive-disclosure/),
[AI UX Playground](https://aiuxplayground.com/pattern/progressive-disclosure/)):

| Ekran | Ne | Genişlik kuralı |
|---|---|---|
| **Gözden geçirme** (varsayılan) | digest kartları + sessiz bölüm katlı | kart ≥ **520 px** |
| **Liste** | "Tümü (N rapor)" → tam liste + süzgeç | liste ≥ **260 px** |
| **Okuma** | okuyucu **baskın**, liste dar kenar çubuğu | okuyucu ≥ **560 px** (≈ 65–72 karakter) |

Kural: **aynı anda en çok iki bölge**. Okuyucu açılınca digest katlanır (sinyal zaten
var: `show_all_requested`, `report_center.py:849`), kapanınca geri gelir.

### 1.4 Görevler kanbanı — 7 sütun sığmıyor (aritmetik kanıt)

`task_board_widget.py`: `COLUMN_MIN_WIDTH = 168` (`:39`), 8 durum → **7 sütun**
(`STATUS_TO_COLUMN`, `:63-72`), her sütun `setMinimumWidth(COLUMN_MIN_WIDTH)` (`:790`),
detay paneli `setMinimumWidth(180)` (`:806`).

> 7 × 168 + 180 ≈ **1.356 px** gerçek asgari.

Widget'ın kendi beyanı ise `setMinimumWidth(220)` (`:808`) — **beyan ile gerçek
arasında 6× sapma**; `ui-design` SKILL.md §0/10'un ("kapı beyana dayanamaz")
tam olarak yasakladığı durum.

**Öneri:**
1. `failed`/`canceled` zaten `COLLAPSIBLE_COLUMNS` (`:60`) — **varsayılan katlı**
   → 5 sütun × 168 + 180 = **1.020 px**.
2. Genişlik **< 1.020 px** ise kanban yerine **liste + detay** görünümü (aynı veri).
   Masaüstü karşılığı: [WCAG 1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html)
   ruhu — içerik iki eksende kaydırmaya zorlanmaz.
3. `setMinimumWidth` gerçek toplamı beyan etsin (`sum(cols)+detail`); 220 sabiti kalksın.

### 1.5 Rapor başlığı üretimi — kök neden kesin

Kullanıcının gördüğü **"Tamamdır, şimdi senden yeni bir yetenek (+2)"** bir rapor
başlığı değil, **kullanıcının kendi sohbet mesajının ilk 40 karakteri**.

Kanıt — `src/entropy/core/agy_bridge.py:2381-2384`:

```python
clean_prompt = re.sub(r'^(?:\[SİZ\]:\s*)?', '', raw_user_prompt.strip(), flags=re.IGNORECASE)
clean_prompt = re.sub(r'^(?:/[a-zA-Z0-9_\-:]+\s*)+', '', clean_prompt.strip())
first_line = clean_prompt.strip().split("\n")[0][:40]
clean_title = re.sub(r'[\\/*?:"<>|]', "", first_line).strip() or "Araştırma Raporu"
```

Bu başlık `vault_manager.save_research_report()` ile hem **dosya adına** hem
**frontmatter `title:`** alanına yazılıyor (`memory/obsidian/vault_manager.py:462,477,493-499`);
okuyucu da önce frontmatter `title`'ı okuyor (`reports_viewer.py:47,86-87`) — yani
yanlış başlık zincirin her yerinde görünüyor.

**Asıl soru: bu sohbet turu neden rapor oldu?** `agy_bridge.py:2360-2368`:

```python
is_explicit_research = is_explicit_learn or any(w in raw_user_prompt.lower() for w in [
    "araştır", "araştırma yap", "rapor hazırla", "raporla", "analiz et",
    "derinlemesine incele", "dossier", "dokümantasyon oluştur"])
has_markdown_structure = ("# " in full_text or "## " in full_text) and len(full_text) > 250
if not is_err and (is_task_prompt or (is_explicit_research and has_markdown_structure)):
```

Serbest sohbette kullanıcının mesajı bu 8 anahtar kelimeden birini içeriyor **ve**
yanıt 250 karakterden uzun + başlıklıysa, **tur olduğu gibi rapora dönüşüyor**.
`report_watcher.py` bu işi yapmıyor — o yalnızca kasadaki `.md`'leri **indeksliyor**
(`_check_now` → `index_new_reports`), rapor **üretmiyor**. Yani sorumlu tek yol
köprünün sohbet dalıdır.

Kasada bugün **713 rapor `.md`** var; 423'ü kök `Entropy/Reports/` altında
(`Projects/EntropiAI/Reports` 133, `Skills/financial-auditor/Reports` 50 …).
Bu 423'ün ne kadarının sohbet turu olduğu **sınıflandırılmadı**.

**Öneri (üç adım):**

1. **Başlık kaynağı sırası:** çıktının ilk `# H1`'i → yoksa ilk cümleden üretilen
   özet → yoksa dosya adı. **Kullanıcının istem satırı başlık kaynağı olmaktan çıkar.**
   Tek fonksiyon: `derive_report_title(body, fallback)`.
2. **Sohbet turları rapor değildir:** serbest sohbet çıktısı
   `Entropy/Sessions/<tarih>/<saat>-<konu>.md` altına `type: session` frontmatter'ıyla
   yazılır; `collect_recent_entries` **varsayılan olarak `Sessions/` taramaz**, Rapor
   Merkezi'nde ayrı süzgeçle açılır. Rapor sayılan tek şey: (a) pano kartı çıktısı
   (`Gorev_*`), (b) `[OTONOM PLANLI GÖREV]`, (c) açık `/learn`. **8 anahtar kelime
   sezgisi kaldırılır.**
3. **Geriye dönük veri taşınmaz** (kullanıcı verisine dokunulmaz kuralı). Bunun yerine
   görüntüleme katmanı, frontmatter başlığı istem gibi görünen künyeleri `H1`'den
   yeniden başlıklandırır — dosyayı değiştirmeden.

### 1.6 Zen çekirdek görseli

`src/entropy/ui/widgets/core_visualizer.py` **duruyor ve sağlam** (durum farkındalıklı,
görünmezken boyamıyor — `:1-8`). Kaybolma nedeni Faz 11-E'nin çekirdeği üst çubukta
**24 px'lik bir durum noktasına** indirmesi (`zen_mode.py:1337`, `header_bar.py:110`).
Paralel ui ajanı bunu **zaten geri alıyor** (`prefs.py:91-95`,
`zen_mode.py:156-158,473`).

**Kalıcı ilke:** çekirdek süs değil **kimlik + durum göstergesidir**; sadeleştirme
turları onu "kaldırılabilir dekor" sayamaz. `ARCHITECTURE.md` §8'e "korunan kimlik
öğeleri" listesi (çekirdek, marka kümesi, model kapsülü) yazılmalı ve `tests/ui/`
içinde bir sözleşme testi çekirdeğin Zen'de **var ve ≥ 48 px** olduğunu ölçmeli.

### 1.7 `ui-design` skill'ine eklenecek kapılar (Faz 13 kapı seti)

Mevcut kapı seti (`skills/ui-design/SKILL.md` §6 + `scripts/ui_audit.py`) kontrast,
hedef boyutu, odak, emoji ve gömülü hex'i ölçüyor; **12-F'de exit 0 verdiği hâlde**
boş düğme ve 139 ms tıklama gecikmesi canlıydı. Dört yeni kapı:

| Kapı | Eşik | Nasıl ölçülür | Dayanak |
|---|---|---|---|
| **G13-1 Boş etkileşimli öğe** | `empty_interactive_count == 0` | Her `QAbstractButton`: `text().strip()` dolu **veya** `icon()` boş değil **veya** `accessibleName()` dolu | [WCAG 4.1.2](https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html) |
| **G13-2 Düğme kontrastı (ghost dâhil)** | metin/zemin ≥ **4,5:1**; kenarlık/zemin ayrımı ≥ **3:1** | `ghost` için de ölçülür; şeffaf kenarlıkta zemin farkı hesaplanır | [1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html), [1.4.11](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) |
| **G13-3 Tıklama gecikmesi** | eylem → yeniden çizim **≤ 50 ms** (uyarı 100 ms) | `QElapsedTimer`; Rapor Merkezi'nde **sessiz bölüm AÇIK**, ≥ 150 kümede sentetik `click()` | [RAIL](https://web.dev/rail/), [NN/g](https://www.nngroup.com/articles/response-times-3-important-limits/) |
| **G13-4 Okuyucu asgarisi + beyan doğruluğu** | okuma kipinde gövde ≥ **560 px**; her panelde `minimumWidth()` **beyanı ≥ hesaplanan** çocuk toplamı | `minimumSizeHint` toplamı vs. `setMinimumWidth` | [1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html), [Baymard](https://baymard.com/blog/line-length-readability) |

Ek değişmez (§0): **"Bir sadeleştirme turu bir etkileşimli öğeden metni kaldırıyorsa
yerine ikon + `accessibleName` koymak zorundadır; ikisi de yoksa öğe silinir."**
(11-E'de üç kez ihlal edildi: slash paleti, terminal düğmesi, pin/arşiv düğmeleri.)

---

## 2. `entropy.memory` → `entropy.brain` paket taşıması

### 2.1 Güncel yüzey (bugün ölçüldü)

| Yüzey | ADR-0004 (Faz 11) | 12-B | **Bugün (12-E sonrası)** | Komut |
|---|---:|---:|---:|---|
| `src/` dosya | 41 | 45 | **48** | `grep -rl 'entropy\.memory' src --include=*.py \| wc -l` |
| `src/` geçen satır | — | — | **181** | aynı, `grep -rn … \| wc -l` |
| `tests/` dosya | 41 | 49 | **55** | aynı, `tests` |
| `scripts/` **kök** (gerçek araç) | — | 60 | **5** | `grep -rl … scripts/*.py` |
| `scripts/_oneshot/` (koşulmaz) | — | (60'ın içinde) | **55** | `grep -rl … scripts/_oneshot/*.py` |
| `tests/_reference/` | — | — | **0** | `grep -rl … tests/_reference/*.py` |
| `EntropyAI.spec` satır | 22 | 22 | **27** | `grep -c` |
| Canlı belge | — | 4 | **4** | `ROADMAP.md`, `STATE.md`, `ADR-0004`, `.claude/agents/memory-rag-engineer.md` |
| Göreli import (`from .memory`) | — | 0 | **0** | `grep -rn 'from \.\.\?memory' src` |

**Gerçek taşıma yüzeyi = 48 + 55 + 5 + 1 (spec) + 4 (canlı belge) = 113 dosya.**
`_oneshot/` (55) sayılmasa bile **113 > 100** → ADR-0004'ün "≤ 100" hedefi
**karşılanmadı** (12-E yüzeyi 154 → 113'e indirdi ama `src`/`tests` büyümesi
kazancın bir kısmını yedi).

### 2.2 ADR-0004 ön koşulları — durum

| Ön koşul | Durum | Kanıt |
|---|---|---|
| `docs/ARCHITECTURE.md` yazılmış | **KARŞILANDI** | 456 satır (`STATE.md` §2.5/3) |
| Tam süit yeşil | **KARŞILANDI** | 12-F: **2.456 passed / 0 failed / 472,55 s** |
| `.exe` bir kez sorunsuz derlenmiş | **KARŞILANDI** | 12-F: exit 0, 256 s, `--version` → `Entropy AI 0.10.0` |
| Spec eşleme testi (12-B'nin eklediği risk kapısı) | **KARŞILANDI** | `tests/contracts/test_spec_sync.py` **9 passed** |
| Tek seferlik `scripts/` ailesine karar | **KARŞILANDI** | `scripts/_oneshot/` + "koşulmaz" README (12-E) |
| Yüzey ≤ 100 dosya | **KARŞILANMADI** | **113** |

**Beş gerçek risk ön koşulunun beşi de yeşil; yalnızca sayısal "≤ 100" hedefi 13 dosya aşılıyor.**

### 2.3 Karar önerisi: **YAPILSIN** — uyumluluk shim'iyle, tek başına bir dilimde

1. ADR-0004'ün asıl risk kapısı **spec sapmasıydı**; artık **kalıcı bir test** onu
   ölçüyor. "≤ 100" bir hedefti, risk kapısı değil.
2. Uyumluluk shim'i `_oneshot/` 55 betiğini ve dış atıfları çalışır tutar, geri alma
   maliyetini sıfıra yaklaştırır.
3. Kazanç yalnızca estetik değil: `ARCHITECTURE.md`'nin **belgelenmiş hedef şeması**
   `core / brain / agents / desk / ui / skills`; `memory` adı ile "beyin v2" (kapı,
   kategoriler, rüya, wiki, amplifikasyon) arasındaki uçurum her yeni ajanı şaşırtıyor.
4. **Şimdi yapılmazsa hiç yapılmaz:** yüzey her fazda büyüyor (41 → 45 → 48 `src` dosyası).

### 2.4 Adım planı (tek commit, `git revert` ile geri alınabilir)

| # | Adım | Doğrulama (kabul ölçütü) |
|---|---|---|
| 1 | **Taban kanıtı:** taşımadan önce tam süit + `--collect-only` sayısı kaydedilir | `pytest --collect-only -q \| tail -1` |
| 2 | `git mv src/entropy/memory src/entropy/brain` | `git status` yalnızca R (rename) satırları |
| 3 | Metin değişimi `entropy.memory` → `entropy.brain`: `src/` (48 dosya / 181 satır), `tests/` (55), `scripts/*.py` kökü (5), `EntropyAI.spec` (27 satır) | `grep -rn 'entropy\.memory' src tests scripts/*.py EntropyAI.spec` → **0** |
| 4 | **Elle üç dizgi** (AST aracı göremez): `ui/widgets/memory_inspector_dialog.py:508-509` (`"entropy.memory.graph_store"`, `"entropy.memory.cognitive_memory"`), `memory/supabase/cognitive_memory.py:36` (`logging.getLogger("entropy.memory.cognitive")`) | üçü `grep` ile doğrulanır; günlük süzgeci `entropy.brain.cognitive` görür |
| 5 | **Uyumluluk shim'i:** yeni `src/entropy/memory/__init__.py` → `entropy.brain` alt modüllerini `sys.modules` üzerinden yeniden yayınlar + **`DeprecationWarning`**. Ömür **bir sürüm** (v0.11.x), v0.12.0'da silinir | yeni `tests/contracts/test_brain_package_move.py`: `import entropy.memory.gate` çalışır, `entropy.memory.gate is entropy.brain.gate` **True**, uyarı yükselir |
| 6 | `EntropyAI.spec` hiddenimports: 27 satır + **shim modülü** | `tests/contracts/test_spec_sync.py` **yeşil** |
| 7 | Canlı belgeler (`ROADMAP.md`, `STATE.md`, `ARCHITECTURE.md` §2, `.claude/agents/memory-rag-engineer.md`). **31 tarihsel rapor DÜZELTİLMEZ** (geçmiş dondurulur — `docs/` arşiv kuralı) | `grep -rn 'entropy/memory' docs/*.md` → 0 |
| 8 | **Doğrulama zinciri:** `python -c "import entropy.main"` → tam süit → `pyinstaller EntropyAI.spec` → `--version` → 20 sn canlı koşum → `dist/EntropyAI/_internal/entropy/brain/` var mı | test sayısı **adım 1'e eşit**; build exit 0; `--version` doğru; `Traceback`/`CRITICAL` **0**; `brain` klasörü pakette |
| 9 | ADR-0008 ("taşıma yapıldı"); ADR-0004 durumu "yerine geçildi" | — |

**Riskler**

| Risk | Olasılık | Karşılık |
|---|---|---|
| PyInstaller **sessiz** eksik paketleme (Faz 10-C'de yaşandı) | orta | adım 6 kalıcı spec testi + adım 8'de `_internal/entropy/brain/` klasör kontrolü + 20 sn canlı koşum |
| Dizgi ile modül adı (3 yer) | **kesin, ölçüldü** | adım 4 elle + `grep` kapısı |
| `~/.entropy` veri göçü | **yok** | ADR-0004 §4, 12-B §6.2/4: durum paket adına göre anahtarlanmıyor |
| `_oneshot/` 55 betiği kırılır | düşük (koşulmuyorlar) | adım 5 shim'i |
| Paralel ajanların `src/` düzenlemesiyle çakışma | **yüksek** | taşıma **tek başına** bir dilimde (13-B) koşar |

---

## 3. Desk'e dönüş — iş listesi (Faz 10 kalanları)

### 3.1 Ofis kartlarında araç bloğu sızıntısı — kök neden kesin

`src/entropy/agents/tasks.py:1689-1693`:

```python
# OFİS kartı KAPSAM DIŞI: Desk harness'ı blokları kartın `summary`sinden
# geri ayrıştırıyor (kontrol noktası dosyası, kanıt, kural adayı).
summary = raw_output if card.office else _strip_tool_blocks(raw_output)
```

**Bilinçli bir taviz:** ofis kartında `summary` = ham çıktı, çünkü `agents/harness.py`
blokları oradan okuyor (`:1030-1048` kontrol noktası, `:1078-1086` kanıt,
`:1853` `text = child.summary`). Sonuç: Desk arayüzünde ofis kartlarında
`[PANO …] {json} [/PANO]` blokları kullanıcıya görünüyor.

**Çözüm (tek yönlü ve temiz):** `TaskCard` zaten `checkpoint` ve `proof` **alanlarına**
sahip (`STATE.md` §3). `tasks._finish` ofis kartında da blokları **ayrıştırıp alanlara
yazsın**, `summary`ye **temizlenmiş** metni koysun; harness `card.summary` yerine
`card.checkpoint` / `card.proof` alanlarını okusun. Ham metin zaten olay günlüğünde ve
köprü raporunda kayıpsız. Böylece `_strip_tool_blocks` **koşulsuz** çalışır ve
`card.office` istisnası kalkar.

**Kabul ölçütü:** ofis kartı `board_checkpoint` + `board_finish` içeren ham çıktıyla
bitirildiğinde `card.summary` içinde `[PANO` **0 kez** geçer, `card.checkpoint` dosya
yolu **dolu**, `card.proof.green` **doğru**; `tests/desk/` içinde fixture harness turu
bunu doğrular.

### 3.2 Kanıt / makbuz / etkileşimli akışın canlı doğrulaması

`STATE.md` §2.6 **Entropy** panosunu canlı doğruladı; **Desk ofis kartını doğrulamadı**.
Eksik canlı zincir: ofis kartı → orkestratör board'a bölme → işçi ajan kendi terminalinde
→ `board_checkpoint` dosyası → testleri koşup **yeşil kanıtı** `board_finish`e ekleme →
makbuz = ofis raporu → Desk "Makbuz"/"Değişiklikler" panelleri. **Uçtan uca hiç koşulmadı.**

### 3.3 `gh` yokken PR yolu — **zaten çözülmüş, canlı doğrulanmadı**

`src/entropy/agents/pr_flow.py:5-6` sözleşmeyi net yazıyor: "`gh` yoksa yedek" değil,
**"her zaman yerel dal + diff özeti, `gh` varsa ÜSTÜNE taslak PR"**. `has_gh()`
(`:61-65`) `shutil.which` + `gh auth status` rc; `create_draft_pr` `gh` yoksa
`{"skipped": "gh yok"}` döndürüp **kartı etkilemiyor** (`:205-211`); `gh` çıktısı
**loglanmıyor** (jeton ipucu riski, `:15,243-245`). Kalan iş: **canlı doğrulama**
(yerel dal + diff Desk "Değişiklikler" panelinde görünüyor mu; `push` yalnızca
`/desk push <kart>` ile mi tetikleniyor).

### 3.4 Ofis eforu uçtan uca

Efor Faz 9.1'de "model varyantı" oldu. Entropy tarafında argv kanıtı var
(`--effort low`, `STATE.md` §2.3). **Desk ofis kartında efor → şartname → argv
zinciri ölçülmedi.** Kabul ölçütü: ofis kartına `effort` yazılınca işçi ajanın
argv'sinde (claude) `--effort <seviye>`, (agy) doğru model varyantı görünür.

### 3.5 Desk'te `claude --bg` (ADR-0007)

ADR-0007 kuralı: **"Faz 13'e kadar üründen çağıran çıkmazsa modül
`docs/_archive/spikes/` altına iner."** Bugün üründe içe aktaran **yok**, spec'te
**yok**, yalnızca `tests/test_phase11_claude_bg.py` (32 test) canlı tutuyor.

- **(A) Bağla** — bağlanırsa aynı commit'te spec girdisi de eklenir (ADR-0007/3).
- **(B) Arşivle** — `docs/_archive/spikes/claude_bg/`, testler `tests/_reference/`'a.
- **Önerim: (B).** Faz 13'ün üç dilimi zaten dolu; kalıcı süreç yaşam döngüsü
  (yetim süreç, kilit, Windows temizliği) yeni bir risk sınıfı açar ve Faz 10'un
  **etkileşimli kart** çözümü bugünkü ihtiyacı karşılıyor. Arşivleme geri alınabilir,
  bağlama değil.

### 3.6 Entropy → Desk tek yönü ve Entropy'nin Desk'i geliştirme yetkisi

**Ölçüm: yüzey büyük ölçüde ZATEN VAR.** `src/entropy/core/slash_commands.py:689-707`
(`_desk_usage()`):

```
/desk · /desk office add <ad> :: <amaç> · /desk office rm <ad>
/desk agent add|edit|rm <ofis> <ad> :: <açıklama>
/desk project add <ofis> <ad> :: <hedef> [:: <depo yolu> [dal]]
/desk templates · /desk create <ofis> --template <ad>
/desk review <kart> · /desk push <kart>
/desk task <ofis> [@proje] <başlık> :: <hedef> · /desk stop <kart>
/desk msg <ofis> :: <talimat>
```

`_handle_desk_admin` (`:708-…`) **yerel**: dosya yazar, model çağırmaz, kota harcamaz;
ofis açıldığı anda **orkestratörü de doğuruyor** (kural 2 koda yazılmış).
`/offices` roster, `/ask <ofis>` mesajlaşma; `board_ask` Desk → Entropy **soru** yolunu
yön kilidini koruyarak açık izinle taşıyor.

**Eksik üç şey:**

1. **Entropy'nin KENDİ kararıyla Desk'i düzenlemesi yok.** Bugün `[PANO board_create]`
   Entropy'nin **kendi** panosuna kart açıyor; `[DESK …]` karşılığı **yok**. Kullanıcı
   kuralı "Entropy Desk'i geliştirebilir" diyor → Entropy'nin araç setine
   `desk_office_create` / `desk_agent_edit` / `desk_task` blokları eklenmeli
   (`board_tools.py` deseniyle aynı taşıma biçimi), **yalnız `claude` sohbet yolunda**
   ve **kullanıcı onaylı** (ofis/ajan yaratmak kalıcı yapı değişikliğidir).
2. **Tek yön testi eksik yüzeyde.** `tests/contracts/test_architecture_rules.py` 13 test
   marka + ayrımı ölçüyor; ayrıca **"orkestratör istemlerinde Entropy kimliği geçmez"**
   ve **"Desk hiçbir yoldan Entropy panosuna kart yazamaz"** ayrı ölçülmeli.
3. **Entropy kontrol noktası çift yazıcı** (12-F kalanı): `checkpoints.write_checkpoint(office="entropy")`
   ve `board_tool_exec.write_entropy_checkpoint` aynı biçimi iki yerden yazıyor;
   `task_board_widget.py:110` hâlâ eski kökten okuyor. **Tek yazıcıya indirilmeli.**

---

## 4. Kota / koşu planı

Ertelenen canlı koşular (12-F, tavan 120k aşıldığı için durduruldu) —
**paralel QA'da koşuyor**, Faz 13 bunları **tekrar etmez**:

| Koşu | Tahmini | Ne kanıtlar |
|---|---:|---|
| `/distill wiki compile financial-auditor --turns 25` | ~30k | K6 wiki payı %29'un üstüne çıkar |
| `/memory merge` gerçek tur (kuyrukta 2 aday) | ~5k | gri bant birleştirme uçtan uca |
| 4. kart → oturum devri + `handoff.md` + `--resume` argv | ~15k | oturum bütçesi ve devir |
| `/skill synth` 1 tur zenginleştirme + `/skill approve` | ~10k | aday → `validated` → kasada `Skills/<ad>/SKILL.md` |
| **toplam** | **~60k** | |

**Faz 13'ün YENİ canlı bütçesi — Desk kanıt zinciri: ~60k token**

| Adım | Tahmini | Kabul ölçütü |
|---|---:|---|
| Ofis + orkestratör + 2 işçi kurulumu (`/desk office add`, `--template`) | **0** (yerel) | ofis açılınca orkestratör doğar; `Desk/Offices/<ad>/workspace/{BOARD,ARCHITECTURE,RULES}.md` yazılır |
| Orkestratör turu: görevi board'a böler, **kod yazmaz** | ~15k | BOARD.md'de ≥ 2 alt kart; orkestratörün `output_paths` içinde `.py` **yok** |
| İşçi #1 turu + `board_checkpoint` + testler + **yeşil kanıt** | ~20k | `checkpoints/*.md` **var**; `card.proof.green == True`; kanıtsız `board_finish` **reddedilir** |
| İşçi #2 paralel tur (izole terminal, sprite durumu) | ~15k | `agent_stream` iki ajandan akar; terminaller panelinde iki sekme |
| Makbuz + `/desk review <kart>` (yerel dal + diff; `gh` yoksa PR atlanır) | ~5k | makbuz = ofis raporu; Değişiklikler panelinde diff; `{"skipped": "gh yok"}` |
| Ofis eforu argv kanıtı | ~5k | argv'de doğru efor/model varyantı |
| **toplam** | **~60k** | |

**Tavan önerisi: 120k** (60k paralel QA + 60k Desk). `TaskLedger.record_chat_turn`
12-F'de eklendiği için bu turda **sohbet tüketimi de deftere düşecek** → tavan ilk kez
**gerçek** ölçülecek. Kural: `chat_token_totals()` + görev toplamı **100k**'yı geçince
canlı koşular durur, kalan adımlar bir sonraki oturuma yazılır.

---

## 5. Faz 13 dilimleri

### 13-A — UX ve çekirdek (kota **0**)

| # | İş | Ajan | Kabul ölçütü | Risk |
|---|---|---|---|---|
| A1 | Boş düğmeler: `pin_btn`/`archive_btn` metin **veya** ikon + `accessibleName` (`report_center.py:802-807`) | ui-engineer *(devam ediyor)* | G13-1 `empty_interactive_count == 0` | düşük |
| A2 | `refresh()` **fark uygulasın** (kart imzası → widget eşlemesi) | ui-engineer | sessiz bölüm **AÇIK** (158 kart) iken okundu tıklaması **≤ 50 ms** (bugün 139 ms) | orta — küme sırası değişince eşleme bozulur; imza testi şart |
| A3 | `ReportInboxStore.set_many` yazımı tıklama yolundan çıksın (ertelenmiş/toplu) | ui-engineer | 143 KB JSON tıklamada yazılmaz; 1 sn debounce + `aboutToQuit` kancası; veri kaybı testi | orta — çökmede son tıklama kaybı |
| A4 | Rapor Merkezi bilgi mimarisi: **aynı anda en çok iki bölge**; okuma kipinde digest katlanır | ui-engineer | okuyucu ≥ **560 px**; kart ≥ **520 px**; G13-4 yeşil | orta |
| A5 | Görevler: `failed`/`canceled` varsayılan katlı; < 1.020 px'te **liste + detay**; `setMinimumWidth(220)` beyanı gerçekle değişir | ui-engineer | 1.020 px'te 5 sütun taşmasız; 800 px'te liste; `declared ≥ computed` | orta |
| A6 | `derive_report_title(body, fallback)` — `H1` → ilk cümle → dosya adı; **istem satırı asla** | memory-rag-engineer | test: "Tamamdır, şimdi senden…" başlık **üretilmez**; frontmatter'sız dosyada `H1` kazanır | düşük |
| A7 | **Sohbet turu ≠ rapor:** 8 anahtar kelime sezgisi kalkar; serbest sohbet çıktısı `Entropy/Sessions/` altına `type: session`; Rapor Merkezi varsayılanı dışında | memory-rag-engineer | `agy_bridge.py:2360-2368` sezgisi silinir; sözleşme testi: yalnız `[OTONOM PLANLI GÖREV]`, pano kartı, açık `/learn` rapor üretir; **eski dosyalar taşınmaz** | orta — Rapor Merkezi sayacı düşer (beklenen) |
| A8 | Zen çekirdeği (kompakt animasyonlu + durum) + `prefs` anahtarı | ui-engineer *(devam ediyor)* | çekirdek Zen'de görünür ve ≥ 48 px; sözleşme testi | düşük |
| A9 | `ui-design` 1.2.0: G13-1…G13-4 + §0 değişmezi; `scripts/ui_audit.py` yeni sayaçlar | ui-engineer | `ui_audit --gate --final` exit 0 **ve** kapılar gerçekten ölçüyor (bilerek bozulmuş düğmeyle kırmızıya döner) | düşük |

### 13-B — `brain` taşıması (kota **0**, tek başına koşar)

| # | İş | Ajan | Kabul ölçütü | Risk |
|---|---|---|---|---|
| B1 | §2.4 adım 1–4 (`git mv` + 181+ satır + 3 dizgi) | memory-rag-engineer | `grep -rn 'entropy\.memory' src tests scripts/*.py EntropyAI.spec` → **0** | orta |
| B2 | Uyumluluk shim'i (`DeprecationWarning`, bir sürüm) | memory-rag-engineer | `entropy.memory.gate is entropy.brain.gate` **True** + uyarı | düşük |
| B3 | Spec + canlı belgeler + ADR-0008 | memory-rag-engineer | `test_spec_sync.py` yeşil; canlı belgelerde 0 atıf; 31 tarihsel rapor **dokunulmaz** | düşük |
| B4 | Doğrulama zinciri (import → tam süit → build → `--version` → 20 sn canlı → `_internal/entropy/brain/`) | qa-build-engineer | test sayısı **değişmez**; build exit 0; `Traceback`/`CRITICAL` **0**; `brain` klasörü pakette | **yüksek** (PyInstaller sessiz hata) |

> **Kilit kural:** 13-B koşarken başka hiçbir ajan `src/entropy/memory`, `EntropyAI.spec`
> ya da `tests/` altına yazmaz. Aksi hâlde bir `.exe` hatasının sebebi ölçülemez (ADR-0004 §3).

### 13-C — Desk kanıt zinciri ve temizlik (kota **~60k**)

| # | İş | Ajan | Kabul ölçütü | Risk |
|---|---|---|---|---|
| C1 | Ofis kartı araç bloğu sızıntısı: harness `card.checkpoint`/`card.proof` okusun, `summary` **koşulsuz** temizlensin | agy-integration-engineer | ofis kartı `summary`sinde `[PANO` **0**; `checkpoint` dolu; `proof.green` doğru | orta — harness'ın gerçek kaynağı değişiyor, ofis testleri toplu koşmalı |
| C2 | Entropy kontrol noktası **tek yazıcıya** insin; `task_board_widget.py:110` kartın mutlak `checkpoint` alanını okusun | agy-integration-engineer | iki yazıcıdan biri kalır; kontrol noktası Desk kökü altına düşmez (mevcut test korunur) | düşük |
| C3 | Entropy → Desk **düzenleme araçları**: `[DESK office_create/agent_edit/task]`, kullanıcı onaylı, yalnız `claude` sohbet yolunda | agy-integration-engineer | Entropy sohbetten ofis/ajan oluşturabilir; onaysız yapı değişmez; blok gösterilen metinde **görünmez** | orta |
| C4 | Tek yön sözleşme testleri (orkestratör isteminde Entropy kimliği yok; Desk → Entropy panosuna kart yazamaz) | qa-build-engineer | 2 yeni test yeşil | düşük |
| C5 | **Canlı Desk kanıt zinciri** (§4 tablosu, ~60k) | qa-build-engineer | orkestratör kod yazmaz; iki işçi paralel; kanıtsız `board_finish` reddedilir; makbuz + diff panelde; `gh` yoksa `{"skipped": "gh yok"}` | **yüksek** — kota; 100k'da durdur |
| C6 | Ofis eforu uçtan uca argv kanıtı | agy-integration-engineer | argv'de doğru efor/model varyantı | düşük |
| C7 | ADR-0008/0009: `claude_bg` **arşive** (öneri B); Desk tasarım sistemi kalanları | repo-curator | modül `docs/_archive/spikes/`, testler `tests/_reference/`; süit sayısı değişmez | düşük |

### 13-D — Kapanış (kota **0**)

| # | İş | Ajan | Kabul ölçütü |
|---|---|---|---|
| D1 | Tam süit + build + `--version` + 20 sn canlı + `ui_audit --gate --final` | qa-build-engineer | süit **0 failed**; build exit 0; kapılar exit 0; **G13-3 tıklama ≤ 50 ms canlı ölçüldü** |
| D2 | Gerçek ekran denetimi (LG %200): Rapor Merkezi / okuyucu / Görevler / Zen çekirdeği | qa-build-engineer | 4/4 kullanıcı şikâyeti görsel kanıtla kapandı |
| D3 | Yalıtım kanıtı (`tasks_ledger.db`, `skills_state.json`, `cognitive_memory.db` önce = sonra) | qa-build-engineer | üçü de değişmedi |
| D4 | Marka taraması (`git grep -ril`, iki ad) | qa-build-engineer | **0 dosya** |
| D5 | `STATE.md` + `ROADMAP.md` + Faz 13 ilerleme raporu, etiket **v0.11.0** | orkestratör | — |

**Sıra:** 13-A → **13-B (tek başına)** → 13-C → 13-D. 13-A ile 13-C paralel koşabilir
(kapsamlar ayrık: `ui/` vs `agents/`+`desk/`); **13-B hiçbir şeyle paralel koşmaz**.

---

## 6. Karar özeti

| # | Karar | Gerekçe (ölçüm) |
|---|---|---|
| K1 | **Boş düğme = ürün hatası**; kapı eklenir (G13-1) | `pin_btn`/`archive_btn` `text() == ''`; `ghost` = şeffaf kenarlık + `text.muted` |
| K2 | **Tıklama bütçesi 50 ms** (uyarı 100 ms); `refresh()` fark uygular | 158 kartta **139 ms**, 10 kartta 11 ms → maliyet widget kurulumu |
| K3 | **Aynı anda en çok iki bölge**; okuyucu ≥ 560 px | kart `sizeHint` 675 px vs panel asgarisi 240 px; okuyucu 380 px ≈ 50 karakter |
| K4 | **Görevler: 7 sütun 1.020–1.356 px istiyor**; altında liste+detay | 7×168+180 = 1.356; beyan 220 (6× sapma) |
| K5 | **Sohbet turu rapor değildir**; başlık `H1`'den türer, istemden **asla** | `agy_bridge.py:2360-2368` sezgisi + `:2383` `first_line[:40]` |
| K6 | **`memory → brain` YAPILSIN** (13-B, tek başına, shim'li) | 5/5 gerçek ön koşul yeşil; yüzey 113 (sayısal hedefin 13 üstü, risk kapısı kalıcı test) |
| K7 | **Ofis kartı `summary` koşulsuz temizlensin**; harness alanları okusun | `tasks.py:1693` `card.office` istisnası; `checkpoint`/`proof` **zaten kart alanı** |
| K8 | **`claude_bg` arşivlensin** (ADR-0007'nin Faz 13 koşulu) | üründe çağıran 0, spec'te 0; 32 test `tests/_reference/`'a |
| K9 | **Entropy'ye `[DESK …]` düzenleme araçları** eklensin (onaylı) | `/desk` yüzeyi var; Entropy kendi kararıyla Desk'i düzenleyemiyor |
| K10 | **Faz 13 canlı bütçe 120k**; ilk kez sohbet dâhil ölçülür | `record_chat_turn` 12-F'de eklendi |

## 7. Doğrulanamayanlar (açıkça)

1. **Gerçek ekranın mantıksal genişliği.** `scratch/ui/phase12/live_metrics.json`
   ekranı `avail [1920,1032], dpr 2.0` diyor, ama aynı dosyada `shellSplitter`
   **573 + 375 = 948 px** ölçülmüş. İkisi tutarsız: ya pencere ekranın yarısı kadar
   açıktı ya da mantıksal genişlik gerçekten ~960 px. **Sıkışıklığın ne kadarının DPI
   ölçeklemesinden geldiği ölçülmedi** — 13-A'da gerçek ekranda
   `screen().availableGeometry()` ve `window().width()` **birlikte** kaydedilmeli.
2. **713 raporun kaçı sohbet turu.** Kök `Entropy/Reports/` altında 423 dosya var;
   başlık kalıbına göre sınıflandırma **yapılmadı** (salt okunur tur; kasa içeriği taranmadı).
3. **`ReportInboxStore.set_many` yazım süresi** ölçülmedi (dosyaya yazmamak için);
   yalnızca dosya boyutu (143.612 B) kanıt.
4. **Zen "Raporlar & Notlar" sekmesinin gerçek panel genişlikleri** ölçülmedi:
   `ZenMode` örneklemek izleyici/zamanlayıcı başlatıp kullanıcı durumuna yazabilirdi.
5. **Desk kanıt zinciri hiç canlı koşulmadı** (kota); §3.2–3.4'teki her şey kod
   okumasına dayanıyor, **çalıştığı gözlemlenmedi**.
6. **`--autocompact` / `--fork-session`** hâlâ bağlı değil (12-F kalanı, sürüm bağımlı).
7. **`repolish` maliyeti** ayrı ölçülemedi: profil `refresh()` toplamını verdi;
   `unpolish/polish` payı ayrıştırılmadı (widget yeniden kurulumu baskın olduğu için
   önce A2 yapılmalı, sonra yeniden ölçülmeli).

## 8. Kaynaklar

**Birincil (standart / resmi belge)**
- W3C, *Understanding SC 1.4.3 Contrast (Minimum)*, WCAG 2.2 — https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- W3C, *Understanding SC 1.4.11 Non-text Contrast*, WCAG 2.2 — https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
- W3C, *Understanding SC 1.4.10 Reflow*, WCAG 2.2 — https://www.w3.org/WAI/WCAG22/Understanding/reflow.html
- W3C, *Understanding SC 2.5.8 Target Size (Minimum)*, WCAG 2.2 (AA, 24×24 CSS px) — https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- W3C, *Understanding SC 4.1.2 Name, Role, Value*, WCAG 2.2 — https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html
- Google / web.dev, *Measure performance with the RAIL model* (girdi yanıtı ≤ 100 ms, uygulama bütçesi 50 ms) — https://web.dev/rail/
- Qt 6, *QElapsedTimer* — https://doc.qt.io/qt-6/qelapsedtimer.html
- PyInstaller, *Using Spec Files / hiddenimports* — https://pyinstaller.org/en/stable/spec-files.html

**İkincil**
- Nielsen Norman Group, *Response Times: The 3 Important Limits* (0,1 s / 1 s / 10 s) — https://www.nngroup.com/articles/response-times-3-important-limits/
- Baymard Institute, *Line Length Readability* (45–75 karakter) — https://baymard.com/blog/line-length-readability
- UXPin, *What Is Progressive Disclosure in UX? (2026)* — https://www.uxpin.com/studio/blog/what-is-progressive-disclosure/
- AI UX Playground, *Progressive Disclosure — Outputs pattern* — https://aiuxplayground.com/pattern/progressive-disclosure/
- Lollypop Design, *Progressive Disclosure UX: Guide + Examples* (2025-05) — https://lollypop.design/blog/2025/may/progressive-disclosure/
- Groovyweb, *UI/UX Design Trends for AI Apps (2026)* — https://www.groovyweb.co/blog/ui-ux-design-trends-ai-apps-2026

**Depo içi (birincil kanıt)**
- `src/entropy/ui/widgets/report_center.py:234-238, 802-807, 811-817, 849, 867, 1076-1098, 1146-1160, 1199-1287`
- `src/entropy/ui/widgets/report_inbox.py:51-83, 122`
- `src/entropy/ui/widgets/reports_viewer.py:47, 86-87, 385, 396`
- `src/entropy/ui/widgets/task_board_widget.py:39, 60-72, 790, 806-808`
- `src/entropy/ui/design/qss.py:105-118, 145-157`
- `src/entropy/core/agy_bridge.py:2360-2384`; `src/entropy/core/claude_bridge.py:2320-2360`
- `src/entropy/memory/obsidian/vault_manager.py:426-503`
- `src/entropy/memory/report_watcher.py` (yalnız indeksler, rapor üretmez)
- `src/entropy/agents/tasks.py:1685-1698, 1994-2004`; `src/entropy/agents/harness.py:1030-1048, 1078-1086, 1853`
- `src/entropy/agents/pr_flow.py:5-6, 15, 40-65, 205-245`
- `src/entropy/core/slash_commands.py:238-251, 689-707, 708, 839-940`
- `src/entropy/ui/widgets/core_visualizer.py:1-8`; `src/entropy/ui/design/prefs.py:91-95`; `src/entropy/ui/modes/zen_mode.py:156-158, 473, 1337`
- `docs/adr/ADR-0004-faz11-paket-tasima-yok.md`; `docs/adr/ADR-0007-claude-bg-ertelendi.md`
- `docs/STATE.md` §2.4, §2.5, §2.6, §3; `docs/reports/2026-09-10_Faz12_Arastirma_B_Depo_Denetimi.md` §6
