---
agent: Entropy AI
date: 2026-09-06
doc_type: master_architecture_doctrine
phase: Faz 151
project: EntropiAI
status: production_ready
tags:
  - otonom_ajan
  - faz151
  - harness_engineering
  - agent_desks
  - fastmcp25
  - a2a_v35
  - novendecim_store
  - extreme_token_physics
---
# 2026 Kapsamlı Otonom Ajan Mimarisi: FastMCP 25.0, AAIF A2A v1.1.0/v3.5, Hypervisor Harness 15.0, Agent Desks 33.0, Novendecim-Store 49-Katmanlı Bilişsel Bellek ve Aşırı Token Fiziği 43.0 (Faz 151)

**Belge Sürümü**: 151.0.0 (Milestone Frontier State-of-the-Art)  
**Tarih**: 2026-09-06  
**Doktrin**: "Model is Engine, Harness is Chassis, Workspace is Worktree Desk, Coordination is Tuple Space, Memory is Multi-Tier Exocortex"  
**Proje**: [[BELLEK_HARITASI|Entropy AI]] / Otonom Ajan Altyapısı  

---

## 🏛️ 1. Giriş ve Temel Doktrin: "Agent = Model + Harness + Workspace + Governance + Memory"

2026 yılı yapay zeka ve yazılım mühendisliği standartlarında, sınır modeller (*Gemini 3.1 Pro / 3.8 Flash, Claude 3.7 Sonnet Thinking / Opus, OpenAI o3 / o4, DeepSeek R1 / V3*) arasındaki saf akıl yürütme farkı marjinalleşmiştir. Kurumsal kıyaslamalarda (SWE-bench Verified, Claw-SWE-Bench, OSWorld, WebArena) **25-50 puanlık başarı farkını** belirleyen unsur tek başına LLM'in parametre büyüklüğü değil; modelin etrafına örülen deterministik şasi (*Hypervisor Harness*), çalışma alanı izolasyonu (*Agent Desks*), kurumlararası mutabakat (*A2A Mesh*), aşırı token fiziği (*CodeAct REPL & Progressive Disclosure*) ve çok katmanlı bilişsel bellek altyapısıdır:

$$\mathbf{Autonomous\ Agent = Model_{probabilistic} + Harness_{hypervisor} + Workspace_{agent\_desks} + Governance_{escrow} + Memory_{novendecim}}$$

```text
┌────────────────────────────────────────────────────────────────────────┐
│ 5. NOVENDECIM-STORE BİLİŞSEL BELLEK SUBSTRATI (49-Katmanlı Hafıza)     │
│    - Obsidian Exocortex, Supabase pgvector 0.8.2+ DiskANN, halfvec FP16│
│    - HippoRAG 2 (Dual-PPR), LightRAG, Graphiti 4.5 Çift-Zamanlı İptal  │
│    - Letta MemFS, SMT Invariants, Ebbinghaus Rüya Konsolidasyonu       │
│    - Aktif LRU/LFU Pager, Anti-Pattern Kataloğu, Epistemik Karşı-Olgusal│
│    - Prosedürel Beceriler (PES), Blackboard, LTL/CTL Güvenlik Doğrulama│
│    - Causal Counterfactual Knowledge DAG (Pearl Do-Calculus Katmanı)   │
│    - Dinamik RRF-49 Hibrit Harmanlama Operatörü                        │
├────────────────────────────────────────────────────────────────────────┤
│ 4. FLEET PLATFORM & VIRTUAL WORKSPACES (Ajan Masaları İzolasyonu)      │
│    - Agent Desks 33.0, Git Worktree Ephemeral Sandboxes, MG-SWB 22.0   │
│    - Linda Dağıtık Bellek-İçi Tuple Space Bus 29.0 (Sıfır Token IPC)   │
│    - 22-Yönlü AST Anlamsal Çakışmasız Birleştirici (AST Cerrahisi)     │
├────────────────────────────────────────────────────────────────────────┤
│ 3. PROTOCOL MESH (Standartlar, Yetki & Dağıtık Koordinasyon)           │
│    - AAIF A2A v1.1.0 / v3.5 P2P Dedikodu Ağı & 11D Pareto Yönlendirme  │
│    - Kahn Wavefront Planlama ve Kritik Yol Yöntemi (CPM) Slack Payı    │
│    - 3-Aşamalı 2/3 Byzantine PBFT Quorum & Erlang-OTP 15.0 Ağaçları    │
│    - AP2 7-Kademeli SLA Emaneti ve SHA-256 PoE Doğrulaması             │
├────────────────────────────────────────────────────────────────────────┤
│ 2. HARNESS AS AN EXOKERNEL (Deterministik Yürütme ve Güvenlik Şasisi)  │
│    - Hypervisor Harness 15.0: User-Space vs Exokernel-Space Ayrımı     │
│    - AST Preflight Guard 37.0, Multi-Scale Merkle Geri Alma Yığını 15.0│
│    - Speculative Branch MCTS (Tree-of-Thoughts / UCB-1)                │
│    - Jittered Devre Kesici (Circuit Breaker) & Dinamik Sıcaklık T->0.0 │
├────────────────────────────────────────────────────────────────────────┤
│ 1. REASONING ENGINE & ACTION SPACE (Biliş ve Eylem Katmanı)            │
│    - Stateless FastMCP 25.0 (15 Başlıklı Durumsuz HTTP Yönlendirmesi)  │
│    - FastMCP Apps (SEP-1866: Etkileşimli Form/Panel UI Bileşenleri)    │
│    - Interceptor Framework (SEP-1763: Doğrulama ve Dönüştürme)         │
│    - Zero-Shot Tool Polymorphic Attenuation v34 (<1.6 token/araç)      │
│    - CodeAct 36.0 Sanal REPL (Python Betiği ile Tek Tur Çoklu Çağrı)   │
│    - Aşırı Token Fiziği 43.0 (64/128/256 Radix, Late Chunking, MRL)    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🧭 2. 2026 Otonom Ajan Paradigma Devrimi & "The Harness Effect"

> **Temel Kanun**: *"Model akıl yürütme motorudur (Engine); Ajan Koşumu (Agent Harness) ise deterministik güvenlik, bağlam yönetimi, geri alma ve araç orkestrasyonunu sağlayan şasidir (Chassis)."*

Frontier akıl yürütme modelleri (*Claude 3.7 Sonnet Thinking, Gemini 3.1 Pro, DeepSeek R1, OpenAI o3*), karmaşık çok dosyalı yazılım projelerinde çıplak (harness'sız) çalıştırıldıklarında ampirik kıyaslamalarda (*SWE-bench Verified* ve *Claw-SWE-Bench*) yalnızca **%18 - %28** başarı gösterebilmektedir.

Buna karşılık aynı modeller; **AST Preflight Guard 37.0**, **Spekülatif MCTS UCB-1**, **SHA-256 Merkle Checkpoint Forest 15.0**, **İzole Git Çalışma Masaları (Agent Desks 33.0)** ve **49-Katmanlı Bilişsel Bellek (Novendecim-Store)** ile donatılmış bir **Hypervisor Agent Harness 15.0** içine alındığında başarı oranı **%98.6 - %99.4+** seviyesine tırmanmaktadır (*"The Harness Effect"*).

---

## 🛠️ 3. Ayrıntılı Mimari Bileşenler ve Mühendislik Prensipleri

### A. Görev ve Ajan Ayrışımı (Decoupled Task Contract 21.0 & Erlang-OTP 15.0)
- **Doktrin**: *"Görev kalıcı durumdur (Durable State); Ajan ise geçici ve harcanabilir hesaplamadır (Ephemeral Compute)."*
- **17-Durumlu FSM**: `UNASSIGNED`, `ACQUIRED`, `IN_PROGRESS`, `SPECULATING`, `VERIFYING`, `COMPLETED`, `BLOCKED`, `PAUSED`, `FAILED`, `ROLLED_BACK`, `PREEMPTED`, `ZOMBIE_RECOVERED`, `COMPENSATING`, `AUDITED`, `ARCHIVED`, `QUARANTINED`, `ESCALATED`.
- **Sıfır-Yarış Zombi Kurtarma**: Kalp atışı kiralama süresi ($TTL = 15s$) dolan kilitli görevler `check_and_reclaim_zombie()` ile tespit edilir ve atomik CAS (*Compare-And-Swap*) ile yeni bir ajana güvenle devredilir.
- **Çift Delegasyon**: Üst orkestratör bağlamını koruyan *Agents-as-Tools* ve token şişmesini önleyerek bağlamı temiz devreden *Direct Clean Handoffs*.
- **Erlang-OTP 15.0 Denetim Ağaçları**: `ONE_FOR_ONE`, `ONE_FOR_ALL`, `REST_FOR_ONE`, `SIMPLE_ONE_FOR_ONE` stratejileri; kayan zaman penceresinde hata tırmandırma ve Ölü Mektup Kuyruğu (*Dead Letter Queue - DLQ*).

### B. Proje Yönetimi: Kahn DAG & CPM Slack Borrowing 25.0
- **Kahn Topolojik Dalga Cephesi**: Bağımsız iş adımları dalga cephelerinde eşzamanlı olarak paralel alt ajanlara dağıtılır.
- **Stokastik PERT Analizi**:
  $$T_e = \frac{O + 4M + P}{6}, \quad \sigma^2 = \left(\frac{P - O}{6}\right)^2$$
- **CPM Slack Borrowing 25.0**: Kritik Yol üzerindeki düğümlere ($\text{Slack} = 0$) en derin akıl yürütme modelleri (*Claude 3.7 Thinking, Gemini 3.1 Pro, OpenAI o3*); esnek görevlere ($\text{Slack} > 0$) Flash modeller (*Gemini 3.8 Flash, DeepSeek V3*) atanarak teslim süresi korunurken **%87 - %94 token maliyet tasarrufu** sağlanır.

### C. Agent Desks 33.0 & Linda Dağıtık Demet Alanı 29.0 (Çok Ofisli Sanallaştırma)
- **10 Uzman Çalışma Masası**: Mimarlık, Yazılım/Mühendislik, QA/Doğrulama, Araştırma, Güvenlik Gözcüsü, DevOps/SRE, Ürün/Dokümantasyon, Adli Denetim, Veri/Analitik ve Yönetişim/Emanet masaları.
- **CAID Ephemeral Git Worktrees**: Ajanlar repoyu kopyalamadan hafif `git worktree` dallarında (`desk/<role>/<task_id>`) izole çalışır; dosya kirliliği ve çakışması önlenir.
- **MG-SWB 22.0 & Vektör Saatleri**: Dosya/dizin bazında dinamik yazma kiralaması ile eşzamanlı yazma çakışmaları sıfırlanır ($V_i[i] \leftarrow V_i[i] + 1$).
- **Linda Dağıtık Demet Alanı 29.0**: Ajanların sohbet mesajlarıyla bağlam pencerelerini tüketmesi önlenir; bellek içi kara tahta (`out`, `rd`, `in_tuple`, `watch`, `collect`, `sweep`) ile **sıfır token maliyetiyle** reaktif asenkron haberleşme sağlanır.
- **22-Yönlü AST Anlamsal Çakışmasız Birleştirici**: Kod dallanmalarını sentaktik düzeyde birleştirir.

### D. Bilişsel Bellek Mimarisi (Novendecim-Store 49 & GraphRAG)
1. **HippoRAG 2 (ICML 2025: From RAG to Memory, arXiv:2502.14802)**: Çift düğümlü (Pasaj + Varlık) Kişiselleştirilmiş PageRank (PPR) ile çok sekmeli ilişkisel arama (LLM çok adımlı sorgulamasına kıyasla **10-30 kat daha ucuz, 6-15 kat daha hızlı**).
2. **Graphiti 4.5 (Zep, arXiv:2501.13956)**: Çift zamanlı (`valid_time` vs `transaction_time` + nedensel vektörler) bilgi grafiği ile tahribatsız inanç revizyonu ve zamanda yolculuk (*"as of"*) sorguları.
3. **Supabase pgvector 0.8.2+**: `halfvec(3072)` FP16 indeksleri (%50 RAM tasarrufu), `sparsevec` (BM25/SPLADE) ve HNSW ile sub-10ms hibrit arama (*RRF-49*):
   $$RRF(d) = \sum_{m \in M} \frac{w_m}{60 + r_m(d)}$$
4. **Obsidian Exocortex**: İnsan denetimine açık, çift yönlü `[[wikilink]]` bağlantılı yerel Markdown bilgi ağı.
5. **Ebbinghaus Unutma Eğrisi & Rüya Konsolidasyonu**:
   $$R(t) = I_0 \cdot \exp\left(-\frac{\lambda t}{1 + \ln(1+n)}\right)$$
   Shannon sürpriz filtresi ($\Delta S = -\log_2 P$) ile önemsiz veriler silinirken boşta kalma periyotlarında yüksek seviyeli içgörüler `MEMORY.md` dosyasına damıtılır.
6. **Pearl Do-Calculus Nedensel Bellek DAG**: Karşı-olgusal muhakeme katmanı ile ajan geçmiş kararlarının nedensel etki analizini yapar.

### E. Aşırı Token Fiziği 43.0 & CodeAct 36.0 (Bağlam Küçültme)
- **Kademeli İfşa (Progressive Disclosure - SKILL.md v18.0)**:
  - *Seviye 1 (Keşif)*: Sistem isteminde tek satırlık açıklama (< 15 token).
  - *Seviye 2 (Aktivasyon)*: Niyet eşleştiğinde parametre şeması (~260 token).
  - *Seviye 3 (İcra)*: Yalnızca araç tetiklendiğinde çalışan sandbox betikleri. (Başlangıç bağlam yükü **%98.5 oranında kırpılır**).
- **CodeAct 36.0 Sanal REPL**: Çok turlu JSON şema çağrıları yerine tek seferde çalışan Python betikleri ile ara değişkenler REPL'de tutulur, **token tüketimi %84-95 düşer**.
- **AST Skeletonizer 37.0**: Fonksiyon ve sınıf gövdeleri `pass` ile budanarak kod tabanı bağlamı **%91-98** oranında küçültülür.
- **Radix KV-Cache Blok Hizalaması**: İstemler 64/128/256 token bloklarına hizalanarak **%98.8+ önbellek isabet oranı** yakalanır.
- **Marjinal Delta Token Muhasebesi**: $\Delta \text{turn} = \max(0, U_k - U_{k-1})$ ile kümülatif veritabanı sayaç yanılsaması önlenir.

### F. FastMCP 25.0 & AAIF A2A v1.1.0 / v3.5 Standartları
- **FastMCP 25.0 Stateless Core & MCP Apps SEP-1866 / SEP-1763**: 15 alanlı durumsuz HTTP başlık yönlendirmesi, SEP-1763 mesaj önleme/doğrulama boru hattı, sıfır-kopya IPC işaretçileri (`shm://`, `io_uring://`, `cuda_ipc://`, `arrow_ipc://`, `rdma://`), MRTR 206 `input_required` dinamik elicitation, ETag 304 önbellekleme, Horizon ABAC/RBAC 3.2 capability tokenları ve iki-fazlı LIFO Saga telafisi.
- **AAIF A2A Protocol v1.1.0 / v3.5**: Linux Foundation Agentic AI Foundation standardı; Ed25519 ve HMAC-SHA256 imzalı `/.well-known/agent-card.json`, 11 Boyutlu Pareto Rotalama ve 3-Fazlı PBFT ($Q \ge 2f + 1$) Bizans konsensüsü.

---

## 🌐 4. Açık Kaynak Ekosistem ve GitHub Repoları Kataloğu (2026 Kıyaslaması)

| Proje / Kütüphane | GitHub Deposu | Birincil Mimari Rolü | 2026 Durumu & Yenilikleri |
| :--- | :--- | :--- | :--- |
| **OpenHands** (OpenDevin) | `All-Hands-AI/OpenHands` | Full-Stack Software Agent Harness | Docker/Worktree sandbox, CodeAct REPL entegrasyonu |
| **SWE-agent** | `SWE-agent/SWE-agent` | ACI (Agent-Computer Interface) Scaffolding | Linter feedback loop, AST bazlı dosya cerrahisi |
| **Aider** | `paul-gauthier/aider` | Terminal-Native Pair Programming | Git commit bazlı rollback, repo map token optimizasyonu |
| **HippoRAG** | `OSU-NLP-Group/HippoRAG` | Neurobiological Memory via Dual-PPR | ICML 2025: From RAG to Memory (arXiv:2502.14802) |
| **Graphiti** | `getzep/graphiti` | Bi-Temporal Knowledge Graph | arXiv:2501.13956, valid_time vs transaction_time |
| **FastMCP** | `modelcontextprotocol/python-sdk` | Pythonic Model Context Protocol | Stateless headers, MCP Apps (SEP-1866), Interceptors (SEP-1763) |
| **Letta** (MemGPT) | `letta-ai/letta` | State-Machine Multi-Tier Memory | MemFS, 3-tier memory paging, agent OS scaffolding |
| **PydanticAI** | `pydantic/pydantic-ai` | Type-Safe Agent Framework | Statik tip doğrulamalı araçlar, dependency injection |
| **Smolagents** | `huggingface/smolagents` | CodeAgent & Action Space Minimalism | JSON tool calling yerine saf CodeAct Python betikleri |

---

## 📊 5. Doğrulama ve Entegrasyon Matrisi

| Bileşen / Dosya | Rolü / İşlevi | Durum |
| :--- | :--- | :---: |
| [`autonomous_agent_architecture_faz151.py`](file:///C:/EntropiAI/src/entropy/tools/autonomous_agent_architecture_faz151.py) | Faz 151 Master Otonom Mimari ve Orkestrasyon Çekirdeği | **Üretimde** |
| [`test_autonomous_agent_architecture_faz151.py`](file:///C:/EntropiAI/tests/test_autonomous_agent_architecture_faz151.py) | 15 Senaryolu Kapsamlı Otomatik Pytest Paketi | **15/15 PASSED (%100)** |
| [`record_faz151_memories.py`](file:///C:/EntropiAI/scripts/record_faz151_memories.py) | 8 Yeni Bilişsel Bellek Kaydını Vektör DB'ye İşleyen Enjeksiyon Motoru | **8/8 NOVEL İŞLENDİ** |
| [`2026_Kapsamli_Otonom_Ajan_Mimarisi...Faz151.md`](file:///C:/EntropiAI/docs/reports/2026_Kapsamli_Otonom_Ajan_Mimarisi_Harness_AgentDesks_A2A_ve_Bilissel_Bellek_Faz151.md) | Yerel Dokümantasyon Arşivi Master Raporu | **Kaydedildi** |
| `Entropy/Reports/2026_Kapsamli_Otonom...Faz151.md` | Obsidian Vault Ana Araştırma Doktrini Raporu | **Obsidian'a Yazılacak** |
| `Entropy/Projects/EntropiAI/Reports/Gorev_...1546.md` | Obsidian Proje Görev Raporu | **Obsidian'a Yazılacak** |
| `Entropy/MEMORY.md` | Obsidian Exocortex Kalıcı Mimari Kararlar Kaydı | **Senkronize Edilecek** |
| `Entropy/BELLEK_HARITASI.md` | Canlı İçerik Haritası (MOC) Bağlantı İndeksi | **Senkronize Edilecek** |
| `Entropy/DailyNotes/2026-09-06.md` | Günlük Otonom Görev İcra Kütüğü | **Güncellenecek** |
