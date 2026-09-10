# -*- coding: utf-8 -*-
"""Phase 56 Cognitive Memory Synchronizer for Entropy AI."""

import sys
import datetime
from pathlib import Path

# Add src to python path
sys.path.insert(0, r"c:\EntropiAI\src")
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager

def run_sync():
    ovm = ObsidianVaultManager()
    brain_file = Path(r"C:\Users\batu_\.gemini\antigravity-cli\brain\268651c6-3a2a-4b4e-84c9-2cff0af6cc3a\2026_Yeni_Nesil_Otonom_Ajan_Mimarileri_Harness_AgentDesks_Token_Optimizasyonu_ve_Bilissel_Hafiza_Master_Ansiklopedisi.md")
    master_content = brain_file.read_text(encoding="utf-8")

    # 1. Save Master Encyclopedia Report
    master_title = "2026_Yeni_Nesil_Otonom_Ajan_Mimarileri_Harness_AgentDesks_Token_Optimizasyonu_ve_Bilissel_Hafiza_Master_Ansiklopedisi"
    master_tags = [
        "otonom_ajanlar",
        "harness_engineering",
        "agent_desks",
        "token_optimizasyonu",
        "bilissel_hafiza",
        "graphrag",
        "supabase_pgvector",
        "obsidian",
        "mcp",
        "a2a",
        "faz_56"
    ]
    rep1 = ovm.save_research_report(master_title, master_content, tags=master_tags)
    print(f"Saved master report: {rep1}")

    # 2. Save Task Record Report
    task_title = "Gorev_Otonom Ajan Mimarisi Araştırma_20260905_0645"
    task_tags = ["otonom_gorev", "faz_56", "arastirma_raporu"]
    task_content = """# Otonom Görev Raporu: Otonom Ajan Mimarisi Araştırma (Faz 56)

- **Görev Kimliği**: `scheduled-autonomous-agent-research-f56`
- **Tamamlanma Zamanı**: 2026-09-05 06:45:00
- **Durum**: Başarılı (%100 Tamamlandı)
- **Model / Motor**: Gemini 3.8 Flash (High) / Google Antigravity (AGY) Engine

---

## 🎯 İcra Özeti & Temel Bulgular

Kullanıcı talimatı ve bilişsel bellek direktifleri doğrultusunda **2026 Yeni Nesil Otonom Ajan Mimarisi Araştırması (Faz 56)** icra edilmiştir.

### 🏛️ 1. Otonom Ajan Paradigması: Agent = Model + Harness
- Temel modeller (Foundation Models) durumsuz ve olasılıksal muhakeme motorlarıdır.
- Deterministik başarı, modeli saran **Agentic Harness (İskele / Kontrol Düzlemi)** ile sağlanır.
- Yürütme döngüsü: **PDA-R** (Perceive -> Decide -> Act -> Observe -> Reflect).

### ⚖️ 2. Görev (Task) vs. Ajan (Agent) & Sıfır Kayıplı Yük Devri
- **Görev**: Bildirisel ve değişmez sözleşme (`spec.md`, programatik Definition of Done: `%100 pytest pass`).
- **Ajan**: Durumsal ve geçici yürütücü.
- Ajan kilitlendiğinde veya çöktüğünde görev nesnesi korunur; Git rollback ve yeni ajan diriltme ile sıfır bağlam kaybıyla devredilir (`Zero-Context-Loss Failover`).

### 🖥️ 3. Agent Desks (Ajan Masaları) Mimarisi
1. **Operasyonel Kontrol Masası (HITL Cockpit)**: Çoklu ajan telemetrisi ve insan onay kapıları (`Elicitation`).
2. **Bilişsel Masa (Working Memory Desk)**: "Desk Clutter" ve "Context Rot"u önleyen minimalist çalışma yüzeyi.
3. **Yalıtılmış Sanal Masalar (Git Worktrees)**: Ajanların çakışmasını engelleyen bağımsız disk havuzları.

### ⚡ 4. Token Fiziği & Önbellek Hiyerarşisi
- **Katmanlı Önbellek**: Anlamsal Önbellek (>0.96 benzerlik -> 0 token, 2ms) + Prompt Caching / RadixAttention (%80-%95 KV-cache tasarrufu).
- **Stable Prefix, Dynamic Suffix**: KV-cache isabetini koruyan mimari.
- **The Compaction Paradox**: Geleneksel özetlemenin KV önbelleğini kırması sorununa karşı **Anchored Iterative Compaction**.
- **Code-as-Action**: 50.000 satırlık veriyi prompta dökmek yerine Python REPL ile süzme (500k token -> 20 token).
- **Delta Token Muhasebesi**: Tekil turun gerçek tüketiminin hesaplanması: $\\Delta turn = \\max(0, U_k - U_{k-1})$.

### 🧠 5. 5 Katmanlı Bilişsel Bellek Sistemi & Rüya Konsolidasyonu
1. Çalışma Belleği (Scratchpad / Sliding Context)
2. Bölümsel Bellek (DailyNotes / JSONL)
3. Anlamsal Bellek (Supabase pgvector HNSW + PostgreSQL BM25 RRF)
4. İlişkisel Exocortex (Obsidian GraphRAG 2-Hop Wikilinks)
5. Prosedürel Bellek (Progressive Disclosure Skills / Pydantic Tools)
- **Sleep-Time Compute (Rüya Konsolidasyonu)**: Sistem boştayken Sürpriz Filtresi ve Ebbinghaus unutma eğrisi ($R = e^{-t/S}$) ile günlük logların kalıcı `MEMORY.md` mimari kararlarına dönüştürülmesi.

### 🔌 6. İletişim Protokolleri & Açık Kaynak Standartları
- **Model Context Protocol (MCP v2026-07-28)**: Stateless JSON-RPC 2.0, Tools, Resources, Prompts, Sampling, Roots, Elicitation.
- **Agent-to-Agent (A2A) & Artifact Passing**: Ajanlar arası sohbet geçmişi yerine yapılandırılmış Markdown ve diff aktarımı.
- **Açık Kaynak Liderleri**: Google Antigravity (`agy`), Anthropic MCP, Claude Code, OpenHands, SWE-agent, AutoGen/AG2, Aider, Letta, Mem0, AgentDesk.

---

## 🔗 İlgili Belgeler & Bağlantılar
- **Detaylı Master Ansiklopedi**: [[2026_Yeni_Nesil_Otonom_Ajan_Mimarileri_Harness_AgentDesks_Token_Optimizasyonu_ve_Bilissel_Hafiza_Master_Ansiklopedisi]]
- **Kalıcı Bilişsel Bellek**: [[MEMORY]] (Faz 56 Güncellemesi)
- **Master Bellek Haritası**: [[BELLEK_HARITASI]]
"""
    rep2 = ovm.save_research_report(task_title, task_content, tags=task_tags)
    print(f"Saved task report: {rep2}")

    # 3. Update MEMORY.md
    memory_file = ovm.memory_file
    current_mem = memory_file.read_text(encoding="utf-8")

    mem_addition = """
## 2026 Yeni Nesil Otonom Ajan Mimarileri, Harness Mühendisliği, Agent Desks, Token Fiziği ve Bilişsel Hafıza Sentezi (Faz 56) (2026-09-05)
- **Agent = Model + Harness Aksiyomu & Deterministik Kontrol**: Temel modeller olasılıksal ve durumsuzdur; kurumsal ve endüstriyel başarı modelin etrafındaki çalışma zamanı iskele (harness) ve kontrol düzlemi mühendisliğine bağlıdır.
- **Görev (Task) vs. Ajan (Agent) Ayrımı & Sıfır Kayıplı Devir (Zero-Loss Failover)**: Görev, serileştirilebilir bildirisel bir DAG Durum Makinesi sözleşmesidir (`PENDING -> IN_PROGRESS -> BLOCKED -> VERIFYING -> COMPLETED`). Ajan çöktüğünde görev durumu, kabul kriterleri ve git diff'i korunarak sıfır bağlam kaybıyla yeni ajana devredilir. Kabul kriteri programatik test başarısıdır (`exit_code == 0`).
- **Agent Desks (Ajan Masaları) & İzolasyon**: Operasyonel Kontrol Masası (HITL steering, onay kapıları), Bilişsel Masa (Desk Clutter ve Context Rot'u engelleyen odaklanmış çalışma alanı) ve Yalıtılmış Sanal Masalar (`git worktree add ../desk-x` ile bağımsız disk ve derleme havuzları).
- **Model Context Protocol (MCP v2026-07-28) & Linux Foundation A2A**: MCP'de durumsuz (stateless) JSON-RPC 2.0 mimarisi, `_meta` başlıkları, sunucu seviyesinde model zekası ödünç alma (Sampling), güvenli dosya kum havuzu (Roots) ve dinamik form tabanlı insan girdisi (Elicitation). A2A protokolünde `agent-card.json` ve sohbet geçmişi yerine yapılandırılmış Markdown ve diff aktarımı (Artifact Passing).
- **Token Fiziği & The Compaction Paradox**: Dinamik geçmiş özetlemenin KV-önbellek önekini bozması sorununa karşı **Anchored Iterative Compaction**. Katmanlı önbellek (Anlamsal Önbellek >0.96 -> 0 token, RadixAttention / Prefix Caching ile %80-%95 GPU tasarrufu), Delta Token Muhasebesi ($\Delta turn = \max(0, U_k - U_{k-1})$) ve Code-as-Action (Python REPL ile 500k -> 20 token) entegrasyonu.
- **5 Katmanlı Bilişsel Bellek Sistemi & Rüya Konsolidasyonu (Sleep-Time Compute)**: Çalışma, Bölümsel, Anlamsal, İlişkisel ve Prosedürel bellek hiyerarşisi. Supabase HNSW pgvector + PostgreSQL BM25 Reciprocal Rank Fusion (RRF) hibrit araması, Obsidian 2-Hop GraphRAG komşuluk taraması ve sistem boştayken çalışan rüya döngüsüyle Ebbinghaus sönümlenmesi ($R = e^{-t/S}$) ve sürpriz filtresi.
- **SWE-bench Pro & Açık Kaynak Ekosistem Haritası**: SWE-bench Verified doygunluğu sonrası SWE-bench Pro standardı; Google Antigravity, Anthropic MCP, Claude Code, OpenHands, SWE-agent, AutoGen/AG2, Aider, Letta, Mem0 ve AgentDesk ekosistemlerinin sentezi.
- **Detaylı Rapor**: [[2026_Yeni_Nesil_Otonom_Ajan_Mimarileri_Harness_AgentDesks_Token_Optimizasyonu_ve_Bilissel_Hafiza_Master_Ansiklopedisi]]

### Otonom Bilişsel Konsolidasyon (Rüya) (2026-09-05)
- Konsolide Bilişsel Özet (2026-09-05): 2026 Yeni Nesil Otonom Ajan Mimarileri Master Ansiklopedisi (Faz 56) tamamlandı. "Agent = Model + Harness" formülasyonu, Görev/Ajan durum makinesi ayrımı ve Zero-Loss Failover, Git Worktree yalıtımlı Agent Desks ve HITL telemetrisi, Temmuz 2026 MCP v2026-07-28 stateless spesifikasyonu (Tools, Resources, Prompts, Sampling, Roots, Elicitation), Linux Foundation A2A protokolü ve Artifact Passing, The Compaction Paradox ve Anchored Iterative Compaction, Tiered Caching, Code-as-Action, Delta Token Muhasebesi, Supabase pgvector HNSW + BM25 RRF ve Obsidian 2-Hop GraphRAG Bilişsel Bellek Triadı, Letta Sleep-Time Compute rüya konsolidasyonu ve 2026 model/ekosistem haritası eksiksiz olarak kalıcı bilişsel hafızaya işlendi.
- İpuçları: Faz 56 Otonom Ajan Mimarileri; Harness Engineering; Agent Desks Worktrees; Compaction Paradox; Stateless MCP 2026; Linux Foundation A2A; Letta Decoupled Sleep-Time Compute; SWE-bench Pro; Bilişsel Bellek Triadı.
"""

    memory_file.write_text(current_mem.strip() + "\n" + mem_addition.strip() + "\n", encoding="utf-8")
    print("Updated MEMORY.md successfully.")

    # 4. Update DailyNotes
    today = datetime.date.today().strftime("%Y-%m-%d")
    daily_file = ovm.daily_notes_dir / f"{today}.md"
    daily_entry = '[06:45:00] - **Otonom Bilişsel Görev**: [OTONOM PLANLI GÖREV: Otonom Ajan Mimarisi Araştırma] -> 2026 Yeni Nesil Otonom Ajan Mimarileri araştırması (Faz 56) başarıyla icra edildi. "Agent = Model + Harness" aksiyomu, Task/Agent ayrımı ve Zero-Loss Failover, Agent Desks üç boyutlu mimarisi (HITL Steering, Context Desk ve Git Worktree yalıtımı), Stateless MCP v2026-07-28, Linux Foundation A2A ve Artifact Passing, Anchored Iterative Compaction, Tiered Caching, Code-as-Action, Supabase HNSW pgvector + BM25 RRF ve Obsidian 2-Hop GraphRAG Bilişsel Bellek Triadı, Letta "Sleep-Time Compute" rüya konsolidasyonu ve açık kaynak ekosistemi (Google Antigravity, MCP, Claude Code, OpenHands, SWE-agent, Mem0) derinlemesine araştırılarak "Entropy/Reports/2026_Yeni_Nesil_Otonom_Ajan_Mimarileri_Harness_AgentDesks_Token_Optimizasyonu_ve_Bilissel_Hafiza_Master_Ansiklopedisi.md" raporu ve "Entropy/Reports/Gorev_Otonom Ajan Mimarisi Araştırma_20260905_0645.md" görev kaydı oluşturuldu. MEMORY.md (Faz 56) ve BELLEK_HARITASI.md senkronize edildi.\n'

    with open(daily_file, "a", encoding="utf-8") as f:
        f.write(daily_entry)
    print("Updated DailyNotes successfully.")

    # 5. Update BELLEK_HARITASI.md
    map_file = ovm.entropy_dir / "BELLEK_HARITASI.md"
    if map_file.exists():
        map_text = map_file.read_text(encoding="utf-8")
        new_rows = """| [[2026_Yeni_Nesil_Otonom_Ajan_Mimarileri_Harness_AgentDesks_Token_Optimizasyonu_ve_Bilissel_Hafiza_Master_Ansiklopedisi|2026 Yeni Nesil Otonom Ajan Mimarileri Harness AgentDesks Token Optimizasyonu ve Bilissel Hafiza Master Ansiklopedisi]] | `2026_Yeni_Nesil_Otonom_Ajan_Mimarileri_Harness_AgentDesks_Token_Optimizasyonu_ve_Bilissel_Hafiza_Master_Ansiklopedisi.md` | **3** | 2026-09-05 06:45 |
| [[Gorev_Otonom Ajan Mimarisi Araştırma_20260905_0645|Gorev Otonom Ajan Mimarisi Araştırma 20260905 0645]] | `Gorev_Otonom Ajan Mimarisi Araştırma_20260905_0645.md` | **2** | 2026-09-05 06:45 |
"""
        table_header_marker = "| :--- | :--- | :---: | :--- |\n"
        if table_header_marker in map_text:
            updated_map = map_text.replace(table_header_marker, table_header_marker + new_rows)
            map_file.write_text(updated_map, encoding="utf-8")
            print("Updated BELLEK_HARITASI.md successfully.")
        else:
            print("Table header marker not found in BELLEK_HARITASI.md")

if __name__ == "__main__":
    run_sync()
