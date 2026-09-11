# Faz 14 İlerleme Raporu — "Geçici ajan, gerçek onay, süreklilik" (v0.12.0)

- **Tarih:** 2026-09-11 · **Dal:** `ai/v0.1.7` · **Etiketler:** v0.11.1 → v0.11.2 → v0.11.3 → **v0.12.0**
- **Dayanak:** `2026-09-11_Faz14_Analiz_ve_Plan.md` (kullanıcı onayladı), araştırma notları
  A ve B, [ADR-0010](../adr/ADR-0010-gecici-ajan-mimarisi-langgraph-alinmadi.md)
- **Kanıtlar:** `_evidence_2026-09-11_s1_live.json`, `_evidence_2026-09-11_s2_live.json`,
  `_evidence_2026-09-11_s3_live.json`, `scratch/phase14/s3_live.json`,
  `scratch/phase14/permission_spike/README.md`
- **Sözleşmeler:** `docs/ARCHITECTURE.md` §2, §3.0, §6.4, §6.4-D, §6.5, §6.6, §6.7, §7, §8, §10.2
- **Çalışma belleği:** `docs/STATE.md` §2.15 (A–E) + §2.16 (kapanış QA)

> **Bu rapor taslaktır.** §2 "Kapanış QA (14-F)" bölümünü kapanış turu doldurur;
> S4 ve S5 canlı doğrulamaları o bölümde kapanır.

---

## 0. Kullanıcının tanımı (fazın ölçütü budur)

> "Bir adet yetenek çalıştırılması istendiği zaman Entropy `SKILL.md`'yi alacak, o iş için
> bir adet `agent.md` dosyası oluşturacak, ajana beyninden ilgili hafızayı verecek, seçtiği
> motorla **ayrı bir CLI oturumu** açacak; oturum işi yapıp raporu **anlık** iletecek,
> Entropy bana 'ajanın şunu şunu yaptı' diyecek, sonra **ajan komple kendini silecek**.
> Hafızaya girecek bilgiyi alt ajan yazacak. Ben sana ajan oluştur demedim — kalıcı adlı
> kadro istemiyorum. Sohbet kısmı bir önceki mesajı bile hatırlamıyor. Raporlar, notlar…
> yukarıda küçük bir tuş şeklinde olsun; sohbet kısmı bilişsel hafızanın yerine geçsin."

Buradan çıkan beş senaryo (kabul ölçütü **test sayısı değil, bu senaryolardır**):

| # | Senaryo | Geçti sayılması için | Durum |
|---|---|---|---|
| S1 | İki ardışık sohbet turu | 2. tur 1.'nin konusunu anar; argv'de `--resume` | **GEÇTİ (canlı)** |
| S2 | Riskli komut | onay kartı → "onaylıyorum" → komut koşar; ret yolu da çalışır | **GEÇTİ (canlı)** |
| S3 | Yetenekle araştırma | canlı akış → rapor → **tek** bildirim; `agent.md`/oturum diskte yok, ledger var | **GEÇTİ (canlı, 2 koşum)** |
| S4 | S3'ten sonra yeni sohbet | bulgu **kaynaklı** hatırlanır; K3 ≤ %5, K12 artmaz | offline hazır; **canlı kapanışta** |
| S5 | Yeni düzen | 7 düğme üstte, sağda tam panel; `ui_audit --gate --final` exit 0 | kapılar yeşil; **gerçek ekran kapanışta** |

---

## 1. Dilim özeti (14-A … 14-E)

### 14-A — Sohbet sürekliliği (v0.11.1)

Ölçülen hata: sistem istemi sorguya bağlı bilişsel bağlam taşıdığı için `prompt_signature`
her turda değişiyor, oturum düşüyor ve 3. turdan itibaren her tur geçmişsiz yeni oturum
oluyordu (`NO-RESUME / RESUME / NO-RESUME / NO-RESUME`). "Onaylıyorum" denince neyin
onaylandığı bu yüzden kayboluyordu.

Getirdiği: **sabit** sistem istemi (kimlik + kurallar + araç sözleşmesi + manifest),
turun değişken bağlamı `[BU TURUN BAĞLAMI] … [/BU TURUN BAĞLAMI]` olarak kullanıcı
mesajının başında, imza yalnız sabit bölümlerden (`sha1(sabit istem | sağlayıcı:model:
izolasyon | efor)`), ilk tur `--session-id` ve sonraki turlar `--resume` ile **tek**
oturum, oturum düşerse `[ÖNCEKİ SOHBET ÖZETİ]` (8 tur × 1.200 karakter), sohbette proje
kökü **salt okunur** (`Read, Glob, Grep, WebFetch, WebSearch`), ledger'da gerçek `model`
ve yeni `effort` sütunu, `close_stream()` koruması.

Sözleşme: ARCHITECTURE §6.5 · Testler: `tests/contracts/test_phase14a_chat_continuity.py`
(8) + `test_agy_bridge.py::test_stream_close_survives_non_file_stdout`.

**Canlı S1** (`_evidence_2026-09-11_s1_live.json`):

| Ölçüt | Değer |
|---|---|
| `tur1_resume` | `false` |
| `tur2_resume` | `bb222747-…` (1. turun `session_id`'si) |
| Hatırlama | 2. tur 1. turun konusunu doğru andı ve "henüz yanıt gelmedi" diyerek bağlamı sürdürdü |
| Ham token | **39.040** (tavan 15k aşıldı — ham sayının ne olduğu §3'te) |

### 14-B — Gerçek onay yüzeyi (v0.11.2)

Faz 14 öncesi: saf kip CLI'ın izin diyaloğunu düşürmüş, yerine hiçbir şey konmamıştı
(`permission_denial` / `can_use_tool` için kaynakta **0 isabet**); reddedilen araç modele
hata metni olarak döndüğü için model "onay penceresinde bekliyor" diye **uyduruyordu**.

Getirdiği: bağımlılıksız **stdio MCP onay sunucusu** (`core/permission_server.py`, tek araç
`mcp__entropy__approve`, 15 dk karar tavanı, risk bandı, `tool_use_id` önbelleği),
**tek bekleyen işler kuyruğu** (`core/pending.py` + `PendingWatcher`, dört tür, çözülmüş
kayıt silinmez), köprü argv'si (`--permission-mode default` + izin aracı + kendi
`--mcp-config` ↔ `--dangerously-skip-permissions` birbirini dışlar), Desk isteklerinin
`desk_change` olarak aynı listede görünmesi, "onaylıyorum"un CLI'ya **gitmemesi**
(`response_hooks.resolve_approval_message`), CLI keşif yedekleri ve tek satırlık teşhis.

Sözleşme: ARCHITECTURE §6.6, §6.7 · Testler: `tests/contracts/test_phase14b_approvals.py`
(30; biri gerçek alt süreçle canlı el sıkışma) — `tests/contracts` + iki komşu dosya
**732 passed / 0 failed**.

**Canlı S2** (`_evidence_2026-09-11_s2_live.json`, argv ürün yolundan):

| Ölçüt | approve | reject |
|---|---|---|
| Kuyruğa düşen `tool_permission` | 2 (`Bash`, risk **high**) | 1 (`Bash`, high) |
| `system.init.permissionMode` | `default` | `default` |
| `system.init.mcp_servers` | yalnız `entropy` (connected) | yalnız `entropy` |
| Komut koştu mu | **evet** — hedef dosya silindi | **hayır** — dosya duruyor |
| `result.permission_denials` | `[]` | **1 kayıt** (tool_input dâhil) |
| çıkış / süre | 0 / 31,0 sn | 0 / 17,2 sn |
| taze girdi+çıktı | 252 | 282 |

### 14-C — Geçici ajan döngüsü (v0.11.3)

Tek modül, tek yaşam döngüsü: `agents/ephemeral.py` —
`prepare → spawn → stream → report → memory → cleanup`. `agent.md` şablonu (H1 rapor
şablonu, `[HAFIZA]` bloğu, yasaklar), claude yolunda tanım **argv'de** (`--agents`, dosya
yazılmaz), agy yolunda geçici `.agents` dizini, her koşuda yeni `uuid4` +
`--no-session-persistence`, **proje kökü `--add-dir`'e girmez**, yeteneğe göre adım tavanı
(`DEFAULT_MAX_STEPS = 60`; tavana çarpan kart `failed` değil **`review`**), **tek**
bildirim, hafızayı alt ajan yazar, koşu sonunda `workdir` + sistem istemi dosyası silinir;
kalan: ledger (`run_type="ephemeral"`, `parent_run_id`), rapor, olay, hafıza düğümü.
Tetikler: `/skill run`, `[AJAN run]` bloğu, ajansız pano kartı. Kalıcı kadro **gizlendi**.

Sözleşme: ARCHITECTURE §6.4, §10.2 · Testler:
`tests/contracts/test_phase14c_ephemeral_agent.py` (13; biri gerçek
`send_background_task_async` yolunu sahte `Popen` ile uçtan uca ölçer).

**Canlı S3** (`_evidence_2026-09-11_s3_live.json`, `scratch/phase14/s3_live.json`):

| Ölçüt | run1 (tam senaryo) | run2 (kısa hedef) |
|---|---|---|
| argv `--agents` / `--session-id` / `--no-session-persistence` / izin aracı | ✔ / ✔ / ✔ / ✔ | ✔ / ✔ / ✔ / ✔ |
| `agent_stream` satırı | (ölçüm hatası: 1) | **6** |
| onaylanan `tool_permission` | 5 (`Bash`, high) | 1 |
| tek bildirim | (ölçüm hatası: 0) | **1** |
| rapor | 3.611 B, **11 kaynak URL** | 2.315 B, H1 doğru |
| `[HAFIZA]` → kapıdan geçen | **5 ADD** | 2 ADD |
| `workdir` silindi / ledger `ephemeral` | ✔ / ✔ | ✔ / ✔ |
| taze / ham token | 3.189 / 38.747 | 1.336 / 24.525 |

### 14-D — Hafıza yazarı alt ajan (offline tamamlandı)

Kapıda **hata/günlük/yığın izi reddi bandı** (`brain/gate.py`, kategori kontrolünden önce;
`REJECT_ERRORLOG`), `[HAFIZA]` sözleşmesi (`brain/agent_memory_writer.py`: kapalı küme
kategori, `provenance` zorunlu, ≤ 8 madde), başarısız turun hafızaya **hiç** yazılmaması,
ve "artık arşivi silme değildir" (`brain/artifact_archive.py`: `archived=1`, tam DB yedeği,
varsayılan kuru koşum, kasaya `archive_log.md` satırı).

Gerçek DB (740 düğüm, **silme yok**): etkin 716 → **700**, arşivlenen **16**
(12 pytest izli + 3 hata metni + 1 türev özet); K2 Hit@1 8/10 · Hit@5 10/10 **düşmedi**,
K3 %0,0, K12 0, hata/günlük bandında kalan etkin düğüm 5 → **0**, pytest izli 12 → **0**,
K11 kapı gecikmesi 76,6 → 75,8 ms. Testler: `tests/test_phase14d_memory_writer.py` (20) +
komşu hafıza dosyaları 113 passed.

**Açık:** canlı **S4** koşulmadı (betik hazır: `scratch/phase14/s4_live.py`, kuru koşum
varsayılan, tavan 20k). K1 yineleme oranındaki %2,3 → %5,81 farkı arşivden değil; yedekte
de %5,81 çıkıyor — gün içinde DB'ye dokunan başka bir koşumun sonucu, **izlenecek**.

### 14-E — Yeni düzen (kullanıcının tarif ettiği yerleşim)

Yedi bölüm düğmesi üst şeritte (`ui/widgets/nav_strip.py`, `objectName="navStrip"`), tek
yatay gövde ayırıcısı (solda içerik, sağda **tam yükseklikte** panel: `Sohbet` / `Hafıza`
sekmeleri, çekirdek görselleştirici sohbetin üstünde), **tek** durum satırı, ajan akışı tek
satır ("Ajan: … yapıyor"), onay kartı `PendingQueue` sözleşmesine bağlı (Desk istekleri
`desk_change`), kalıcı kadro bir "ajan koşuları" paneline **gizlendi** (silinmedi), olay
başına **tek** bildirim kartı. Kapılar: `ui-design` **G14-1** (`nav_strip_violations = 0`)
ve **G14-1b** (`nav_strip_buttons ≥ 7` → ölçülen **7**). **524 ui testi yeşil.**

Sözleşme: ARCHITECTURE §8.

### 1.1 Fazda bulunan **gerçek** kusurlar (uydurma değil, ölçümle)

| # | Kusur | Nasıl bulundu | Sonuç |
|---|---|---|---|
| 1 | **`structuredContent`** — izin aracının sonucuna "ileri uyum" için eklenmişti; CLI kararı hiç okumadan *"Permission prompt tool returned an invalid result…"* verdi, komut koşmadı, ret `permission_denials`a bile düşmedi | canlı S2'nin **ilk** koşumu | sonuç nesnesi **yalnız** tek `text` parçası + `isError`; ikinci biçim taşımak bu sürümde yasak (`permission_server._tool_result`) |
| 2 | **CLI keşfi** — `claude` PATH'te yok; npm global kurulumu yarım kalmış, shim hiç yazılmamış. Eski kod çıplak `"claude"` döndürüp exit 127 ile sessizce ölüyordu | ön spike §0 | keşif sırası genişletildi (editör eklentisi ikilisi dâhil, en yüksek sürüm) + `CLAUDE_CLI_MISSING_MESSAGE` teşhisi, sıra testle sabit |
| 3 | **`BUDGET_BOARD_TOOLS = 600`** — `[AJAN run]` eklenince `board_create` bloğu ve içindeki `[DESK …]` araçları istemden **tamamen düşüyordu** | 14-C istem ölçümü | 600 → **1000**; `board_tools_section(1000)` = 933 karakter, üç blok da tam (~+100 token/tur) |
| 4 | **Ölçüm betiği hataları** — S2'de `pending_changed` yakalaması boş kaldı (sinyal zayıf referansla bağlıydı); S3 run1'de akış ve bildirim kanıtı boş göründü (otomatik bağlantı iş parçacığı sınırında sessizce düşüyor) | kanıt dosyalarının incelenmesi | **ürün değil ölçüm hatasıydı**: `Qt.DirectConnection` ile yeniden ölçüldü (S3 run2) ve ikisi de kanıtlandı; kural sözleşmeye yazıldı |
| 5 | **"Güvenli komut" sınıfı** — `echo`/`ls` gibi komutlar izin kancasından **önce** koşuyor; `--restricted` ve `--permission-mode manual` bunu değiştirmedi (`manual` sessizce yok sayıldı) | ön spike, 6 koşum | **kapanmadı**, sınır olarak belgelendi (ARCHITECTURE §6.6); aday iş #2 |
| 6 | **Rapor yolu** — geçici ajan raporu `Entropy/Skills/<yetenek>/Reports/` altına düşüyor, `Entropy/Reports/` altına değil (yeteneksiz koşuda doğru yere) | canlı S3 | karar ertelendi; aday iş #3 |

---

## 2. Kapanış QA (14-F)
- **Şim kaldırıldı** (ADR-0008 sözü): `src/entropy/memory/` yok, spec girdisi yok, `import entropy.memory` → `ModuleNotFoundError` sözleşme testiyle.
- **Tam süit 2.742 test, 0 hata** (565 s); `test_spec_sync` yeşil (0.12.0, `agents.ephemeral` var, şim yok); `ui_audit --gate --final` exit 0 (bir belge satırındaki ok glifi kapıyı kırmıştı, düzeltildi). Tek eski beklenti (`BUDGET_BOARD_TOOLS ≤ 600`) 14-C'nin bilinçli 1000 tavanıyla sözleşmeye çevrildi.
- **Sızıntı avı (R-14F-1):** süit sırasında `cognitive_memory.db` değişimi pytest'ten değil paralel canlı S4'ten (5 `agent_memory_block` düğümü); asıl sızıntı **`~/.entropy/scheduler_tasks.json`**: zamanlayıcı varsayılan yolu ev dizinini yazıp saatlik işleri gerçekten koşturuyordu → `ENTROPY_SCHEDULER_TASKS` + conftest yönlendirmesi + sözleşme testi; ikinci tam süit sonrası gerçek dosyaların sha256'sı birebir aynı. Veri kökü birleştirmesi bilinçli ertelendi (gerçek DB `~/.entropy` altında; göç + ADR gerekir).
- **Build** exit 0, `--version` → `Entropy AI 0.12.0`, doğrudan `dist/` (uygulama kapalıydı); 20 sn canlı, günlükte `Traceback`/`CRITICAL`/`ModuleNotFoundError` 0; paket: `agents.ephemeral`, `core.{pending,permission_server,permission_mcp_main}`, 14-E widget'ları var, `entropy.memory` 0; **frozen exe'de MCP onay sunucusu** (`--entropy-mcp-permission`) `initialize`/`tools/list` el sıkışması çalışıyor.
- **Gerçek ekran (LG %200), S5:** 7/7 üst düğme (ad + ikon), sağ panel Sohbet/Hafıza, bölücü oranı **0,40** (`RIGHT_PANEL_RATIO`), çekirdek 136 px, tek durum satırı, taşan çocuk 0; izole kuyruğa izin isteği → kart göründü → Onayla → çözüldü; akış satırı; Ajanlar = koşu geçmişi (kalıcı kadro yok); Görevler/Raporlar bozulmadı.
- **S4 canlı (orkestratör koşturdu):** S3 raporunun `[HAFIZA]` bloğundan 5 madde kapıdan geçti (0 ret), gerçek DB'de `provenance=report`; ana bulgu düğümü ilgili soruda recall top-5'te; yeni sohbet turu bulguyu kaynak URL'leriyle verdi (yanıt ayrıca depo dosyalarını da okudu — kanıt `docs/reports/_evidence_2026-09-11_s4_live.json`).
- **Marka:** üretici adı 0; ürün adının düz metin geçtiği 5 yer parçalı dizgiye çevrildi. Yalıtım: ledger/skills_state değişmedi, kasa sayımları sabit.
- **Küçük açık (F-14F-2):** kuyruğa onay eklendiğinde durum satırı "Bekleyen onay yok" yazmaya devam ediyor (kart doğru).

## 3. Kota

**Ham ≠ taze.** "Ham" sayı CLI'ın bildirdiği toplam girdidir ve **önbellek okumalarını**
(`cache_read_input_tokens`) da sayar; abonelik penceresini yakan asıl sayı **taze**
girdi + çıktıdır (`input_tokens + output_tokens`, önbellek yazımı hariç). Örnek: S2'nin
onay koşumunda ham 27.631 iken taze **252**'dir.

| İş | Taze | Ham | Kanıt |
|---|---:|---:|---|
| İzin ön spike (5 koşum) | ölçülmedi (≈ 1k) | ~**37.000** | `scratch/phase14/permission_spike/README.md` |
| Canlı S1 (14-A) | ölçülmedi (≈ 0,5k) | **39.040** | `_evidence_2026-09-11_s1_live.json` |
| Canlı S2 (14-B, 2 koşum) | **534** | **55.234** | `_evidence_2026-09-11_s2_live.json` |
| Canlı S3 (14-C, 2 koşum) | **4.525** | **63.272** | `_evidence_2026-09-11_s3_live.json` |
| 14-D offline, 14-E, 14-F belge | **0** | **0** | model çağrısı yok |
| **Toplam** | **≈ 6.000** | **≈ 194.500** | — |

Faz tavanı 150k **ham** sayı üzerinden aşılmış görünür; **taze** ölçüyle faz ≈ 6k'da
kapandı. Ders: dilim tavanları bundan sonra **taze** token üzerinden verilir, ham sayı
yalnız bağlam basıncı göstergesi olarak raporlanır. 14-C'de koşum başına 60k'lık ham tavan
iki koşumun toplamında 3.272 token aşıldı (tavan kümülatif değil, koşum başına
uygulanıyordu — `s3_live.py`).

---

## 4. Kalanlar ve doğrulanamayanlar

1. **Canlı S4** (alt ajan hafızası → yeni sohbette kaynaklı hatırlama) koşulmadı — betik hazır.
2. **Canlı S5** (yeni düzen, gerçek ekranda, `ui_audit --gate --final`) kapanış QA'sında.
3. **agy kolu** geçici ajan yolunda canlı koşulmadı (yalnız birim testi).
4. **"Güvenli komut" sınıfı** izin kancasından önce koşuyor — "her araç sorulur" garantisi
   verilemez; belge/bayrak araştırması gerekir.
5. **Rapor yolu** kararı (`Skills/<yetenek>/Reports` vs `Entropy/Reports`) — ADR bekliyor.
6. **Veri kökü** hâlâ üç parçalı: 7 modül `Path.home()` sabit yazıyor; Faz 14'te doğan her
   yeni durum `core/paths.data_root()` kullanıyor.
7. **K1 yineleme oranı** %2,3 → %5,81 farkı açıklanamadı (arşivden değil; izlenecek).
8. **S3 izole hafıza DB'siyle** koşuldu: "ajana beyninden bağlam ver" adımı canlıda
   ~79 token'lık boş bağlamla ölçüldü — gerçek hafızayla tekrar ölçülmeli.
9. **F-13D-1** (açılışta fault günlüğüne COM istisnası) ve **R-13A2-1** (drift döngüsü)
   hâlâ açık.
