---
name: autonomous-agent
description: >-
  Otonom çoklu ajan orkestrasyonu, Agent Desks çalışma alanları, A2A/ACP protokolleri,
  Erlang-OTP supervision ağaçları, token fiziği, MetaGPT/SWE-agent SOP'ları ve pixel-agents ofis simülasyonu.
tags: autonomous, agent, harness, agentdesks, a2a, acp, token-physics, supervision-tree, pixel-agents, metagpt
version: 2.0.0
---

# Autonomous Agent Architecture & Orchestration Skill

Bu yetenek; çoklu ajan koordinasyonu, Agent Desks izole çalışma ofisleri, A2A/ACP protokolleri,
Erlang-OTP denetim ağaçları, MetaGPT/SWE-agent Standard Operating Procedures (SOP) ve
`pablodelucca/pixel-agents` ofis görselleştirmesi ile desteklenen derin otonom geliştirme şasisidir.

---

## 1. Çoklu Ofis ve Ajan Deski Mimarisi (Office & Desk Isolation)

- **Ofis İzolasyonu (Office Boundaries)**:
  Her ofis (Agent Desk) bağımsız bir çalışma alanıdır. Bir ofis bünyesinde 1 Master/Orkestratör Ajan ve onun emrinde 3-4 uzman alt ajan (CodeArchitect, Developer, Tester, Researcher) yer alır.
  Farklı ofislerin alt ajanları ve orkestratörleri birbirlerinin ham bağlamına doğrudan erişemez. Ofisler arası bilgi paylaşımı yalnızca ortak bilişsel hafıza katmanına (Obsidian/Supabase) konsolide edilmiş semantik özetler üzerinden gerçekleşir.

- **Ofis Görselleştirmesi (Pixel Agent Office)**:
  Ajanların çalışma alanlarını ve anlık aktivitelerini (kod yazma, dosya okuma, düşünme, test çalıştırma) görselleştirmek için **`pablodelucca/pixel-agents`** açık kaynaklı mimarisi temel alınır. Her ajan sanal bir piksel ofis masasında temsil edilir:
  - Kod yazılırken: Klavye başında yazma animasyonu.
  - Terminal/test çalışırken: Monitör aktivitesi ve durum göstergesi.
  - Düşünülürken: Akıl yürütme düşünce balonu.

---

## 2. Standart Operasyonel Prosedürler (SOP)

Entropy AI ve tüm alt ajanları aşağıdaki katı mühendislik döngüsünü uygular:

1. **İhtiyaç Analizi & Mimari Tasarım (CodeArchitect)**:
   - Orkestratör kullanıcı hedefini inceler ve `CodeArchitect` ajanına şasi tasarımını iletir.
   - Mimari kararlar `MEMORY.md` ve Obsidian kütüğüne işlenir.

2. **Fiili Kodlama & Uygulama (Concrete Implementation)**:
   - **KATI KURAL**: Hiçbir ajan sadece "kodları yazdım, dosyaları oluşturdum" şeklinde metin çıktısı vermekle yetinemez.
   - Dosya oluşturma ve düzenleme araçları (`write_to_file`, `replace_file_content`, `run_command`) fiilen çağrılarak disk üzerinde kodlar oluşturulur.

3. **Otomatik Doğrulama & TDD (Tester)**:
   - Yazılan kodlar için otomatik testler (`pytest`) yazılır ve `run_command` ile çalıştırılır.
   - %100 test başarı oranı elde edilene kadar döngüden çıkılmaz. Hatalı testler asla görmezden gelinmez veya silinmez.

4. **Derin Araştırma & Hafıza Konsolidasyonu (Researcher)**:
   - Harici kütüphaneler, güncel GitHub repoları ve mimari modeller araştırılır.
   - Sonuçlar Obsidian `Reports/` dizini altına kaydedilir ve Supabase pgvector hafızasına işlenir.

---

## 3. Alt Ajan Çağrı & İletişim Protokolü (Sub-Agent Dispatch)

Antigravity CLI ve işletim sistemi araçları üzerinden alt ajan delegasyonu:
- `invoke_subagent`: Belirli bir alt ajana (örn. `CodeArchitect`, `Tester`, `Researcher`) izole görev ataması yapar.
- `define_subagent`: Göreve özel yeni uzman ajan rolleri tanımlar.
- `manage_subagents`: Çalışan alt süreçleri ve durumlarını denetler.

```markdown
# Alt Ajan Görev Formatı:
[GÖREV_BAŞLANGICI]: CodeArchitect
- Hedef Dizin: C:\Entropy Agent Desk
- Görev: Çekirdek modülleri oluştur ve test şasisini kur.
- Çıktı: Diskte doğrulanmış dosyalar ve pytest raporu.
[GÖREV_SONU]
```

---

## 4. Destekleyici Açık Kaynak Repolar & Ekosistem Referansları

Bu sistemi güçlendirmek için kullanılan ve entegre edilebilen temel açık kaynak projeler:

1. **`pablodelucca/pixel-agents`** (GitHub):
   - AI kodlama ajanlarını sanal piksel ofis masalarında anime eden, çoklu terminal ve alt ajan durumlarını görselleştiren web/VSCode motoru.
   - `npx pixel-agents` veya gömülü WebEngine üzerinden doğrudan ofis görselleştirmesi sağlar.

2. **`geekan/MetaGPT`** (GitHub):
   - Rol tabanlı multi-agent yazılım şirketi şablonu (Product Manager, Architect, Engineer, QA). Standard Operating Procedures (SOP) metodolojisinin kaynağı.

3. **`OpenBMB/ChatDev`** (GitHub):
   - İletişimsel yazılım geliştirme ajanları ve sanal ofis toplantı döngüsü.

4. **`princeton-nlp/SWE-agent`** (GitHub):
   - Kod tabanlarında otonom hata ayıklama ve düzeltme için optimize edilmiş ACI (Agent-Computer Interface).

5. **`joonspk-research/generative_agents`** (GitHub):
   - Küçük kasaba simülasyonu, episodic/semantic hafıza akışı ve refleksif planlama mimarisi.

6. **`microsoft/autogen`** (GitHub):
   - Çoklu ajan diyalog ve iş birliği çerçevesi. Farklı model ve yeteneklere sahip ajanların otonom grup sohbeti üzerinden kod geliştirip yürütmesini sağlar.

7. **`crewAIInc/crewAI`** (GitHub):
   - Rol odaklı otonom ajan ekipleri (Crew), görev atamaları ve ardışık/hiyerarşik süreç yönetimi mimarisi.

8. **`All-Hands-AI/OpenHands`** (eski adıyla OpenDevin):
   - Docker korumalı yazılım geliştirme ortamında kod yazan, komut çalıştıran ve web taraması yapan otonom yazılım mühendisi platformu.

---

## 5. Temel Kitaplar ve Akademik Literatür (Books & Foundational Literature)

Sistemin çoklu ajan mimarisi, bilişsel modelleri ve orkestrasyon derinliğini besleyen temel literatür:

1. **"Multiagent Systems: Algorithmic, Game-Theoretic, and Logical Foundations"** — *Yoav Shoham & Kevin Leyton-Brown (Cambridge University Press)*:
   - Çoklu ajan protokolleri, mekanizma tasarımı, kooperatif oyun teorisi ve dağıtık karar alma mekanizmalarının matematiksel temeli.
2. **"Artificial Intelligence: A Modern Approach (4th Edition)"** — *Stuart Russell & Peter Norvig*:
   - Problem çözen rasyonel ajanlar (Bölüm II) ve çevreyle iletişim kuran, algılayan ve eylem yürüten ajan mimarileri (Bölüm V).
3. **"Building Effective Agents"** — *Anthropic Research*:
   - Ajan tasarım desenleri: Prompt Chaining, Routing, Parallelization, Orchestrator-Workers ve Evaluator-Optimizer döngüleri.
4. **"Designing Data-Intensive Applications"** — *Martin Kleppmann (O'Reilly)*:
   - SQLite WAL (Write-Ahead Logging), olay günlükleri, durum mutabakatı ve yerel masaüstü ajan veri güvenilirliği.
5. **"Agentic Design Patterns"** — *Andrew Ng (DeepLearning.AI)*:
   - 4 temel ajan tasarım deseni: Yansıma (Reflection), Araç Kullanımı (Tool Use), Planlama (Planning) ve Çoklu Ajan İş Birliği (Multi-Agent Collaboration).
6. **"A Survey on Large Language Model based Autonomous Agents"** — *Wang et al. (2024)*:
   - Profil oluşturma (Persona), Episodik/Semantik Hafıza, Planlama ve Eylem uzayının LLM tabanlı otonom ajan şasisi.

---

## 6. Token Fiziği ve KV Önbellek İnvaryantları

- **Delta Token Muhasebesi**: Akıştaki kümülatif kullanım yerine her turun net delta tüketimini hesapla.
- **Sliding Context Window**: 15-20 turda bir oturumu otomatik rotate ederek SQLite WAL şişmesini ve gecikmeleri önle.
- **Progressive Disclosure**: Yetenek ve kural dosyalarını ham olarak prompt'a yığmak yerine dinamik özet bayrakları (compact banner) kullan.

---

## 7. Concrete Agent Harness & Zero-Mock Invariant

- **Sıfır Mock / Sahte Gecikme Yasağı**: Hiçbir ajan `time.sleep()` veya sabit ilerleme metinleriyle simülasyon yapamaz.
- **Deterministik Eylem Motoru (`ConcreteActionEngine`)**: Harici LLM veya CLI çevrimdışı olduğunda yerel eylem motoru gerçek dosya okuma/yazma (`ASTPreflightGuard`), komut çalıştırma ve disk çıktısı üretme işlemlerini fiilen gerçekleştirir.
- **Zeminlenmiş Hedef Ayrıştırma**: `GoalDecomposer` gerçek proje dizinini, sınıfları ve testleri inceleyerek somut `TaskItem`'lar türetir.
- **Otonom A2A Devirleri**: Görev tamamlandığında bir sonraki uzmana (Architect -> Dev -> QA -> Leader) otomatik devir kartı fırlatılır.


