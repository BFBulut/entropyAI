# Faz 11 — Araştırma A: "Entropy'nin Beyni"
## Yapay zekâ hafıza sistemleri ve RAG mimarilerinde güncel durum + mevcut hafızamızın dürüst denetimi

**Tarih:** 2026-09-10 · **Depo:** `C:\EntropiAI` (v0.8.0, dal `ai/v0.1.7`) · **Kip:** salt okunur araştırma
**Yöntem:** literatür taraması (web, tarihli) + kod denetimi (`dosya:satır` kanıtı) + gerçek veritabanı üzerinde ölçüm
**Model çağrısı yapılmadı.** Kod, kasa, ayar ve üretim veritabanı değiştirilmedi; tüm ölçümler `~/.entropy/cognitive_memory.db` dosyasının geçici bir **kopyası** üzerinde koşturuldu.

---

## 0. Yönetici özeti (önce sonuç)

Beş cümlelik özet:

1. **Geri çağırma iyi çalışıyor.** 10 sorgulu kör testte Hit@1 = 8/10, Hit@5 = 9/10, top-5'te gürültü %2. Sorun *okuma* tarafında değil.
2. **Yazma tarafı denetimsiz.** `record_memory` yalnızca **birebir metin özeti** ile yineleme eler; başka sözcüklerle yazılmış aynı bilgi yeni bir düğüm açar. Ölçüm: 1544 düğümün **%55,7'si fazlalık** (cos ≥ 0,90 kümelemesi ile 684 benzersiz konu).
3. **Kendi kendini besleyen bir döngü var.** Zamanlanmış "Otonom Ajan Mimarisi Araştırma" görevi kendi çıktısını okuyup numarasını bir artırarak yeniden yazıyor: `src/entropy/tools/` altında **59 dosya / 3,2 MB** üretilmiş modül, hafızada **29 farklı uydurma "N-Layer Cognitive Memory Architecture" adı**. Aynı hattın finans tarafında yinelenme **%0**; mimari tarafında **%87**. Fark, konu uzayının tükenmiş olması + yazma tarafında yenilik kapısı bulunmaması.
4. **Damıtma katmanı yarım.** Yetenekli sohbette bağlamın %44,9'u playbook'tan geliyor (iyi); **yeteneksiz sohbette damıtılmış pay %0 ve 4000 token bütçenin yalnızca %11'i kullanılıyor** — genel sohbetin beyni yok. Wiki katmanı bağlamın %0,8'i (7 yetenekten yalnızca 1'inde wiki sayfası var).
5. **Karar: kütüphaneyi değil algoritmayı al; hafızayı silme, süz.** mem0 çalışma zamanı bağımlılığı olarak **uygun değil** (her yazımda LLM zorunlu, graph memory açık kaynaktan **kaldırıldı**, Nisan 2026 sürümü **UPDATE/DELETE'i bıraktı** — yani bizim asıl sorunumuzu çözmüyor). Apache-2.0 olduğu için fikri kendi katmanımızda yeniden yazmak serbest. Mevcut 1544 düğümün **~668'i (%43)** temiz çekirdek; sıfırdan kur, bu çekirdeği yeni yazma kapısından geçirerek göç ettir.

---

## 1. Literatür haritası

Her madde: **ne diyor → bize ne öğretiyor → kanıt/tarih**.

### 1.1 Yazma tarafı denetimi (bizim asıl açığımız)

| Kaynak | Ne diyor | Bize ne öğretiyor |
|---|---|---|
| **SAGE: A Novelty Gate for Efficient Memory Evolution in Agentic LLMs** — Sijia Wang, Dhanajit Brahma, Ricardo Henao. arXiv:2605.30711, v1 29 May 2026, v2 18 Haz 2026 | Alan "geri çağırma ve depolamaya odaklandı, **ilkeli yazma-tarafı denetimini** ihmal etti". Aday olguları bellek gömmeleri üzerindeki **von Mises-Fisher yoğunluk kestirimi** ile puanlar; bellek geometrisini izleyen **uyarlanabilir eşikle** ADD (açıkça yeni) / NOOP (açıkça fazlalık) / **belirsiz → LLM birleştirme** olarak yönlendirir. GPT-4o-mini'de ekleme aşaması API maliyeti **3,4×**, gecikme **2,5×** düşüyor; beş modelde LLM çağrılarının **%16-18'i atlanıyor**, kalite kaybı ihmal edilebilir. | **Faz 11'in çekirdek deseni.** Bize tam olarak kullanıcının istediği şeyi veriyor: "LLM'siz + CLI destekli add/update/noop kararı". Üç bantlı kapı: net yeni → yaz (model yok), net kopya → NOOP (model yok), gri bant → CLI'ye bir tur. Sabit eşik değil, korpus geometrisine uyarlanan eşik. |
| **Dual-Layer Agentic Memory with Fast Write Routing and Slow Consolidation** — Li, Nie, Lan, Lyu, Wang, Hong, Pan, Lin, Pan, Hu. arXiv:2608.22215, 23 Ağu 2026 (rev. 31 Ağu 2026) | Dış belleği "tekdüze büyüyen" bir yığın saymayı bırakır; **non-write / write-new / write-update** üçlüsüne **küçükten-büyüğe model kaskadı** ile yönlendirir ("cost-aware epistemic routing"). 1,7B/8B kaskadı fazlalık dış belleğin **%68'ini** budarken girdilerin **%50'sinden azını** yönlendiriyor ve alt-görev başarımının **%98'inden fazlasını** koruyor. | Kaskad fikri bize doğrudan uyar: **ucuz yerel katman (gömme + BM25 + kural) çoğu kararı verir, pahalı CLI turu yalnızca gri bantta çağrılır.** Abonelik kotasıyla çalışan bir sistemde bu, "her yazımda model" yaklaşımının tek uygulanabilir alternatifi. |
| **Hindsight — "The Consolidation Problem in Agent Memory"**, 21 May 2026 | Birleştirme eşikleri **konsolidasyonda (0,95) yazma anından (0,92) daha yüksek** tutulur: yazarken öncelik kopya engellemek, konsolidasyonda öncelik ayrı bilgileri korumaktır. | Somut eşik değerleri. Bizim ölçümümüzde (§3.2) cos ≥ 0,92 bandı gerçekten "aynı şey"i topluyor; bu sayı deneysel olarak da doğrulanmış. |
| **When Memory Becomes Authority: Benchmarking Authority Collapse at the Memory Consolidation Boundary** — arXiv:2608.01679 · **Manufactured Confidence: How Memory Consolidation Turns Hearsay into Confident Facts** — arXiv:2606.29279 | Konsolidasyon, bir iddiayı korurken **kaynağını ve geçerlilik koşullarını silebilir**; sistem sonradan "duyum"u kesin olgu gibi sunar, çekimser kalması gereken yerde emin yanlış üretir. | Konsolidasyon düğümlerine **kaynak (provenance) ve güven bandı** zorunlu alan yapılmalı. Bizde rüya döngüsü özeti (`cognitive_memory.py:1340`) 0,6 önemle yazılıyor ama kaynak izini gövdeye gömüyor — yapısal alan değil. |
| **What to Keep, What to Forget: A Rate–Distortion View of Memory Compaction** — arXiv:2607.08032 | Bellek sıkıştırmasını hız-bozulma problemi olarak kurar: neyin atılacağı, atmanın alt-görev kaybına oranıyla ölçülmeli. | Unutmayı "eskiyeni sil" değil, **ölçülebilir kayıp bütçesi** olarak tanımlamalıyız. Bizdeki Ebbinghaus budaması (`prune_decayed_memories`, `cognitive_memory.py:1470`) yalnızca zaman/önem tabanlı — kayıp ölçülmüyor. |

### 1.2 Bellek mimarisi çerçeveleri

| Kaynak | Ne diyor | Bize ne öğretiyor |
|---|---|---|
| **CoALA — Cognitive Architectures for Language Agents** — arXiv:2309.02427 (Sumers, Yao, Narasimhan, Griffiths) | Ajan bilişini **çalışma / epizodik / anlamsal / yordamsal** belleğe ayırır (Tulving üçlemesi). Çalışma belleği o karar döngüsünün etkin değişkenleri; epizodik geçmiş döngülerin deneyimi; anlamsal dünyaya dair olgular; yordamsal "bu iş nasıl yapılır". İç eylemler (akıl yürütme, bellek güncelleme) ve dış eylemler (araç) ayrı eylem uzayları. | **Brain v2'nin katman iskeleti.** Bizde bu ayrım *isim düzeyinde* var (`CognitiveMemoryNode.category`) ama uygulanmıyor: veritabanında 4 yerine **17 kategori** dolaşıyor ve %82,6'sı tek bir kovaya (`semantic`) yığılmış (§3.1). |
| **Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers** — Pengfei Du, arXiv:2603.07670, 8 Mar 2026 | Belleği üç eksende düzenler: **zamansal kapsam, temsil taşıyıcısı, denetim politikası**. Beş mekanizma ailesi: bağlam-içi sıkıştırma, geri getirmeli depolar, yansıtmalı öz-iyileştirme, hiyerarşik sanal bağlam, politika-öğrenen yönetim. Belleği **yaz–yönet–oku döngüsü** olarak formüle eder. Açık sorunlar: sürekli konsolidasyon, nedensel geri getirme, güvenilir yansıma, **öğrenilmiş unutma**, çok-kipli bellek. | "Denetim politikası" üçüncü eksen olarak bizde **hiç yok** — bu raporun ana bulgusu ile birebir örtüşüyor. Yaz–yönet–oku üçlüsü Brain v2'nin bölüm başlıkları olacak. |
| **MemGPT / Letta — memory blocks, sleep-time compute, context repositories** (letta.com blog, 2026) | Bağlamı işletim sistemi gibi yönetir: **Core Memory (RAM) / Recall (disk önbelleği) / Archival (soğuk depo)**. "Sleep-time compute": ajan boştayken paylaşılan bellek bloklarını işler. 2026'da **Context Repositories** ile bağlamı **yerel dosya sistemine + git sürümlemesine** taşıdı. | İki şey: (a) bizim rüya döngümüz zaten sleep-time compute'un basit hâli — ama şu an `enabled: False` (§3.4); (b) **git tabanlı, dosya sistemi üstünde bağlam** deseni Desk'in dosya-tabanlı ortak çalışma belleği kuralımızla aynı yöne bakıyor, doğru yoldayız. |
| **A-MEM: Agentic Memory for LLM Agents** — Xu, Liang, Mei, Gao, Tan, Zhang. arXiv:2502.12110 (17 Şub 2025, v11 8 Eki 2025) | Zettelkasten esinli: her yeni anı için **bağlamsal betimleme + anahtar sözcük + etiket** taşıyan yapılandırılmış not üretir; geçmiş anılarla anlamlı benzerlik varsa **bağ kurar**; yeni bilgi eski notların betimleme ve niteliklerini **evrimleştirebilir**. LoCoMo'da %60,84 (karşılaştırma: HippoRAG %72,10). | Wiki katmanımızın (`wiki.py`) teorik dayanağı. Ama A-MEM'in LoCoMo skoru düşük: **not ağı tek başına yetmiyor**, altında sağlam bir olgu deposu gerekiyor. Wiki'yi "tek gerçek kaynak" değil, **gezinme katmanı** olarak konumlandırmalıyız. |
| **HippoRAG 2 — "From RAG to Memory: Non-Parametric Continual Learning for LLMs"** — Gutiérrez, Shu, Qi, Zhou, Su. arXiv:2502.14802, ICML 2025 | Bilgi grafını **Personalized PageRank** ile gezer, ilgili üçlüleri bulup yoğun geri getirmeyi yeniden sıralar; HippoRAG 1'e göre daha derin pasaj tümleştirmesi. **Çağrışımsal bellek görevlerinde en iyi gömme modeline göre +%7**; olgusal ve anlamlandırma görevlerinde de üstün. LoCoMo %72,10. | **Bizde zaten var:** `graph_store.py:1016 _personalized_pagerank`, `graph_store.py:970` PPR ile tohumlama. Bu, mem0'a karşı elimizdeki asıl koz (§2.4). |
| **Zep / Graphiti — A Temporal Knowledge Graph Architecture for Agent Memory** — arXiv:2501.13956; Neo4j geliştirici blogu | **Çift-zamanlı (bi-temporal)**: her olgu için *geçerlilik zamanı* ve *alım zamanı* ayrı tutulur; her kenarda açık geçerlilik aralığı (t_valid, t_invalid). Çelişkide eski olgu **silinmez, geçersizleştirilir**. DMR'de %94,8 (MemGPT %93,4). LoCoMo %80,32, LongMemEval 71,2. | **Bizde zaten var:** `edges` tablosunda `t_valid_from`, `t_valid_to`, `ingested_at` (şema §3.1) ve `reconcile.py:234 reconcile_facts` çelişkide `superseded` üretiyor. Kanıt: üretim veritabanında 1548 graf düğümü, 3216 kenar, 89 topluluk. |
| **Generative Agents / Reflection** ve **Voyager beceri kütüphanesi** (temel eserler) | Voyager açık uçlu ortamda **kod tabanlı, doğal dille indekslenmiş yeniden kullanılabilir beceriler** biriktirir; her beceri yürütmeyle doğrulanıp kalıcı kütüphaneye girer. | Bizim PLAYBOOK.md + SKILL.md ikilisinin atası. Kritik nokta: **doğrulama**. Voyager beceriyi *çalıştırarak* onaylıyor; bizde playbook'un doğruluğu hiçbir yerde sınanmıyor (§3.5). |
| **SoK: Agentic Skills — Beyond Tool Use in LLM Agents** — Jiang, Li, Deng, Ma, Wang, Wang, Yu. arXiv:2602.20867, 24 Şub 2026 | Beceriyi araçtan ayırır: beceri = **uygulanabilirlik koşulları + yürütme politikası + sonlandırma ölçütü + yeniden kullanılabilir arayüz** paketleyen çağrılabilir modül. Yaşam döngüsü: **keşif → pratik → damıtma → depolama → besteleme → değerlendirme → güncelleme**. Açık sorun olarak **küratörlü beceri ile öz-üretilmiş beceri arasındaki kalite uçurumunu** ve tedarik zinciri riskini işaret ediyor. | Yedi aşamalı yaşam döngüsü, skill sentez döngümüzün eksik halkalarını gösteriyor: bizde keşif + damıtma + depolama var; **pratik, değerlendirme ve güncelleme yok**. "Öz-üretilmiş beceri kalite uçurumu" uyarısı §3.3'teki bulgumuzla birebir aynı. |
| **HyperSkill: Self-Evolving LLM Agents via Hypergraph-Structured Skill Memory** — arXiv:2608.16114 · **SkillForge** — arXiv:2604.08618 · **SkillAudit: Ground-Truth-Free Skill Evolution via Paired Trajectory Auditing** — arXiv:2606.14239 | Beceri kütüphanesini hipergraf olarak tutmak, alan-özel beceriyi kendiliğinden geliştirmek ve **yer-gerçeği olmadan** eşli yörünge denetimiyle beceri evrimini doğrulamak. | SkillAudit özellikle bizim için: **doğru cevap listesi olmadan** bir playbook güncellemesinin iyileştirme mi bozma mı olduğunu ölçmenin yolu — "close with proof" kuralımızın hafıza karşılığı. |

### 1.3 RAG tarafı

| Kaynak | Ne diyor | Bize ne öğretiyor |
|---|---|---|
| **GraphRAG vs LightRAG** (Graph RAG: A Survey, arXiv:2408.08921; LEGO-GraphRAG arXiv:2411.05844; GraphRAG-Bench arXiv:2506.02404) | GraphRAG'in üç pratik sakıncası: çok geçişli varlık/ilişki çıkarımı + topluluk özeti üretimi **token/hesap açısından pahalı**; sorgu anında graf gezme **2-3× gecikme**; indeks külliyatla **süper-doğrusal** büyüyor, artımlı güncelleme zorlaşıyor. LightRAG ilişkisel sinyali yoğun indekse katlayıp çift-düzeyli kaba-ince geri getirme kullanır: **indeksleme token maliyeti ~%60 düşer**, medyan sorgu gecikmesi yaklaşık yarılanır. | Bizim tercihimiz doğru: **PPR'yi sorgu anında değil, tohumlanmış küçük komşulukta** koşturuyoruz ve topluluk özetlerini rüya döngüsünde (çevrimdışı) üretiyoruz. GraphRAG'in tam sürümüne geçmek kota açısından yanlış olur. |
| **Is Agentic RAG worth it? An experimental comparison** — arXiv:2601.07711 (v2, Oca 2026) · **Reasoning RAG via System 1 or System 2** — arXiv:2506.10408 · **Towards Agentic RAG with Deep Reasoning** — arXiv:2507.09477 | "Enhanced RAG" (CRAG, Self-RAG, RaCoT) ile "Agentic RAG" (LLM'in iş akışını kendi yönettiği) ayrımı. CRAG hafif bir **geri getirme değerlendiricisi** ile parçaları doğru/yanlış/belirsiz olarak puanlar; kalite düşükse **sorgu yeniden yazma veya web araması** devreye girer. Self-RAG üretim sırasında kendi taslağını eleştirir. | **CRAG deseni bizim "araştırma → rapor" akışımızın kapısı olmalı:** önce beyinden getir, değerlendir, yetersizse internete çık. Şu an bu değerlendirme adımı yok — her araştırma turu doğrudan internete gidiyor ve zaten bilineni tekrar getiriyor (§3.3). |
| **RAPTOR** ve hiyerarşik özetleme; **Advanced RAG 2026 derlemeleri** | "Hybrid retrieval, RAPTOR ve Self-RAG'in **hepsi temiz, iyi yapılandırılmış, yönetişimi olan bir bilgi tabanı varsayar**." | En sert uyarı: gelişmiş geri getirme teknikleri **kirli korpusu kurtarmaz**. Bizde geri getirme zaten iyi (%80 Hit@1); yatırım yeri korpus hijyeni. |
| **LlamaIndex — agent memory blocks** (llamaindex.ai blog, 2026) | Sohbet geçmişini "her şey" saymayı bırakır: **static memory / fact extraction memory / vector memory** blokları. Kısa vadeli kuyruk belli boyutu aşınca arşivlenir ve uzun vadeli bloklara boşaltılır; okumada kısa ve uzun vadeli birleştirilir. | Bizim `handoff.py` + `context_builder.py` ikilisinin endüstri karşılığı. "Static memory block" = bizim promoted rules; doğru hizada. |
| **Microsoft Agent Framework / AG2 (eski AutoGen)** (learn.microsoft.com, 2026) | AutoGen ile Semantic Kernel birleşti. Durum bilgili ajanlar için **dört aşamalı yaşam döngüsü**: *Persistence* (durumu depodan yükle), *Assembly* (bilgi deposundan bağlam kur), *Execution*, *Post-Processing* (geçmişi sıkıştır, belleği güncelle, temizle). AG2 GraphRAG-SDK üzerinden FalkorDB'ye bağlanabiliyor. | **Post-Processing aşaması bizde yok.** Bir tur bittikten sonra "geçmişi sıkıştır + belleği güncelle" adımı yalnızca rüya döngüsünde (o da kapalı) çalışıyor. Tur sonu konsolidasyonu Brain v2'ye zorunlu adım olarak girmeli. |

### 1.4 Karpathy — LLM wiki / bilgi derleme deseni

Karpathy, Nisan 2026'da yayımladığı desende (GitHub gist `442a6bf555914893e9891c11519de94f`) "kod işletmekten **bilgi işletmeye**" geçişi tarif ediyor. Üç katman:

1. **Ham kaynaklar** (`sources/`) — değiştirilemez girdi: PDF, markdown, düz metin.
2. **Derlenmiş wiki** (`wiki/`) — LLM'in bakımını yaptığı, birbirine bağlı markdown sayfaları; YAML ön bilgisinde `last_updated`, etiketler.
3. **Şema / indeks** (`_index/`) — ajanın gezinmesini sağlayan, otomatik üretilen dizin listeleri.

Anahtar cümle: *"Bilgi bir kez derlenir ve güncel tutulur, her sorguda yeniden türetilmez."* Bakım için **haftalık çelişki denetimi** ("knowledge linting") öneriliyor ve kritik uyarı şu: *"ajana hangi sayfaların güncelleneceğini kapsamlandırmadan asla 'wiki'yi güncelle' deme."*

**Bize ne öğretiyor:** Bizde bu desenin *iskeleti* var (`wiki.py`, `lint.py`, Obsidian kasası), ama **ikinci katman neredeyse boş** — 7 yetenekten yalnızca `autonomous-agent`'ın 25 wiki sayfası var, diğerlerinde 0 (§3.5). Yani "her sorguda yeniden türetme" hâlâ devrede: bağlamın %25,3'ü ham **rapor alıntısı**, %0,8'i derlenmiş wiki.

**Kaynak notu:** Kullanıcının listesindeki **paperswithcode.com artık kendi başına yayında değil**; 302 ile `huggingface.co/papers/trending` adresine yönlendiriyor (10 Eyl 2026 tarihli denetim). Bu kaynağı Faz 11 araştırma akışından çıkarıp HF Papers'ı tek adres yapmalıyız.

### 1.5 Kıyaslamalar — 2026 tablosu

Ölçü birimi: LoCoMo (1540 soru, 300 tura kadar çok oturumlu sohbet, 35 oturum), LongMemEval (500 soru), BEAM (1M ve 10M token ölçeğinde).

| Sistem | LoCoMo | LongMemEval | Not |
|---|---|---|---|
| mem0 (Nisan 2026 algoritması) | **92,5** | **94,4** | BEAM 1M: 64,1 · BEAM 10M: 48,6 · sorgu başına ~6.700-7.000 token |
| Zep | 80,32 | 71,2 | yapılandırmaya bağlı |
| Letta | 74,0 | yayımlanmadı | |
| HippoRAG | 72,10 | — | |
| A-Mem | 60,84 | — | |
| OpenAI Memory | 52,9 | — | |

*(Kaynak: mem0.ai "State of AI Agent Memory 2026" ve "AI Memory Benchmarks in 2026". **Uyarı: satıcı blogu, bağımsız doğrulama yok.** mem0 kendi raporunda LangMem, A-Mem ve HippoRAG'i değerlendirmediğini açıkça yazıyor; A-Mem/HippoRAG rakamları AMA-Bench arXiv:2602.22769'dan.)*

Aynı rapordaki açık sorunlar listesi bizim için de geçerli: ölçekte zamansal soyutlama, oturumlar arası yapı modelleme, **uygulama düzeyinde değerlendirme çerçeveleri**, gizlilik/onam, oturumlar arası kimlik çözümleme, **yüksek-alaka olgularda bayatlama**.

---

## 2. mem0 derin inceleme ve karar

### 2.1 Ne olduğu

Apache-2.0 lisanslı ("Apache 2.0 — see the LICENSE file for details"), `pip install mem0ai` ile kurulan bir bellek katmanı. Klasik algoritması iki fazlı: **Çıkarım** (sohbet özeti + son mesajlar bağlamında LLM ile öne çıkan olguları seçme) ve **Güncelleme** (her aday olgu vektör benzerliğiyle mevcut anılarla kıyaslanır, LLM **ADD / UPDATE / DELETE / NOOP** kararını verir). Graf değişkeni Mem0g, anıları yönlü etiketli graf G=(V,E,L) olarak modelliyordu.

### 2.2 2026'da ne değişti — üç kritik gelişme

1. **Nisan 2026 yeni algoritma: ADD-only.** Resmî belgelerin ifadesiyle: *"single-pass ADD-only extraction — one LLM call, no UPDATE/DELETE. Memories accumulate; nothing is overwritten."* Kıyaslamalarda büyük sıçrama sağladı (LoCoMo +21 puan, LongMemEval +27 puan; zamansal akıl yürütmede +29,6, çok-atlamalıda +23,1) — **ama bizim asıl derdimiz olan fazlalık birikimini çözmüyor, tam tersine kabul ediyor.**
2. **Graph memory açık kaynaktan kaldırıldı.** Göç kılavuzu: *"Graph memory is removed from the open-source SDK. It is not being replaced by an OSS equivalent: graph memory is a **Mem0 Platform** feature."* Neo4j, Memgraph, Kuzu, Apache AGE ve Neptune sürücüleri (~4.000 satır) silindi; `enable_graph` ve `graph_store` yapılandırma blokları artık okunmuyor.
3. **Ekosistem büyüdü:** 21 çerçeve tümleştirmesi, 20 vektör deposu arka ucu.

### 2.3 API anahtarı olmadan çalışır mı?

**Kısmen — ama bizim koşullarımızda pratik değil.**

- **LLM zorunlu.** Belge açık: *"Mem0 requires an LLM to function, with `gpt-5-mini` from OpenAI as the default."* Varsayılan gömme modeli de OpenAI `text-embedding-3-small`.
- **Yerel sağlayıcılar destekleniyor.** Desteklenen liste: *"OpenAI, Anthropic, Groq, **Ollama**, Together, Azure OpenAI, Mistral AI, Google AI, AWS Bedrock, DeepSeek, MiniMax, xAI, Sarvam AI, **LM Studio**, and **Langchain**."* Ollama ve LM Studio yerel çalışır, anahtar istemez.
- **Ama bizim sağlayıcımız yerel bir sunucu değil, bir CLI süreci.** mem0'da "abonelik oturumuyla çalışan `claude`/`agy` alt sürecini başlat, `--output-format stream-json` çıktısını ayrıştır" diye hazır bir adaptör **yok**. Kendi `LLMBase` alt sınıfımızı yazmamız gerekir.

### 2.4 Bizim köprülerimizle uyarlama maliyeti

Teknik olarak yapılabilir: `claude_bridge.py` zaten başsız çalışma iskeletine sahip — `-p / --print`, `--output-format stream-json` (+ `--verbose` şart), `--input-format stream-json` (`claude_bridge.py:10-14`, komut kurulumu `claude_bridge.py:648`, `:695`). `distiller.py` de tam bu deseni kullanıyor: prompt üret → köprüye ver → çıktıyı kaydet, doğrudan model çağrısı yok (`distiller.py:5-6`, `run_with_bridge` `distiller.py:508`).

**Ama maliyet tablosu kötü:**

| Kalem | Değer |
|---|---|
| Yazılacak adaptör | `LLMBase` alt sınıfı + stream-json ayrıştırıcı + zaman aşımı/iptal + eşzamanlılık kilidi |
| Yazma başına gecikme | CLI süreci başlatma **saniyeler** mertebesinde (bizim kendi ölçümümüzde gömme yolu 316 ms; süreç başlatma bunun 10-30 katı) |
| Kota | Her `add()` en az bir tur. Bizde günde 500+ düğüm yazılıyor (6 Eyl'de tek günde 526) → **500+ CLI turu/gün**, kabul edilemez |
| Bağımlılık ağırlığı | PyInstaller paketine yeni ağaç; `pyproject.toml` şu an yalnızca 4 sert bağımlılık tutuyor (PySide6, pydantic, numpy, pypdf) |
| Kayıp | Graph memory OSS'ten kalktı → bizim **çift-zamanlı graf + PPR + topluluk** katmanımızın (asıl farkımız) mem0 karşılığı yok; yine kendi kodumuzu tutmamız gerekir |
| Kazanç | Fikirler + olgunlaşmış promptlar — **kodun kendisi değil** |

### 2.5 KARAR: Kütüphaneyi alma, algoritmayı al

> **mem0 çalışma zamanı bağımlılığı olarak reddedilmiştir. Apache-2.0 lisansı fikri kendi katmanımızda yeniden yazmaya izin verir; Faz 11'de yapılacak olan budur.**

Gerekçe, sırayla:
1. Her yazımda LLM zorunluluğu, API anahtarsız/abonelik-CLI mimarimizle bağdaşmıyor (500+ tur/gün).
2. Nisan 2026 sürümü UPDATE/DELETE'i bıraktı — **bizim asıl problemimiz olan yineleme birikimini çözmüyor.**
3. Graf yeteneği OSS'ten kaldırıldı; bizim en güçlü tarafımız orada ve zaten çalışıyor (1548 düğüm / 3216 kenar / 89 topluluk).
4. Kıyaslama üstünlüğü satıcı blogundan geliyor, bağımsız doğrulama yok.

**Alacağımız fikirler:**

| mem0'dan | Bizdeki karşılığı | Faz 11'de yapılacak |
|---|---|---|
| Olgu çıkarımı (aday olgu listesi) | `reconcile.py:122 extract_facts` — **var, LLM'siz** | Yazma yoluna bağla |
| ADD / UPDATE / DELETE / NOOP | `reconcile.py:234 reconcile_facts` → `created` / `superseded` / `duplicate` — **var, LLM'siz** | Yazma yoluna bağla (§4.2) |
| Vektör benzerliğiyle aday eşleştirme | `hybrid_recall` altyapısı — var | Yazma kapısı için yeniden kullan |
| Çelişki çözümü | çift-zamanlı `superseded` kenarı — **bizimki daha iyi (Zep hattı)** | Koru |

**mem0 yerine örnek alınacak asıl makale SAGE'dir** (arXiv:2605.30711): vMF yoğunluk kestirimi + uyarlanabilir eşik ile üç bantlı yönlendirme, LLM yalnızca gri bantta. Bu, mem0'ın kararını **modelsiz** vermenin yayımlanmış yoludur ve bizim kısıtımıza (kota) doğrudan cevaptır.

---

## 3. Mevcut hafızanın dürüst denetimi

**Ölçüm ortamı:** `~/.entropy/cognitive_memory.db` (21,1 MB) kopyası; 1544 `cognitive_nodes` satırı; tüm gömmeler `ok` durumunda ve tek modelde (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 boyut) — bu iyi haber, bayat gömme yok.

### 3.1 Neyi iyi yapıyor

| Bulgu | Kanıt |
|---|---|
| **Geri çağırma kalitesi yüksek.** 10 sorgulu kör test (Türkçe, gerçek korpus konuları): **Hit@1 = 8/10, Hit@3 = 8/10, Hit@5 = 9/10.** | Ölçüm §3.6 |
| **Gürültü bastırma çalışıyor.** 10 sorgunun top-5 sonuçlarında (50 satır) test/ofis kartı gürültüsü yalnızca **1 satır (%2)**. | `_hybrid_recall_indexed` içindeki `suppress = (bm25 == 0) & (vec_sim < 0.35)` maskesi, `cognitive_memory.py:1120+` |
| **Hibrit skorlama dengeli.** 0,40·vektör + 0,20·BM25 + 0,25·Ebbinghaus + 0,15·tazelik; vektör benzerliği 0,50-1,00 aralığından 0-1'e gerdiriliyor (çok dilli modelin dar dinamik aralığı için doğru düzeltme). | `cognitive_memory.py:1120-1180` |
| **Çok dilli gömme seçimi ölçümle yapılmış.** Kod içinde kayıtlı: `bge-small-en` 4/6 doğru / 0,041 ayrım; `multilingual-MiniLM` 5/6 / 0,179 ayrım (4,4×). | `cognitive_memory.py:88-95` |
| **Vektörleştirilmiş indeks + geri düşme yolu.** numpy varsa indeksli, yoksa skaler; ikisi aynı sıralamayı üretiyor; indeks parmak iziyle geçersizleniyor. | `cognitive_memory.py:958-1046` |
| **Çift-zamanlı graf gerçekten dolu.** `edges` tablosunda `t_valid_from` / `t_valid_to` / `ingested_at`; üretimde 1548 düğüm, **3216 kenar**, **89 topluluk**. PPR uygulanmış. | Şema; `graph_store.py:1016` |
| **LLM'siz uzlaştırıcı yazılmış ve test edilmiş.** Aynı normalize metin → `duplicate`; aynı varlık+yüklem farklı değer → `superseded` (eski geçersizleşir, yeni `supersedes` ile bağlanır). | `reconcile.py:234-283`; `tests/test_graph_store_and_reconcile.py` |
| **Yazma yolu artık iki depoya senkron yazıyor.** Faz 10-A düzeltmesi; graf sapması kapandı. | `cognitive_memory.py:745-752` |
| **Yetenekli bağlamda damıtma payı yüksek.** Playbook bağlamın %43,6-%51,4'ü; sorguya göre bölüm seçimi ve özet-kırpma çalışıyor. | Ölçüm §3.7 |
| **Hata görünürlüğü kazanılmış.** Sessiz `except: pass` blokları `_record_error` ile değiştirilmiş; `DreamResult.errors` kısmi başarısızlığı taşıyor. | `cognitive_memory.py:36-52`, `:503` |

### 3.2 Neyi yapmıyor — (A) "Bunu zaten biliyorum" yok

**Kök neden, tek satır:**

```python
def _generate_node_id(self, category: str, content: str) -> str:
    h = hashlib.sha256(f"{category}:{content.strip().lower()}".encode("utf-8")).hexdigest()[:16]
```
`src/entropy/memory/supabase/cognitive_memory.py:701-703`

Düğüm kimliği **içeriğin birebir özeti**. `record_memory` (`:911`) "Layer 2: Surprise/Novelty Filter" başlığını taşıyor ama yaptığı tek şey bu kimliğin var olup olmadığına bakmak (`:924-935`). **Tek bir kelime, tek bir noktalama, tek bir büyük harf farkı yeni düğüm açar.** Anlamsal yenilik hiçbir yerde ölçülmüyor — oysa gömme motoru aynı fonksiyonun üç satır altında çalışıyor.

**Ölçüm — yineleme oranı (1544 düğüm, kosinüs benzerliği):**

| Eşik | Çift sayısı | İçinde geçen düğüm | Oran |
|---|---|---|---|
| cos ≥ 0,98 | 6.364 | 735 | **%47,6** |
| cos ≥ 0,95 | 8.618 | 855 | %55,4 |
| cos ≥ 0,90 | 14.237 | 961 | %62,2 |
| cos ≥ 0,85 | 21.999 | 1.066 | %69,0 |
| cos ≥ 0,80 | 38.260 | 1.145 | %74,2 |

cos ≥ 0,90 eşiğinde birleşik-küme (union-find) analizi: **684 benzersiz konu, 101 çok-üyeli küme, 860 fazladan düğüm — veritabanının %55,7'si.**

En büyük kümeler:

| Boyut | Kategori | İçerik |
|---|---|---|
| **322** | `query` | `arastirma-ofisi: Pazar araştırması / Ofis: ... · arastirmaci · review` — **test fikstürü** |
| 43 | `query` | `Ayrıştırıcı Modül bitti. [KANIT] Komut: python -m pytest tests/test_modul.py Sonuç: yeşil (12 passed)` — **test fikstürü** |
| 30 | `query` | `medya: Kampanya ... ### Slogan · yazar · review` — **test fikstürü** |
| 28 | `semantic` | `claude-ofisi: Kart ### Alt · isci · review` — **test fikstürü** |
| **26** | `semantic` | `Pentacosa-Store 25-Layer ... / 26-Layer ... / Heptacosa-Store 27-Layer Cognitive Memory Architecture` — **üretilmiş sahte mimari** |

Ayrıca:
- **469 düğüm (%30,4)** ofis kartı/test fikstürü kalıbında (`Ofis:` + `review`/`·`). Test verisi üretim hafızasına sızmış.
- **1.100 / 1.544 (%71,2)** düğümün `access_count = 1` — **hiç geri çağrılmamış**.
- **17 farklı kategori** dolaşıyor (`semantic` 1276, `procedural` 134, `query` 93, `episodic` 11, `architecture` 8, `office` 8, `agent` 2, `ego` 2, `session` 2, ve 8 tekil kategori) — oysa `CognitiveMemoryNode` docstring'i dört kategori tanımlıyor (`cognitive_memory.py:66`). **Kategori serbest metin; hiçbir yerde doğrulanmıyor.** `query` diye bir CoALA katmanı yok; bu kategori tamamen test artığı.

**Kritik mimari gözlem:** Bu sorunun çözümü **zaten yazılmış** ama **yanlış yere bağlanmış.** `reconcile_facts` (`reconcile.py:234`) ADD/duplicate/superseded kararını LLM'siz veriyor — ancak yalnızca **graf katmanında**, `GraphStore.ingest_text` içinden çağrılıyor (`graph_store.py:830`). Gerçek yazma yolu ise şu:

```
7 üretim çağrı noktası → store_node (cognitive_memory.py:1269) → record_memory (:911) → yalnızca hash eşitliği
```

Çağrı noktaları: `core/agy_bridge.py:1320`, `core/agy_bridge.py:2344`, `memory/handoff.py:424`, `memory/wiki.py:386`, `skills/manager.py:481`, `skills/pdf_engine.py:87`, `ui/widgets/reports_viewer.py:823`. **Hiçbiri uzlaştırıcıdan geçmiyor.**

### 3.3 Neyi yapmıyor — (B) Kendini besleyen döngü (öz-amplifikasyon)

En sert bulgu. Zamanlanmış görev **"Otonom Ajan Mimarisi Araştırma"** (`~/.entropy/scheduler_tasks.json`, `interval_type: minutely`, `interval_value: 10`) prompt'una şöyle başlıyor:

> *"Kendi hafızanı ve bilgini kontrol ederek, en güncel bilgileri alacak şekilde. Günümüz çağında OTONOM ajan mimarisi nasıl kullanılır, ... task ve agent, harness agent, agent desks gibi kavramları araştırarak ..."*

Sabit ve dar bir konu listesi, **10 dakikada bir**. Konu uzayı birkaç turda tükeniyor; sonrasında ajan kendi önceki çıktısını okuyup numarasını artırarak yeniden yazıyor.

**Kanıt 1 — hafızada:** 29 farklı uydurma mimari adı, 32 düğümde:
`Hexadeca-Store 16-Layer` … `Docosa-Store 24-Layer` … `Pentacosa-Store 25-Layer` … `Pentacosa-Store 26-Layer` … `Heptacosa-Store 27-Layer` … `Triaconta-Store 30-Layer` … `Quadraginta-Store 40-Layer` … `Novendecim-Store 49-Layer` … `Novendecim-Store 50-Layer` … `Quindecim-Store 54-Layer` … `Sexaginta-Store 55-Layer`. Aynı gövde, artan sayı, bazen aynı Latince önekin iki farklı sayıya bağlanması (adlandırma bile tutarsız).

**Kanıt 2 — diskte:** `src/entropy/tools/` altında `autonomous_agent_architecture_faz98.py` … `faz158.py` arası **59 dosya, 3,2 MB**. Ardışık dosyalar metin düzeyinde %52-55 aynı, gömme düzeyinde aynı kümede. `docs/reports/` altında aynı serinin **20 raporu**. Git'te `src/entropy/tools/` altında yalnızca **4 dosya izleniyor** — kalan 55'i izlenmeyen üretim artığı (temizlik ucuz ve risksiz).

**Kanıt 3 — kontrollü karşılaştırma.** Aynı hat, iki farklı konu uzayı:

| Zamanlanmış görev | Düğüm | Benzersiz konu (cos ≥ 0,90) | Fazlalık | Ortalama iç-kosinüs |
|---|---|---|---|---|
| Finans araştırması (faz ≤ 100) | 36 | **36** | **0 (%0)** | 0,507 |
| Mimari araştırması (faz ≥ 120) | 219 | **28** | **191 (%87)** | 0,439 |

Finans tarafı gerçekten öğreniyor: Ohlson O-Score, Gatheral SVI, Dupire yerel volatilite, Fung-Hsieh yedi faktör, Christoffersen/Kupiec VaR geri testi, Cartea-Jaimungal HJB, Ho-Stoll, Engle-Russell ACD, Harrison-Pliska, HJM, Lucas ağacı, Campbell-Shiller, Leland-Toft, Duffie-Lando, GRS testi — **her biri ayrı, gerçek, adlandırılmış literatür.** Aynı motor, aynı köprü, aynı hafıza.

**Fark neden?** Finans görevinin konu uzayı pratikte tükenmez (tüm kantitatif finans literatürü); mimari görevinin konu listesi sabit ve dar. **Ve iki tarafta da yazma anında yenilik kapısı yok** — dolayısıyla konu uzayı tükendiği anda sistem kopya üretmeye başlıyor ve kimse durdurmuyor.

Bu, SoK: Agentic Skills'in (arXiv:2602.20867) "küratörlü beceri ile öz-üretilmiş beceri arasındaki kalite uçurumu" uyarısının ve *Manufactured Confidence* (arXiv:2606.29279) bulgusunun canlı örneği: sistem kendi türettiği kurguyu, kaynağını yitirmiş kesin bilgi gibi yeniden yazıyor.

### 3.4 Neyi yapmıyor — (C) Üç katman ayrımı ve konsolidasyon

- **Katman ayrımı yok.** CoALA'nın dört katmanı isim olarak var, uygulamada yok: düğümlerin **%82,6'sı `semantic`** kovasında. Epizodik yalnızca **11 düğüm**.
- **Rüya döngüsü fiilen ölü.** `dream_and_consolidate` (`cognitive_memory.py:1293`) yalnızca **son 48 saatin `episodic` düğümlerini** okuyor (`:1310`) ve en az 2 satır arıyor (`:1329`). Epizodik toplam 11 düğüm olduğuna göre bu koşul neredeyse hiç sağlanmıyor. Üstelik zamanlanmış "Hafıza Konsolidasyonu & Rüya Görme" görevi `enabled: False` (son çalışma 6 Eyl 2026) — **tüm zamanlanmış görevler kapalı.**
- **Konsolidasyon çıktısı ham özet.** Sağlansaydı bile üretilen şey "son 6 epizodik anının ilk 220 karakteri" listesi (`:1330-1347`) — sentez değil, kırpma. Kaynak alanı yapısal değil, gövdeye gömülü.
- **Unutma ölçüsüz.** `prune_decayed_memories` (`:1470`) `min_strength=0.10` ve `days_dormant=30` ile yalnızca epizodikleri buduyor; 1276 semantik düğüme hiç dokunmuyor. *Rate–distortion* (arXiv:2607.08032) anlamında kayıp bütçesi yok.
- **Topluluk tespiti Louvain değil.** `graph_store.py:1189 _label_propagation` — etiket yayılımı. (Görev tanımında "Louvain" geçiyordu; dürüstlük gereği düzeltiyorum. Etiket yayılımı daha ucuz ve bizim ölçeğimizde yeterli, ama modülerlik güvencesi vermez.)

### 3.5 Neyi yapmıyor — (D) Skill sentezi ve beyin↔ajan aktarımı

**Kasa durumu** (`C:\Users\batu_\OneDrive\Belgeler\Obsidian Vault`):

| Yetenek | md | wiki sayfası | rapor | PLAYBOOK.md |
|---|---|---|---|---|
| autonomous-agent | 26 | **25** | 0 | 9.294 B |
| financial-auditor | 51 | **0** | 50 | 9.537 B |
| media-agency-soldier | 17 | **0** | 16 | 8.644 B |
| pdf-analyzer | 1 | 0 | 0 | 7.608 B |
| research | 4 | 4 | 0 | **yok** |
| skill-creator | 2 | 0 | 2 | **yok** |
| slide-deck-architect | 1 | 0 | 0 | 6.813 B |

Toplam: `Entropy/Reports` altında **423 rapor**, 7 yetenekten **5'inde playbook**, wiki katmanı fiilen **tek yetenekte**.

- **Wiki derlemesi çalışmıyor.** 50 raporu olan `financial-auditor`'ın **0 wiki sayfası** var. Karpathy deseninin ikinci katmanı boş; sistem hâlâ her sorguda ham rapordan türetiyor.
- **Playbook doğrulanmıyor.** Voyager'ın beceriyi *çalıştırarak* onaylaması karşılığı bizde yok. `lint.py` sayısal iddia/çapraz bağ denetimi yapıyor (`lint.py:154 _numeric_claims`) ama playbook'un işe yarayıp yaramadığını ölçmüyor. SoK'un yedi aşamalı döngüsünden **pratik, değerlendirme ve güncelleme** eksik.
- **Beceri sentezi tek yönlü.** `skills/manager.py:446 create_skill` yeni SKILL.md yazıp `store_node` ile hafızaya `skill_synthesis` kaynaklı düğüm koyuyor (16 düğüm) — ama bu düğümler geri okunup bir sonraki beceri kararını beslemiyor.
- **Beyin → ajan aktarımı zayıf.** `handoff.py` (session devri) test senaryolarının hiçbirinde bağlama girmedi; `BUDGET_HANDOFF = 300` ayrılmış ama sayfa "tüketildi" işaretlemesi nedeniyle nadiren tetikleniyor (`context_builder.py:55-57`).

### 3.6 Ölçüm: kör geri çağırma testi

**Yöntem:** 10 Türkçe sorgu, her biri için önceden belirlenmiş "ilgili düğüm" örüntüsü; `hybrid_recall(top_k=5)` gerçek kodla, veritabanı kopyası üzerinde.

| # | Sorgu | Sonuç |
|---|---|---|
| 1 | Ohlson O-Score ile temerrüt olasılığı | OK@4 |
| 2 | Volatilite yüzeyini arbitrajsız modelleme SVI | **OK@1** (Gatheral SVI, 0,480) |
| 3 | VaR geriye dönük test yöntemi Basel | **OK@1** (Christoffersen/Kupiec, 0,564) |
| 4 | Trend takip eden hedge fon faktör modeli | **OK@1** (Fung & Hsieh, 0,513) |
| 5 | Bilanço/gelir tablosu/nakit akış birlikte okuma | **OK@1** (financial-auditor, 0,500) |
| 6 | Piyasa yapıcılığında envanter riski optimal kontrol | **OK@1** (Ho & Stoll, 0,482) |
| 7 | Agent harness nedir | **OK@1** (Agent = Model + Harness + Task, 0,580) |
| 8 | MCP token maliyeti yerine kod yazdırma | **OK@1** (CodeAct vs MCP Tax, 0,478) |
| 9 | Çok ajanlı iş akışını DAG olarak planlama, kritik yol | **KAÇIRDI** — top1: `# Yarım iş Ofis: arastirma-ofisi ...` (0,398) |
| 10 | Hata izolasyonu için denetim ağacı stratejileri | **OK@1** (Erlang-OTP Supervision Trees, 0,585) |

**Sonuç: Hit@1 = 8/10 · Hit@3 = 8/10 · Hit@5 = 9/10 · ortalama gecikme 316 ms** (ilk sorgu indeks kurulumuyla 2.513 ms) · **top-5 gürültü oranı 1/50 = %2**.

Tek kaçırma (#9) tam olarak §3.2'deki kirliliğin sonucu: DAG/CPM bilgisi korpusta **var** ama 322 üyeli test-fikstür kümesi ile aynı anlamsal komşulukta ve top-5'i işgal ediyor.

> **Bu ölçümün anlamı büyük: geri getirme motorunu değiştirmeye gerek yok. Yatırım yeri korpus hijyeni ve yazma kapısı.** (RAPTOR/Self-RAG derlemelerinin uyarısıyla birebir aynı: gelişmiş geri getirme temiz korpus varsayar.)

### 3.7 Ölçüm: damıtma çıktısının yeniden kullanım oranı

**Yöntem:** `CognitiveContextBuilder.build()` gerçek kodla, dört senaryo, 4000 token bütçe.

| Senaryo | Toplam | playbook | wiki | recall | rapor | global |
|---|---|---|---|---|---|---|
| financial-auditor | 3.197 | **1.494 (%46,7)** | 0 | 583 (%18,2) | 841 (%26,3) | 279 (%8,7) |
| autonomous-agent | 3.419 | **1.492 (%43,6)** | 80 (%2,3) | 691 (%20,2) | 877 (%25,7) | 279 (%8,2) |
| media-agency-soldier | 2.902 | **1.491 (%51,4)** | 0 | 329 (%11,3) | 803 (%27,7) | 279 (%9,6) |
| **yetenek yok (genel sohbet)** | **457** | **0** | **0** | 178 (%38,9) | 0 | 279 (%61,1) |

**Toplam pay:** playbook %44,9 · rapor alıntısı %25,3 · recall %17,9 · global memory %11,2 · **wiki %0,8**.
**Damıtılmış (playbook + wiki + handoff) %45,7 · ham (recall + rapor + proje + kod + global) %54,3.**

İki sert bulgu:

1. **Genel sohbetin beyni yok.** Yetenek eşleşmediğinde bağlam **457 token** — 4000 token bütçenin **%11,4'ü**. Damıtılmış pay **%0**. Kullanıcının hedeflediği "girdi → beyin + internet araştırması → ajanlara görev → rapor → sohbete geri" akışının ilk adımı, yetenek eşleşmediği anda çöküyor.
2. **Wiki katmanı yok sayılabilir (%0,8).** `BUDGET_WIKI_PAGES = 400` ayrılmış (`context_builder.py:52`) ama dolduracak sayfa yok. Bağlamın dörtte biri hâlâ **ham rapor alıntısı** — yani Karpathy'nin "her sorguda yeniden türetme" dediği şey.

### 3.8 Denetim özeti — puan tablosu

| Yetenek | Durum | Kanıt |
|---|---|---|
| Anlamsal geri çağırma | **İyi** | Hit@1 8/10, gürültü %2 |
| Çok dilli gömme | **İyi** | tek model, 1544/1544 `ok` |
| Çift-zamanlı graf + PPR | **İyi** | 3216 kenar, 89 topluluk |
| LLM'siz uzlaştırıcı | **Yazılmış, bağlanmamış** | `reconcile.py:234` ↔ `cognitive_memory.py:911` |
| Yetenekli bağlam kurma | **İyi** | playbook %44,9 |
| Yineleme engelleme ("zaten biliyorum") | **YOK** | %55,7 fazlalık |
| Kategori disiplini (3 katman) | **YOK** | 17 kategori, %82,6 tek kovada |
| Konsolidasyon / rüya | **ÖLÜ** | 11 epizodik; görev `enabled: False` |
| Öz-amplifikasyon savunması | **YOK** | 59 dosya, 29 uydurma mimari adı |
| Wiki derlemesi (Karpathy L2) | **NEREDEYSE YOK** | 7 yetenekten 1'inde |
| Genel sohbette beyin | **YOK** | 457/4000 token, %0 damıtılmış |
| Skill doğrulama döngüsü | **YOK** | playbook çalıştırılarak sınanmıyor |
| Ölçülmüş unutma | **YOK** | yalnızca epizodik budama |
| Test/üretim yalıtımı | **BOZUK** | 469 fikstür düğümü üretimde |

---

## 4. "Brain v2" mimari önerisi

Tasarım ilkesi: **okuma yolu iyi, ona dokunma; yazma yolunu ve derleme katmanını inşa et.**

### 4.1 Katmanlar (CoALA hizalı, 4 katman, kapalı küme)

```
L0  ÇALIŞMA BELLEĞİ (working)        — tur ve oturum kapsamlı, kalıcı düğüm DEĞİL
     · handoff.py (oturum devri) + checkpoints.py (modül sonu durumu)
     · disk: Sessions/, Desk checkpoint dosyaları · vektör indekse GİRMEZ

L1  EPİZODİK (episodic)              — "ne oldu": tur kaydı, rapor, ofis kartı
     · SOĞUK DEPO = Obsidian (Entropy/Reports, Sessions, DailyNotes)
     · SQLite'ta yalnızca hafif künye (başlık + yol + tarih + varlıklar), gövde DEĞİL
     · varsayılan geri çağırma kapsamı DIŞINDA; ancak açık "geçmişte ara" ile

L2  ANLAMSAL (semantic)              — "ne doğru": atomik olgu + varlık grafı
     · cognitive_nodes (vektör + BM25) ⟷ nodes/edges (çift-zamanlı, PPR, topluluk)
     · her olgu: kaynak (provenance) + geçerlilik aralığı + güven bandı ZORUNLU

L3  YORDAMSAL (procedural)           — "nasıl yapılır": PLAYBOOK.md + SKILL.md + wiki
     · derlenmiş katman (Karpathy L2); ham rapordan damıtılır, ham raporun YERİNE geçer

L4  KİMLİK / KURAL (ego)             — ego düğümü + promoted_rules (kullanıcı onaylı)
```

**Sert kural:** `category` artık serbest metin değil; `{episodic, semantic, procedural, ego}` dışındaki her değer yazma anında reddedilir. `query`, `office`, `architecture`, `math`, `federation` gibi 13 uydurma kategori kaldırılır.

### 4.2 Yazma yolu — üç bantlı yenilik kapısı (SAGE deseni, kotasız)

Tek giriş noktası: `store_node` → **yeni** `MemoryGate.admit()`. Yedi çağrı noktasının hiçbiri değişmez.

```
aday metin
   │
   ├─ 1. ÇIKARIM (LLM YOK)  ── reconcile.extract_facts() → atomik olgular
   │
   ├─ 2. AYIKLAMA (LLM YOK) ── fikstür/log/kısa metin süzgeci
   │      · "Ofis: ... · ... · review" kalıbı → REDDET
   │      · < 40 karakter → REDDET   · traceback/log → REDDET (kullanıcı kuralı)
   │
   ├─ 3. YOĞUNLUK PUANI (LLM YOK) ── SAGE: mevcut korpus gömmeleri üzerinde
   │      vMF benzeri yoğunluk + korpus geometrisine uyarlanan eşik
   │      (başlangıç kalibrasyonu: bizim ölçümümüz ve Hindsight ile uyumlu)
   │
   ├─ 4. YÖNLENDİRME (üç bant)
   │      cos < 0,85  ................ ADD      → yaz, graf kenarlarını kur
   │      cos ≥ 0,95  ................ NOOP     → yazma; mevcut düğümün access_count++
   │      0,85 ≤ cos < 0,95 (GRİ BANT)
   │           ├─ aynı varlık+yüklem, farklı değer → SUPERSEDE (reconcile_facts, LLM YOK)
   │           └─ belirsiz → KUYRUĞA AL, tur içinde model çağırma
   │
   └─ 5. KUYRUK → gece toplu CLI turu (claude/agy, tek prompt, N aday birlikte)
          "şunlar aynı bilgi mi? birleştir / ayrı tut / hangisi güncel?"
```

**Kota etkisi:** SAGE'in ölçümüne göre gri bant yazımların yaklaşık %16-18'i. Bizde günde ~500 yazım → ~85 aday → **tek toplu turda 3-5 CLI çağrısı/gün**. mem0'ın "her yazımda bir tur" modelinde bu 500 tur olurdu. Dual-Layer (arXiv:2608.22215) kaskadının aynı mantığı.

**Uygulama notu:** 1-4. adımlar **tamamen mevcut kodla** yapılabilir — `extract_facts`, `reconcile_facts`, gömme motoru ve `_RecallIndex` zaten var. Yeni yazılacak olan yalnızca yoğunluk puanı + bant yönlendirmesi + kuyruk. 5. adım `distiller.run_with_bridge` desenini birebir tekrar eder.

### 4.3 Okuma yolu — dokunma, üstüne koy

`hybrid_recall` skorlaması **değişmez** (0,40/0,20/0,25/0,15 — 8/10 Hit@1 veriyor). Eklenecekler:

1. **Kapsam süzgeci:** varsayılan geri çağırma L2+L3 üzerinde; L1 epizodik yalnızca açık istekle. (Tek başına bu, §3.6'daki #9 kaçırmasını çözer.)
2. **PPR genişletmesi:** ilk k düğümü tohum alıp `graph_store._personalized_pagerank` ile 1-2 atlama komşu getir (HippoRAG 2 deseni — kod zaten var, okuma yoluna bağlı değil).
3. **CRAG kapısı:** en iyi skor bir eşiğin altındaysa "beyinde yok" bilgisini **açıkça** döndür — böylece araştırma akışı (§4.5) tetiklenir. Şu an sistem zayıf sonuçları da güvenle sunuyor.

### 4.4 Konsolidasyon — gece döngüsü (LLM'siz çekirdek + CLI destekli sentez)

`dream_and_consolidate` yeniden yazılır; epizodik-48saat koşulu kaldırılır.

| Adım | Model? | İş |
|---|---|---|
| 1. Küme | Hayır | Tüm L2 üzerinde cos ≥ **0,95** kümeleme (konsolidasyonda yazma eşiğinden yüksek — Hindsight kuralı) |
| 2. Birleştir | Hayır | Küme içinde en yüksek `importance`+`access_count` olanı temsilci seç; diğerlerini `merged_into` kenarıyla bağla ve indeksten düşür |
| 3. Yükselt | **Evet, toplu** | ≥ 3 üyeli her küme için tek CLI turu: kümenin wiki sayfasını yaz/güncelle (Karpathy L2 derlemesi) |
| 4. Denetle | Hayır | `lint.py` çelişki + sayısal iddia denetimi (Karpathy "knowledge linting", haftalık) |
| 5. Unut | Hayır | Rate–distortion bütçesi: `access_count = 1` **ve** yaş > 60 gün **ve** cos ≥ 0,95 ile bir temsilcisi olan düğümleri arşivle (silme değil, `archived` bayrağı) |
| 6. Uzlaştır | Hayır | mevcut `reconcile_stores` + `reembed_stale` (zaten var, çalışıyor) |

**Kota:** adım 3, gecede küme sayısı kadar tur. Temiz korpusta (~670 düğüm) beklenen 5-15 tur/gece.

### 4.5 Araştırma → rapor → hafıza akışı (öz-amplifikasyon kilidi)

Bu, §3.3'teki döngüyü kıran asıl değişiklik. **Her araştırma turu bu üç kapıdan geçer:**

```
1. AÇIK TESPİTİ (LLM YOK)
   Konu için beyni sorgula. Hit@1 skoru > 0,55 ise → "BU KONU BİLİNİYOR, ARAŞTIRMA YOK"
   Yalnızca beyinde OLMAYAN alt-başlıklar araştırma girdisi olur.        [CRAG deseni]

2. YENİLİK KOTASI (LLM YOK)
   Tur sonunda üretilen düğümlerin ≥ %70'i mevcut korpusa cos < 0,85 olmalı.
   Aksi hâlde tur ÇÖPE ATILIR ve zamanlanmış görev otomatik olarak
   "konu uzayı tükendi" bayrağıyla DURDURULUR ve kullanıcıya bildirilir.

3. KAYNAK ZORUNLULUĞU
   Dış kaynağa (URL / yayın / tarih) bağlanamayan hiçbir düğüm L2'ye yazılamaz.
   Kendi önceki çıktısı geçerli kaynak DEĞİLDİR.       [Manufactured Confidence]
```

Üçüncü kural tek başına 32 uydurma mimari düğümünün tamamını engellerdi.

### 4.6 Beyin → ajan bağlam enjeksiyonu

- **Yeteneksiz sohbet için varsayılan beyin paketi.** Yetenek eşleşmediğinde bağlam boş kalmaz: `BUDGET_GENERAL_BRAIN` eklenir ve şunlarla doldurulur — ego/kimlik, promoted rules, en alakalı **wiki sayfaları** (playbook yerine), PPR ile genişletilmiş recall. Hedef: bütçe kullanımı **%11 → ≥ %60**, damıtılmış pay **%0 → ≥ %30**.
- **Bütçe yeniden dağıtımı.** `BUDGET_REPORTS` (900) düşürülür, `BUDGET_WIKI_PAGES` (400) yükseltilir — wiki katmanı dolduğu ölçüde. Ham rapor alıntısı **son çare** olmalı, birincil kaynak değil.
- **Desk yönü tek yönlü kalır.** Ofis belleği Entropy grafına akar (`office_graph.schedule_office_ingest`, rüya döngüsünden); ters yön yok. Mevcut kural korunur.

### 4.7 Obsidian'ın rolü — soğuk depo ve insan arayüzü

| Katman | Sıcak (SQLite) | Soğuk (Obsidian) |
|---|---|---|
| L1 epizodik | yalnızca künye | **gövde burada** (Reports, Sessions, DailyNotes) |
| L2 anlamsal | **birincil** (vektör + graf) | BELLEK_HARITASI.md aynası (insan okusun diye) |
| L3 yordamsal | künye + gömme | **birincil** (PLAYBOOK.md, wiki/, SKILL.md) |
| L4 kural | ego düğümü | **birincil** (promoted rules markdown) |

Obsidian **tek gerçek kaynak olarak yordam ve kural için**; SQLite **tek gerçek kaynak olarak olgu ve graf için**. Bu ayrım, veritabanı silinse bile 423 raporun ve 5 playbook'un kaybolmaması demektir — geri dönüş planının temeli (§5.3).

### 4.8 Ölçülebilir kabul ölçütleri

| # | Ölçüt | Bugün | Hedef | Nasıl ölçülür |
|---|---|---|---|---|
| K1 | Yineleme oranı (cos ≥ 0,92 fazlalık) | **%55,7** | **≤ %10** | union-find kümeleme betiği (bu raporun betiği) |
| K2 | Hit@1 / Hit@5 (10 sorgu kör test) | 8/10, 9/10 | **≥ 8/10, ≥ 10/10** | aynı 10 sorgu + 10 yeni sorgu |
| K3 | top-5 gürültü oranı | %2 | **≤ %2** (korunmalı) | aynı test |
| K4 | Yeteneksiz sohbette bütçe kullanımı | **%11,4** | **≥ %60** | `AssembledContext.tokens / budget` |
| K5 | Yeteneksiz sohbette damıtılmış pay | **%0** | **≥ %30** | bölüm türü dağılımı |
| K6 | Wiki payı (yetenekli bağlam) | %0,8 | **≥ %15** | bölüm türü dağılımı |
| K7 | Kategori disiplini | 17 kategori | **tam 4** | `SELECT DISTINCT category` |
| K8 | Araştırma turu yenilik oranı | mimari: %13 | **≥ %70** | tur çıktısının korpusa cos < 0,85 payı |
| K9 | Yazma başına CLI turu | — | **≤ 0,02** (≈%2) | gri bant kuyruk sayacı |
| K10 | Fikstür sızıntısı | 469 düğüm | **0** | `Ofis:`+`review` kalıbı sayımı |
| K11 | Yazma yolu gecikmesi | ~300 ms | **≤ 400 ms** | kapı dâhil ölçüm |
| K12 | Kaynaksız L2 düğümü | ölçülmedi | **0** | `provenance` boş sayımı |

---

## 5. Hafıza: sil mi, taşı mı?

### 5.1 Kanıt — mevcut verinin kalitesi

Kademeli süzme (gerçek veri üzerinde koşturuldu):

| Adım | Düğüm | Kalan |
|---|---|---|
| Ham | — | **1.544** |
| − fikstür/ofis kartı/`query`/< 40 karakter | −578 | 966 |
| − uydurma "N-Layer" mimari | −31 | **935** |
| − cos ≥ 0,92 yakın kopyalar | −267 | **668** |

**Temiz çekirdek ≈ 668 düğüm = ham verinin %43'ü.** Bunların 803'ü (süzme öncesi) 150+ karakterlik gerçek içerik. İçinde: 36 benzersiz kantitatif finans düğümü (%0 yinelenme), gerçek 2026 ajan mimarisi bilgisi, `financial-auditor` ve `media-agency-soldier` yetenek bilgisi, ego/kimlik.

Karşı tarafta: %30,4 test fikstürü, %2 uydurma mimari, %55,7 yinelenme, %71,2 hiç geri çağrılmamış.

### 5.2 KARAR: **Sıfırdan kur + seçici göç** (ne saf silme, ne saf taşıma)

> **Veritabanını yeni şema ile sıfırdan kur; eski veriden yalnızca ~668 düğümlük temiz çekirdeği, yeni yazma kapısından geçirerek göç ettir.**

Neden saf silme değil:
- 36 benzersiz finans düğümü ve gerçek 2026 araştırma bilgisi yeniden üretilemez (özgün kaynak taramaları, kotayla alınmış).
- Ego/kimlik ve `financial-auditor` yetenek bilgisi doğrudan üretim değeri taşıyor.
- Göç maliyeti düşük: tek betik, model çağrısı yok, ~670 düğüm için birkaç dakika.

Neden saf taşıma değil:
- 17 kategori → 4 kategoriye geçiş **şema değişikliği** gerektiriyor; yerinde `ALTER` ile yapılırsa 13 kategorinin düğümleri nereye gideceği belirsiz kalır.
- L1/L2 ayrımı (epizodik gövdeyi soğuk depoya taşıma) mevcut satırların büyük kısmının **yeniden sınıflandırılması** demek — temiz kurulum daha ucuz ve daha denetlenebilir.
- Fikstür kirliliği (469 düğüm) yerinde silinse bile aynı test koşusu tekrar üretir; asıl düzeltme **test yalıtımı** (`ENTROPY_COGNITIVE_DB` her testte zorunlu — `cognitive_memory.py:412-419`'da altyapı var, ama 7 çağrı noktasının tamamı bunu kullanmıyor).

### 5.3 Geri dönüş planı

1. **Göç öncesi yedek zorunlu:** `~/.entropy/cognitive_memory.db` → `cognitive_memory.db.pre_brain_v2.bak`. (Zaten iki eski yedek var: `.bak-202609070301` 7,0 MB, `.pre_graph.bak` 10,8 MB — desen kurulu.)
2. **Göç betiği idempotent ve kuru-koşumlu (`--dry-run`):** önce yalnızca rapor üretir (kaç düğüm ADD, kaç NOOP, kaç SUPERSEDE, kaç reddedilir), kullanıcı onayından sonra yazar.
3. **Asıl güvence Obsidian'da:** 423 rapor + 5 playbook + wiki kasada duruyor ve göçten etkilenmiyor. En kötü senaryoda L2 raporlardan yeniden türetilebilir (`report_watcher.py` + `graph_store.ingest_text` zaten bu yolu biliyor).
4. **Geri alma:** `.bak` dosyasını geri kopyala + `ENTROPY_COGNITIVE_DB` ile eski dosyaya işaret et. Kod tarafında yeni kapı bayrakla kapatılabilir olmalı (`ENTROPY_MEMORY_GATE=0`).
5. **Doğrulama kapısı:** göç sonrası K1, K2, K3, K7, K10 ölçülmeden faz kapatılmaz. K2 (Hit@1) **düşerse göç geri alınır.**

### 5.4 Ayrıca temizlenecek — depo tarafı

`src/entropy/tools/autonomous_agent_architecture_faz*.py`: **59 dosya, 3,2 MB**, git'te yalnızca 4'ü izleniyor. Bunlar kod değil, üretim artığı. Öneri: izlenmeyen 55 dosya silinir; izlenen `faz158.py` ve `autonomous_agent_architecture.py` gözden geçirilip gerçekten içe aktarılan bir şey yoksa arşivlenir. `docs/reports/` altındaki 20 `...Faz1NN.md` raporu `docs/reports/_archive/` altına taşınır (silinmez — üretim tarihi kaydı).

Depo kökündeki `module_task_*.py`, `schema_task_*.py`, `test_task_*.py` (40+ dosya) ve `scratch/_*.log` dosyaları da aynı sınıfta; ayrı bir temizlik kartı hak ediyorlar.

---

## 6. Faz 11 iş listesi

Sıra bağımlılığa göre. Kota tahmini = CLI turu (bir tur ≈ orta boy bir prompt + yanıt).

| # | İş | Ajan | Bağımlılık | Kota | Kabul ölçütü |
|---|---|---|---|---|---|
| **11.1** | **Kategori disiplini + şema v2.** `category` kapalı küme doğrulaması; `provenance`, `confidence`, `valid_from/to`, `archived` sütunları; 13 uydurma kategorinin eşlemesi | memory-rag-engineer | — | ~8 | K7 = 4 kategori; mevcut testler yeşil |
| **11.2** | **Yazma kapısı `MemoryGate` (LLM'siz çekirdek).** Fikstür süzgeci + yoğunluk puanı + üç bant + `reconcile_facts` bağlantısı; `store_node` tek giriş | memory-rag-engineer | 11.1 | ~15 | K1 ≤ %10 (sentetik yineleme testinde); K11 ≤ 400 ms |
| **11.3** | **Gri bant kuyruğu + toplu CLI birleştirme turu.** `distiller.run_with_bridge` deseni; N aday tek promptta | agy-integration-engineer | 11.2 | ~12 | K9 ≤ %2; kuyruk boşalıyor; iptal edilebilir |
| **11.4** | **Test yalıtımı.** 7 `store_node` çağrı noktasının tamamı test ortamında geçici veritabanına; fikstür kalıbı üretim kapısında reddediliyor | qa-build-engineer | 11.2 | ~10 | K10 = 0; tam paket yeşil; üretim DB'sine test yazımı **0** |
| **11.5** | **Göç betiği (`--dry-run` + onay).** 1544 → ~668 seçici göç; yedek zorunlu; geri alma bayrağı | memory-rag-engineer | 11.2, 11.4 | ~10 | kuru koşum raporu; göç sonrası K1/K2/K3/K7/K10 |
| **11.6** | **Öz-amplifikasyon kilidi.** Açık tespiti (CRAG kapısı) + yenilik kotası + kaynak zorunluluğu; kota düşerse görev otomatik durur ve kullanıcıya bildirir | memory-rag-engineer + agy-integration-engineer | 11.2 | ~12 | K8 ≥ %70; kaynaksız L2 yazımı reddediliyor (K12 = 0) |
| **11.7** | **Konsolidasyon v2 (rüya).** Epizodik-48s koşulu kalkar; 0,95 kümeleme + birleştirme + arşivleme + wiki yükseltme; kaynak alanı yapısal | memory-rag-engineer | 11.2, 11.5 | ~15 | gecelik koşumda K1 sabit kalıyor; K6 artıyor |
| **11.8** | **Wiki derleme hattı (Karpathy L2).** `financial-auditor` (50 rapor) ve `media-agency-soldier` (16 rapor) için wiki sayfası üretimi; `lint.py` çelişki denetimi haftalık | memory-rag-engineer | 11.7 | **~40** (rapor sayısına bağlı, en pahalı kalem) | K6 ≥ %15; lint 0 çelişki |
| **11.9** | **Genel sohbet beyin paketi.** `BUDGET_GENERAL_BRAIN`; yetenek eşleşmediğinde ego + kurallar + wiki + PPR-genişletilmiş recall | memory-rag-engineer | 11.8 | ~8 | K4 ≥ %60; K5 ≥ %30 |
| **11.10** | **Okuma yolu eklentileri.** L1 kapsam süzgeci + PPR genişletme + CRAG eşiği ("beyinde yok" sinyali) | memory-rag-engineer | 11.5 | ~10 | K2 ≥ 8/10 ve #9 kaçırması düzeliyor; K3 ≤ %2 |
| **11.11** | **Depo temizliği.** 55 izlenmeyen `faz*.py` sil; 20 rapor `_archive/`'a; kök dizindeki `module_task_*`, `schema_task_*`, `test_task_*` ve `scratch/_*.log` temizliği | repo-curator | 11.5 | ~5 | `git status` temiz; import kırılmıyor; tam paket yeşil |
| **11.12** | **Bellek panosu (Desk "Bellek" sekmesi + Entropy).** Yineleme oranı, kategori dağılımı, gri bant kuyruk boyu, son göç raporu, K1-K12 canlı | ui-engineer | 11.5 | ~10 | panel açılıyor; sayılar betikle aynı |
| **11.13** | **Ölçüm paketi (regresyon).** 20 sorgulu kör test + yineleme betiği + bağlam kompozisyon betiği `tests/` altında kalıcı | qa-build-engineer | 11.10 | ~12 | `pytest` içinde koşuyor; K1-K12 raporu üretiyor |
| **11.14** | **Build + duman testi + faz raporu.** | qa-build-engineer | tümü | ~10 | `dist_check` açılıyor; hafıza paneli çalışıyor |

**Toplam kota tahmini: ~180 CLI turu.** En pahalı kalem 11.8 (wiki derleme, ~40); istenirse yetenek başına bölünüp iki faza yayılabilir.

**Öneri — kritik yol:** 11.1 → 11.2 → 11.4 → 11.5 → 11.6. Bu beşi bittiğinde asıl hasar (yineleme + öz-amplifikasyon + test sızıntısı) durmuş olur; kalanlar iyileştirmedir.

**Riskler:**
- *11.2 geri çağırmayı bozarsa* — K2 kapısı var, göç öncesi yakalanır.
- *11.5 göçte veri kaybı* — `.bak` + Obsidian ikili güvence (§5.3).
- *11.8 kota aşımı* — rapor başına damıtma turu; `distiller.plan()` zaten tur planlaması yapıyor, tavan konabilir.
- *11.11 import kırılması* — `faz*.py` dosyaları birbirini içe aktarıyor olabilir; silmeden önce bağımlılık taraması şart.

---

## 7. Kaynaklar

**Yazma tarafı denetimi ve konsolidasyon**
- SAGE: A Novelty Gate for Efficient Memory Evolution in Agentic LLMs — Wang, Brahma, Henao — arXiv:2605.30711 (29 May 2026; v2 18 Haz 2026) — https://arxiv.org/abs/2605.30711
- Dual-Layer Agentic Memory with Fast Write Routing and Slow Consolidation — Li ve ark. — arXiv:2608.22215 (23 Ağu 2026) — https://arxiv.org/abs/2608.22215
- The Consolidation Problem in Agent Memory — Hindsight, 21 May 2026 — https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation
- When Memory Becomes Authority: Benchmarking Authority Collapse at the Memory Consolidation Boundary — arXiv:2608.01679
- Manufactured Confidence: How Memory Consolidation Turns Hearsay into Confident Facts — arXiv:2606.29279
- What to Keep, What to Forget: A Rate–Distortion View of Memory Compaction in LLMs and Agents — arXiv:2607.08032

**Bellek mimarileri**
- Cognitive Architectures for Language Agents (CoALA) — arXiv:2309.02427 — https://arxiv.org/abs/2309.02427
- Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers — Pengfei Du — arXiv:2603.07670 (8 Mar 2026)
- A-MEM: Agentic Memory for LLM Agents — Xu, Liang, Mei, Gao, Tan, Zhang — arXiv:2502.12110
- HippoRAG 2 / From RAG to Memory: Non-Parametric Continual Learning for LLMs — Gutiérrez, Shu, Qi, Zhou, Su — arXiv:2502.14802, ICML 2025
- Zep: A Temporal Knowledge Graph Architecture for Agent Memory — arXiv:2501.13956 — https://arxiv.org/abs/2501.13956
- Graphiti: Knowledge graph memory for an agentic world — Neo4j geliştirici blogu — https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/
- Zep — Temporal Knowledge Graph tanımı — https://www.getzep.com/ai-agents/temporal-knowledge-graph/
- Letta — Memory Blocks — https://www.letta.com/blog/memory-blocks/
- Letta — Sleep-time Compute — https://www.letta.com/blog/sleep-time-compute/
- Letta — Context Repositories: Git-based Memory for Coding Agents — https://www.letta.com/blog/context-repositories/
- AMA-Bench: Evaluating Long-Horizon Memory for Agentic Applications — arXiv:2602.22769
- MAPLE: A Sub-Agent Architecture for Memory, Learning, and Personalization — arXiv:2602.13258
- Agent Memory: Characterization and System Implications of Stateful Long-Horizon Workloads — arXiv:2606.06448
- Governed Memory: A Production Architecture for Multi-Agent Workflows — arXiv:2603.17787

**Beceri / yordamsal bellek**
- SoK: Agentic Skills — Beyond Tool Use in LLM Agents — Jiang, Li, Deng, Ma, Wang, Wang, Yu — arXiv:2602.20867 (24 Şub 2026) — https://arxiv.org/abs/2602.20867
- HyperSkill: Self-Evolving LLM Agents via Hypergraph-Structured Skill Memory — arXiv:2608.16114
- SkillForge: Forging Domain-Specific, Self-Evolving Agent Skills — arXiv:2604.08618
- SkillAudit: Ground-Truth-Free Skill Evolution via Paired Trajectory Auditing — arXiv:2606.14239
- AEL: Agent Evolving Learning for Open-Ended Environments — arXiv:2604.21725
- Procedural Graphs: Self-Evolving Execution Structures for LLM Agents — arXiv:2609.09153 (HF Daily Papers, Eyl 2026)
- Environments as Scaffold: Enriching Feedback to Bootstrap Self-Evolving Agents — arXiv:2609.08404

**RAG**
- Graph Retrieval-Augmented Generation: A Survey — arXiv:2408.08921
- LEGO-GraphRAG: Modularizing Graph-based RAG for Design Space Exploration — arXiv:2411.05844
- GraphRAG-Bench — arXiv:2506.02404
- Is Agentic RAG worth it? An experimental comparison of RAG approaches — arXiv:2601.07711 (v2, Oca 2026)
- Reasoning RAG via System 1 or System 2: A Survey — arXiv:2506.10408
- Towards Agentic RAG with Deep Reasoning: A Survey of RAG-Reasoning Systems — arXiv:2507.09477
- Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG — arXiv:2501.09136
- Awesome-GraphRAG (kaynak listesi) — https://github.com/DEEP-PolyU/Awesome-GraphRAG
- LlamaIndex — Improved long and short-term memory for agents — https://www.llamaindex.ai/blog/improved-long-and-short-term-memory-for-llamaindex-agents

**mem0**
- Depo (Apache-2.0) — https://github.com/mem0ai/mem0
- Desteklenen LLM sağlayıcıları — https://docs.mem0.ai/components/llms/overview
- Graph memory (OSS'ten kaldırıldı; Platform özelliği) — https://docs.mem0.ai/open-source/graph_memory/overview
- OSS v2 → v3 göç kılavuzu — https://docs.mem0.ai/migration/oss-v2-to-v3
- Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory — arXiv:2504.19413
- State of AI Agent Memory 2026 (satıcı blogu) — https://mem0.ai/blog/state-of-ai-agent-memory-2026
- LoCoMo, LongMemEval & BEAM Leaderboard 2026 (satıcı blogu) — https://mem0.ai/blog/ai-memory-benchmarks-in-2026

**Karpathy / bilgi derleme**
- Karpathy LLM wiki deseni (GitHub gist `442a6bf555914893e9891c11519de94f`, Nis 2026) — açıklamalı derleme: https://www.kunalganglani.com/blog/llm-wiki-karpathy-local-knowledge-base
- Andrej Karpathy's LLM Wiki: Why the Future of AI Memory Isn't RAG — https://gamgee.ai/blogs/karpathy-llm-wiki-memory-pattern/

**Çerçeveler**
- Microsoft Agent Framework (AutoGen + Semantic Kernel) — https://learn.microsoft.com/en-us/agent-framework/overview/
- AutoGen → Microsoft Agent Framework göç kılavuzu — https://learn.microsoft.com/en-us/agent-framework/migration-guide/from-autogen/
- AG2 + GraphRAG-SDK (FalkorDB) — https://docs.falkordb.com/genai-tools/ag2.html

**Ajanda listelenen, durumu değişmiş kaynak**
- paperswithcode.com — **artık bağımsız yayında değil**; 302 ile https://huggingface.co/papers/trending adresine yönlendiriyor (10 Eyl 2026 denetimi). Yerine HF Daily Papers (https://huggingface.co/papers) kullanılmalı.
- @_akhaliq (X) — X erişimi yok; HF Daily Papers üzerinden takip edildi.

---

## Ek A — Ölçüm yeniden üretilebilirliği

Tüm sayılar `~/.entropy/cognitive_memory.db` (10 Eyl 2026, 21.061.632 bayt, 1544 satır) dosyasının bir kopyası üzerinde üretildi. Üretim veritabanı, kasa, kod ve ayarlar **değiştirilmedi**. Ölçüm adımları:

1. **Yineleme:** tüm `embedding_json` sütunları 384-boyutlu matrise yüklenir, L2 normalize edilir, `S = E·Eᵀ`; eşik üstü çiftlerde union-find.
2. **Kör geri çağırma:** `CognitiveMemorySystem(db_path=<kopya>)` (varsayılan olmayan yol verildiğinde `startup_maintenance` çalışmaz — `cognitive_memory.py:447-449`), 10 sorgu × `hybrid_recall(top_k=5)`, ilgililik önceden tanımlı düzenli ifadeyle.
3. **Bağlam kompozisyonu:** `CognitiveContextBuilder(memory_system=...).build(query, skill_name)`, `AssembledContext.sections` üzerinden `kind` bazında token toplamı.
4. **Üretilmiş dosya benzerliği:** `difflib.SequenceMatcher` ardışık `faz*.py` çiftlerinde.

Bu adımlar Faz 11'de `tests/` altına kalıcı regresyon paketi olarak taşınmalıdır (iş kalemi 11.13).
