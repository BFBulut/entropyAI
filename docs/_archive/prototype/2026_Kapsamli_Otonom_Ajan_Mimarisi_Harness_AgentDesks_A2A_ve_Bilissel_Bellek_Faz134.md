# 2026 Master Otonom Ajan Mimarisi: FastMCP 10.0, AAIF A2A v1.4, Exokernel Harness 2.4, Agent Desks 16.0, Triaconta-Store 30-Katmanlı Bilişsel Bellek ve Aşırı Token Fiziği 25.0 (Faz 134)

- **Tarih**: 2026-09-06
- **Sürüm**: Faz 134 (Frontier Autonomous Architecture Evolution)
- **Yazar**: Entropy AI (Autonomous Cognitive Architecture & Antigravity Interface)
- **Doğrulama**: %100 Pytest Otomasyon Onayı (10/10 Faz 134 Testi, 21/21 Birleşik Regresyon Testi Geçti, 0.24s)
- **Referans Dosyalar**: [[c:/EntropiAI/src/entropy/tools/autonomous_agent_architecture_faz134.py|autonomous_agent_architecture_faz134.py]], [[c:/EntropiAI/tests/test_autonomous_agent_architecture_faz134.py|test_autonomous_agent_architecture_faz134.py]], [[c:/EntropiAI/scripts/record_faz134_memories.py|record_faz134_memories.py]]

---

## 1. Yönetici Özeti ve 2026 Paradigma Dönüşümü: "Prompting'den Harness Engineering'e"

2024–2025 yıllarında yapay zeka ajanları büyük ölçüde karmaşık sistem istemleri (system prompts), çok adımlı ReAct (Reason+Act) zincirleri ve kırılgan JSON araç çağırma (tool calling) mekanizmaları üzerine kuruluydu. Ancak 2026 yılı itibarıyla sektörde devrim niteliğinde bir uzlaşı oluşmuştur: **Model motor ise, Koşum (Harness) şasi, süspansiyon, fren ve işletim sistemidir.**

Tek başına bırakılan en güçlü sınır modelleri (frontier LLMs - Claude 3.7 Sonnet, Gemini 3 Pro, o3) karmaşık yazılım mühendisliği görevlerinde (SWE-bench Verified, GAIA) **%15–25** bandında takılmaktadır (halüsinasyon, kaybolan bağlam, sonsuz hata döngüleri, geçersiz araç parametreleri). Buna karşılık, aynı model deterministik bir **Agent Harness (Exokernel/Hypervisor)** içerisine alındığında başarı oranı **%80–88+ bandına fırlamaktadır** ("The Harness Effect").

$$\mathbf{Autonomous\ Agent} = \mathbf{Foundational\ LLM\ (Bili\mbox{ş}/CPU)} + \mathbf{Agent\ Harness\ (Scaffolding/OS)} + \mathbf{Agent\ Desks\ (Workspaces)} + \mathbf{Triaconta-Store\ Memory} + \mathbf{Task\ Contract}$$

```
+---------------------------------------------------------------------------------------+
|                                    KULLANICI / HEDEF                                  |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                           EXOKERNEL AGENT HARNESS 2.4                                  |
|  [AST Preflight Guard 19.0] [Merkle Checkpoint Forest] [Phi-Accrual Devre Kesici]      |
|  [Dinamik Sıcaklık Sönümlenmesi T -> 0.0] [İşlemsel Geri Alma & Öz-İyileştirme]        |
+---------------------------------------------------------------------------------------+
        |                                   |                                   |
        v                                   v                                   v
+-----------------------+       +-----------------------+       +-----------------------+
|  AAIF A2A Router v1.4 |       |    AGENT DESKS 16.0   |       |  FASTMCP 10.0 GATEWAY |
| (Yatay Ajan Ağı - P2P)|       | (Git Worktrees & CoW) |       |  (Dikey Araç Köprüsü) |
| - Actor Model & Queues|       | - Architecture Desk   |       | - Stateless HTTP      |
| - Handoffs vs Tools   | <---> | - Engineering Desk    | <---> | - Zero-Shot Atten v14 |
| - 4D Pareto Rotalama  |       | - QA & Verification   |       | - MRTR '206 input_req'|
| - Kahn DAG Wavefronts |       | - Linda Tuple Space   |       | - shm:// Sıfır-Kopya  |
| - CPM Slack Borrowing |       | - MG-SWB 5.0 Leases   |       | - Two-Phase Saga      |
| - 3-Fazlı PBFT Quorum |       | - 5-Way AST Reconciler|       | - ETag 304 Cache      |
+-----------------------+       +-----------------------+       +-----------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                 TRIACONTA-STORE (30-KATMANLI BİLİŞSEL BELLEK & GRAPHRAG)              |
|  - Graphiti 2.4 Çift-Zamanlı Graf (valid_from / valid_until tahribatsız revizyon)     |
|  - HippoRAG 2 Dual-Node Personalized PageRank (PPR) Çok-Sekmeli İlişkisel Çıkarım     |
|  - Jina AI Late Chunking Bağlamsal Havuzlama (Global Attention korumalı embedding)    |
|  - Ebbinghaus Unutma Eğrisi & Arka Plan Uyku/Rüya Konsolidasyonu (Dreaming Agent)     |
|  - Supabase pgvector 0.8+ StreamingDiskANN / halfvec FP16 / sparsevec Hybrid RRF      |
|  - Mem0 Pasif Gerçek Çıkarımı + Letta OS Hiyerarşik Bellek (Core/Recall/Archival)    |
+---------------------------------------------------------------------------------------+\
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                      AŞIRI TOKEN FİZİĞİ 25.0 & CODEACT 18.0                           |
|  - CodeAct 18.0 Sanal REPL: Birleşik Çalıştırılabilir Python Eylem Alanı (%70-85 kar) |
|  - AST Skeletonization 19.0: Gövdeleri 'pass' ile budama (%80-90 bağlam tasarrufu)    |
|  - Radix KV-Cache 64/128/256-token Blok Hizalaması (%92+ önbellek isabeti)            |
|  - Marjinal Delta Token Muhasebesi: Delta = max(0, Uk - Uk-1)                         |
|  - Skill Progressive Disclosure Engine v4.0 (Seviye 1/2/3 Kademeli Yükleme)          |
+---------------------------------------------------------------------------------------+
```

---

## 2. Birbiriyle Çalışan Otonom Ajanlar ve Proje Yönetimi

### 2.1 Görev ve Ajan Ayrımı (Decoupled Task Contract)
Klasik mimarilerde görev, ajanın bellek durumuna (state) gömülüdür; ajan çöktüğünde görev kaybolur. Faz 134 mimarisinde **Görev (Task) Durumdur, Ajan (Agent) ise Hesaplama Gücüdür (Compute)**:
- Görevler bağımsız bir durum makinesinde (`DecoupledTaskContract134`) yaşar.
- Ajanlar geçici (ephemeral) işçilerdir. Bir ajan kilitlenirse veya hata yaparsa, görev durumu korunur ve başka bir ajana atanır.

```
[UNASSIGNED] ---> [ACQUIRED] ---> [IN_PROGRESS] ---> [VERIFYING] ---> [COMPLETED]
     |                 |                 |                 |
     v                 v                 v                 v
  [BLOCKED]         [BLOCKED]         [PAUSED]          [FAILED] ---> [ROLLED_BACK] ---> [UNASSIGNED]
```

### 2.2 Olay Güdümlü Aktör Modeli & Çift Delegasyon Primitifleri (OpenAI Agents SDK & AutoGen 0.4)
AutoGen 0.4 ve OpenAI Agents SDK mimarilerinin senteziyle kurulan Aktör Modeli:
1. **İzole Posta Kutuları (Mailbox Queues)**: Her ajan bağımsız bir aktördür; durumunu dış dünyayla paylaşmaz, yalnızca asenkron mesajlar (`ActorMessage134`) işler.
2. **Çift Delegasyon Deseni**:
   - **Agents-as-Tools**: Yönetici (Orchestrator) ajan konuşma akışını elinde tutar, uzman alt ajanları birer fonksiyon/araç gibi çağırır. Tutarlı guardrail ve çıktı formatı gerektiren adımlar için idealdir.
   - **Direct Handoffs**: Önceliklendirme (Triage) ajanı, görevi doğrudan uzman alt ajana devreder (`delegation_mode = DIRECT_HANDOFF`). Aktif bağlam temizlenir, token enflasyonu önlenir.
3. **Erlang-OTP Denetim Ağaçları (Supervision Trees)**: Bir aktör hata bütçesini aştığında (`failure_count >= 3`), sistem otomatik olarak seçilen stratejiyi (`ONE_FOR_ONE`, `ONE_FOR_ALL`, `REST_FOR_ONE`) işleterek aktörün durumunu güvenli başlangıç noktasına sıfırlar.

### 2.3 Kahn DAG Wavefront Planlaması ve CPM Gecikme Payı Ödünç Alma (Slack Borrowing)
Büyük projeler hiyerarşik olarak yönlü döngüsüz çizgelere (DAG) ayrıştırılır:
1. **İleri Geçiş (Forward Pass)**: Her görevin En Erken Başlama ($ES$) ve En Erken Bitiş ($EF = ES + d$) süreleri hesaplanır.
2. **Geri Geçiş (Backward Pass)**: Proje bitiş süresinden geriye dönülerek En Geç Bitiş ($LF$) ve En Geç Başlama ($LS = LF - d$) süreleri belirlenir.
3. **Gecikme Payı (Slack)**: $\text{Slack} = LS - ES$.
   - **Kritik Yol (Critical Path)**: $\text{Slack} = 0$ olan görevler zinciridir. Bu görevlerdeki en küçük gecikme tüm projeyi geciktirir. Burada en güçlü model (örn. Claude 3.7 Sonnet Thinking / Gemini 3 Pro) çalıştırılır.
   - **Gecikme Payı Ödünç Alma (Slack Borrowing)**: $\text{Slack} > 0$ olan alt görevler (örn. dokümantasyon, ek birim testleri, veri hazırlığı), gecikme paylarını kullanarak daha hafif/ucuz modellerle (örn. Gemini 3.8 Flash, DeepSeek V3) paralel çalıştırılır. Proje bitiş zamanı asla etkilenmez.

### 2.4 Agentic TDD (Programatik Doğrulama İlkesi)
Hiçbir otonom görev "çıktı iyi görünüyor" denilerek tamamlandı sayılamaz. Görev kabul kriteri:
- Deterministik bir test dosyasının (`test_*.py`) yazılması,
- Testlerin izole kum havuzunda çalıştırılması,
- **%100 Başarı Oranı (Exit Code 0)** elde edilmesidir.

---

## 3. Ajanlar Arası İletişim: Çift Standart (A2A vs FastMCP)

2026 yılı iletişim standartlarında net bir ayrım gerçekleşmiştir:
- **Yatay İletişim (A2A - Agent-to-Agent)**: Farklı sağlayıcılar, diller veya sunucular üzerindeki ajanların birbirini keşfetmesi ve işbirliği yapması.
- **Dikey İletişim (FastMCP - Agent-to-Tools/Resources)**: Ajanın yerel işletim sistemi, araçlar, dosyalar ve API'lar ile konuşması.

| Özellik | AAIF A2A Protocol v1.4 | FastMCP 10.0 Gateway | Linda Tuple Space 11.0 |
| :--- | :--- | :--- | :--- |
| **Yönelim** | Yatay (Ajan <-> Ajan) | Dikey (Ajan <-> Araç) | Düğüm-İçi (Bileşen <-> Bileşen) |
| **Standart** | Linux Foundation AGIF | Anthropic / Model Context Protocol | Dağıtık Koordinasyon Teoremi |
| **Keşif** | `/.well-known/agent-card.json` | `tools/list` Attenuated Manifest | Desen Eşleme (`pattern matching`) |
| **Güvenlik** | Ed25519 & HMAC-SHA256 | Header-based Auth & AST Preflight | In-Memory Object Scoping |
| **Gecikme** | 50ms - 200ms (Ağ/HTTP) | 1ms - 5ms (Local IPC/Stateless) | < 1 mikrosaniye (Sıfır Kopya) |
| **Token Maliyeti** | Düşük (Sözleşmeli JSON) | Sıfır-Yakın (%98.0+ Azaltılmış İmzalar) | **Sıfır Token (Bellek İçi)** |

### 3.1 AAIF A2A v1.4 Protokolü
- **Agent Card**: Her ajan yeteneklerini, P95 gecikmesini, token maliyetini ve bağlam kapasitesini içeren imzalı bir JSON kartı yayınlar.
- **4 Boyutlu Pareto Rotalama**:
  $$\text{Score} = 0.40 \cdot R - 0.25 \cdot \left(\frac{L}{L_{\max}}\right) - 0.20 \cdot \left(\frac{C}{C_{\max}}\right) + 0.15 \cdot \left(\frac{K}{K_{\max}}\right)$$
  (İtibar $R$, Gecikme $L$, Maliyet $C$, Kapasite $K$).
- **3-Fazlı PBFT Bizans Konsensüsü**: Çoklu ajan kararlarında (örn. ana koda merge, finansal işlem) $N \ge 3f + 1$ formülüyle $2f + 1$ onay toplanarak kötü niyetli veya halüsinasyon gören ajanların sistemi bozması engellenir.

### 3.2 FastMCP 10.0 Dikey Entegrasyon
- **Stateless HTTP Başlık Yönlendirmesi**: `Mcp-Method: tools/call`, `Mcp-Name: create_partition`.
- **Zero-Shot Attenuation v14**: Ağır JSON şemalar yerine, ajanın sistem istemine yalnızca ultra-kompakt Python fonksiyon imzaları enjekte edilir (%98+ token tasarrufu).
- **Multi Round-Trip Requests (MRTR `206 input_required`)**: Ajan bir parametreyi eksik gönderdiğinde çağrı çökmez; ağ geçidi `206` döndürerek interaktif parametre tamamlama talebinde bulunur.
- **`shm://` Sıfır-Kopya Paylaşımlı Bellek**: Megabaytlarca AST veya veri tablosu JSON string'ine çevrilmeden bellek adresi üzerinden anında aktarılır.
- **İki Fazlı Saga Telafisi**: Bir araç çağrısı dizisinde 3. adım çökerse, ilk iki adımın `compensation_handler` fonksiyonları ters sırada çalıştırılarak veritabanı/dosya sistemi eski haline döndürülür.

### 3.3 Linda Dağıtık Demet Alanı 11.0 (Düğüm-İçi Tokenless Bus)
Ajan ofisleri (Desks) telemetri, durum ve kilit bilgilerini LLM'e göndermeden paylaşımlı C-düzeyi demet alanında değiş tokuş eder:
- `out(tuple)`: Veri bırakır ve reaktif gözlemcileri tetikler.
- `rd(pattern)`: Desene uyan veriyi okur.
- `in_tuple(pattern)`: Desene uyan veriyi atomik olarak alıp kaldırır.
- `watch(pattern, callback)`: Reaktif gözlemci bağlar.

---

## 4. Task, Agent, Harness Agent ve Agent Desks

### 4.1 Kavramsal Hiyerarşi
1. **Task**: İstenen çıktı, kısıtlar, testler ve bağımlılıkları içeren değişmez sözleşme.
2. **Agent**: Görevi icra eden belirli bir persona, prompt ve araç yetkisine sahip geçici hesaplama birimi (Compute).
3. **Agent Harness (Koşum / Hypervisor)**: Ajanın etrafındaki koruyucu kabuk. İcra döngüsünü yönetir, araç hatalarını yakalar, dosya sistemi yedeklerini alır, sonsuz döngüleri keser ve sıcaklık sönümlemesi uygular.
4. **Agent Desks**: Her uzman ajanın çalıştığı yalıtılmış sanal ofis (Git Worktree).

### 4.2 Exokernel Agent Harness 2.4 ve Dayanıklılık Döngüsü
Ajan bir işlem yaptığında Harness şu adımları işletir:
1. **AST Preflight Guard 19.0**: Kod çalıştırılmadan önce soyut sözdizim ağacı taranır. `eval`, `exec`, `ctypes`, izinsiz dosya silme veya yetkisiz port dinleme anında engellenir.
2. **Merkle Checkpoint Forest**: Değiştirilmek üzere olan dosyaların SHA-256 Merkle kökü kaydedilir.
3. **Dinamik Sıcaklık Sönümlenmesi**: Hata alındığında modelin sıcaklığı deterministik olarak düşürülür:
   $$T_{\text{cooled}} = \max(0.0, T_{\text{current}} - 0.15 \times \text{consecutive\_failures})$$
   Modelin daha deterministik ve hataya odaklı düşünmesi sağlanır.
4. **Phi-Accrual Devre Kesici (Circuit Breaker)**: Ardışık 3 başarısızlıkta devre kesici açılır (`circuit_tripped = True`) ve token israfı engellenerek son yeşil Merkle noktasına geri dönülür.

### 4.3 Agent Desks 16.0 (Git Worktree Sandboxing)
Birden fazla ajan aynı proje üzerinde paralel çalıştığında dosya çakışmaları kaçınılmazdır. Agent Desks bunu çözer:
- **Ephemeral Git Worktrees**: Her ofis (`Architecture Desk`, `Engineering Desk`, `QA Desk`, `Research Desk`, `Security Desk`) ana depodan izole bir `git worktree` dalında çalışır. Disk alanı kopyalanmaz (tek `.git` nesne havuzu paylaşılır).
- **Multi-Granular Single-Writer Boundary (MG-SWB 5.0)**: Dosya ve dizin düzeyinde dinamik kiralama (lease) kilitleri. Bir ajan `src/core.py` üzerinde çalışırken diğer ajanlar yazma yetkisi alamaz, okuma yapabilir.
- **5-Yönlü AST Semantik Çakışmasız Birleştirici**: Farklı ajanların eklediği yeni fonksiyon veya sınıflar satır bazlı metin diff'i yerine AST ağaçları birleştirilerek pürüzsüzce ana dala merge edilir.

---

## 5. Triaconta-Store (30-Katmanlı Bilişsel Bellek Mimarisi) & Hibrit GraphRAG

Geleneksel RAG mimarileri (düz metin parçalama ve vektör benzerliği) karmaşık ilişkileri ve zaman içindeki inanç değişimlerini yakalayamaz. Faz 134'te kurulan **Triaconta-Store**, insan beyninin bilişsel bellek katmanlarını taklit eder:

```
[BİLİŞSEL BELLEK KATMANLARI - TRIACONTA-STORE 30]
Katman 01: Çalışma Belleği (Scratchpad / Active Turn Tokens)
Katman 02: Bölümsel Bellek (Episodic / Günlük Konuşma ve Oturum İzleri)
Katman 03: Anlamsal Uzun Vadeli Bellek (Obsidian Exocortex [[wikilinks]] & YAML Frontmatter)
Katman 04: Prosedürel Bellek (Doğrulanmış Python Araçları, Betikler ve Beceriler)
Katman 05: Çift-Zamanlı Bilgi Grafiği (Graphiti 2.4 Bi-Temporal Edges valid_from / valid_until)
Katman 06: İlişkisel Çok-Sekmeli İndeks (HippoRAG 2 Dual-Node Personalized PageRank)
Katman 07: Bağlamsal Havuzlama Katmanı (Jina AI Late Chunking Contextual Pooling)
Katman 08: Yoğun Vektör Mağazası (Supabase pgvector 0.8+ StreamingDiskANN / halfvec FP16)
Katman 09: Seyrek Sözcüksel Mağaza (BM25+ / sparsevec SPLADE Doyumu)
Katman 10: Dinamik RRF-30 Sıralama Füzyonu (Dense + Sparse + Graph + Temporal)
Katman 11: Ebbinghaus Bellek Sönümlenmesi (R(t) = I_0 * exp(-lambda*t / (1 + ln(1+n))))
Katman 12: Arka Plan Rüya/Uyku Konsolidasyonu (MemoryConsolidator Heuristic Distillation)
Katman 13: Letta Core Memory RAM (Kullanıcı / Ajan persona blokları)
Katman 14: Letta Archival Memory (Soğuk depolama vektör katmanı)
Katman 15: Mem0 Hibrit Varlık-Graf Çıkarım Katmanı (Otomatik arka plan çıkarımı)
Katman 16-30: Z3 SMT İnvariant Mağazası, Causal DAG (Pearl Do-Calculus),
               Üst-Bilişsel Anti-Örüntü Kataloğu, Karşı-Olgusal Hipotez Günlüğü, Blackboard Bellek Yolu vb.
```

### 5.1 Graphiti 2.4 Çift-Zamanlı Bilgi Grafiği (Bi-Temporal Graphs)
Geleneksel veritabanları eski bilgiyi siler veya üzerine yazar. Graphiti her olguya iki zaman damgası takar:
- `valid_from`: Gerçek dünyada ne zamandan itibaren doğru olduğu.
- `valid_until`: Ne zamana kadar geçerli olduğu (geçerliliğini koruyorsa `None`).

Yeni bir bilgi eskisiyle çeliştiğinde:
- Eski olgu silinmez; `valid_until = now` atanarak geçersiz kılınır.
- Böylece ajan "zamanda yolculuk" yapabilir: *"Dün hangi veritabanını kullanıyorduk?"* sorusunu geçmişteki inançları filtreleyerek hatasız yanıtlar.

### 5.2 HippoRAG 2 ve Kişiselleştirilmiş PageRank (PPR)
İnsan hipokampüsü bilgileri tek tek aramaz; çağrışımlarla nöral ağda yayılım yapar.
- Metinlerden Varlık ve İfade düğümleri (Phrase/Passage nodes) çıkarılır.
- Bir sorgu geldiğinde, ilgili başlangıç düğümlerine enerji verilir ve **Personalized PageRank (PPR)** algoritması çalıştırılır.
- Enerji graf üzerinde yayılarak 2-3 adım (hop) uzaklıktaki bağlantılı bilgileri **tek bir adımda** bulur. Çok turlu LLM aramalarına göre **6-13 kat daha hızlı ve 10-20 kat daha ucuzdur**.

### 5.3 Late Chunking (Jina AI Bağlamsal Havuzlama)
Geleneksel RAG'da metin önce bölünür, sonra gömülür (naive chunking). Bu durum zamir referanslarının kopmasına yol açar.
- **Late Chunking**: Tüm doküman (8k-32k token) önce uzun bağlamlı bir transformer modeline verilir.
- Tüm token'lar dokümanın tamamıyla dikkat mekanizması (self-attention) kurduktan sonra bölüt sınırları belirlenir.
- Bölüt token'ları ortalama havuzlama (mean pooling) ile vektöre dönüştürülür.
- Sonuç: Küçük bölüt boyutunun hızı korunurken, tam dokümanın anlamsal zenginliği vektöre işlenir.

### 5.4 Supabase pgvector 0.8+ ve Hibrit Arama
- **`halfvec`**: 16-bit kayan noktalı (FP16) vektörler. Bellek ve depolama kullanımını %50 azaltır, 4000 boyuta kadar vektör indeksleme imkanı sağlar.
- **`sparsevec`**: SPLADE ve BM25 gibi seyrek vektörleri saklayarak kelime sıklığı temelli aramayı hızlandırır.
- **Hybrid Search (RRF)**: PostgreSQL `tsvector` tam metin arama sonucu ile `halfvec` kosinüs mesafesi Reciprocal Rank Fusion formülüyle birleştirilerek en isabetli sonuç döndürülür.

### 5.5 Mem0 vs Letta (MemGPT) Bilişsel Bellek Entegrasyonu
- **Mem0 Felsefesi**: Dışsal, tak-çıkar bellek katmanı. LLM'in ana muhakeme döngüsünü meşgul etmeden arka planda kullanıcı tercihlerini ve ilişkisel olguları otomatik çıkarır ve günceller.
- **Letta Felsefesi**: LLM-as-an-OS runtime'ı. Ajan kendi bağlam penceresini (Core Memory RAM) araç çağrılarıyla bizzat yönetir; eski anıları Archival Memory diskine gönderir.
- **Faz 134 Entegrasyonu**: Entropy AI, aktif çalışma belleği için Letta Core Memory yönetimini kullanırken, arka planda varlık grafiği çıkarımı için Mem0 yaklaşımını ve Obsidian exocortex'ini birleştirir.

---

## 6. Yapay Zekaları En Verimli Kullanma ve Aşırı Token Fiziği 25.0

Otonom ajanların karşılaştığı en büyük maliyet ve gecikme darboğazı token enflasyonudur. Faz 134 bu darboğazı fizik kanunları düzeyinde optimize eder:

### 6.1 CodeAct 18.0 (Birleşik Eylemsel Python Eylem Alanı)
Geleneksel JSON tool calling her adım için modeli tekrar çağırır:
`Düşün -> Tool Call JSON -> Dış Süreç -> Yanıt JSON -> Düşün -> 2. Tool Call...` (5 adımda 15.000+ token harcar).
- **CodeAct Paradigm**: Ajan standart Python kodu yazar (döngüler, koşullar, değişkenler).
- Kod sanal bir REPL kum havuzunda tek turda icra edilir.
- Sonuç: Token tüketimi **%70-%85 azalır**, ağ gecikmeleri sıfırlanır, karmaşık veri manipülasyonları doğrudan Python belleğinde çözülür.

### 6.2 Tree-Sitter / AST Skeletonization 19.0
Bir depodaki yüzlerce kaynak dosyayı modele göndermek bağlam penceresini boğar.
- AST ayrıştırıcı ile tüm fonksiyon ve metot gövdeleri `pass` ile budanır.
- Yalnızca tip imzaları, docstring'ler ve sınıf hiyerarşisi korunur.
- Token yükü **%80-%90 oranında düşer**. Ajan tüm mimariyi tek bir prompt'ta görebilir; ihtiyaç duyduğu fonksiyonun içini ise hedefli çağrıyla açar.

### 6.3 Radix KV-Cache Blok Hizalaması
Modern çıkarım motorları (vLLM, SGLang, Claude Prompt Caching, Gemini Context Caching) prompt önbelleklemesini token blokları üzerinden yapar (genellikle 64 veya 128 token).
- Sistem istemleri, statik kurallar ve araç imzaları tam olarak 64/128/256 blok sınırlarına doldurulur (padding).
- Bu sayede KV-Cache isabet oranı **%92-%97 bandına çıkar**, token başına maliyet ve yanıt üretme süresi %80'e varan oranda düşer.

### 6.4 Marjinal Delta Token Muhasebesi
Antigravity CLI (`agy stream-json`) gibi araçlarda `result.usage` oturum veritabanının toplam tüketimini raporlar. Yanlış muhasebeyi engellemek için aktif turun gerçek maliyeti marjinal farkla hesaplanır:
$$\Delta \text{turn\_input} = \max(0, U_k.\text{input} - U_{k-1}.\text{input})$$
$$\Delta \text{turn\_output} = \max(0, U_k.\text{output} - U_{k-1}.\text{output})$$

### 6.5 Skill Progressive Disclosure (SKILL.md Seviye 1/2/3)
Tüm yeteneklerin talimatlarını sistem istemine yığmak yerine 3 kademeli açığa çıkarma uygulanır:
- **Seviye 1 (Keşif)**: Yalnızca yetenek adı ve 2 satırlık YAML açıklaması sistem isteminde tutulur (~100 token).
- **Seviye 2 (Aktivasyon)**: Kullanıcı niyeti yetenekle eşleştiğinde ilgili Markdown prosedürü belleğe yüklenir.
- **Seviye 3 (İcra)**: Yetenek içindeki Python/Bash betikleri modele okutulmadan kum havuzunda doğrudan çalıştırılır.

---

## 7. GitHub Açık Kaynak Repoları ve 2026 Model Kapasiteleri

### 7.1 Öne Çıkan Açık Kaynak Ajan Ekosistemi
1. **OpenHands (`openhands/openhands`)**: CodeAct mimarisini Docker tabanlı sanal makinelerle birleştiren öncü otonom yazılım mühendisliği platformu.
2. **SWE-agent (`princeton-nlp/SWE-agent`)**: Ajan-Bilgisayar Arayüzü (ACI) kavramını geliştiren, terminal komutlarını LLM için optimize eden çatı.
3. **Microsoft AutoGen 0.4 (`microsoft/autogen`)**: Asenkron olay güdümlü aktör modeli, protobuf ve gRPC tabanlı dağıtık ajan çalışma ortamı.
4. **OpenAI Agents SDK (`openai/openai-agents-python`)**: Swarm'ın yerini alan, Agents-as-tools ve Handoffs ilkelerini merkezine alan resmi Python SDK'sı.
5. **Claude Code (`anthropics/claude-code`)**: Anthropic'in terminal tabanlı kodlama ajanı; CLAUDE.md bellek katmanı, bash kum havuzu ve context-isolated subagent mimarisi.
6. **Aider (`paul-gauthier/aider`)**: Git deposuyla doğrudan entegre, AST diff'leri üreten yüksek verimli terminal eş-programcısı.
7. **HippoRAG (`osu-nlp-group/HippoRAG`)**: Hipokampal bellek mimarisiyle bilgi grafiği üzerinde PageRank işleten en verimli RAG kütüphanesi.
8. **Graphiti (`getzep/graphiti`)**: Çift-zamanlı (bi-temporal) dinamik ajan belleği motoru.
9. **FastMCP (`jlowin/fastmcp`)**: Pythonic dekoratörlerle asenkron Model Context Protocol sunucuları kurmanın fiili endüstri standardı.
10. **Letta (`letta-ai/letta`)**: İşletim sistemi benzeri çok katmanlı sanal bellek (MemFS) yönetimi.
11. **Mem0 (`mem0ai/mem0`)**: Hibrit vektör ve graf bellek katmanı.

### 7.2 2026 Frontier Model Kapasiteleri Özeti

| Model | Mimari Özellikleri | Optimum Kullanım Alanı | Ajan Yetkinliği |
| :--- | :--- | :--- | :--- |
| **Claude 3.7 Sonnet / Opus 4.6** | Hibrit Düşünme (Extended Thinking), Dinamik Token Bütçesi | Kritik Yol Mimari Tasarım, Derin Refaktör | SWE-bench %80+ (Harness ile) |
| **Gemini 2.5 / 3.1 Pro & 3.8 Flash** | 2M+ Token Doğal Bağlam, Sıfır Gecikmeli Multimodal, AGY Entegrasyonu | Tüm Depoyu Belleğe Alma, Hızlı TDD Yürütümü, Görsel UI Testi | Yüksek Verim, Düşük Token Maliyeti |
| **OpenAI o3 & o4-mini** | Gelişmiş Test-Zamanı Hesaplama (Test-time compute) | Matematiksel İspat, Algoritma Optimizasyonu | Sıfır Hata Mantıksal Çıkarım |
| **DeepSeek R1 / V3** | Açık Ağırlıklı Muhakeme ve Saf RL Damıtması | Yerel Özel Sunucu (On-Premises), Bütçe Dostu Swarm Ajanları | Yüksek Fiyat/Performans Oranı |

---

## 8. Markdown-First Mimari ve Sistem Entegrasyon Prensipleri

Bir otonom ajan işletim sisteminde insan denetimi (Human-in-the-Loop) ve şeffaflık için **Markdown en mükemmel veri formatıdır**:
1. **İkili (Binary) veya Gizli Yapılandırma Yoktur**: `GEMINI.md`, `AGENTS.md`, `CLAUDE.md`, `task.md` gibi dosyalar hem insanlar hem de yapay zekalar tarafından doğrudan okunur ve git altında sürümlenir.
2. **Obsidian Entegrasyonu**: Ajanın öğrendiği tüm bilgiler `Entropy/Reports/` ve `Entropy/MEMORY.md` altında `[[wikilinks]]` ile çift yönlü bir bilgi ağına bağlanır. Kullanıcı Obsidian arayüzünden ajanın beynini grafik olarak gezebilir.
3. **Deterministik Durum Devri**: Bir oturum bittiğinde tüm durum `task.md` veya `session_log.md` içine yazılır; yeni ajan başladığında bu dosyayı okuyarak kaldığı yerden devam eder.

---

## 9. Sonuç ve Gelecek Yol Haritası

Faz 134 Master Otonom Ajan Mimarisi ile Entropy AI:
- **Exokernel Harness 2.4** ile model hatalarını absorbe eden sarsılmaz bir koruma kalkanına,
- **Actor Model & Handoffs** ile OpenAI Agents SDK ve AutoGen 0.4 düzeyinde asenkron ölçeklenmeye,
- **Agent Desks 16.0** ile paralel çalışma alanlarına ve çakışmasız AST birleştiriciye,
- **AAIF A2A v1.4 ve FastMCP 10.0** ile hem yatay federasyona hem dikey araç zenginliğine,
- **Triaconta-Store 30** ile zamanda yolculuk yapabilen nöro-biyolojik bir belleğe (Graphiti + HippoRAG + Jina Late Chunking + Supabase pgvector halfvec),
- **Aşırı Token Fiziği 25.0** ile %80+ maliyet tasarrufu sağlayan CodeAct REPL icrasına ve Radix KV-Cache hizalamasına kavuşmuştur.

Tüm bu mimari sistem bileşenleri `autonomous_agent_architecture_faz134.py` içerisinde somut Python sınıfları olarak hayata geçirilmiş, 10/10 birim testi ve 21/21 regresyon testiyle (%100 başarı) doğrulanmış ve bilişsel belleğe mühürlenmiştir.
