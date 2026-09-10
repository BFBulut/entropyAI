"""Append Faz 135 to MEMORY.md and BELLEK_HARITASI.md in Obsidian Vault."""

from pathlib import Path
import datetime

vault_path = Path(r"C:\Users\batu_\OneDrive\Belgeler\Obsidian Vault\Entropy")
memory_file = vault_path / "MEMORY.md"
map_file = vault_path / "BELLEK_HARITASI.md"

faz135_memory_entry = """

## Faz 135 Otonom Ajan Mimarileri: FastMCP 10.5++, AAIF A2A v1.5, Exokernel Harness 2.5, Agent Desks 17.0, Dotriaconta-Store 32-Katmanlı Bilişsel Bellek ve Aşırı Token Fiziği 26.0 (2026-09-06)
- **FastMCP 10.5++ & AAIF A2A v1.5 Çift Standart İletişim**: Dikeyde Mcp-Method/Name başlıklı, MRTR 206 input_required ara parametreli, shm:// ve blob:// sıfır-kopya paylaşımlı bellekli ve İki-Aşamalı Saga telafili FastMCP motoru; yatayda ise Ed25519/HMAC imzalı AgentCard, 4D Pareto rotalama ve 3-Aşamalı PBFT konsensüslü AAIF A2A federasyonu.
- **Exokernel Agent Harness 2.5 & "The Harness Effect"**: Ham modellerin SWE-bench'teki %15-25 başarısını deterministik AST Preflight Guard 20.0, Merkle Checkpoint Forest atomik geri alma, dinamik sıcaklık sönümlenmesi (T -> 0.0) ve Phi-Accrual devre kesici ile %85-88+ seviyesine fırlatan işletim sistemi koşumu.
- **Agent Desks 17.0 & Linda Dağıtık Demet Alanı 12.0**: Rol tabanlı izole sanal çalışma masaları (Architecture, Engineering, QA, Research, Security, Product), Git Worktree CoW kum havuzu, MG-SWB 6.0 dosya kiralama ve Vektör Saatleri ile 5-Way AST Semantic Conflict-Free Reconciler.
- **Kahn DAG Wavefronts & CPM Gecikme Payı Ödünç Alma (Slack Borrowing)**: İleri/geri geçiş ve Stokastik PERT Te = (O + 4M + P)/6 ile kritik yol tespiti; kritik yola Claude 3.7 Thinking / Gemini 3 Pro, slack > 0 görevlere ise Gemini 3.8 Flash atanarak maliyet ve süre optimizasyonu.
- **Dotriaconta-Store 32-Katmanlı Bilişsel Bellek & Gelişmiş GraphRAG**: Graphiti 2.5 bi-temporal kenar geçerliliği (valid_from / valid_until), HippoRAG 2 Dual-Node PPR çok sekmeli ilişkisel çıkarım, Jina AI Late Chunking + Anthropic Contextual Retrieval hibriti, Ebbinghaus unutma eğrisi ve Dreaming uyku konsolidasyonu, Supabase pgvector 0.8+ StreamingDiskANN ve Hybrid Reciprocal Rank Fusion (RRF).
- **Aşırı Token Fiziği 26.0 & CodeAct 19.0**: Çok turlu JSON tool call yerine tekil çalıştırılabilir Python REPL (%75-85 token tasarrufu), AST Skeletonization 20.0 (%85-92 bağlam tasarrufu), Radix KV-Cache blok hizalaması (>%94 önbellek isabeti), Marjinal Delta token muhasebesi ve Seviye 1/2/3 Skill Progressive Disclosure v4.5.
- **Detaylı Rapor**: [[2026_Kapsamli_Otonom_Ajan_Mimarisi_Harness_AgentDesks_A2A_ve_Bilissel_Bellek_Faz135]]
"""

if memory_file.exists():
    with open(memory_file, "a", encoding="utf-8") as f:
        f.write(faz135_memory_entry)
    print("Successfully updated MEMORY.md with Faz 135.")

# Update BELLEK_HARITASI.md
faz135_map_row = "| [[2026_Kapsamli_Otonom_Ajan_Mimarisi_Harness_AgentDesks_A2A_ve_Bilissel_Bellek_Faz135|2026 Kapsamli Otonom Ajan Mimarisi Faz 135]] | `2026_Kapsamli_Otonom_Ajan_Mimarisi_Harness_AgentDesks_A2A_ve_Bilissel_Bellek_Faz135.md` | **10** | 2026-09-06 11:48 |\n"
faz135_task_row = "| [[Gorev_Otonom_Ajan_Mimarisi_Arastirma_20260906_1145|Gorev Otonom Ajan Mimarisi Arastirma 20260906 1145]] | `Gorev_Otonom_Ajan_Mimarisi_Arastirma_20260906_1145.md` | **5** | 2026-09-06 11:48 |\n"

if map_file.exists():
    content = map_file.read_text(encoding="utf-8")
    if "## 📊 2. Araştırma ve Konu Raporları" in content:
        parts = content.split("## 📊 2. Araştırma ve Konu Raporları")
        table_header = parts[1].split("\n| :--- | :--- | :---: | :---: |\n")
        if len(table_header) > 1:
            new_table = "\n| :--- | :--- | :---: | :---: |\n" + faz135_map_row + faz135_task_row + table_header[1]
            new_content = parts[0] + "## 📊 2. Araştırma ve Konu Raporları" + table_header[0] + new_table
            map_file.write_text(new_content, encoding="utf-8")
            print("Successfully updated BELLEK_HARITASI.md with Faz 135 rows.")
        else:
            with open(map_file, "a", encoding="utf-8") as f:
                f.write(faz135_map_row)
            print("Appended Faz 135 to BELLEK_HARITASI.md.")
    else:
        with open(map_file, "a", encoding="utf-8") as f:
            f.write(faz135_map_row)
        print("Appended Faz 135 to BELLEK_HARITASI.md.")
