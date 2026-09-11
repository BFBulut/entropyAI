# Araştırma Notu — LangChain, LangGraph, LangSmith: Entropy AI'da iş yapar mı?

- **Tarih:** 2026-09-11
- **Sürüm bağlamı:** v0.11.0 kapanışı, dal `ai/v0.1.7`
- **Kip:** salt okunur araştırma (kod/test/kasa/ayar değişmedi, model çağrısı yapılmadı)
- **Soru (kullanıcı):** "langchain, langgraph, langsmith konularını detaylıca araştır;
  projemizde iş yapar mı? ücretsiz repoları var diye biliyorum."
- **Emsal karar:** [ADR-0003](../adr/ADR-0003-hafiza-algoritmasi-mem0-degil.md) —
  *kütüphane değil algoritma alınır.*

---

## 1. Üç cümlelik yanıt

LangChain ve LangGraph **gerçekten MIT lisanslı ve ücretsizdir** (kullanıcının hatırladığı
doğru), ama asıl işi yapan ikisi değil; LangSmith'in **sunucusu tescillidir** ve self-host
yalnızca Enterprise planındadır, LangGraph'ın çalışma zamanı sunucusu `langgraph-api` ise
**Elastic-2.0** ile gelir ve yerel geliştirme sunucusu bile LangSmith hesabı ister. API
anahtarsız çalışma teknik olarak **mümkündür** (CLI arkalı `BaseChatModel` sarmalayıcısı
yazılabilir; hatta 2026-02-10'da yayımlanmış hazır bir örneği var), fakat Anthropic'in
Agent SDK belgesi üçüncü taraf ürünlerde abonelik oturumu sunmayı **önceden onay şartına
bağlamıştır** — bu, LangChain'e geçmenin kazandıracağı şeyi değil, bizim zaten kurduğumuz
CLI köprüsünün sınırını ilgilendiren bir uyarıdır.

Bizim tarafta LangGraph'ın satacağı dört özelliğin (checkpointer, interrupt/insan onayı,
durable execution, alt-graf) **dördü de ölçülebilir biçimde zaten yazılmıştır** —
`board_fsm.py` (8 durum / 14 olay / 13 geçiş), `board_events.py` (yalnız-ekleme
`events.jsonl` + projeksiyon karması), `harness.py` (2.661 satır: kontrol noktası, bütçe,
kanıtlı bitiş), `brain/checkpoints.py` (445 satır, `resume_section`) — dolayısıyla LangGraph
bize yeni yetenek değil, **ikinci bir çalışma zamanı** getirir.

Önerim ADR-0003 ile birebir tutarlıdır: **Seçenek A — almıyoruz, desen ödünç alıyoruz**
(özellikle `interrupt`/dayanıklı yürütme sözleşmesi ve trace şeması), gözlemlenebilirlik
için de dış SaaS yerine **yerel OpenTelemetry semantik sözleşmesini** kendi ledger'ımıza
uyduruyoruz; kota bedeli 0.

---

## 2. Ne nedir, lisans ve 2026 durumu

Ölçüm yöntemi: PyPI JSON API ve GitHub API, 2026-09-11'de çekildi.

| Bileşen | Depo / paket | Sürüm (2026-09-11) | Lisans | Ne yapar | Bedava mı? |
|---|---|---|---|---|---|
| LangChain | `langchain-ai/langchain` (146.093 yıldız) | `langchain` **1.4.0** | **MIT** | `create_agent` + middleware; 1.0'dan beri **LangGraph çalışma zamanı üstüne** kuruludur | Evet, tamamen |
| LangChain çekirdek | `langchain-core` | **1.6.2** | **MIT** | mesaj/model/araç soyutlamaları (`BaseChatModel`) | Evet |
| LangGraph | `langchain-ai/langgraph` (41.414 yıldız) | `langgraph` **1.2.11** | **MIT** | durum grafı, `StateGraph`, `Send`/map-reduce, alt-graf, `interrupt`, checkpointer | Evet |
| LangGraph kalıcılık | `langgraph-checkpoint` 4.2.0, `langgraph-checkpoint-sqlite` 3.1.1 | — | MIT (depo `libs/checkpoint*`) | `SqliteSaver` ile yerel dosya kalıcılığı | Evet |
| deepagents | `langchain-ai/deepagents` (29.295 yıldız) | **0.7.13** | **MIT** | "pilleri dahil" ajan harness'i (planlama, dosya sistemi, alt ajanlar) | Evet |
| **LangGraph Platform sunucusu** | `langgraph-api` | **0.14.0** | **Elastic-2.0** | graf'ı API olarak koşturan sunucu, kuyruk, cron, Studio arka ucu | **Hayır — ELv2, "hizmet olarak sunma" yasak** |
| `langgraph-cli` | `langgraph-cli` 0.4.31 | — | MIT (rozet) | `langgraph dev` komutu; **ama çalıştırdığı sunucu `langgraph-api`dir** | Kısmen |
| **LangSmith** (ürün) | — | — | **Tescilli** | izleme, değerlendirme, istem yönetimi, Studio web arayüzü | **Hayır** |
| LangSmith istemcisi | `langchain-ai/langsmith-sdk` (1.049 yıldız) | `langsmith` **0.12.4** | **MIT** | yalnızca istemci; veriyi LangSmith sunucusuna gönderir | SDK evet, hizmet hayır |

**LangSmith fiyatı (langchain.com/pricing-langsmith, 2026-09-11):** Developer $0 —
**ayda 5.000 temel trace**, **1 koltuk**, yalnız topluluk desteği; Plus $39/koltuk/ay,
10.000 trace; Enterprise özel fiyat. **Self-host ve hibrit yalnızca Enterprise'da** ve
geçerli bir lisans anahtarı ister (support.langchain.com/articles/7011309930).
Kullanım ücreti: LCU $1,50, LSU $1,00.

### 2.1 "Ücretsiz repoları var" iddiasının doğrulanması

**Kısmen doğru, ve ayrım tam olarak kritik yerden geçiyor.**

- **Doğru olan:** `langchain`, `langchain-core`, `langgraph`, `langgraph-checkpoint*`,
  `deepagents`, `langsmith` (SDK) hepsi MIT, ticari kullanımda serbest, ücret yok.
- **Doğru olmayan beklenti:** "LangSmith'in de ücretsiz reposu var" — açık olan yalnızca
  **istemci kütüphanesidir**; izleme arayüzü, depolama ve değerlendirme motoru kapalı
  kaynaktır ve verinin LangChain'in bulutuna (US ya da EU) gitmesini gerektirir. 2026
  Mayıs'ta US Cloud arka ucu ClickHouse'tan tescilli "SmithDB" motoruna geçmiştir.
- **İkinci tuzak:** LangGraph'ı "ücretsiz MIT" diye alıp `langgraph dev` / LangGraph
  Studio'yu kullanmaya kalkarsak iki kapıya birden takılırız: çalışan sunucu
  **Elastic-2.0** (`langgraph-api` PyPI meta verisi: `license: Elastic-2.0`) ve resmî
  yerel sunucu belgesi **"Before you begin, ensure you have: An API key for LangSmith"**
  diyor. Yani "yerel" sunucu bile hesapsız açılmıyor.
- **Üçüncü tuzak (bizim için asıl önemli olan):** `langchain-core`'un **zorunlu**
  bağımlılıkları arasında `langsmith<1.0.0,>=0.3.45` vardır. Yani LangChain kurulduğunda
  LangSmith istemcisi **kaçınılmaz olarak** paketlenir. İzleme varsayılan olarak kapalıdır
  (`LANGSMITH_TRACING=true` gerekir — SDK README'si), ama bir ortam değişkeni ile
  dışarıya veri akıtabilen bir istemciyi PyInstaller paketine koymak, "veri yerelde kalır"
  sözleşmemiz açısından ayrıca gerekçe ister.

---

## 3. Kilit soru: API anahtarı olmadan çalışır mı?

**Kesin cevap: Evet, teknik olarak çalışır — ama kazanılan şey bizim zaten sahip
olduğumuz şeydir, kaybedilen şey ise ölçüm ve sadeliktir.**

### 3.1 Teknik yol açıktır

`langchain-core`'un model soyutlaması HTTP istemcisi değil, **soyut sınıftır**:
`BaseChatModel._generate` / `_stream` implemente edilir; içi ne isterse o olabilir,
alt süreç de olabilir. Bunun kanıtı varsayım değil, yayımlanmış bir pakettir:

> **`langchain-claude-code-cli` 0.1.0, yayım 2026-02-10, MIT.** `ChatAnthropic` için
> "drop-in replacement"; API anahtarı yerine Claude Pro/Max aboneliğini kullanır,
> altta Claude Code CLI'yı çağırır. Desteklediği: `invoke`/`stream`/`batch`,
> sistem mesajı, `bind_tools()`, `with_structured_output()`, genişletilmiş düşünme,
> efor seviyeleri. **Desteklemediği:** token kullanım ölçümü ("CLI çağrı başına
> metrik yayımlamıyor"), `temperature`/`top_k`/`top_p` (kabul edilir, yok sayılır),
> stop dizileri, ses/video girdi. Ek maliyet: **çağrı başına alt süreç yükü.**

Bu paket bizim için hem iyi hem kötü haberdir:

- **İyi:** "API anahtarsız LangChain" bir hayal değil, çalışan bir desen.
- **Kötü:** Bu paketin listelediği kayıpların **ikisi bizim için kritiktir**.
  (a) **Token ölçümü yok** — oysa bizim `core/task_ledger.py` (544 satır) ve
  `harness.py`'deki bütçe mantığı (`_budget`, `_spend`, `_remaining_budget`,
  `estimate_subcard_tokens`) tam olarak kota muhasebesi üzerine kuruludur; LangChain
  katmanı bu ölçümü taşımaz, biz zaten CLI'nın kendi çıktısından topluyoruz.
  (b) **Alt süreç yükü çağrı başınadır** — bizim mimarimiz ise ajan başına **kalıcı
  oturum** (`AgentSessionStore`, `session_id`/`conversation_id`, `sha1(istem|model|efor)`
  imzası) tutarak bu yükten kaçmak için tasarlandı.

### 3.2 Asıl mimari itiraz: araç döngüsü zaten CLI'nın içinde

LangGraph'ın ana satış noktası "model → araç düğümü → model" döngüsünü sizin adınıza
yönetmesidir. Bizde bu döngü **CLI'nın içinde** koşuyor: Claude Code kendi Read/Write/
Bash/Glob araçlarını kendi ajan döngüsünde çalıştırıyor; biz dışarıdan yalnız
**sonucu** ve onaylı `[DESK]`/`[PANO]` bloklarını görüyoruz
(`agents/board_tools.py`: `AGENT_TOOLS` 4 araç + `ENTROPY_TOOLS` 1 araç).
Yani LangGraph'ı araya koyarsak **iki ajan döngüsü iç içe** çalışır: dışta LangGraph'ın
grafı, içte CLI'nın kendi harness'i. LangGraph'ın `ToolNode`'u bizim için ölü ağırlıktır,
çünkü aracı biz çağırmıyoruz.

### 3.3 Claude Agent SDK — abonelikle çalışır mı?

`claude-agent-sdk` **0.2.152, MIT**, bağımlılıkları hafif (`anyio`, `jsonschema`, `mcp`,
`sniffio`). Teknik olarak Claude Code'un ajan döngüsünü kendi sürecimizde koşturur.
Ancak resmî genel bakış sayfası (code.claude.com/docs/en/agent-sdk/overview,
2026-09-11'de okundu) şu notu içeriyor:

> "Unless previously approved, Anthropic does not allow third party developers to offer
> claude.ai login or rate limits for their products, including agents built on the Claude
> Agent SDK. Use the API key authentication methods described in the Quickstart instead."

**Yorum (dikkatli):** bu cümle *üçüncü taraf geliştiricinin kendi ürününün kullanıcılarına*
claude.ai oturumu/limitleri **sunmasını** kısıtlar. Entropy AI dağıtılmış bir hizmet değil,
kullanıcının kendi makinesinde kendi kurduğu ve kendi oturumunu kullandığı bir masaüstü
kabuğudur; aynı sayfa, başka dillerden ajan döngüsünü sürmek için **"run the CLI as a
subprocess with the `-p` flag and `--output-format json`"** yolunu açıkça önerir — bizim
bugün yaptığımız tam olarak budur. Yine de bu, hukuki bir görüş değildir ve
**doğrulanamayanlar** listesinde yerini alır (§7).

**Karar açısından sonucu:** Agent SDK'ya geçmek bize CLI'ya göre yeni bir yetenek
vermiyor (aynı araçlar, aynı oturumlar, aynı hooks), buna karşılık yukarıdaki not bir
belirsizlik ekliyor. **Geçiş için gerekçe yok.**

---

## 4. Bizde var/yok — özellik özelliğe karşılaştırma

Sütunlar: LangGraph/LangSmith özelliği → bizdeki karşılığı (dosya kanıtı) → LangGraph'a
geçmenin **kazancı** → **bedeli**.

| Özellik | Bizde | Kanıt | Kazanç | Bedel |
|---|---|---|---|---|
| Durum makinesi | **VAR** | `agents/board_fsm.py` — `STATUSES` 8, `EVENTS` 14, `TRANSITIONS` 13, `transition()`, `InvalidTransition` (canlı Python ile sayıldı) | Yok; grafımız zaten tipli ve testli | Yeniden yazım + 2.573 testin bir kısmının göçü |
| Checkpointer / kalıcılık | **VAR** | `brain/checkpoints.py` 445 satır (`write_checkpoint`, `read_checkpoint`, `resume_section`, `parse_checkpoint_block`) + `agents/harness.py:1086 record_checkpoint` | `SqliteSaver` hazır gelir; şema bakımı onlarda | Kontrol noktalarımız **insan-okunur `.md`**; LangGraph'ınki `ormsgpack` ikili. Kasa/Obsidian sözleşmesini bozar |
| Yalnız-ekleme olay günlüğü + zaman yolculuğu | **VAR** | `agents/board_events.py` 515 satır; şema `{schema_version, seq, ts, correlation_id, task_id, attempt_id, actor, action, idempotency_key, payload}`, `projection_hash` = kanonik JSON + SHA-256 | LangGraph'ın `get_state_history()` benzeri | Bizimki denetlenebilir ve `TASKBOARD.md`'ye türeyebiliyor; ikili checkpoint türetemez |
| `interrupt` / insan onayı | **VAR** | `board_fsm`: `review → done` **yalnızca** `actor="human"` + kanıt; kanıtsız `board_finish` reddedilir | LangGraph'ın `interrupt()` API'si daha genel | Bizimki **ürün kuralını** (kanıtlı bitiş) tipte zorluyor; genel API bu kuralı zorlamaz |
| Durable execution (çökme sonrası devam) | **VAR (kısmi)** | `agents/dispatcher.py:519` — `reconcile()` açılışta önce koşar (`bootstrap.start_board_dispatch`, `main.py:160-163`); sahiplenme `claims/<id>.lock` `O_CREAT\|O_EXCL` | LangGraph süper-adım düzeyinde otomatik devam eder | LangGraph dayanıklılığı **determinizm** varsayar; bizim düğümlerimiz CLI alt süreçleridir, yeniden oynatma kota harcar |
| `Send` / map-reduce, alt-graf | **KISMEN** | `harness.py` alt kart üretimi + `_terminate_children`, `estimate_subcard_tokens`; paralellik `entropy_max_parallel` (varsayılan 2) | Dinamik fan-out API'si daha olgun | Bizim paralelliğimiz **kota ile sınırlıdır**, graf genişliğiyle değil; fan-out kazanç değil risk |
| Araç çağrı döngüsü | **GEREKSİZ** | Döngü CLI içinde; `board_tools.py` `AGENT_TOOLS` 4 + `ENTROPY_TOOLS` 1, taşıma `[PANO <araç>] {json} [/PANO]` | — | İç içe iki ajan döngüsü (§3.2) |
| İzleme / trace | **VAR (yerel)** | `core/task_ledger.py` 544 satır, `~/.entropy/tasks_ledger.db`; `core/perf_history.py`; rapor merkezi (`ui/widgets/report_center.py`); `core/crash_log.py` | LangSmith'in zaman çizelgesi arayüzü olgun | Veri **dışarı** çıkar; ücretsiz katman **5k trace/ay, 1 koltuk**; self-host Enterprise |
| Değerlendirme (eval) | **VAR (yerel)** | K1–K12 ölçüm paketi testte tutulur (ADR-0003 "Sonuçlar"); beyin kör testi Hit@1 8/10, Hit@5 9/10, 316 ms | LangSmith dataset/eval yönetimi | Bizim ölçütlerimiz ürün-özel (yenilik oranı, öz-amplifikasyon); genel eval aracı bunları ölçmez |
| İstem yönetimi | **VAR** | Kaynak tek: kasa `Entropy/Agents/<ad>/AGENT.md` → `agents/compile.py` iki sağlayıcı biçimine derler | Sürümlenmiş istem deposu | İstem kullanıcının Obsidian kasasındadır; bulut deposu bu sözleşmeyi böler |

**Net okuma:** on satırdan **yedisinde bizde karşılık var ve karşılığımız ürün kuralını
tipte zorluyor**; LangGraph'ın karşılıkları daha genel ama kuralımızı taşımıyor.
LangGraph'ı almak = 8 durum/14 olaylık sözleşmeyi ikinci bir çalışma zamanının
diline çevirmek. Bu, ADR-0003'teki aynı hatanın grafiksel sürümüdür.

### 4.1 Paketleme ağırlığı (ölçülen)

PyPI wheel boyutları (2026-09-11, Windows amd64 / py3-none-any):

| Paket | Sürüm | Wheel |
|---|---|---:|
| `langchain` | 1.4.0 | 0,16 MB |
| `langchain-core` | 1.6.2 | 0,57 MB |
| `langgraph` | 1.2.11 | 0,25 MB |
| `langsmith` (zorunlu) | 0.12.4 | 0,77 MB |
| `langgraph-checkpoint` + `prebuilt` + `sdk` | — | 0,46 MB |
| Yeni geçişli bağımlılıklar (`orjson`, `zstandard`, `ormsgpack`, `xxhash`, `uuid-utils`, `httpx`, `httpx2`, `jsonpatch`, `tenacity`, `langchain-protocol`, `websockets`, `requests-toolbelt`, `distro`) | — | ~1,27 MB |
| **Toplam (sıkıştırılmış)** | | **~3,5 MB** |

Boyut **sorun değil**. Asıl risk ARCHITECTURE.md §2'de yazılı olan kuraldır:

> "`EntropyAI.spec` hiddenimports bir dizgi listesidir. Bir paket yalnızca `importlib`
> ile çağrılıyorsa PyInstaller'ın statik tarayıcısı göremez ve `.exe` **sessizce eksik**
> paketlenir (Faz 10-C'de worktree/PR/şablon/makbuz yolları böyle kapanmıştı)."

LangChain **tam olarak** `importlib` ile dinamik sağlayıcı yükleyen bir kütüphanedir
(`init_chat_model`, giriş noktaları). Yani bu mimaride LangChain, ürün geçmişimizde
adı konmuş bir arıza sınıfının içine düşer. Bugünkü çalışma zamanı bağımlılığımız
**beş pakettir** (`pyproject.toml`: PySide6, pydantic, numpy, pypdf, qtawesome);
LangChain bunu ~20'ye çıkarır. Bu bir kat üç artıştır ve karşılığında §4'e göre
yeni yetenek gelmez.

> **Doğrulanamadı:** `.exe` boyut artışı ve modül sayısı ölçülmedi — kurulum yapılmadı
> (salt okunur kip). Ölçmek isteyen tek komut: izole venv'de `pip install langgraph`
> sonrası `python -c "import langgraph, sys; print(len(sys.modules))"` ve bir kukla
> PyInstaller derlemesi.

---

## 5. Seçenekler ve karar önerisi

### Seçenek A — Almıyoruz, **deseni** ödünç alıyoruz ✅ ÖNERİLEN

| | |
|---|---|
| **Ne** | Hiçbir yeni bağımlılık yok. LangGraph belgelerinden dört deseni kendi sözleşmemize yazıyoruz. |
| **Ödünç alınacak desenler** | (1) **Dayanıklı yürütme sözleşmesi:** bir düğüm yeniden oynatılabilir olmalı ya da açıkça "yan etkili, oynatma" diye işaretlenmeli — bizde CLI çağrısı kota harcadığı için bu işaretleme zorunlu. (2) **`interrupt` semantiği:** duraklama noktası değerini *döndürür*, devam ederken *tekrar* çalışır — `review` durumumuzda aynı garanti yazılı değil. (3) **Alt-graf/`Send` yerine kota-sınırlı fan-out:** genişlik `entropy_max_parallel` ile değil kart bütçesiyle sınırlansın. (4) **Trace şeması:** `run_type ∈ {llm, chain, tool}` + ebeveyn/çocuk ilişkisi (LangSmith SDK README) — ledger'ımıza ebeveyn alanı eklemek için hazır sözleşme. |
| **Kazanç** | Kota 0, bağımlılık 0, geri alma bedeli 0; ürün kuralları tipte kalır |
| **Maliyet** | Yalnızca belge işi |
| **Risk** | Düşük |
| **Kabul ölçütü** | `docs/ARCHITECTURE.md`'ye "yeniden oynatma güvenliği" satırı; `board_fsm` `review` geçişinin idempotentliğini sınayan bir sözleşme testi yeşil |

### Seçenek B — LangGraph'ı pano/harness çalışma zamanı yapmak ❌ ÖNERİLMEZ

| | |
|---|---|
| **Ne** | `board_fsm` + `dispatcher` + `harness` yerine `StateGraph` + `SqliteSaver`; model düğümü CLI arkalı `BaseChatModel` |
| **Kazanç** | Tek bir olgun çalışma zamanı, dışarıdan bilinen API |
| **Maliyet** | +~15 bağımlılık (5 → ~20), `langsmith` istemcisi zorunlu olarak pakete girer; ~3.600 satır çalışma zamanı kodunun (`board_fsm` 423 + `board_events` 515 + `dispatcher` 519 + `harness` 2.661'in bir kısmı) yeniden yazımı; PyInstaller `importlib` riski (§4.1); kontrol noktalarının insan-okunur `.md`'den ikili `ormsgpack`'e dönmesi — Obsidian kasası sözleşmesini bozar |
| **Risk** | **Yüksek.** Yeniden oynatma kota harcar; sessiz eksik paketleme geçmişte yaşandı; 2.573 testin bir bölümü göç eder |
| **Geri alma** | Zor (çalışma zamanı değişimi tek `git revert` ile dönmez) |
| **Kabul ölçütü (tutulamayacak olan)** | "Aynı testler, aynı yeşil, aynı `.exe` davranışı, kota artışı 0" — §3.1'e göre token ölçümü CLI sarmalayıcısında kaybolduğu için **ölçülemez** |

### Seçenek C — Yalnız gözlemlenebilirlik (yerel) ⚠️ SINIRLI EVET

| Aday | Lisans | Değerlendirme |
|---|---|---|
| LangSmith bulut | tescilli | **Hayır** — veri dışarı çıkar, 5k trace/ay + 1 koltuk, self-host Enterprise |
| Langfuse self-host | depo kökü `NOASSERTION`: MIT çekirdek + ayrı lisanslı bölümler ("Portions of this software are licensed as follows", telif 2023-2026 ClickHouse, Inc.) | **Hayır** — Postgres + ClickHouse + web sunucusu; masaüstü `.exe`'ye sığmaz |
| Arize Phoenix | **Elastic-2.0** | **Hayır** — ELv2 açık kaynak değildir; ayrıca sunucu bileşeni |
| **OpenTelemetry semantik sözleşmesi + kendi ledger'ımız** | Apache-2.0 (sözleşme; kod almak zorunlu değil) | **Evet, sınırlı** — yalnız **alan adlarını** ödünç alırız: `parent_run_id`, `run_type`, süre, girdi/çıktı özeti. Yeni bağımlılık yok, veri `~/.entropy/tasks_ledger.db`'de kalır |

**Öneri:** C'nin yalnız son satırı, A'nın 4. maddesiyle birleştirilerek alınır.

### 5.1 Karar özeti tablosu

| # | Karar | Gerekçe | Emsal |
|---|---|---|---|
| K1 | LangChain/LangGraph **çalışma zamanı olarak alınmaz** | 10 özellikten 7'si bizde var ve ürün kuralını tipte zorluyor; 5→20 bağımlılık; PyInstaller `importlib` riski | ADR-0003 |
| K2 | LangSmith **hiçbir biçimde alınmaz** | Sunucu tescilli, veri dışarı, 5k/ay + 1 koltuk, self-host Enterprise | "veri yerelde kalır" |
| K3 | `claude-agent-sdk`'ya **geçilmez** | CLI'ya göre yeni yetenek yok; abonelik notu belirsizlik ekler | ADR-0009 (spike bağlanmadan ürüne girmez) |
| K4 | Dört desen ödünç alınır | Kota 0, geri alma 0 | — |
| K5 | Ledger'a OTel/LangSmith trace alan adları eklenir | Yerel kalır, arayüz türetilebilir | — |
| K6 | Karar bir **ADR-0010** ile yazılır | ADR-0003'ün ikizi; ileride tekrar sorulmasın | ADR-0003 |

### 5.2 Faz 14 için dilim önerisi (kota 0)

| İş | Ajan | Kapsam | Kabul ölçütü |
|---|---|---|---|
| **İ1** — ADR-0010 "LangChain/LangGraph/LangSmith alınmadı" | repo-curator | yalnız `docs/adr/ADR-0010-*.md` + `ARCHITECTURE.md` bağlantısı | ADR şablonuna uygun; §5.1 tablosu içinde; `docs/adr/` bağlantı testi yeşil |
| **İ2** — Yeniden oynatma güvenliği sözleşmesi | qa-build-engineer | `tests/contracts/` içinde yeni dosya; **kaynak değişmez** | Aynı olayın iki kez uygulanması `events.jsonl`'de ikinci satır üretmez (`idempotency_key`); `review → done` yalnız `actor="human"` + kanıt ile geçer |
| **İ3** — Ledger'a `parent_run_id` + `run_type` | memory-rag-engineer | `core/task_ledger.py` (idempotent `ALTER`), geriye dönük uyumlu | Eski `.db` açılır, yeni sütunlar boş; en az 1 birim testi; K1–K12 paketinde gerileme yok |
| **İ4** — Ölçüm doğrulaması (isteğe bağlı) | qa-build-engineer | izole venv'de `pip install langgraph`, modül sayısı + kukla `.exe` boyutu ölç, **depoya kurulum girmez** | Ölçüm raporu; `pyproject.toml` değişmez |

İ2–İ4 kota harcamaz (model çağrısı yok). İ1 yalnız belge işidir.

---

## 6. Riskler

| # | Risk | Etki | Azaltma |
|---|---|---|---|
| R1 | "MIT, ücretsiz" görülüp LangGraph Studio ile denemeye girişilmesi | LangSmith hesabı + `langgraph-api` ELv2 kapısı | §2.1 bu notta yazılı; ADR-0010 ile kalıcılaşır |
| R2 | LangChain kurulursa `langsmith` istemcisi **zorunlu** olarak pakete girer | tek ortam değişkeniyle dış SaaS'a veri akışı | K1 ile konu kapanır |
| R3 | Desen ödünç alırken sözcük dağarcığının sızması (`ToolNode`, `Send`) | mimarinin kendi dili bulanır | Kod adlarımız korunur; ADR yalnız *fikri* alır |
| R4 | Kararın ileride "denemedik ki" diye yeniden açılması | tekrar araştırma maliyeti | §4 tablosu ölçülü; ADR-0010 ölçümleri içerir |

## 7. Doğrulanamayanlar

1. **Anthropic'in abonelik notunun bizim kullanımımıza uygulanıp uygulanmadığı.** Alıntı
   birebir doğrudur (code.claude.com/docs/en/agent-sdk/overview, 2026-09-11), ama
   "kendi makinesinde kendi oturumunu kullanan kullanıcı" senaryosunun kapsam dışı
   olduğu **hukuki olarak doğrulanmadı**. Aynı sayfanın `-p` ile CLI'yı alt süreç
   olarak koşturmayı önermesi lehte bir işarettir, muafiyet belgesi değildir.
2. **PyInstaller gerçek ağırlığı.** Wheel boyutları ölçüldü (~3,5 MB); `.exe` artışı,
   modül sayısı ve `hiddenimports` ihtiyacı **ölçülmedi** (kurulum yapılmadı).
3. **`langgraph-checkpoint-sqlite` lisansı.** PyPI `license` alanı boş; depoda
   `libs/checkpoint-sqlite` altında ve depo kökü MIT — **çok büyük olasılıkla MIT**,
   ama paket meta verisinden **doğrulanamadı**.
4. **LangSmith self-host lisans anahtarı fiyatı** — "Enterprise, satışla görüşün"
   dışında sayı yok.
5. **`langchain-claude-code-cli`'nin gerçek davranışı** — PyPI sayfasından okundu,
   **çalıştırılmadı** (model çağrısı yasak). Araç çağrısı ve yapılandırılmış çıktının
   CLI üzerinden ne kadar sağlam çalıştığı bizim tarafımızda sınanmadı.
6. **Langfuse'un tam lisans dağılımı** — LICENSE dosyası "Portions ... licensed as
   follows" diyor; hangi dizinin hangi lisansta olduğu satır satır okunmadı.
7. **LangGraph Platform "Developer planı ile ücretsiz self-host, 100k düğüm/ay"**
   iddiası ikincil kaynaktan geldi; birincil fiyat sayfasından doğrulanmadı ve
   `langgraph-api`'nin ELv2 meta verisiyle gerilim içindedir.

## 8. Kaynaklar

Birincil (resmî belge / paket meta verisi / depo), hepsi **2026-09-11**'de okundu:

1. PyPI JSON API — `langchain` 1.4.0 (MIT), `langchain-core` 1.6.2 (MIT),
   `langgraph` 1.2.11 (MIT), `langsmith` 0.12.4 (MIT), `claude-agent-sdk` 0.2.152 (MIT),
   `deepagents` 0.7.13 (MIT), **`langgraph-api` 0.14.0 (`license: Elastic-2.0`)**,
   `langgraph-cli` 0.4.31, `langgraph-checkpoint-sqlite` 3.1.1 — `https://pypi.org/pypi/<paket>/json`
2. GitHub API — `langchain-ai/langchain` MIT/146.093★, `langchain-ai/langgraph` MIT/41.414★,
   `langchain-ai/langsmith-sdk` MIT/1.049★, `langchain-ai/deepagents` MIT/29.295★,
   `langfuse/langfuse` NOASSERTION/34.449★, `Arize-ai/phoenix` NOASSERTION/11.413★
3. `langfuse/langfuse` LICENSE ham dosyası — "Copyright (c) 2023-2026 ClickHouse, Inc. /
   Portions of this software are licensed as follows"
4. `Arize-ai/phoenix` LICENSE ham dosyası — "Elastic License 2.0 (ELv2)"
5. Claude Agent SDK genel bakış — `https://code.claude.com/docs/en/agent-sdk/overview`
   (üçüncü taraf abonelik notu; `-p` + `--output-format json` önerisi; Commercial Terms)
6. LangSmith fiyatlandırma — `https://www.langchain.com/pricing-langsmith`
   (Developer $0 / 5k trace / 1 koltuk; Plus $39; LCU $1,50, LSU $1,00; self-host = Enterprise)
7. LangSmith self-host lisans anahtarı — `https://support.langchain.com/articles/7011309930-how-do-i-obtain-a-self-hosted-langsmith-license-key`
8. LangGraph yerel sunucu belgesi — `https://docs.langchain.com/langgraph-platform/local-server`
   ("An API key for LangSmith")
9. LangGraph dayanıklı yürütme / checkpointer — `https://docs.langchain.com/oss/python/langgraph/durable-execution`
   (`SqliteSaver` yerel dosya kalıcılığı, `PostgresSaver` üretim)
10. LangChain v1 sürüm notları — `https://docs.langchain.com/oss/python/releases/langchain-v1`;
    duyuru `https://www.langchain.com/blog/langchain-langgraph-1dot0` (LangChain 1.0, Ekim 2025;
    `create_agent` LangGraph çalışma zamanı üstünde; middleware: human-in-the-loop, özetleme, PII)
11. `langsmith-sdk` Python README — `LANGSMITH_TRACING=true` (izleme **opt-in**), `run_type ∈ {llm, chain, tool}`
12. `langchain-claude-code-cli` 0.1.0, 2026-02-10, MIT — `https://pypi.org/project/langchain-claude-code-cli/`

İkincil (yalnız bağlam, karar dayanağı değil): clickittech.com "LangChain 1.0 vs LangGraph 1.0"
(2026), langfuse.com "LangSmith Alternative", morphllm.com "Langfuse vs LangSmith (2026)".

Depo içi kanıt (bu notta atıf verilen dosyalar): `docs/ARCHITECTURE.md` §2,
`docs/STATE.md` §3, `docs/adr/ADR-0003-hafiza-algoritmasi-mem0-degil.md`,
`docs/adr/ADR-0007-claude-bg-ertelendi.md`, `docs/adr/ADR-0009-claude-bg-arsivlendi.md`,
`pyproject.toml` (5 çalışma zamanı bağımlılığı), `src/entropy/agents/board_fsm.py`,
`src/entropy/agents/board_events.py`, `src/entropy/agents/dispatcher.py`,
`src/entropy/agents/harness.py`, `src/entropy/agents/board_tools.py`,
`src/entropy/brain/checkpoints.py`, `src/entropy/core/task_ledger.py`.

---

## 9. Özet

Kullanıcının "ücretsiz repoları var" bilgisi LangChain/LangGraph için doğru, LangSmith
için yanıltıcıdır: açık olan yalnız istemci SDK'sıdır, sunucu tescillidir ve ücretsiz
katman ayda 5.000 trace/1 koltuktur. API anahtarsız çalıştırmak teknik olarak mümkündür
ve yayımlanmış bir örneği vardır, ancak o örnek bile **token ölçümünü kaybettiğini** ve
**çağrı başına alt süreç yükü** eklediğini kendi belgesinde yazar — ikisi de bizim kota
muhasebemizin ve kalıcı oturum tasarımımızın tam karşıtıdır. LangGraph'ın satacağı on
özellikten yedisi bizde ölçülebilir biçimde zaten yazılıdır ve bizimkiler ürün kuralını
(kanıtlı bitiş, insan onayı, insan-okunur kontrol noktası) tipte zorlar. Bu yüzden öneri
ADR-0003'ün aynısıdır: **kütüphane değil desen alınır** — dört desen ödünç alınır,
trace alan adları yerel ledger'a eklenir, hiçbir yeni bağımlılık girmez, kota bedeli
sıfırdır.
