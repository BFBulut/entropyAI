# ADR-0010 — Geçici ajan mimarisi; LangGraph çalışma zamanı olarak alınmadı, dört desen alındı

- **Durum:** Kabul edildi (Faz 14 açılışı, 2026-09-11) · **Uygulandı: 14-A…14-E**
  (2026-09-11, v0.11.1 → v0.11.3; belge kapanışı 14-F). Kod karşılıkları:
  `agents/ephemeral.py`, `core/pending.py`, `core/permission_server.py`,
  `brain/agent_memory_writer.py`, `ui/widgets/nav_strip.py` — sözleşmeler
  `docs/ARCHITECTURE.md` §6.4, §6.4-D, §6.5, §6.6, §6.7, §8, §10.2.
  LangGraph **alınmadı** (park), dört desen alındı.

### Canlı kanıt özeti (S1–S3, 2026-09-11, `claude` 2.1.268)

| Senaryo | Tarih/saat | Sonuç | Taze / ham token | Kanıt |
|---|---|---|---:|---|
| **S1** sohbet sürekliliği | 2026-09-11 | GEÇTİ — 1. tur `resume=false`, 2. tur aynı `session_id` ile `--resume`, konu doğru anıldı | ölçülmedi / **39.040** | `docs/reports/_evidence_2026-09-11_s1_live.json` |
| **S2** gerçek onay | 2026-09-11 07:08–07:19 | GEÇTİ — onayda komut koştu (dosya silindi), rette koşmadı ve `permission_denials`'a 1 kayıt düştü; yalnız `entropy` MCP sunucusu yüklü | 534 / **55.234** | `docs/reports/_evidence_2026-09-11_s2_live.json` |
| **S3** geçici ajan | 2026-09-11 07:44 ve 07:46 | GEÇTİ — `--agents`/`--session-id`/`--no-session-persistence`/izin aracı argv'de, akış + tek bildirim + H1 raporu, `workdir` silindi, ledger `ephemeral` | 4.525 / **63.272** | `docs/reports/_evidence_2026-09-11_s3_live.json`, `scratch/phase14/s3_live.json` |

**S4** (alt ajan hafızası, canlı) ve **S5** (yeni düzen, gerçek ekran) 14-F kapanış
QA'sında doğrulanacak; 14-D'nin offline kısmı ve 14-E'nin kapıları yeşildir.
- **Bağlam belgeleri:** `docs/reports/2026-09-11_Faz14_Analiz_ve_Plan.md` (§0, §4, §6, §7),
  `docs/reports/2026-09-11_Faz14_Arastirma_A_Mevcut_Mimari_ve_Hata_Izi.md` (§1, §2, §5),
  `docs/reports/2026-09-11_Faz14_Arastirma_B_Istenen_Mimari_ve_Fark_Analizi.md` (§3, §5, §6, §9),
  `docs/reports/2026-09-11_Arastirma_LangChain_LangGraph_LangSmith.md` (§4.1, §5)
- **Akraba kararlar:** [ADR-0003](ADR-0003-hafiza-algoritmasi-mem0-degil.md) (dış kütüphane
  yerine kendi sözleşmemiz — bu ADR onun ikizidir), [ADR-0002](ADR-0002-claude-saf-kip.md)
  (saf kip izin diyaloğunu da düşürmüştü; §"Onay yüzeyi" onu tamamlar),
  [ADR-0001](ADR-0001-desk-ayrimi.md) (tek yönlü akış korunur)

## Bağlam

Kullanıcı 2026-09-11'de istediği döngüyü tek cümlede tanımladı: bir yetenek
çalıştırılması istendiğinde Entropy `SKILL.md`'yi alır → o iş için bir `agent.md`
üretir → ajana beyinden ilgili hafızayı verir → seçili motorla **ayrı bir CLI
oturumu** açar → oturum işi yapar, raporu **anlık** geri iletir → Entropy
"ajanın şunu şunu yaptı" der → **ajan kendini siler**; hafızaya girecek bilgiyi
**alt ajan** yazar. Kalıcı adlı ajan kadrosu (araştırmacı/yazar/analist)
istenmedi.

Ölçülen bugünkü durum bunun tersi: kalıcı kadro (`Entropy/Agents/<ad>/AGENT.md` +
`Board/agents/<ad>/session.json`), oturum imzası rotasyonu, claim kilidi, 8 durumlu
pano FSM'i ve 19 adımlık bir "yetenek koştur → rapor al" zinciri (A notu §2.4).
Bu ağırlığın bedeli ölçüldü: sohbet 3. turdan sonra her turda yeni oturum açıyor
(A notu Ölçüm B), CLI'ın araç izni reddi köprüde hiç işlenmiyor (`permission_denial`
için 0 isabet), başarısız turun hata metni hafızaya düğüm olarak yazılıyor.

Aynı hafta kullanıcı **iki kez** LangChain/LangGraph/LangSmith'in alınıp
alınmayacağını sordu. Cevabın tekrar tekrar aranmaması için karar buraya yazıldı.

## Karar

### 1. Ajan modeli: yetenek başına **geçici** oturum

1. Her yetenek koşusu için `agent.md` **koşu anında üretilir** (küçük, saf Python,
   Qt'siz): girdi `SkillDefinition` + kullanıcı istemi + `AssembledContext`;
   gövde `## Görev / ## Kabul ölçütleri / ## Rapor şablonu / ## Yasaklar`.
   Rapor şablonunun ilk satırı `# H1` olmak zorundadır
   (`core/report_title.derive_report_title` sözleşmesi, ARCHITECTURE §6.3).
2. Claude yolunda tanım **dosyaya yazılmaz**, `--agents <json>` ile argv'de taşınır;
   agy yolunda geçici `.agents/agents/<slug>/agent.md` yazılır ve koşu sonunda silinir.
3. Her koşu yeni uuid alır, kalıcı oturum deposuna **yazılmaz**.
4. **Kalır / silinir** ayrımı: silinen = `agent.md` / geçici dizin, sistem istemi
   dosyası, oturum kaydı. Kalan = ledger satırı, rapor dosyası, `events.jsonl`
   satırları, hafıza düğümü. "Ajan yok oldu, ne yaptığı duruyor."
5. **Kalıcı kadro gizlenir, SİLİNMEZ.** Desk ve pano rostera bağlıdır; silmek
   ADR-0001 sözleşmesini ve FSM'i kırar. Arayüzde ölü yüzey (kalıcı "oturum yok"
   rozeti) gizlenir.
6. **Pano FSM'ine dokunulmaz** (8 durum / 14 olay / 13 geçiş). Geçici koşu yalnızca
   `running → review → done|failed` alt kümesini kullanır.

### 2. Sohbet sürekliliği: tek oturum + **sabit** sistem istemi

Sistem istemi turdan tura değişmez (kimlik + kural + araç sözleşmesi); o turun
bilişsel bağlamı **kullanıcı mesajının başına** blok olarak konur. İmza yalnız
sabit bölümlerden hesaplanır; model/efor değişimi dışında oturum düşürülmez.
Gerekçe ölçümle: bugün `system_prompt = identity + sorguya bağlı bağlam` olduğu
için imza hemen her turda değişiyor ve `--resume` düşüyor.

### 3. Gerçek onay: `--permission-prompt-tool` + stdio MCP

`--permission-prompt-tool mcp__entropy__ask`; Entropy kendi stdio MCP onay
sunucusunu ayrı bir süreç olarak açar (`platform/proc.popen_kwargs` zorunlu —
ARCHITECTURE §4.3), `--mcp-config` + `--strict-mcp-config` ile yalnız onu bırakır.
İstek uygulamada **tek bekleyen işler kuyruğuna** kart olarak düşer (ne / hangi
araç / hangi komut / risk); "onaylıyorum" o isteği çözer.
`--dangerously-skip-permissions` **koşullu** hâle gelir — açıkken izin aracı hiç
çağrılmaz, yani onay kartı hiç çıkmaz.
**Sohbette proje kökü salt okunurdur;** kod değişikliği yalnızca onaylı kart
(worktree) yolundan yapılır.

### 4. Hafızaya **alt ajan** yazar

`MemoryGate.admit` tek kapı olarak kalır (ARCHITECTURE §5.1); değişen **yazar**dır.
Raporu okuyan kısa bir ikinci oturum kapıya verilecek JSON'u üretir; Entropy yalnız
kapıdan geçirir. Kapıya ayrıca "hata metni / yığın izi / günlük" reddi bandı eklenir
(reddedilenler gri kuyruğa düşer, sessizce yutulmaz).

### 5. LangGraph **alınmaz**; dört desen alınır

Ölçüm (PyPI, 2026-09-11):

| Ölçüm | Sonuç |
|---|---|
| Lisans | LangGraph 1.2.11 **MIT** (engel lisans değil) |
| Zorunlu zincir | `langgraph → langchain-core → langsmith`; "yalnız langgraph" kurulumu **yok** |
| Asgari bağımlılık ağacı | bugün 5 → **~18–20 paket** |
| Durum/kontrol noktası biçimi | ikili **msgpack** — Obsidian kasasının insan-okunur `.md` sözleşmesini bozar |
| Sunucu/Studio | `langgraph-api` **Elastic-2.0**; yerel Studio bile LangSmith anahtarı ister (veri dışarı) |
| Token ölçümü | CLI arkalı model sarmalayıcıda **kaybolur** — "kota artışı 0" iddiası ölçülemez |
| Yeniden yazılacak kod | `board_fsm` + `board_events` + `dispatcher` ≈ 1.450 satır + harness'ın bir bölümü |
| PyInstaller | `importlib` ile yüklenen paketler sessizce eksik paketlenir (Faz 10-C'de yaşandı) |

Buna karşılık istenen 7 adımlı döngü LangGraph'sız beş küçük bileşenle yazılıyor ve
parçaların çoğu zaten var (`bus.agent_stream`, `MemoryGate`, `report_title`, ledger).
**LangSmith hiçbir biçimde alınmaz** (tescilli sunucu, veri dışarı, kota limiti);
`claude-agent-sdk`'ya geçilmez (CLI'ya göre yeni yetenek yok).

Ödünç alınan **dört desen** (kod değil, sözleşme):

1. **Yeniden-oynatma güvenliği:** bir adım ya yeniden oynatılabilir ya da açıkça
   "yan etkili, oynatma" diye işaretlenir — CLI çağrısı kota harcadığı için bu
   işaretleme bizde zorunludur.
2. **`interrupt` = onay bekleme semantiği:** duraklama noktası değeri döndürür ve
   devam ederken **tekrar** çalışır; `review` durumunun ve onay kuyruğunun
   idempotentliği bu garantiye bağlanır.
3. **Kota sınırlı fan-out:** paralel genişlik `entropy_max_parallel` ile değil
   kartın token bütçesiyle sınırlanır.
4. **Trace şeması:** ledger'a `parent_run_id` + `run_type ∈ {llm, chain, tool}`
   (OpenTelemetry/LangSmith alan adları, Apache-2.0 sözleşme). Veri
   `~/.entropy/tasks_ledger.db`'de **yerelde** kalır.

## Sonuçlar

- **Kazanç:** yeni bağımlılık 0, kota 0, geri alma bedeli 0; "API anahtarı yok" ve
  "veri yerelde kalır" kuralları tipte kalır; silinecek dosya bırakmayan ajan
  (argv'de doğar) "kendini silme" sözleşmesini bedava sağlar.
- **Bedel:** bilişsel bağlam sistem isteminden kullanıcı mesajına indiği için
  ağırlığı bir tık düşer; onay yüzeyi stream-json/MCP şemasına bağımlıdır, CLI
  sürümü değişirse kırılabilir (bu yüzden sürüm tespitiyle birlikte yazılır);
  kalıcı kadroya bağlı arayüz yüzeyleri gizlenip bakımsız kalma riski taşır.
- **Ölçülemeyen:** MCP onay aracının birebir JSON şeması resmî belgede
  yayımlanmamıştır (B notu §8); 30 sn'lik bağlantı zaman aşımının kullanıcı
  bekleme süresini kapsamadığı **doğrulanmadı**.
  > **14-B güncellemesi (2026-09-11):** şema artık **ölçüldü**
  > (`scratch/phase14/permission_spike/README.md`, 5 canlı koşum): sonuç nesnesi
  > yalnız tek `text` parçası + `isError` taşır, karar o metnin içinde düz JSON'dur,
  > `structuredContent` eklemek koşumu kırar. 30 sn **bağlantı** zaman aşımıdır;
  > 45 sn'lik karar beklemesi sorunsuz geçti, üst sınır hâlâ ölçülmedi.
  > Ayrıca ölçüldü: CLI'ın yerleşik "güvenli komut" sınıfı izin kancasından **önce**
  > koşar; "her araç sorulur" garantisi verilemez (ARCHITECTURE §6.6).
- Faz 14 dilimleri bu karara dayanır: 14-A (süreklilik), 14-B (onay),
  14-C (geçici ajan), 14-D (hafıza yazarı), 14-E (düzen), 14-F (kapanış).

## Geri alma

- Geçici ajan döngüsü: kalıcı kadro **silinmediği** için geri dönüş, geçici üreticiyi
  devre dışı bırakıp `--agents` enjeksiyonunu eski kadroya döndürmektir (tek bayrak).
- LangGraph: karar yeniden açılmak istenirse yol **izole bir venv'de ~10k'lık spike**
  ölçümüdür (modül sayısı + kukla `.exe` boyutu); `pyproject.toml` spike sırasında
  değişmez. Kabul eşiği: msgpack kontrol noktası kasa sözleşmesini bozmadan
  `.md`'ye yazılabiliyorsa ve token ölçümü korunuyorsa yeniden tartışılır.
