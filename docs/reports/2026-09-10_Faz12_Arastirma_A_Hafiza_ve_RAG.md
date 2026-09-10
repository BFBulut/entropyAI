# Faz 12 — Araştırma A: "Entropy'nin Beyni" (ikinci tur)
## Hafıza sistemleri ve RAG mimarilerinde güncel durum · Faz 11 sonrası dürüst denetim

**Tarih:** 2026-09-10 · **Depo:** `C:\EntropiAI` (v0.9.4, dal `ai/v0.1.7`, HEAD `1815f32`) · **Kip:** salt okunur araştırma
**Yöntem:** literatür yeniden taraması (aynı kaynak listesi, "Faz 11'den sonra ne yeni" işaretli) + kod denetimi (`dosya:satır`) + gerçek veritabanının **kopyası** üzerinde ölçüm
**Model çağrısı yapılmadı.** Kod, kasa, ayar ve üretim veritabanı değiştirilmedi.
**Yalıtım kanıtı:** `~/.entropy/cognitive_memory.db` 7.593.984 B / mtime 1789015233 · `tasks_ledger.db` 73.728 B / 1789012264 · `skills_state.json` 112 B / 1788993407 — ölçüm öncesi ve sonrası aynı.
**Önceki tur:** [`2026-09-10_Faz11_Arastirma_A_Hafiza_ve_RAG.md`](2026-09-10_Faz11_Arastirma_A_Hafiza_ve_RAG.md) · **İlerleme:** [`2026-09-10_Faz11_Ilerleme_Raporu_v0.9.4.md`](2026-09-10_Faz11_Ilerleme_Raporu_v0.9.4.md)

---

## 0. Yönetici özeti (önce sonuç)

1. **Faz 11'in hafıza cerrahisi tuttu ve ölçümle doğrulandı.** Gerçek DB'de bugün: 729 düğüm, K1 yineleme **%5,49**, K2 **Hit@1 9/10 · Hit@5 10/10**, K3 gürültü **%0,0**, K7 kanonik dışı kategori **0**, K10 fikstür sızıntısı **0**, K11 kapı gecikmesi medyan **82,4 ms**. Yedi ölçütten altısı PASS. *(kanıt: `scripts/brain_metrics.py --json`, §3.1)*
2. **Faz 11'de ölçülemeyen K4/K5 bu turda ölçüldü ve ikisi de hedefi geçti.** Genel sohbette bağlam bütçesi kullanımı **%77,1** (hedef ≥ %60; Faz 11-D'de %56,8) ve damıtılmış pay **%41,8** (hedef ≥ %30). Beyin paketi (`general_brain`) 5 sorgunun 5'inde de bağlama giriyor. *(§3.2)*
3. **Ama derleme katmanı üretimde fiilen bağlı değil — üç somut kablolama hatası buldum.** `/memory merge` **hiç çalışmıyor** (`ImportError`, kullanıcıya "modül kurulu değil" yalanı dönüyor), `/wiki compile` **köprüyü hiç almıyor ve `--turns` sessizce yutuluyor**, `/memory dream` elinde köprü varken `send_prompt=None` geçiyor. Yani Faz 11'de yazılan üç konsolidasyon modülünün üçü de üretimde **kuru koşum** kipinde. *(§3.3 — bu raporun en yüksek değerli bulgusu)*
4. **Sonuç olarak K6 hâlâ FAIL:** yetenekli bağlamda wiki payı `media-agency-soldier` **%3,7**, `autonomous-agent` **%2,3**, `financial-auditor` **%0,0** (50 raporu var, 0 wiki sayfası) — hedef ≥ %15. Sayfalar köprüsüz üretildiği için "damıtılmış bilgi" değil iskelet. *(§3.4)*
5. **mem0 kararı değişmedi ama Faz 11 notundaki bir teknik iddia yanlıştı ve düzeltiyorum:** graph memory OSS'ten *silinip yerine bir şey konmamış* değil — **harici graf sürücüleri** (Neo4j/Memgraph/Kuzu/AGE, ~4.000 satır) kaldırıldı, yerine **vektör deposu içinde varlık bağlama ile yerleşik graf belleği** geldi (v2.0.0/v3.0.0, 14 Nis 2026). Karar aynı kalıyor (her yazımda LLM + ADD-only), gerekçe düzeltildi. *(§2)*

---

## 1. Literatür haritası — Faz 11'den sonra ne değişti

> **[YENİ]** = Faz 11 notunda yoktu, bu turda bulundu. Ötekiler doğrulandı/durumu güncellendi.

### 1.1 Yazma tarafı denetimi

| Kaynak | Ne diyor | Bize ne öğretiyor |
|---|---|---|
| **SAGE — A Novelty Gate for Efficient Memory Evolution in Agentic LLMs** · Wang, Brahma, Henao · arXiv:2605.30711 (29 May 2026) | vMF yoğunluk kestirimi + bellek geometrisini izleyen uyarlanabilir eşik; ADD / NOOP / belirsiz→LLM. LoCoMo'da yedi açık ağırlıklı omurganın **hepsinde** mem0'ı geçiyor; GPT-4o-mini'de ekleme aşaması API maliyeti **3,4×**, gecikme **2,5×** düşüyor. | **Uygulandı.** `memory/gate.py` üç bant (`≥0,95` NOOP · `<0,80` ADD · arası gri). Ölçülen etki: K1 %52,5 → %5,49, K11 medyan 82 ms. Kalan fark: bizim eşiğimiz **sabit**, SAGE'inki korpus geometrisine uyarlanıyor → Brain v3 kalemi (§4.2). |
| **[YENİ] ConsistencyGate — Preventing Memory Contamination in LLM Agents via Self-Consistency Admission Control** · Yan Zhang, Shibo Li · arXiv:2607.22962 (25 Tem 2026) | Halüsine olguların belleğe yazılıp sonraki adımlarda **yanlış öncül** olarak kalmasını "memory contamination" diye adlandırıyor. Aday olguyu LLM'e **K kez** sorup ortalama destek skoru eşiği aşarsa kabul ediyor; ince ayar gerekmiyor, model-bağımsız. Gecikmeye duyarlı dağıtımlar için **log-olasılık varyantı** var. Yeni kıyaslar: LoCoMo-Contam, MSC-Contam, MemContam. | Bizim K12 açığının (kaynaksız/uydurma L2) *ikinci savunma hattı*. Bizde kaynak zorunluluğu var ama **iddianın kendisi doğrulanmıyor**. K-kez sorma bizim kotamıza uymaz; **log-olasılık varyantı da uymaz (CLI'da logprob yok)**. Uygulanabilir tek biçim: gri banda düşen ve *dış kaynağı olmayan* adaylar için gece turunda **tek** tutarlılık sorusu. |
| **[YENİ] Governing Evolving Memory in LLM Agents: Risks, Mechanisms, and the SSGM Framework** · arXiv:2603.11768 | Evrilen belleği bir **yönetişim** problemi kurar (kararlılık + güvenlik); yazma/güncelleme/silme yetkilerini politikaya bağlar. | Bizdeki `promoted_rules` (kullanıcı onayı olmadan kural kalıcılaşmaz) tam bu desen. Eksik olan: **arşivleme ve supersede kararlarının denetim izi**. |
| **Dual-Layer Agentic Memory** · arXiv:2608.22215 (23 Ağu 2026) | non-write / write-new / write-update üçlüsüne maliyet-duyarlı model kaskadı; fazlalığın **%68'ini** budarken girdilerin **%50'sinden azını** yönlendiriyor, başarımın **%98+**'ini koruyor. | Kaskad doğrulandı; bizim "ucuz yerel katman + gri bantta CLI" hattımızın referansı. |
| **Hindsight — Consolidation Problem** (21 May 2026) · **Manufactured Confidence** arXiv:2606.29279 · **Authority Collapse** arXiv:2608.01679 · **Rate–Distortion Memory Compaction** arXiv:2607.08032 | Konsolidasyon eşiği yazma eşiğinden yüksek; konsolidasyon kaynağı silip duyumu kesin olguya çeviriyor; unutma ölçülebilir kayıp bütçesi olmalı. | Eşik ayrımı **uygulandı** (yazma 0,80–0,95 / rüya kopya birleştirme 0,95). Kaynak alanı **yapısal** oldu (`provenance` sütunu). **Rate–distortion hâlâ yok:** `dream.forget_stale` önem+erişim+yaş kuralı, kayıp ölçmüyor. |

### 1.2 Bellek mimarisi çerçeveleri

| Kaynak | Durum |
|---|---|
| **CoALA** arXiv:2309.02427 | **Uygulandı.** `memory/categories.py:CANONICAL_CATEGORIES = ("working","episodic","semantic","procedural")`; kimlik ayrı bayrak (`is_identity`). Gerçek dağılım: `semantic 651 / procedural 59 / episodic 19`, kanonik dışı **0**. |
| **HippoRAG 2** arXiv:2502.14802 | **Uygulandı** (`graph_store._personalized_pagerank`, `hybrid_recall(expand_graph=True)`). [YENİ] **GroupMemBench** (arXiv:2605.14498, May 2026): HippoRAG dört alanın dördünde de **maliyet–doğruluk Pareto sınırında**; çoğu temel yöntem onun tarafından domine ediliyor. Yani PPR seçimimiz bağımsız kıyasla da destekleniyor. |
| **Zep / Graphiti** arXiv:2501.13956 | **Uygulandı** (çift-zamanlı `edges`, `reconcile.reconcile_facts` → `superseded`). Değişiklik yok. |
| **A-MEM** arXiv:2502.12110 · **Letta / MemGPT** | Değişiklik yok. Letta'nın "sleep-time compute" karşılığı bizde `dream.ensure_daily_dreaming_task` (saat 04:00, `bootstrap.ensure_memory_tasks()` ile bağlandı) — ama §3.3'teki hata yüzünden **modelsiz** koşuyor. |
| **[YENİ] MemGraphRAG** arXiv:2606.00610 (May 2026) | Bellek tabanlı çok-ajanlı GraphRAG; Karmaşık Akıl Yürütmede Recall **90,42** / Relevance **82,64** ile HippoRAG2 ve LightRAG'i geçiyor. **Bizim için uygun değil**: çok-ajanlı graf gezme = tur başına birden çok LLM çağrısı; kota mimarimizle bağdaşmaz. Kayda geçir, alma. |
| **[YENİ] AMA-Bench** arXiv:2602.22769 · **Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks** arXiv:2602.16313 | 2026'da hafıza kıyaslaması ayrı bir literatür oldu (Mem2ActBench, MemTrack, EMemBench, AgentLongBench). **Bize etkisi:** K1–K12 paketimizin dış geçerliliği yok; ileride bir dış kıyasa (LoCoMo Türkçe alt kümesi gibi) bağlanabilir — ama bu kota ister, Faz 12 kapsamı değil. |

### 1.3 Beceri / yordamsal bellek — bu turun en verimli alanı

Faz 11'de SoK: Agentic Skills (arXiv:2602.20867) tekti; bu turda **beceri sentezi ve doğrulaması** için olgun bir aile çıktı. Kullanıcının "kendine skill ekler" hedefinin doğrudan literatürü:

| Kaynak | Ne diyor | Bize ne öğretiyor |
|---|---|---|
| **[YENİ] SKILLFOUNDRY — Building Self-Evolving Agent Skill Libraries from Heterogeneous Scientific Resources** · arXiv:2604.03964 | Kaynakları **doğrulanmış** becerilere çevirir; her beceri paketi şunları kodlar: **görev kapsamı, girdi/çıktı, yürütme adımları, ortam varsayımları, provenance ve testler**. | **Bizim `SKILL.md` + `PLAYBOOK.md` şemamızın eksik dört alanı bu:** ortam varsayımı, provenance, test, sonlandırma ölçütü. Beceri şemasını genişletmek ucuz ve ölçülebilir. |
| **[YENİ] EvoSkills / CoEvoSkills — Self-Evolving Agent Skills via Co-Evolutionary Verification** · arXiv:2604.01687 | Beceri ile **doğrulayıcısı** birlikte evrilir. | "Kanıtla kapat" kuralımızın beceri karşılığı: bir playbook güncellemesi ancak kendi doğrulayıcısını geçerse kalıcılaşır. |
| **[YENİ] SkillCoach — Self-Evolving Rubrics for Evaluating and Enhancing Agentic Skill-Use** · arXiv:2607.01874 | Beceri kullanımını **kendi kendine evrilen rubrikle** puanlar. | Yer-gerçeği olmadan playbook kalitesi ölçmenin yolu (SkillAudit arXiv:2606.14239 ile aynı aile). |
| **[YENİ] SkillOS** arXiv:2605.06614 · **SkillSmith** arXiv:2606.01314 · **SkillOpt** arXiv:2605.23904 | Beceri **küratörlüğü** öğrenilir; beceri ve araç birlikte evrilir; strateji katmanı becerileri seçer. | Bizde `skills/manager.create_skill` beceri yazıyor ama **hangi becerinin tutulacağına karar veren bir küratör yok**; 7 yetenekten 2'sinin playbook'u bile yok (`research`, `skill-creator`). |

### 1.4 RAG ve bilgi derleme

| Kaynak | Durum / yeni |
|---|---|
| **Karpathy LLM wiki** (gist, 4 Nis 2026) | Doğrulandı ve **tarih netleşti: 4 Nisan 2026**; iki hafta içinde 5.000+ yıldız, 4.000+ fork. Üç işlem: **ingest / query / lint**. [YENİ] Türev uygulamalarda dikkat çeken sapma: bazıları **çelişkiyi lint turuna bırakmayıp alım anında** yakalıyor. **Bize:** `lint.py` bizde alım sonrası; `MemoryGate` zaten alım anında çalışıyor — çelişki denetimini kapının içine almak (supersede yolu) doğal uzantı. |
| **[YENİ] Knowledge Compounding: An Empirical Economic Analysis of Self-Evolving Knowledge Wikis under the Agentic ROI Framework** · arXiv:2604.11243 | Derlenmiş wiki rejiminde kümülatif token **47K**, eşleşmiş RAG temelinde **305K** — **%84,6 tasarruf**. Projeksiyon: orta konu yoğunluğunda %53,7, yüksekte %81,3 tasarruf. Token'ı "tüketim malı"ndan **"sermaye malı"na** yeniden sınıflandırmayı öneriyor. | **Bu, wiki derlemesine harcanacak ~50 turun ekonomik gerekçesidir.** Bizim durumumuz "yüksek konu yoğunluğu" (7 yetenek, dar alan) → beklenen tasarruf üst banda yakın. K6'yı Faz 12'nin ana kalemi yapmanın sayısal dayanağı. |
| **GraphRAG / LightRAG / LEGO-GraphRAG / GraphRAG-Bench** | Değişiklik yok; tam GraphRAG kota açısından hâlâ yanlış tercih. |
| **CRAG / Self-RAG / Agentic RAG** (arXiv:2601.07711, 2506.10408, 2507.09477) | **Uygulandı**: `context_builder.CRAG_MIN_SCORE = 0.45`, `AssembledContext.brain_has_answer`. Ölçüm: 5 genel sorgunun **1'inde** True (§3.2) — eşik gerçek korpusta agresif kalıyor, kalibrasyon gerek. |
| **LlamaIndex memory blocks** | Değişiklik yok (`StaticMemoryBlock` ↔ promoted rules, `FactExtractionMemoryBlock` ↔ `reconcile.extract_facts`, `VectorMemoryBlock` ↔ `hybrid_recall`). Hizamız doğru. |
| **Microsoft Agent Framework (AutoGen + Semantic Kernel)** | Değişiklik yok. Dört aşamalı döngünün **Post-Processing** adımı bizde hâlâ yalnızca rüya döngüsünde ve o da modelsiz koşuyor (§3.3). |

### 1.5 Kaynak durumu notları

- **paperswithcode.com**: Faz 11'de tespit edilen yönlendirme **devam ediyor** → `huggingface.co/papers`. Araştırma akışından çıkarılmalı (kalıcı karar).
- **@_akhaliq (X)**: X erişimi yok; HF Daily Papers üzerinden takip edildi. 10 Eyl 2026 HF ana sayfasında **hafıza/RAG makalesi yok** (öne çıkanlar: Show-Harness 2609.10522, Programmable World Model 2609.10540, Discovery Certification Protocol 2609.09219, Co-Evolving Harnesses and Models 2609.09134). Yani **son ~10 günde bu alanda öne çıkan yeni bir şey yok**; Faz 11 notundaki tablo güncel.
- **mem0 kıyas rakamları** hâlâ satıcı blogundan; bağımsız doğrulama yok. GroupMemBench/AMA-Bench gibi bağımsız kıyaslar farklı sıralama üretiyor.

---

## 2. mem0 ve alternatiflerin yeniden değerlendirmesi

### 2.1 Faz 11 notundaki bir iddiayı düzeltiyorum

Faz 11 notu §2.2(2) şunu yazmıştı: *"Graph memory açık kaynaktan kaldırıldı… OSS eşdeğeriyle değiştirilmiyor."* **Bu eksik/yanıltıcıydı.** Doğrusu (mem0 changelog, 14 Nis 2026):

- **Kaldırılan:** *harici* graf deposu sürücüleri (Neo4j, Memgraph, Kuzu, Apache AGE) — Python SDK v2.0.0'da ~4.000 satır.
- **Gelen:** **yerleşik graf belleği** — varlıklar çıkarılıp gömülüyor ve anılar arasında bağlanıyor; **harici graf deposu gerekmiyor**.

Bu, mem0'ı bizim için *daha* çekici yapar mı? **Hayır** — ve nedeni şu: yerleşik graf, vektör deposu içinde **varlık bağlama**dır; **çift-zamanlı geçerlilik aralığı ve Personalized PageRank değildir**. Bizim `graph_store.py`'deki `t_valid_from/t_valid_to/ingested_at` + PPR + topluluk katmanının karşılığı hâlâ yok. Üstünlüğümüz duruyor.

### 2.2 2026 boyunca mem0'da olan diğer değişiklikler (changelog, doğrulandı)

| Tarih | Değişiklik | Bize etkisi |
|---|---|---|
| 14 Nis 2026 | v2.0.0/v3.0.0 algoritma yeniden yazımı: **ADD-only**, hibrit geri getirme (anlamsal + BM25 + varlık takviyesi). LoCoMo 71,4 → **91,6**; LongMemEval 67,8 → **93,4** | Hibrit skorlama zaten bizde (0,40 vektör + 0,20 BM25 + 0,25 Ebbinghaus + 0,15 tazelik). ADD-only bizim **asıl derdimizin tam tersi** |
| 8 May 2026 | **Memory decay**: son erişilene **0,3×–1,5×** yumuşak sapma; hiçbir aday elenmiyor | Bizde Ebbinghaus ağırlığı (0,25) aynı işi yapıyor — **doğrulama**, alacak bir şey yok |
| 13 May 2026 | **Zamansal akıl yürütme**: "geçen hafta", "yaklaşan" sorguları zaman damgasına çözülüyor | **Bizde yok.** Ucuz ve değerli: sorgudaki Türkçe zaman ifadelerini `valid_from` süzgecine çevirmek. Brain v3 kalemi |
| Ağu 2026 | Ekosistem: kalıcı bellekli harness eklentileri, editör entegrasyonları | İlgisiz |

### 2.3 KARAR (değişmedi, gerekçe güncellendi)

> **mem0 çalışma zamanı bağımlılığı olarak reddedilmeye devam ediyor.** Apache-2.0 fikri kendi katmanımızda uygulamaya izin verir; Faz 11'de yapılan buydu ve ölçümle karşılığını verdi.

Gerekçeler:
1. **Her yazımda LLM zorunlu** (`gpt-5-mini` varsayılan). Bizde yazım/gün üç haneli → abonelik-CLI mimarisiyle bağdaşmaz. SAGE deseniyle bunu **modelsiz** yapıyoruz ve K1'i %5,49'a indirdik.
2. **ADD-only** birikimi kabul ediyor; bizim ana problemimiz olan fazlalık ve öz-amplifikasyonu çözmüyor.
3. **Yerleşik graf ≠ çift-zamanlı graf + PPR.** En güçlü tarafımızın karşılığı hâlâ yok.
4. Kıyas üstünlüğü satıcı blogundan; bağımsız kıyaslarda (GroupMemBench, AMA-Bench) sıralama değişiyor.

### 2.4 Alternatiflerin bu turdaki durumu

| Aday | Karar | Gerekçe |
|---|---|---|
| **Zep / Graphiti** | Fikir alındı, kütüphane alınmadı | Çift-zamanlı desen zaten uygulandı; Neo4j bağımlılığı PyInstaller paketimize giremez |
| **Letta** | Fikir alındı | sleep-time compute = rüya döngüsü; Context Repositories = dosya-tabanlı ofis belleğimiz |
| **LightRAG / GraphRAG** | Alınmadı | Tam GraphRAG kota açısından yanlış; bizim tohumlanmış-PPR yaklaşımımız daha ucuz |
| **[YENİ] MemGraphRAG** | Alınmadı, kayda geçti | En iyi doğruluk ama çok-ajanlı graf gezme = tur başına çoklu çağrı |
| **[YENİ] SKILLFOUNDRY beceri şeması** | **ALINDI (şema fikri)** | `SKILL.md`'ye 4 alan ekleme kalemi (§4.5) |
| **[YENİ] ConsistencyGate** | **Kısmen alındı** | K-kez ve logprob varyantları kotamıza uymaz; gece turunda tek tutarlılık sorusu biçimi alınabilir |

---

## 3. Faz 11 sonrası hafızanın dürüst denetimi

### 3.1 K1–K12 — gerçek DB (kopya), `python scripts/brain_metrics.py --json`

Ölçüm ortamı: `~/.entropy/cognitive_memory.db` kopyası (7.593.984 B, **729 düğüm**).

| # | Ölçüt | Hedef | Faz 11 sonu | **Faz 12 (bugün)** | Karar |
|---|---|---|---:|---:|---|
| K1 | yineleme (cos ≥ 0,92) | ≤ %10 | %4,76 | **%5,49** (689 küme / 729 düğüm) | **PASS** |
| K2 | Hit@1 / Hit@5 | ≥ 8/10 · ≥ 10/10 | 9/10 · 10/10 | **9/10 · 10/10** (medyan 63,6 ms) | **PASS** |
| K3 | top-5 gürültü | ≤ %2 | %0,0 | **%0,0** | **PASS** |
| K4 | genel sohbette bütçe kullanımı | ≥ %60 | %56,8 | **%77,1** | **PASS** ✅ *(ilk kez)* |
| K5 | genel sohbette damıtılmış pay | ≥ %30 | %38,2 | **%41,8** | **PASS** |
| K6 | wiki payı (yetenekli bağlam) | ≥ %15 | ölçülmedi | **%0,0 / %2,3 / %3,7** | **FAIL** |
| K7 | kategori disiplini | kanonik dışı 0 | 0 | **0** (`sem 651 / proc 59 / epi 19`) | **PASS** |
| K8 | araştırma turu yenilik oranı | ≥ %70 | tek ölçüm %83 (kuru) | **ölçülemedi** (kota) | doğrulanamadı |
| K9 | gri bant kuyruğu | — | 0 | **0 satır** | bilgi (§3.3) |
| K10 | fikstür sızıntısı | 0 | 0 | **0** | **PASS** |
| K11 | kapı gecikmesi | ≤ 400 ms | medyan 133,8 ms | **medyan 82,4 ms** (ilk 212 ms, maks 89,3) | **PASS** |
| K12 | kaynaksız L2 | 0 | 2 | **2** (`semantic-f323b831…`, `semantic-69123da0…`; ayrıca `legacy_untagged` 256) | **FAIL (tanımsal)** |

**K1'in %4,76 → %5,49 yükselmesi bozulma değil, büyümedir:** 714 → 729 düğüm, 40 küme fazlalık. Hedefin (≤ %10) yarısında; ama **trend izlenmeli** — yazma kapısı fazlalığı sıfırlamıyor, sınırlıyor.

**K12 iki ayrı şey ölçüyor ve bu bir ölçüm hatası:**
- **2 düğüm** gerçekten kaynaksız ve ikisi de **kimlik düğümü** (`is_identity`). Kimlik düğümünün dış kaynağı olamaz (Entropy'nin kendisi hakkında). → Ölçüt `is_identity=1` satırları muaf tutmalı; o zaman K12 = **0 → PASS**.
- **256 düğüm** `legacy:pre-v2` etiketli. Bunlar ayrı sayaçta ve doğru şekilde "kaynaksız" sayılmıyor.
→ **Karar önerisi:** `brain_metrics.py`'de K12 tanımına `AND is_identity = 0` eklenirse ölçüt dürüstçe PASS olur. Bugün FAIL yazması **ürün hatası değil, ölçüm tanımı hatasıdır.**

### 3.2 K4 / K5 — genel sohbet beyin paketi (5 sorgu, gerçek kod, DB kopyası)

`CognitiveContextBuilder.build(query, skill_name=None)`, bütçe 4.000 token.

| Sorgu | Token | Bütçe % | `general_brain` | recall | reports | global | Damıtılmış % | `brain_confidence` | `has_answer` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:--:|
| Entropy'nin hafıza mimarisi nasıl çalışıyor? | 3.310 | 82,8 | 1.482 | — | — | 279 | 44,8 | — | — |
| Ajan panosunda kart nasıl kapanır? | 2.562 | 64,0 | 623 | 777 | 883 | 279 | 24,3 | 0,405 | false |
| Bir hisse için temerrüt riskini nasıl ölçerim? | 3.369 | 84,2 | 1.483 | 739 | 868 | 279 | 44,0 | 0,391 | false |
| Yeni bir yetenek (skill) nasıl oluşturulur? | 2.936 | 73,4 | 1.469 | 315 | 873 | 279 | 50,0 | **0,664** | **true** |
| Bugün ne üzerinde çalışmalıyım? | 3.236 | 80,9 | 1.490 | 605 | 862 | 279 | 46,0 | 0,364 | false |
| **Ortalama** | **3.083** | **77,1** | | | | | **41,8** | | **1/5** |

**Okunacak dersler:**
1. **K4 çözüldü** — Faz 11'in "wiki dolarsa K4 düzelir" öngörüsü doğru çıktı ama beklenmedik yoldan: `general_brain` bölümü (kimlik + onaylı kurallar + yetenekler arası wiki) 1.469–1.490 token ile bütçe tavanını (`BUDGET_GENERAL_BRAIN = 1500`) neredeyse doldurup **tek başına** hedefi taşıdı.
2. **"Ajan panosunda kart nasıl kapanır?" sorgusunda `general_brain` 623 token'a düşüyor** — Entropy'nin *kendi* çalışma biçimi hakkındaki en operasyonel soruda beyin paketi en zayıf. Neden: pano bilgisi wiki sayfası olarak derlenmiş değil, `docs/` ve kod içinde.
3. **CRAG eşiği agresif:** 5 sorgunun 4'ünde `brain_confidence` 0,36–0,41, eşik 0,45. Yani sistem "beynimde yok" diyor ve araştırmaya çıkacak — oysa 1.482 token'lık ilgili beyin paketi üretebiliyor. **`CRAG_MIN_SCORE` gerçek korpusla kalibre edilmedi.** (Faz 11 notu §4.5 bu eşiği 0,55 önermişti; kodda 0,45; ölçülen dağılım ikisinin de altında.)

### 3.3 En sert bulgu: üç konsolidasyon komutu üretimde kablosuz

Faz 11 üç modül yazdı (`gray_merge.py` 517 satır, `dream.py` 542 satır, `wiki.py:compile_skill`). Üçü de **köprüsüz** çalıştırılıyor, yani **model hiç çağrılmıyor** — dolayısıyla sentez üretilmiyor.

**(a) `/memory merge` hiç çalışmıyor — sessiz `ImportError`**

```python
from entropy.memory.gray_merge import run as gray_run   # src/entropy/core/slash_commands.py:1686
```
`gray_merge` modülünde `run` diye bir ad **yok**; gerçek ad `run_merge_round` (`src/entropy/memory/gray_merge.py:445`). Kanıt (koşturuldu):
```
IMPORT FAIL -> ImportError cannot import name 'run' from 'entropy.memory.gray_merge'
```
`except Exception` bunu yutuyor ve kullanıcıya döndürülen metin: *"Toplu birleştirme modülü (`memory/gray_merge.py`) **henüz kurulu değil**."* — **modül kurulu, çalışıyor ve testleri yeşil.** Bu, `STATE.md` §3'te yazılı sözleşmenin (`/memory merge` → `gray_merge.run_merge_round`) fiilen ihlali. K9 = 0 ölçümünün *"kuyruk boş, iyi durumdayız"* diye okunması **yanlış**; kuyruğu boşaltacak komut hiç koşmamış olabilir.

**(b) `/wiki compile` köprüyü hiç almıyor ve `--turns` sessizce yutuluyor**

```python
def _handle_wiki(args: str) -> str:        # src/entropy/core/slash_commands.py:1265  ← bridge parametresi YOK
...
        res = compile_skill(name, turns=turns)     # :1342
    except TypeError:
        res = compile_skill(name)                  # :1344
```
Gerçek imza: `compile_skill(skill, bridge=None, budget_turns=..., ...)` (`src/entropy/memory/wiki.py:841-849`). Kanıt (koşturuldu):
```
compile_skill turns= -> compile_skill() got an unexpected keyword argument 'turns'
```
Yani **her** `/wiki compile` çağrısı TypeError'a düşüp `compile_skill(name)`'e geriliyor: **köprü yok → `turns = 0` → yalnızca playbook tabanlı iskelet sayfalar.** Üstelik kullanıcıya dönen metin *"Wiki Derlendi — X (N tur)"* diyor; **N kullanıcının yazdığı sayı, gerçekte harcanan tur değil.** Karşılaştırma: `_handle_memory` köprüyü alıyor (`gray_run(bridge=bridge)`), `_handle_wiki` almıyor — asimetri.

**(c) `/memory dream` elinde köprü varken `send_prompt=None` geçiyor**

```python
result = dream_and_consolidate(memory=cog, send_prompt=None)   # src/entropy/core/slash_commands.py:1711
```
Aynı fonksiyonun `bridge` değişkeni kapsamda. Rüya döngüsünün 2. adımı (gri bant turu) `send_prompt` yoksa **kuru koşum** yapıyor (`memory/dream.py:426`). `main.py:192` ve `ui/widgets/tasks_widget.py:307` için `None` **doğrudur** (arka plan zamanlayıcı, kullanıcı onayı yok); ama kullanıcının açıkça yazdığı `/memory dream` için değil.

**Toplam etki:** Faz 11'in "damıtma ve konsolidasyon" katmanı üretimde **LLM'siz iskelet üretecine** dönüşmüş durumda. K6'nın FAIL olmasının tek nedeni budur.

### 3.4 K6 — wiki katmanı: sayfa var, bilgi yok

Kasa envanteri (`C:\Users\batu_\OneDrive\Belgeler\Obsidian Vault\Entropy\Skills`):

| Yetenek | wiki sayfası | rapor | PLAYBOOK.md (B) | `WIKI.state.json` |
|---|---:|---:|---:|---|
| autonomous-agent | 25 | 0 | 9.294 | **yok** |
| financial-auditor | **0** | **50** | 9.537 | **yok** |
| media-agency-soldier | **20** *(Faz 11'de 0 idi)* | 16 | 8.644 | **yok** |
| pdf-analyzer | 0 | 0 | 7.608 | yok |
| research | 4 | 0 | **yok** | yok |
| skill-creator | 0 | 5 | **yok** | yok |
| slide-deck-architect | 0 | 0 | 6.813 | yok |

Toplam `Entropy/Reports`: **423 rapor** (Faz 11 ile aynı).

Yetenekli bağlamda ölçülen wiki payı (aynı builder, DB kopyası):

| Yetenek | toplam token | `wiki_pages` | **wiki payı** | playbook | recall | reports |
|---|---:|---:|---:|---:|---:|---:|
| financial-auditor | 3.382 | 0 | **%0,0** | 1.491 | 757 | 855 |
| media-agency-soldier | 2.891 | 106 | **%3,7** | 1.497 | 360 | 649 |
| autonomous-agent | 3.415 | 80 | **%2,3** | 1.492 | 765 | 799 |

**İki ayrı sorun, ayrı ayrı kaydedilmeli:**
1. **50 raporu olan `financial-auditor`'ın hâlâ 0 wiki sayfası var.** Faz 11'de "kota tavanı" diye ertelenmişti; §3.3(b) bulgusundan sonra artık bunun **ikinci bir nedeni** olduğunu biliyoruz: komut zaten köprüsüz koşuyordu, koşulsa da model turu harcamayacaktı.
2. **`media-agency-soldier`'ın 20 sayfası köprüsüz üretildi** (Faz 11 QA: `turns 0`, 18 sayfa). Bağlama giren pay %3,7 — yani sayfalar var ama geri getirme onları neredeyse hiç seçmiyor. **Sayfa sayısı bir başarı ölçütü değil; K6 doğru ölçüttür.**
3. **`WIKI.state.json` hiçbir yetenekte yok** → artımlılık sözleşmesi (`STATE.md` §3: "ikinci çağrıda yeni rapor yoksa 0 tur") üretimde hiç test edilmemiş. Gerçek köprülü koşumda ilk iş bunun oluştuğunu doğrulamak olmalı.

### 3.5 Diğer açık işlerin bugünkü durumu (STATE.md §5'e karşı denetim)

| STATE.md'de yazan | Bugünkü gerçek | Kanıt |
|---|---|---|
| `tasks_widget.py:425` hâlâ eski `dream_and_consolidate`'i çağırıyor | **KAPANDI** | `src/entropy/ui/widgets/tasks_widget.py:305-307` → `from entropy.memory.dream import dream_and_consolidate` |
| `config.amplification_lock` arayüzde karşılıksız | **KAPANDI** | `src/entropy/ui/modes/zen_mode.py:610,631-634` + `chat_mode.py:715` (`/lock on\|off`) |
| Kartın `report_path` alanı hiç dolmuyor | **KAPANDI** | commit `2719bdf` ("report_path flows to card/board/report signal") |
| `amplification.admit_report` kapıyı iki kez koşuyor | **KAPANDI** | `src/entropy/agents/amplification.py:269-281` → `store_decision` tek geçiş |
| K12 258 kaynaksız | **KAPANDI** (256 `legacy:pre-v2` etiketlendi) | `brain_metrics` `legacy_untagged: 256`, `count: 2` |
| Gerçek gri birleştirme turu koşulmadı | **AÇIK — üstelik komut bozuk** | §3.3(a) |
| Gerçek wiki derleme koşulmadı | **AÇIK — üstelik komut köprüsüz** | §3.3(b) |
| K8 gerçek korpusta ölçülmedi | **AÇIK** | kota; doğrulanamayanlar listesinde |
| `memory` → `brain` paket taşıması (Faz 12) | **YAPILMADI** | `src/entropy/brain` yok; `src/entropy/memory` 23 modül |

**Depo/test durumu:** 2.347 test toplanıyor (`pytest --collect-only -q`; Faz 11 kapanışında 2.320). `src/entropy` altında paketler: `agents, core, desk, mcp, memory, platform, scheduler, skills, tools, ui`.

### 3.6 Denetim özeti — puan tablosu

| Yetenek | Faz 11 sonu | **Faz 12** | Kanıt |
|---|---|---|---|
| Anlamsal geri çağırma | İyi | **İyi** | Hit@1 9/10, gürültü %0 |
| Yazma kapısı (yenilik denetimi) | Kuruldu | **Çalışıyor** | K1 %5,49, K11 82 ms |
| Kategori disiplini | 4 kapalı küme | **Korunuyor** | kanonik dışı 0 |
| Test/üretim yalıtımı | Düzeltildi | **Korunuyor** | K10 = 0 |
| Çift-zamanlı graf + PPR | İyi | **İyi** | okuma yoluna bağlı |
| Genel sohbette beyin | %56,8 | **İyi (%77,1)** | K4/K5 PASS |
| Kaynak zorunluluğu (L2) | 2 kalıntı | **Fiilen tamam** | K12 tanım düzeltmesi bekliyor |
| **Gri bant birleştirme (gerçek tur)** | Koşulmadı | **BOZUK** | `ImportError`, §3.3(a) |
| **Wiki derlemesi (Karpathy L2)** | Neredeyse yok | **BOZUK + FAIL** | köprüsüz, K6 ≤ %3,7 |
| **Rüya döngüsü (sentez)** | v2 yazıldı | **KURU** | `send_prompt=None`, §3.3(c) |
| CRAG eşiği kalibrasyonu | — | **YOK** | 4/5 sorguda `has_answer=false` |
| Skill doğrulama döngüsü | Yok | **YOK** | playbook çalıştırılarak sınanmıyor |
| Beceri küratörlüğü | Yok | **YOK** | 7 yetenekten 2'sinde playbook yok |
| Ölçülmüş unutma (rate–distortion) | Yok | **YOK** | `forget_stale` kural tabanlı |
| Zamansal sorgu çözümleme | Yok | **YOK** | mem0 13 May 2026'da ekledi |
| K8 (araştırma yenilik oranı) | Tek kuru ölçüm | **ÖLÇÜLEMEDİ** | kota |

---

## 4. "Brain v3" önerisi

Tasarım ilkesi değişmedi ve ölçümle doğrulandı: **okuma yolu ve yazma kapısı iyi; şimdi sıra derleme katmanını gerçekten çalıştırmakta.** Brain v3 yeni mimari değil, **Faz 11'in bitmemiş yarısının bitirilmesi + dört küçük yeni yetenek**.

### 4.1 B3-1 — Köprü kablolaması (öncelik 1, kod maliyeti en düşük, etki en yüksek)

Tek bir sözleşme kuralı: **kullanıcı bir konsolidasyon komutu yazdıysa köprü geçilir; zamanlayıcı koştuysa geçilmez.**

| Kalem | Bugün | Olması gereken | Kabul ölçütü |
|---|---|---|---|
| `/memory merge` | `ImportError` → yalan mesaj | `run_merge_round(memory, send_prompt=bridge)` | komut gerçek tur koşar; kuyruk azalır; `gray_merge_log.jsonl` satırı yazılır |
| `/wiki compile` | köprüsüz, `turns` yutuluyor | `_handle_wiki(args, bridge)`; `compile_skill(name, bridge=bridge, budget_turns=turns)` | dönen `turns > 0`; `WIKI.state.json` oluşur; ikinci çağrı `turns = 0` |
| `/memory dream` | `send_prompt=None` | kullanıcı komutunda `send_prompt=bridge` | `DreamReport` gri bant adımı kuru değil |
| Sessiz `except` | modülü "kurulu değil" sayıyor | **`ImportError` ile `AttributeError` ayrılır**; ad hatası kullanıcıya *hata* olarak görünür | sözleşme testi: her yerel komutun hedef sembolü gerçekten var |

> **Yeni kalıcı sözleşme testi önerisi:** `tests/contracts/` altında, `slash_commands` içindeki tüm `from entropy.memory...import X` satırlarını **gerçekten çözümleyen** bir test. Bu tek test §3.3(a)'yı ilk günde yakalardı.

### 4.2 B3-2 — Uyarlanabilir eşik (SAGE'in bizde eksik kalan yarısı)

Bugün bantlar sabit (`0,80` / `0,95`). SAGE eşiği **korpus geometrisine** bağlıyor. Öneri: `MemoryGate` her N yazımda bir, korpusun komşuluk benzerlik dağılımının persentillerini yeniden hesaplasın (`ADD` eşiği = p20, `NOOP` eşiği = p95), sınırlar `[0,75; 0,88]` ve `[0,93; 0,97]` aralığına kelepçelensin.
**Kabul:** K1 ≤ %10 korunur; gri bant oranı yazımların %10–20'sinde kalır (SAGE'in ölçtüğü %16–18 bandı); K11 ≤ 400 ms.

### 4.3 B3-3 — CRAG eşiği kalibrasyonu (ölçülmüş, keyfi değil)

`CRAG_MIN_SCORE = 0.45` gerçek dağılımda 4/5 sorguyu "beyinde yok" sayıyor. Öneri: 20 sorgulu etiketli küme (10'u beyinde **var**, 10'u **yok**) üzerinde ROC benzeri tarama; eşik F1'i en çoklayan noktaya konur ve **koda sabit değil, ölçüm çıktısıyla birlikte** yazılır.
**Kabul:** etiketli kümede `brain_has_answer` doğruluğu ≥ %80; yanlış-pozitif ("var" deyip yanlış) ≤ %10 (yanlış-pozitif yanlış-negatiften pahalıdır: araştırma atlanır).

### 4.4 B3-4 — Zamansal sorgu çözümleme (mem0'ın 13 May 2026 özelliği, bizde yok)

"geçen hafta", "dün", "bu ay", "en son" gibi Türkçe zaman ifadeleri `valid_from/valid_to` süzgecine çevrilir (LLM'siz, düzenli ifade + takvim).
**Kabul:** 10 zamanlı sorguda doğru pencere ≥ 8/10; zamansız sorgularda K2 değişmez.

### 4.5 B3-5 — Beceri paketi şeması + doğrulama halkası (SKILLFOUNDRY + EvoSkills)

`SKILL.md`/`PLAYBOOK.md` şemasına dört zorunlu alan: **ortam varsayımları**, **provenance**, **sonlandırma ölçütü**, **testler**. Bir playbook güncellemesi ancak kendi doğrulayıcısını geçerse kalıcılaşır (bizim "kanıtla kapat" kuralının hafıza karşılığı).
**Kabul:** 7 yeteneğin tamamında playbook var (bugün 5); her playbook'ta dört alan dolu; `lint.py` bu alanların eksikliğini bulgu olarak raporlar.

### 4.6 B3-6 — Ölçüm dürüstlüğü düzeltmeleri

| Düzeltme | Gerekçe |
|---|---|
| K12'ye `AND is_identity = 0` | Kimlik düğümünün dış kaynağı olamaz; bugünkü FAIL ölçüm tanımı hatası (§3.1) |
| K4/K5/K6 kalıcı harness'a alınsın | Bu turda elle koşuldu; `brain_metrics.py --context` bayrağı ile betiğe girmeli |
| K6 "sayfa sayısı" ile değil **bağlam payı** ile ölçülmeye devam etsin | 20 köprüsüz sayfa %3,7 pay üretiyor — sayfa sayısı yanıltıcı |
| K1 trend olarak izlensin | %4,76 → %5,49; kapı fazlalığı sınırlıyor, sıfırlamıyor |

### 4.7 Kabul ölçütleri tablosu (Faz 12 çıkışı)

| # | Ölçüt | Bugün | Faz 12 hedefi |
|---|---|---:|---:|
| K1 | yineleme | %5,49 | ≤ %10 (korunur) |
| K2 | Hit@1 / Hit@5 | 9/10 · 10/10 | ≥ 9/10 · 10/10 (korunur) |
| K3 | gürültü | %0,0 | ≤ %2 (korunur) |
| K4 | genel bütçe kullanımı | %77,1 | ≥ %70 (korunur) |
| K5 | genel damıtılmış pay | %41,8 | ≥ %40 (korunur) |
| **K6** | **wiki payı (3 yetenek ort.)** | **%2,0** | **≥ %15** |
| K7 | kategori | 0 kanonik dışı | 0 |
| **K8** | **araştırma yenilik oranı** | **ölçülmedi** | **≥ %70, gerçek turda ölçülür** |
| **K9** | **gri kuyruk turu** | **komut bozuk** | **gerçek tur koşar, kuyruk boşalır** |
| K10 | fikstür | 0 | 0 |
| K11 | kapı gecikmesi | 82,4 ms | ≤ 400 ms |
| K12 | kaynaksız L2 | 2 (kimlik) | 0 (tanım düzeltmesiyle) |
| **K13** *(yeni)* | **CRAG doğruluğu** (20 etiketli sorgu) | — | **≥ %80** |
| **K14** *(yeni)* | **playbook kapsaması** | 5/7 | **7/7, dört alan dolu** |

---

## 5. Faz 12 iş listesi

Kota tahmini = CLI turu (bir tur ≈ orta boy istem + yanıt).

| # | İş | Ajan | Bağımlılık | Kota | Kabul ölçütü |
|---|---|---|---|---:|---|
| **12.1** | **Köprü kablolaması (B3-1).** `/memory merge` `ImportError` düzeltmesi, `_handle_wiki(args, bridge)`, `compile_skill(bridge=, budget_turns=)`, `/memory dream` köprülü; `except` daralt (`ImportError` ≠ `AttributeError`) | agy-integration-engineer | — | ~8 | üç komut da köprüyle koşuyor; `/wiki compile` dönen `turns > 0` |
| **12.2** | **Yerel komut sembol sözleşmesi testi.** `slash_commands` içindeki tüm hafıza içe aktarımlarının gerçekten çözümlendiğini doğrulayan kalıcı test | qa-build-engineer | 12.1 | ~5 | test §3.3(a) sınıfı hatayı yakalıyor; tam süit yeşil |
| **12.3** | **Gerçek gri bant turu (kotalı).** `/memory merge` ile kuyruk boşaltma; öncesinde yedek | agy-integration-engineer | 12.1, 12.2 | ~10 | K9: kuyruk azalıyor; `gray_merge_log.jsonl` satırları; K1 ≤ %10 korunuyor |
| **12.4** | **Gerçek wiki derleme — `financial-auditor` (50 rapor).** `budget_turns` ile dilimlenerek; artımlılık doğrulanır | memory-rag-engineer + agy-integration-engineer | 12.1 | **~50** (en pahalı kalem) | K6 ≥ %15; `WIKI.state.json` oluşuyor; ikinci çağrı 0 tur; `lint` 0 çelişki |
| **12.5** | **Gerçek wiki derleme — `media-agency-soldier` (16 rapor) + köprüsüz 20 sayfanın yeniden derlenmesi** | memory-rag-engineer | 12.4 | ~18 | bu yetenekte wiki payı ≥ %15 |
| **12.6** | **CRAG eşiği kalibrasyonu (B3-3).** 20 etiketli sorgu; eşik ölçümle belirlenir | memory-rag-engineer | — | ~8 | K13 ≥ %80; yanlış-pozitif ≤ %10 |
| **12.7** | **Uyarlanabilir eşik (B3-2).** `MemoryGate` persentil tabanlı bant, kelepçeli | memory-rag-engineer | 12.6 | ~12 | K1 ≤ %10; gri oran %10–20; K11 ≤ 400 ms |
| **12.8** | **Ölçüm dürüstlüğü (B3-6).** K12 `is_identity` muafiyeti; K4/K5/K6 `brain_metrics.py` içine; K1 trend satırı | qa-build-engineer | — | ~8 | `brain_metrics --json` K1–K14 üretiyor; elle ölçüm gerekmez |
| **12.9** | **K8 gerçek ölçümü.** Öz-amplifikasyon kilidinin (a) açık tespiti kolu gerçek bir araştırma kartında tetikleniyor mu | agy-integration-engineer | 12.6 | ~12 | K8 ≥ %70 raporlanır; kısayol en az bir kez tetiklenir |
| **12.10** | **Zamansal sorgu çözümleme (B3-4).** Türkçe zaman ifadeleri → `valid_from/to` süzgeci | memory-rag-engineer | — | ~10 | 10 zamanlı sorguda ≥ 8/10; K2 bozulmaz |
| **12.11** | **Beceri paketi şeması (B3-5).** Dört zorunlu alan; eksik playbook'lar (`research`, `skill-creator`); `lint.py` denetimi | memory-rag-engineer | — | ~15 | K14 = 7/7; lint eksik alanı bulgu yazıyor |
| **12.12** | **`memory` → `brain` paket taşıması.** 23 modül, içe aktarım güncellemesi, geriye dönük takma ad | repo-curator | 12.1–12.8 sonrası | ~10 | tam süit yeşil; `EntropyAI.spec` derleniyor; `ARCHITECTURE.md`/`STATE.md` eşitlendi |
| **12.13** | **Hafıza panosu (Desk "Bellek" + Entropy).** K1–K14 canlı, gri kuyruk boyu, wiki payı, son derleme raporu | ui-engineer | 12.8 | ~10 | panel açılıyor; sayılar `brain_metrics` ile birebir |
| **12.14** | **Depo temizliği.** Kökteki `module_task_*.py`, `schema_task_*.py` (40+ dosya), `*_audit.md/json`, `scratch/_*.log`, izlenmeyen `.agents/` artıkları | repo-curator | — | ~5 | `git status --short` ≤ 20 satır; import kırılmıyor |
| **12.15** | **Build + duman testi + faz raporu.** | qa-build-engineer | tümü | ~10 | `dist_check` açılıyor; exe smoke exit 0; yalıtım kanıtı (önce = sonra) |

**Toplam kota tahmini: ~191 CLI turu.** Kalemlerin **%36'sı (68 tur)** tek bir işte: gerçek wiki derlemesi (12.4 + 12.5). Bunun ekonomik gerekçesi arXiv:2604.11243'tür (derlenmiş wiki rejiminde kümülatif token **%84,6** daha az; yüksek konu yoğunluğunda %81,3 tasarruf) — **bu 68 tur harcama değil, sermaye yatırımıdır.**

**Kritik yol önerisi:** `12.1 → 12.2 → 12.4 → 12.5`. Bu dördü bitince K6 düzelir ve Faz 11'in bitmemiş yarısı kapanır; kalanı iyileştirmedir. 12.12 (paket taşıması) **en sona** bırakılmalı — hareketli hedef yaratır.

**Riskler:**
- *12.4 kota aşımı* — `budget_turns` tavanı ve `WIKI.state.json` artımlılığı zaten var; **ama artımlılık üretimde hiç doğrulanmadı** (§3.4). İlk dilim 5 raporla koşulup state dosyası doğrulanmadan devam edilmemeli.
- *12.3 veri kaybı* — gri birleştirme içerik günceller; yedek zorunlu (`~/.entropy/backups/`), `cancel_merge()` var, ayrıştırılamayan yanıt kuyruğu boşaltmıyor.
- *12.7 geri çağırmayı bozma* — K2 kapısı; eşik kelepçeleri; geri alma `ENTROPY_MEMORY_GATE=0`.
- *12.12 import kırılması* — 23 modül + `EntropyAI.spec` + testler; geriye dönük takma ad şart.
- *12.1'in gizli kardeşleri* — aynı sessiz-`except` deseni başka yerlerde de olabilir; 12.2 bunu sistematik taramalı.

---

## 6. Karar özeti

| Soru | Karar | Gerekçe |
|---|---|---|
| mem0 kütüphane olarak alınsın mı? | **Hayır** (değişmedi) | Her yazımda LLM; ADD-only; yerleşik graf ≠ çift-zamanlı graf + PPR |
| mem0'dan yeni bir şey alınsın mı? | **Evet: zamansal sorgu çözümleme** (13 May 2026) | Ucuz, LLM'siz, bizde yok |
| ConsistencyGate uygulansın mı? | **Kısmen** | K-kez sorma ve logprob varyantı kotamıza uymaz; gece turunda tek soru biçimi alınabilir — Faz 13 |
| MemGraphRAG? | **Hayır** | Çok-ajanlı graf gezme, tur başına çoklu çağrı |
| SAGE uyarlanabilir eşik? | **Evet** (12.7) | Kapının bizde eksik kalan yarısı |
| SKILLFOUNDRY beceri şeması? | **Evet** (12.11) | 4 eksik alan, doğrudan uygulanabilir |
| Faz 12'nin ana yatırımı? | **Gerçek wiki derlemesi (68 tur)** | K6 tek FAIL; arXiv:2604.11243 ROI gerekçesi |
| K12 FAIL gerçek mi? | **Hayır, ölçüm tanımı hatası** | 2 düğümün ikisi de `is_identity` |
| Hafıza yeniden silinsin mi? | **Hayır** | K1 %5,49, K10 = 0, K2 9/10 — korpus sağlıklı |

---

## 7. Doğrulanamayanlar (dürüstlük listesi)

1. **K8 (araştırma turu yenilik oranı)** — gerçek bir araştırma kartı koşturmak gerekiyordu; kota harcamamak için yapılmadı. Faz 11'deki tek kuru ölçüm (%83) tek karta ait, genellenemez.
2. **Öz-amplifikasyon kilidinin (a) açık tespiti kolu** — Faz 11'de hiç tetiklenmedi, R3 düzeltmesinden sonra da ölçülmedi. **Bugün de ölçülmedi.**
3. **`/memory merge` düzeltilse kuyruğun ne kadar dolacağı** — kuyruk bugün 0 satır; ama komut hiç koşmadığı için bunun "temiz" mi "hiç bakılmamış" mı olduğu ayırt edilemiyor.
4. **`WIKI.state.json` artımlılık sözleşmesi** — hiçbir yetenekte dosya yok; üretimde hiç doğrulanmadı.
5. **Tam test süiti bu turda koşulmadı** (yalnızca `--collect-only`: 2.347 test). Yeşillik iddiası edilmiyor.
6. **mem0 kıyas rakamları** satıcı blogundan; bağımsız doğrulama yok (GroupMemBench/AMA-Bench farklı sıralama üretiyor).
7. **X / @_akhaliq** doğrudan erişilemedi; HF Daily Papers üzerinden dolaylı takip.
8. **SAGE'in %16–18 gri bant oranı** bizim korpusumuzda doğrulanmadı (kuyruk boş).
9. **Bazı yeni arXiv kayıtları** (SkillOS 2605.06614, SkillSmith 2606.01314, SkillOpt 2605.23904, MemGraphRAG 2606.00610, GroupMemBench 2605.14498) arama sonuçlarından alındı; **özet düzeyinde okundu, tam metin denetlenmedi.**

---

## 8. Kaynaklar

**Yazma tarafı denetimi ve konsolidasyon**
- SAGE: A Novelty Gate for Efficient Memory Evolution in Agentic LLMs — Wang, Brahma, Henao — arXiv:2605.30711 (29 May 2026) — https://arxiv.org/abs/2605.30711
- **[YENİ]** ConsistencyGate: Preventing Memory Contamination in LLM Agents via Self-Consistency Admission Control — Yan Zhang, Shibo Li — arXiv:2607.22962 (25 Tem 2026) — https://arxiv.org/abs/2607.22962
- **[YENİ]** Governing Evolving Memory in LLM Agents: Risks, Mechanisms, and the SSGM Framework — arXiv:2603.11768 — https://arxiv.org/pdf/2603.11768
- Dual-Layer Agentic Memory with Fast Write Routing and Slow Consolidation — arXiv:2608.22215 (23 Ağu 2026) — https://arxiv.org/abs/2608.22215
- The Consolidation Problem in Agent Memory — Hindsight (21 May 2026) — https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation
- Manufactured Confidence — arXiv:2606.29279 · When Memory Becomes Authority — arXiv:2608.01679 · Rate–Distortion View of Memory Compaction — arXiv:2607.08032

**Bellek mimarileri ve kıyaslar**
- CoALA — arXiv:2309.02427 — https://arxiv.org/abs/2309.02427
- HippoRAG 2 / From RAG to Memory — arXiv:2502.14802
- Zep: A Temporal Knowledge Graph Architecture for Agent Memory — arXiv:2501.13956
- A-MEM — arXiv:2502.12110 · Letta Memory Blocks — https://www.letta.com/blog/memory-blocks/ · Sleep-time Compute — https://www.letta.com/blog/sleep-time-compute/
- **[YENİ]** MemGraphRAG: Memory-based Multi-Agent System for Graph RAG — arXiv:2606.00610 — https://arxiv.org/html/2606.00610v1
- **[YENİ]** GroupMemBench: Benchmarking LLM Agent Memory in Multi-Party Conversations — arXiv:2605.14498 — https://arxiv.org/pdf/2605.14498
- **[YENİ]** Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks — arXiv:2602.16313
- AMA-Bench — arXiv:2602.22769 — https://arxiv.org/html/2602.22769v4
- **[YENİ]** CALMem: Application-Layer Dual Memory for Conversational AI — arXiv:2605.20724

**Beceri / yordamsal bellek**
- SoK: Agentic Skills — arXiv:2602.20867
- **[YENİ]** SKILLFOUNDRY: Building Self-Evolving Agent Skill Libraries from Heterogeneous Scientific Resources — arXiv:2604.03964 — https://arxiv.org/abs/2604.03964
- **[YENİ]** EvoSkills / CoEvoSkills: Self-Evolving Agent Skills via Co-Evolutionary Verification — arXiv:2604.01687 — https://arxiv.org/html/2604.01687v1
- **[YENİ]** SkillCoach: Self-Evolving Rubrics for Evaluating and Enhancing Agentic Skill-Use — arXiv:2607.01874 — https://arxiv.org/html/2607.01874v1
- **[YENİ]** SkillOS: Learning Skill Curation for Self-Evolving Agents — arXiv:2605.06614 · **[YENİ]** SkillSmith — arXiv:2606.01314 · **[YENİ]** SkillOpt — arXiv:2605.23904
- SkillForge — arXiv:2604.08618 · SkillAudit — arXiv:2606.14239 · HyperSkill — arXiv:2608.16114

**RAG ve bilgi derleme**
- **[YENİ]** Knowledge Compounding: An Empirical Economic Analysis of Self-Evolving Knowledge Wikis under the Agentic ROI Framework — arXiv:2604.11243 — https://arxiv.org/pdf/2604.11243
- Karpathy LLM wiki deseni (gist, **4 Nis 2026**) — açıklamalı derleme: https://www.kunalganglani.com/blog/llm-wiki-karpathy-local-knowledge-base · https://blog.starmorph.com/blog/karpathy-llm-wiki-knowledge-base-guide
- **[YENİ]** Karpathy deseni referans uygulaması (Agent Skills uyumlu) — https://github.com/Astro-Han/karpathy-llm-wiki
- Is Agentic RAG worth it? — arXiv:2601.07711 · Reasoning RAG via System 1 or System 2 — arXiv:2506.10408 · Towards Agentic RAG with Deep Reasoning — arXiv:2507.09477
- Graph RAG: A Survey — arXiv:2408.08921 · LEGO-GraphRAG — arXiv:2411.05844 · GraphRAG-Bench — arXiv:2506.02404
- LlamaIndex — Context Engineering: What it is and techniques to consider — https://www.llamaindex.ai/blog/context-engineering-what-it-is-and-techniques-to-consider

**mem0**
- Depo (Apache-2.0) — https://github.com/mem0ai/mem0
- **Changelog / Highlights (bu turda yeniden okundu)** — https://docs.mem0.ai/changelog · https://mem0.ai/changelog
- Desteklenen LLM sağlayıcıları — https://docs.mem0.ai/components/llms/overview
- OSS v2 → v3 göç kılavuzu — https://docs.mem0.ai/migration/oss-v2-to-v3
- Mem0 (makale) — arXiv:2504.19413 · State of AI Agent Memory 2026 (satıcı blogu) — https://mem0.ai/blog/state-of-ai-agent-memory-2026

**Çerçeveler**
- Microsoft Agent Framework (AutoGen + Semantic Kernel) — https://learn.microsoft.com/en-us/agent-framework/overview/

**Durumu değişmiş kaynak**
- paperswithcode.com — bağımsız yayında değil; https://huggingface.co/papers/trending adresine yönlendiriyor (10 Eyl 2026'da yeniden doğrulandı).
- HF Daily Papers 10 Eyl 2026 listesinde hafıza/RAG makalesi yok.

---

## Ek A — Ölçüm yeniden üretilebilirliği

Tüm sayılar `~/.entropy/cognitive_memory.db` (10 Eyl 2026, 7.593.984 B, 729 satır) dosyasının **kopyası** üzerinde üretildi.

1. **K1/K2/K3/K7/K9/K10/K11/K12:** `python scripts/brain_metrics.py --json --db <kopya>` → exit 0.
2. **K4/K5:** `CognitiveContextBuilder(memory_system=CognitiveMemorySystem(db_path=<kopya>)).build(q, skill_name=None)`, 5 Türkçe genel sorgu, `AssembledContext.sections` üzerinden `kind` bazında token toplamı; damıtılmış küme = `{general_brain, playbook, wiki, wiki_pages, handoff, brain_*, promoted_rules, identity}`.
3. **K6:** aynı builder, `skill_name ∈ {financial-auditor, media-agency-soldier, autonomous-agent}`; `wiki_pages` bölümünün toplam token'a oranı.
4. **Kasa envanteri:** `find <kasa>/Entropy/Skills/<yetenek>/wiki -name '*.md' | wc -l` ve `.../Reports`.
5. **Kablolama hataları:** `from entropy.memory.gray_merge import run` ve `compile_skill('research', turns=2)` doğrudan koşturuldu; çıktılar §3.3'te birebir.
6. **Test sayımı:** `QT_QPA_PLATFORM=offscreen python -m pytest --collect-only -q -p no:cacheprovider` → 2.347.

**Marka kuralı:** Bu belgede ticari referans ürünün ve üreticisinin adı geçmez.
