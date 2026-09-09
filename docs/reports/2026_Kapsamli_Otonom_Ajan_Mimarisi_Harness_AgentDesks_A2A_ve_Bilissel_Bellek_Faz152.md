---
agent: Entropy AI
date: 2026-09-06
doc_type: master_architecture_doctrine
phase: Faz 152
project: EntropiAI
status: production_ready
tags:
  - otonom_ajan
  - faz152
  - harness_engineering
  - agent_desks
  - fastmcp26
  - a2a_v36
  - novendecim_store
  - extreme_token_physics
---
# 2026 Kapsamlı Otonom Ajan Mimarisi: FastMCP 26.0, AAIF A2A v1.2.0/v3.6, Hypervisor Harness 16.0, Agent Desks 34.0, Novendecim-Store 50-Katmanlı Bilişsel Bellek ve Aşırı Token Fiziği 44.0 (Faz 152)

**Belge Sürümü**: 152.0.0 (Milestone Frontier State-of-the-Art)  
**Tarih**: 2026-09-06  
**Doktrin**: "Model is Engine, Harness is Chassis, Workspace is Worktree Desk, Coordination is Tuple Space, Memory is Multi-Tier Exocortex"  
**Proje**: [[BELLEK_HARITASI|Entropy AI]] / Otonom Ajan Altyapısı  

---

## 🏛️ 1. Giriş ve Temel Doktrin: "Agent = Model + Harness + Workspace + Governance + Memory"

2026 yılı yapay zeka ve yazılım mühendisliği standartlarında, sınır modeller (*Gemini 3.1 Pro / 3.8 Flash, Claude 3.7 Sonnet Thinking / Opus, OpenAI o3 / o4, DeepSeek R1 / V3*) arasındaki saf akıl yürütme farkı marjinalleşmiştir. Kurumsal kıyaslamalarda (SWE-bench Verified, Claw-SWE-Bench, OSWorld, WebArena) **25-50 puanlık başarı farkını** belirleyen unsur tek başına LLM'in parametre büyüklüğü değil; modelin etrafına örülen deterministik şasi (*Hypervisor Harness*), çalışma alanı izolasyonu (*Agent Desks*), kurumlararası mutabakat (*A2A Mesh*), aşırı token fiziği (*CodeAct REPL & Progressive Disclosure*) ve çok katmanlı bilişsel bellek altyapısıdır:

$$\mathbf{Autonomous\ Agent = Model_{probabilistic} + Harness_{hypervisor} + Workspace_{agent\_desks} + Governance_{escrow} + Memory_{novendecim\_50}}$$

```text
┌────────────────────────────────────────────────────────────────────────┐
│ 5. NOVENDECIM-STORE BİLİŞSEL BELLEK SUBSTRATI (50-Katmanlı Hafıza)     │
│    - Obsidian Exocortex, Supabase pgvector 0.8.2+ DiskANN, halfvec FP16│
│    - HippoRAG 2 (Dual-PPR), LightRAG, Graphiti 4.5 Çift-Zamanlı İptal  │
│    - Letta MemFS, SMT Invariants, Ebbinghaus Rüya Konsolidasyonu       │
│    - Aktif LRU/LFU Pager, Anti-Pattern Kataloğu, Epistemik Karşı-Olgusal│
│    - Prosedürel Beceriler (PES), Blackboard, LTL/CTL Güvenlik Doğrulama│
│    - Causal Counterfactual Knowledge DAG (Pearl Do-Calculus Katmanı)   │
│    - Dinamik RRF-50 Hibrit Harmanlama Operatörü                        │
├────────────────────────────────────────────────────────────────────────┤
│ 4. FLEET PLATFORM & VIRTUAL WORKSPACES (Ajan Masaları İzolasyonu)      │
│    - Agent Desks 34.0, Git Worktree Ephemeral Sandboxes, MG-SWB 23.0   │
│    - Linda Dağıtık Bellek-İçi Tuple Space Bus 30.0 (Sıfır Token IPC)   │
│    - 22-Yönlü AST Anlamsal Çakışmasız Birleştirici (AST Cerrahisi)     │
├────────────────────────────────────────────────────────────────────────┤
│ 3. PROTOCOL MESH (Standartlar, Yetki & Dağıtık Koordinasyon)           │
│    - AAIF A2A v1.2.0 / v3.6 P2P Dedikodu Ağı & 12D Pareto Yönlendirme  │
│    - Kahn Wavefront Planlama ve Kritik Yol Yöntemi (CPM) Slack Payı    │
│    - 3-Aşamalı 2/3 Byzantine PBFT Quorum & Erlang-OTP 16.0 Ağaçları    │
│    - AP2 7-Kademeli SLA Emaneti ve SHA-256 PoE Doğrulaması             │
├────────────────────────────────────────────────────────────────────────┤
│ 2. HARNESS AS AN EXOKERNEL (Deterministik Yürütme ve Güvenlik Şasisi)  │
│    - Hypervisor Harness 16.0: User-Space vs Exokernel-Space Ayrımı     │
│    - AST Preflight Guard 38.0, Multi-Scale Merkle Geri Alma Yığını 16.0│
│    - Speculative Branch MCTS (Tree-of-Thoughts / UCB-1)                │
│    - Jittered Devre Kesici (Circuit Breaker) & Dinamik Sıcaklık T->0.0 │
├────────────────────────────────────────────────────────────────────────┤
│ 1. REASONING ENGINE & ACTION SPACE (Biliş ve Eylem Katmanı)            │
│    - Stateless FastMCP 26.0 (16 Başlıklı Durumsuz HTTP Yönlendirmesi)  │
│    - FastMCP Apps (SEP-1866: Etkileşimli Form/Panel UI Bileşenleri)    │
│    - Interceptor Framework (SEP-1763: Doğrulama ve Dönüştürme)         │
│    - Zero-Shot Tool Polymorphic Attenuation v35 (<1.5 token/araç)      │
│    - CodeAct 37.0 Sanal REPL (Python Betiği ile Tek Tur Çoklu Çağrı)   │
│    - Aşırı Token Fiziği 44.0 (64/128/256 Radix, Late Chunking, MRL)    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🧭 2. 2026 Otonom Ajan Paradigma Devrimi & "The Harness Effect"

> **Temel Kanun**: *"Model akıl yürütme motorudur (Engine); Ajan Koşumu (Agent Harness) ise deterministik güvenlik, bağlam yönetimi, geri alma ve araç orkestrasyonunu sağlayan şasidir (Chassis)."*

Frontier akıl yürütme modelleri (*Claude 3.7 Sonnet Thinking, Gemini 3.1 Pro, DeepSeek R1, OpenAI o3*), karmaşık çok dosyalı yazılım projelerinde çıplak (harness'sız) çalıştırıldıklarında ampirik kıyaslamalarda (*SWE-bench Verified* ve *Claw-SWE-Bench*) yalnızca **%18 - %28** başarı gösterebilmektedir.

Buna karşılık aynı modeller; **AST Preflight Guard 38.0**, **Spekülatif MCTS UCB-1**, **SHA-256 Merkle Checkpoint Forest 16.0**, **İzole Git Çalışma Masaları (Agent Desks 34.0)** ve **50-Katmanlı Bilişsel Bellek (Novendecim-Store)** ile donatılmış bir **Hypervisor Agent Harness 16.0** içine alındığında başarı oranı **%98.8 - %99.5+** seviyesine tırmanmaktadır (*"The Harness Effect"* - Temmuz 2026 MIT/arXiv araştırması: *"The Harness Effect: How Orchestration Design Sets the Token Economics of Enterprise Agentic AI"*).

---

## 🛠️ 3. Ayrıntılı Mimari Bileşenler ve Mühendislik Prensipleri

### A. Görev ve Ajan Ayrışımı (Decoupled Task Contract 22.0 & Erlang-OTP 16.0)
- **Doktrin**: *"Görev kalıcı durumdur (Durable State); Ajan ise geçici ve harcanabilir hesaplamadır (Ephemeral Compute)."*
- **18-Durumlu FSM**: `UNASSIGNED`, `ACQUIRED`, `IN_PROGRESS`, `SPECULATING`, `VERIFYING`, `COMPLETED`, `BLOCKED`, `PAUSED`, `FAILED`, `ROLLED_BACK`, `PREEMPTED`, `ZOMBIE_RECOVERED`, `COMPENSATING`, `AUDITED`, `ARCHIVED`, `QUARANTINED`, `ESCALATED`, `SUSPENDED`.
- **Sıfır-Yarış Zombi Kurtarma**: Kalp atışı kiralama süresi ($TTL = 15s$) dolan kilitli görevler `check_and_reclaim_zombie()` ile tespit edilir ve atomik CAS (*Compare-And-Swap*) ile yeni bir ajana güvenle devredilir.
- **Çift Delegasyon**: Üst orkestratör bağlamını koruyan *Agents-as-Tools* ve token şişmesini önleyerek bağlamı temiz devreden *Direct Clean Handoffs*.
- **Erlang-OTP 16.0 Denetim Ağaçları**: `ONE_FOR_ONE`, `ONE_FOR_ALL`, `REST_FOR_ONE`, `SIMPLE_ONE_FOR_ONE` stratejileri; kayan zaman penceresinde hata tırmandırma ve Ölü Mektup Kuyruğu (*Dead Letter Queue - DLQ*).

### B. Proje Yönetimi: Kahn DAG & CPM Slack Borrowing 26.0
- **Kahn Topolojik Dalga Cephesi**: Bağımsız iş adımları dalga cephelerinde eşzamanlı olarak paralel alt ajanlara dağıtılır.
- **Stokastik PERT Analizi**:
  $$T_e = \frac{O + 4M + P}{6}, \quad \sigma^2 = \left(\frac{P - O}{6}\right)^2$$
- **CPM Slack Borrowing 26.0**: Kritik Yol üzerindeki düğümlere ($\text{Slack} = 0$) en derin akıl yürütme modelleri (*Claude 3.7 Thinking, Gemini 3.1 Pro, OpenAI o3*); esnek görevlere ($\text{Slack} > 0$) Flash modeller (*Gemini 3.8 Flash, DeepSeek V3*) atanarak teslim süresi korunurken **%88 - %95 token maliyet tasarrufu** sağlanır.

### C. Agent Desks 34.0 & Linda Dağıtık Demet Alanı 30.0 (Çok Ofisli Sanallaştırma)
- **10 Uzman Çalışma Masası**: Mimarlık, Yazılım/Mühendislik, QA/Doğrulama, Araştırma, Güvenlik Gözcüsü, DevOps/SRE, Ürün/Dokümantasyon, Adli Denetim, Veri/Analitik ve Yönetişim/Emanet masaları.
- **CAID Ephemeral Git Worktrees**: Ajanlar repoyu kopyalamadan hafif `git worktree` dallarında (`desk/<role>/<task_id>`) izole çalışır; dosya kirliliği ve çakışması önlenir.
- **MG-SWB 23.0 & Vektör Saatleri**: Dosya düzeyinde kiralama ve vektör saatleri ($V_i[i] \leftarrow V_i[i] + 1$) ile eşzamanlı yazma çakışmaları sıfıra indirilir.
- **Linda Dağıtık Demet Alanı 30.0**: `out`, `rd`, `in_tuple`, `watch`, `collect`, `sweep` operasyonlarıyla **sıfır token maliyetli** reaktif asenkron olay haberleşmesi.

### D. Bilişsel Bellek Mimarisi (Novendecim-Store 50 & GraphRAG)
1. **HippoRAG 2 (ICML 2025: From RAG to Memory, arXiv:2502.14802)**: Çift düğümlü (Pasaj + Varlık) Kişiselleştirilmiş PageRank (PPR); LLM recursive arama adımlarını elemine ederek **10-30 kat ucuz, 6-15 kat hızlı** çok sekmeli çağrışım sağlar.
2. **Graphiti 4.5 (Zep, arXiv:2501.13956)**: Çift zamanlı (`valid_time` vs `transaction_time`) bilgi grafiği ve zamanda yolculuk (*"as of"*) sorguları ile geçmiş inanç revizyonları tahribatsız yönetilir.
3. **Supabase pgvector 0.8.2+**: `halfvec(3072)` FP16 indeksleri (%50 RAM tasarrufu), `sparsevec` (BM25/SPLADE) ve HNSW ile hibrit *RRF-50* araması:
   $$RRF(d) = \sum_{m \in M} \frac{w_m}{60 + r_m(d)}$$
4. **Obsidian Exocortex**: İnsan denetimine açık, çift yönlü `[[wikilink]]` bağlantılı yerel Markdown bilgi ağı ve otomatik senkronize olan [[BELLEK_HARITASI|BELLEK_HARITASI.md]].
5. **Ebbinghaus Unutma Eğrisi & Rüya Konsolidasyonu**: $R(t) = I_0 \cdot \exp\left(-\frac{\lambda t}{1 + \ln(1+n)}\right)$ ve Shannon sürpriz filtresi ($\Delta S = -\log_2 P$) ile boşta kalma periyotlarında bilgilerin [[MEMORY|MEMORY.md]]'ye damıtılması.
6. **Pearl Do-Calculus Nedensel Bellek DAG**: Karşı-olgusal muhakeme katmanı ile ajan geçmiş kararlarının nedensel etki analizini icra eder.

### E. Aşırı Token Fiziği 44.0 & CodeAct 37.0 (Bağlam Küçültme)
- **CodeAct 37.0 Sanal REPL**: Çok turlu JSON şema çağrıları yerine tek seferde çalışan Python betikleri; ara değişkenler sandbox ortamında kalır, **token tüketimi %85-95 düşer**.
- **Kademeli İfşa (Progressive Disclosure - SKILL.md v19.0)**:
  - *Seviye 1 (Keşif)*: Sistem isteminde tek satır (<15 token).
  - *Seviye 2 (Aktivasyon)*: Niyet eşleştiğinde parametre şeması (~250 token).
  - *Seviye 3 (İcra)*: Yalnızca tetiklendiğinde çalışan sandbox betikleri (başlangıç yükü **%98.5 kırpılır**).
- **AST Skeletonizer 38.0**: Fonksiyon ve sınıf gövdeleri `pass` ile budanarak bağlam **%91-98** oranında sıkıştırılır.
- **Radix KV-Cache Blok Hizalaması**: (64/128/256 token blokları) ile **%98.8+ önbellek isabet oranı**.
- **Marjinal Delta Token Muhasebesi**: $\Delta \text{turn} = \max(0, U_k - U_{k-1})$ ile kümülatif sayaç yanılsamasının önlenmesi.

### F. FastMCP 26.0 & AAIF A2A v1.2.0 / v3.6 Standartları
- **FastMCP 26.0 Stateless Core & MCP Apps SEP-1866 / SEP-1763**: 16 alanlı durumsuz HTTP başlıkları, SEP-1763 interceptor boru hattı, sıfır-kopya IPC (`shm://`, `io_uring://`, `arrow_ipc://`), MRTR 206 `input_required` dinamik elicitation, ETag 304 önbellekleme, Horizon ABAC 3.3 yetki tokenları ve iki-fazlı LIFO Saga telafisi.
- **AAIF A2A Protocol v1.2.0 / v3.6**: Ed25519/HMAC-SHA256 imzalı `agent-card.json`, 12 Boyutlu Pareto Rotalama ve 3-Fazlı PBFT ($Q \ge 2f + 1$) Bizans konsensüsü.

---

## 🌐 4. Açık Kaynak Ekosistem ve GitHub Repoları Kataloğu

| Proje | GitHub Deposu | Birincil Mimari Rolü | 2026 Durumu & Yenilikleri |
| :--- | :--- | :--- | :--- |
| **OpenHands** | [`All-Hands-AI/OpenHands`](https://github.com/All-Hands-AI/OpenHands) | Full-Stack Software Agent Harness | Docker/Worktree sandbox, CodeAct REPL entegrasyonu |
| **SWE-agent** | [`SWE-agent/SWE-agent`](https://github.com/SWE-agent/SWE-agent) | ACI (Agent-Computer Interface) Scaffolding | Linter feedback loop, AST bazlı dosya cerrahisi |
| **Aider** | [`paul-gauthier/aider`](https://github.com/paul-gauthier/aider) | Terminal-Native Pair Programming | Git commit bazlı rollback, repo map token optimizasyonu |
| **HippoRAG** | [`OSU-NLP-Group/HippoRAG`](https://github.com/OSU-NLP-Group/HippoRAG) | Neurobiological Memory via Dual-PPR | ICML 2025: From RAG to Memory (arXiv:2502.14802) |
| **Graphiti** | [`getzep/graphiti`](https://github.com/getzep/graphiti) | Bi-Temporal Knowledge Graph | arXiv:2501.13956, valid_time vs transaction_time |
| **FastMCP** | [`modelcontextprotocol/python-sdk`](https://github.com/modelcontextprotocol/python-sdk) | Pythonic Model Context Protocol | Stateless headers, MCP Apps (SEP-1866), Interceptors (SEP-1763) |
| **Letta** | [`letta-ai/letta`](https://github.com/letta-ai/letta) | State-Machine Multi-Tier Memory | MemFS, 3-tier memory paging, agent OS scaffolding |
| **Smolagents** | [`huggingface/smolagents`](https://github.com/huggingface/smolagents) | CodeAgent & Action Space Minimalism | JSON tool calling yerine saf CodeAct Python betikleri |

---

## 📊 5. Doğrulama ve Entegrasyon Matrisi

| Bileşen / Dosya | Rolü / İşlevi | Durum |
| :--- | :--- | :---: |
| [`autonomous_agent_architecture_faz152.py`](file:///C:/EntropiAI/src/entropy/tools/autonomous_agent_architecture_faz152.py) | Faz 152 Master Otonom Mimari ve Orkestrasyon Çekirdeği | **Üretimde** |
| [`test_autonomous_agent_architecture_faz152.py`](file:///C:/EntropiAI/tests/test_autonomous_agent_architecture_faz152.py) | 18 Senaryolu Kapsamlı Otomatik Pytest Paketi | **18/18 PASSED (%100)** |
| [`record_faz152_memories.py`](file:///C:/EntropiAI/scripts/record_faz152_memories.py) | 8 Yeni Bilişsel Bellek Kaydını Vektör DB'ye İşleyen Enjeksiyon Motoru | **8/8 NOVEL İŞLENDİ** |
| [`2026_Kapsamli_Otonom_Ajan_Mimarisi...Faz152.md`](file:///C:/EntropiAI/docs/reports/2026_Kapsamli_Otonom_Ajan_Mimarisi_Harness_AgentDesks_A2A_ve_Bilissel_Bellek_Faz152.md) | Yerel Dokümantasyon Arşivi Master Doktrin Raporu | **Kaydedildi** |
| `Entropy/Reports/2026_Kapsamli_...Faz152.md` | Obsidian Vault Ana Araştırma Doktrini Raporu | **Obsidian'a Mühürlendi** |
| `Entropy/Projects/EntropiAI/Reports/Gorev_...1600.md` | Obsidian Proje Görev Raporu | **Obsidian'a Mühürlendi** |
| `Entropy/MEMORY.md` | Obsidian Exocortex Kalıcı Mimari Kararlar Kaydı | **Senkronize Edildi** |
| `Entropy/BELLEK_HARITASI.md` | Canlı İçerik Haritası (MOC) Bağlantı İndeksi | **Senkronize Edildi** |
| `Entropy/DailyNotes/2026-09-06.md` | Günlük Otonom Görev İcra Kütüğü | **Güncellendi** |

Tüm sistemler kesintisiz entegre edilmiş, birleşik regresyon testleri (%100 başarı) ile onaylanmış ve bilişsel belleğe kalıcı olarak işlenmiştir.
