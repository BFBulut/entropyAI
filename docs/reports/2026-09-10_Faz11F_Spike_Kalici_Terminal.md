# Faz 11-F Spike — Kalıcı Ajan Terminali (`claude --bg`)

Tarih: 2026-09-10 · Dal: `ai/v0.1.7` · CLI sürümü: 2.1.265
Kapsam: yeni `src/entropy/core/claude_bg.py`, `tests/test_phase11_claude_bg.py`.
Mevcut köprülere (`agy_bridge.py`, `claude_bridge.py`, `provider.py`) DOKUNULMADI.

## 0. Özet

`claude --bg` gerçek bir kalıcı ajan terminalidir: süreç Entropy'den bağımsız
yaşar, uygulama kapansa da `claude agents --json` ile bulunur, konuşma korunur
ve takip turu alabilir. Ama üç sert kısıt var: (1) `-p/--print` ile çakışır,
yani **stdout akışı yoktur** — çıktı diskten okunur; (2) oturum kimliğini CLI
verir, uuid5 ile önden atanamaz; (3) canlı bir oturuma bayrakla `--resume`
göndermek oturumu **çatallar ve izolasyon bayraklarını düşürür** (ölçülen bedel:
aynı istem 4,2k yerine 44,6k jeton). Doğru takip sırası `stop` → **bayraksız**
`--bg --resume`.

Öneri: **ertele + hazır tut.** Modül prototip olarak dursun, 11-C oturum
deposuyla birleşene ve agy asimetrisi ürün kararına bağlanana kadar üretim
yoluna bağlanmasın. Gerekçe §5'te.

## 1. Yardım çıktısından sözleşme (kota harcamayan kanıt)

`claude --help`:

> `--bg, --background` Start the session in the background and return
> immediately. Prints the id that `claude attach`, `logs`, `stop` and `rm` take;
> `claude agents` lists them. With `--resume <session-id>`, continues that
> session in the background under the same ID, **or starts a copy and says so
> when the session is already running**

Alt komutlar: `agents [--json|--all|--cwd]`, `attach <id>`, `logs <id>`,
`stop|kill <id>`, `rm <id>`, `respawn [id|--all]`.

> `stop|kill <id>` Stop a background session. Its conversation is kept:
> `claude attach <id>` opens it again, `claude --resume` works once it is stopped

`claude attach --help`: "← returns to agent view, Ctrl+Z drops back to your
shell. The session keeps running either way." → attach etkileşimli bir PTY
kabuğudur.

## 2. Gerçek koşu bulguları

### 2.1 `--bg` + `-p` çakışıyor (kota harcamadan, argv reddi)

```
$ claude --bg -p "1+1 kac eder?" --name entropy-spike-1 --output-format stream-json ...
--bg and --print conflict: --print never starts the interactive session that
`claude agents` attaches to, so the job would be unattachable. The prompt is
the positional — drop --print: `claude --bg '<task>'`
```

Sonuç: Entropy'nin bütün mevcut ayrıştırıcı yatırımı (`stream-json` olay akışı)
bu yolda **kullanılamaz**. İstem pozisyoneldir.

### 2.2 Başlatma ve yok sayılan bayraklar

```
$ claude --bg "1+1 kac eder? Tek cumleyle yanitla." --name entropy-spike-1 \
    --session-id a63d182b-... --output-format stream-json \
    --system-prompt-file <sysprompt.txt> --strict-mcp-config \
    --setting-sources "" --tools "" --permission-mode acceptEdits --add-dir <ws>
warning: --bg manages the session id; ignoring --session-id (use --resume <id> to continue an existing session)
Starting background service…
backgrounded · bfabe6d4 · entropy-spike-1
```

* `--session-id` **yok sayıldı** → kimlik önden atanamaz, dönen kısa kimlik
  (8 hane) saklanmalı; tam uuid iş künyesinden okunur.
* `--output-format stream-json` sessizce yutuldu ve künyeye `"intent":
  "stream-json"` olarak sızdı (arayüzde iş adı/niyeti kirlenir). **Verilmemeli.**
* İzole kip bayraklarının tamamı kabul edildi ve künyeye kalıcı yazıldı:
  `"respawnFlags": ["--name","entropy-spike-1","--system-prompt-file",...,
  "--strict-mcp-config","--setting-sources","","--tools","","--permission-mode",
  "acceptEdits","--add-dir",...]`.

### 2.3 Bağımsız yaşam — doğrulandı

Oturumu açan kabuk süreci hemen sonlandı. Dakikalar sonra:

```
$ claude agents --json
{ "pid": 54708, "id": "bfabe6d4",
  "cwd": "...\\scratchpad\\ws", "kind": "background",
  "sessionId": "bfabe6d4-a440-410a-bdbe-7c11cce1d49a",
  "name": "entropy-spike-1", "status": "idle", "state": "done" }
$ tasklist /FI "PID eq 54708"
claude.exe   54708 Console   1   289,664 K
```

Süreç ayakta, `status: idle` ile yeni tur bekliyor. Durmuş işlerde `pid` alanı
hiç gelmez → `pid` varlığı canlılık ölçütüdür. `--all` bayrağı bitmiş işleri de
listeye ekler.

### 2.4 Çıktıyı okuma: `logs` işe yaramaz, disk yarar

`claude logs bfabe6d4` çıktısı ham PTY ekran dökümüdür:

```
[2J[m[H[2J[K
[K
[K ...
```

Yapılandırılmış kaynak diskte, `~/.claude/jobs/<kısa-id>/`:

* `state.json` — `state` (`done`), `detail`, `tempo`, `tokens`, `output.result`,
  `sessionId`, `resumeSessionId`, `respawnFlags`, `cwd`, `updatedAt`,
  `linkScanPath` (tam transcript jsonl yolu).
* `timeline.jsonl` — tur başına **bir satır**, yalnızca eklenerek büyür:
  ```json
  {"at":"2026-09-10T03:43:22.344Z","state":"done","detail":"1+1 = 2 (answered in Turkish)","text":"1+1 = 2 eder."}
  {"at":"2026-09-10T03:45:24.773Z","state":"done","detail":"calculated 1+1=2, then 2+3=5","text":"1+1 = 2 eder.\n\n2 + 3 = 5 eder."}
  ```
* `linkScanPath` transcript'i (`~/.claude/projects/<slug>/<uuid>.jsonl`) tam
  olay akışını taşır (`user`/`assistant`/`attachment`/`system`) ve `assistant`
  kayıtlarında `message.usage` bulunur → **jeton muhasebesi buradan okunur**.

`timeline.jsonl` bayt imleçli okunabildiği için sahne yoklaması ucuzdur.

### 2.5 Takip turu: çatallanma tuzağı

Canlı oturuma resume:
```
$ claude --bg --resume bfabe6d4-... "Onceki sayiya 3 ekle."
note: session bfabe6d4 is already running in the background, so this started a
copy as d1d56346. `claude attach bfabe6d4` opens the original.
```
Kopyanın künyesi: `"respawnFlags": ["--model","claude-fable-5-1"]` — **izolasyon
bayraklarının tamamı düştü**, model de değişti. Bedeli ölçüldü (§4).

Durdurup bayrakla resume:
```
$ claude stop bfabe6d4 && claude --bg --resume bfabe6d4-... "..." --name ... --system-prompt-file ... --tools "" ...
note: background session bfabe6d4 keeps its own saved options, so the flags you
passed started a copy as 075ba21c. Without flags, the same command continues
bfabe6d4 itself.
```

Durdurup **bayraksız** resume (doğru yol):
```
$ claude --bg --resume bfabe6d4-a440-410a-bdbe-7c11cce1d49a "Onceki sonuca 3 ekle."
note: woke session bfabe6d4 with its saved options (--name, --system-prompt-file,
--strict-mcp-config, --setting-sources, --tools, --permission-mode, --add-dir).
backgrounded · bfabe6d4 · entropy-spike-1
```
Aynı kimlik, aynı izolasyon, konuşma sürüyor:
`state.json → "output": {"result": "previous result (2) + 3 = 5"}`.

### 2.6 `attach` TTY ister

TTY'siz koşuda `claude attach bfabe6d4 < /dev/null` yalnızca alternatif ekran
kaçış dizisini basıp çıkar (`[?1049h[2J[H ... Attaching… ... [?1049l`).
`pywinpty` ile denemeye **gerek kalmadı**: takip turu §2.5'teki bayraksız resume
ile gönderilebiliyor, yani attach yalnızca "kullanıcıya gerçek terminali göster"
senaryosu için gerekir ve o da 11-C terminal bölmesinin işidir.

### 2.7 Sonlandırma

`claude stop <id>` (konuşmayı korur), `claude rm <id>` (kaydı siler).
Spike'ta açılan üç oturum (`bfabe6d4`, `d1d56346`, `075ba21c`) durduruldu ve
silindi; `claude agents --json --all` çıktısında kalmadı.

## 3. Prototip

`src/entropy/core/claude_bg.py`:

| Öğe | Satır | İş |
| --- | --- | --- |
| modül başlığı (ölçülmüş CLI sözleşmesi) | 1-45 | 7 maddelik kural listesi |
| `claude_home` / `jobs_dir` / `job_dir` | 80-95 | `CLAUDE_CONFIG_DIR` kancalı disk kökü |
| `BgAgent` (+`is_alive`, `is_background`) | 102-124 | `agents --json` kaydı |
| `BgJobState` (+`isolated`) | 126-156 | `state.json` özeti; bayrak düşüşü ölçümü |
| `parse_start_output` | 216-233 | kimlik + `forked`/`woken` bayrakları |
| `parse_agents_json` | 236-262 | canlı liste |
| `read_job_state` / `read_timeline` | 265-348 | disk okuyucuları, **bayt imleçli** |
| `timeline_to_stream_events` | 351-402 | sahne yükü (tek üretim noktası `provider.build_agent_stream_event`) |
| `build_start_command` | 405-443 | `-p`/`--session-id`/`--output-format` YOK |
| `build_resume_command` | 446-461 | bilerek bayraksız |
| `ClaudeBgSession` | 513-728 | `start/list/reattach/state/logs/stream_events/send/stop/remove` |

Eşleme `<store_dir>/sessions.json` (atomik `.tmp` → `replace`), ajan başına tek
kayıt. `reattach()` uygulama açılışında kaydı canlı listeyle karşılaştırır ve
yetim girdileri düşürür.

Durum eşlemesi (`_JOB_STATE_TO_SCENE`): `done|idle|stopped → idle`,
`working|running → working`, `thinking → thinking`, `error|failed → error`,
bilinmeyen → `thinking`.

### Yan bulgu (kırılganlık)

`backgrounded · <id>` satırındaki ayraç ASCII değil ve Windows konsol kod
sayfasında `U+FFFD`'ye bozulabiliyor — gerçek altsüreç testi bunu yakaladı.
Ayraç deseni bilerek genişletildi (`claude_bg.py:205-209`).

## 4. Kota

| Oturum | İzolasyon | Girdi (cache dahil) | Çıktı |
| --- | --- | --- | --- |
| `bfabe6d4` (2 tur, izole) | var | 4.210 | 28 |
| `075ba21c` (bayraklı resume kopyası) | var | 4.210 | 28 |
| `d1d56346` (bayraksız kopya, **izolasyon düştü**) | yok | 44.641 | 20 |
| **Toplam** | | **53.061** | **76** |

Gerçek `claude --bg` çağrısı: 4 (biri argv reddiyle 0 jeton). Ölçüm
transcript'lerin `message.usage` alanından; ledger'a yazılmadığı için oradan
okundu. Sözlü tavan 15k idi; aşımın tek nedeni §2.5'teki çatallanma tuzağının
tam da ölçmek istediğimiz riski gerçekleştirmesi: izolasyonsuz oturum tek turda
44,6k jeton yaktı. Bu sayı bulgunun kendisidir — üretimde her takip mesajında
tekrarlanacaktı.

İzole tek tur maliyeti: ~2,05k girdi (sistem istemi `--system-prompt-file` ile
tamamen değiştiği için; varsayılan istem ~24k'dır).

## 5. Karar tablosu

### (a) `--bg` kalıcı terminal olarak uygun mu?

| Ölçüt | Sonuç |
| --- | --- |
| Yaşam süresi | **Evet** — başlatan süreç ölse de daemon altında yaşar |
| Yeniden bağlanma | **Evet** — `agents --json` + `jobs/<id>/state.json` |
| Çıktı erişimi | **Kısmen** — stdout yok; disk (`timeline.jsonl`) yeterli ama tur-granülerdir, araç çağrısı/düşünce akışı gelmez |
| Takip mesajı | **Evet, ama tuzaklı** — `stop` + bayraksız `--resume` şart |
| Kimlik denetimi | **Hayır** — kimliği CLI verir |
| Kota | İzole kalırsa ucuz; çatallanırsa 10× |
| Kapatma | **Evet** — `stop`/`rm` temiz |
| Windows | Sorun görülmedi (ayraç kodlaması dışında) |

### (b) Mevcut etkileşimli kart kipiyle karşılaştırma

| | 10-C etkileşimli kart | 11-F `--bg` |
| --- | --- | --- |
| Ömür | Uygulamaya bağlı (`Popen` çocuğu) | Bağımsız |
| Olay ayrıntısı | `stream-json`: metin, düşünce, araç çağrısı, `usage` | Tur özeti (`state`, `detail`, `text`) |
| Sahne animasyonu | Araç adına kadar hassas | Yalnız `working/idle/thinking/error` |
| Takip turu | Açık stdin'e NDJSON — anlık | `stop` + `resume` — turlar arası, gecikmeli |
| Kimlik/izolasyon | Her koşuda argv'den, tam denetim | Künyeye bir kez yazılır; çatallanmada kaybolur |
| Jeton muhasebesi | Akıştan doğrudan | Transcript dosyasından dolaylı |

Yani ikisi rakip değil, **dikey**: `--bg` uzun ömrü verir, `stream-json` ise
zengin telemetriyi. İkisini birleştirmenin yolu yok (aynı bayraklar çakışıyor).

### (c) agy asimetrisi

agy'de `--bg` karşılığı yok; agy ajanları uygulama ömrüyle sınırlı kalır.
Öneri: asimetriyi **ajan künyesinde açık bir yetenek alanı** olarak taşımak
(`persistent: bool`). Sahne kalıcı ajanları farklı bir rozetle gösterir,
Desk kartı kapatılınca agy ajanı "uykuya alındı" der, Claude ajanı "arka planda
çalışmaya devam ediyor" der. Sözde-kalıcılık (agy'yi yeniden başlatıp
`--resume`) uydurmak kullanıcıyı yanıltır; yapılmamalı.

### (d) 11-C oturum deposuyla birleşme planı

1. `sessions.json` şeması 11-C kart oturum deposuna alan olarak eklenir
   (`backend: "inproc" | "bg"`, `job_id`, `cursor`).
2. Kart açılışında `backend` seçilir: Desk ofis ajanı + Claude sağlayıcı +
   "kalıcı" işareti → `bg`; aksi hâlde bugünkü `inproc`.
3. Sahne yoklaması tek bir zamanlayıcıda toplanır: `reattach()` + ajan başına
   `stream_events()` (yalnızca `bg` kayıtları için, ~1 sn aralık).
4. `task_ledger.mark_orphans_failed` mantığının `bg` karşılığı: `reattach()`
   yetim kayıtları düşürür; ayrıca `state == "done"` olup kartı açık kalan
   işler kapatılır.
5. Jeton muhasebesi `linkScanPath` transcript'inden okunur ve ledger'a işlenir.

### Riskler

* **Yetim süreçler.** Uygulama silinse bile `claude.exe` süreçleri yaşar;
  kullanıcı bunları göremez. Kapanışta "N kalıcı ajan çalışmaya devam edecek"
  uyarısı ve Desk'te toplu durdurma düğmesi şart.
* **Sessiz izolasyon kaybı.** Bir çatallanma Entropy Saf Kip'i düşürür ve
  kullanıcının CLAUDE.md/MCP yapılandırması sızar. `BgJobState.isolated`
  ölçümü her yoklamada denetlenmeli, düşerse oturum kapatılmalı.
* **Kota.** Kalıcı oturum uyandıkça tam bağlamı yeniden okur; uzun konuşmalarda
  tur maliyeti doğrusal büyür. Tur sayısı/`tokens` eşiği ile otomatik kapatma
  gerekir.
* **Sürüm bağımlılığı.** Bulguların tamamı CLI 2.1.265 davranışıdır ve
  belgelenmiş bir API değildir (`jobs/` düzeni özellikle). `respawn` komutunun
  varlığı düzenin sürümler arası değişebildiğini gösteriyor. Modül disk okuma
  hatalarında sessizce boş dönüyor; üretime bağlanırsa sürüm kapısı gerekir.
* **Windows.** Konsol kod sayfası kaynaklı metin bozulması (yakalandı, çözüldü).

## 6. Testler

`python -m pytest tests/test_phase11_claude_bg.py -q` → **32 passed** (0,63 sn).

Kapsam: gerçek CLI çıktılarından kopyalanan dizeler üzerinde ayrıştırıcılar,
çatallanma/uyandırma ayrımı, argv yasakları (`-p`, `--session-id`,
`--output-format`), bayt imleçli zaman çizgisi okuma (dosya küçülmesi ve bozuk
satır dâhil), sahne durum eşlemesi ve balon kırpma, oturum deposunun yeniden
yüklenmesi, `send`'in `stop`→bayraksız-`resume` sırası, yetim kayıt temizliği.

Sahte köprüyle yetinilmedi: `test_real_subprocess_path_starts_and_resumes` ve
`test_real_subprocess_path_surfaces_print_conflict` diske gerçek bir
çalıştırılabilir yazıp `_default_runner`'ı `subprocess` üzerinden sürer;
ayraç bozulması bulgusunu bu test yakaladı.

## 7. Öneri

**Ertele (uygulama Faz 12'ye), modülü koru.** Gerekçe: uzun ömür kazancı
gerçek, ama telemetri kaybı (araç çağrısı/düşünce akışı yok) mevcut piksel
sahnesini fakirleştirir ve izolasyon kaybı riski sessizdir. Önce 11-C oturum
deposu sabitlensin; `--bg` oraya `backend` seçeneği olarak, yalnızca "gece
boyu çalışsın" işaretli ofis kartları için bağlansın.
