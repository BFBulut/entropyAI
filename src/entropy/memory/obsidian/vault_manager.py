"""Obsidian Vault integration for Entropy AI exocortex & memory graph."""

import datetime
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from entropy.core.config import config

class ObsidianVaultManager:
    """Manages the local Obsidian markdown vault as Entropy AI's persistent memory."""

    # T1.1: Regex matching [[Target|Alias]] or [[Target#Header|Alias]] or [[Target]]
    WIKILINK_PATTERN = re.compile(r"\[\[(?P<target>[^\|\]#]+)(?:#[^\|\]]+)?(?:\|(?P<alias>[^\]]+))?\]\]")

    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = Path(vault_path or config.obsidian_vault_path)
        self.entropy_dir = self.vault_path / "Entropy"
        self.daily_notes_dir = self.entropy_dir / "DailyNotes"
        self.reports_dir = self.entropy_dir / "Reports"
        self.projects_dir = self.entropy_dir / "Projects"
        self.memory_file = self.entropy_dir / "MEMORY.md"

        self._ensure_directories()

    def _ensure_directories(self):
        """Create necessary vault directories if they don't exist."""
        for d in [self.entropy_dir, self.daily_notes_dir, self.reports_dir, self.projects_dir]:
            d.mkdir(parents=True, exist_ok=True)

        if not self.memory_file.exists():
            self.memory_file.write_text(
                "# Entropy AI - Global Memory & Architecture Decisions\n\n"
                "## System Beliefs & Core Directives\n"
                "- System Name: Entropy AI\n"
                "- Core Framework: Antigravity CLI (agy)\n"
                "- Privacy Policy: Local data-on-disk priority\n\n"
                "## Learned User Preferences\n"
                "- Zero external LLM API keys requested\n"
                "- Multi-modal interaction with Ctrl+C / Ctrl+V\n",
                encoding="utf-8"
            )

    def read_global_memory(self) -> str:
        """Read the root MEMORY.md file."""
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def append_to_global_memory(self, category: str, note: str):
        """Append an insight or decision to MEMORY.md."""
        current = self.read_global_memory()
        header = f"\n### {category} ({datetime.date.today().isoformat()})\n- {note}\n"
        self.memory_file.write_text(current + header, encoding="utf-8")

    def append_daily_log(self, entry: str) -> Path:
        """Write an episodic log entry to today's daily note in the Obsidian vault."""
        today = datetime.date.today().strftime("%Y-%m-%d")
        daily_file = self.daily_notes_dir / f"{today}.md"
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        header = f"# Entropy AI Session Log - {today}\n\n" if not daily_file.exists() else ""
        formatted = f"{header}[{timestamp}] {entry}\n"

        with open(daily_file, "a", encoding="utf-8") as f:
            f.write(formatted)
        return daily_file

    def save_research_report(self, title: str, content: str, tags: Optional[List[str]] = None) -> Path:
        """Save a research dossier in the Reports directory with wikilinks and frontmatter."""
        safe_title = "".join([c if c.isalnum() or c in " -_" else "_" for c in title]).strip()
        report_file = self.reports_dir / f"{safe_title}.md"
        
        tag_str = ", ".join(tags or ["entropy-ai", "research-report"])
        frontmatter = (
            f"---\n"
            f"title: \"{title}\"\n"
            f"date: {datetime.date.today().isoformat()}\n"
            f"tags: [{tag_str}]\n"
            f"agent: Entropy AI\n"
            f"---\n\n"
        )
        report_file.write_text(frontmatter + content, encoding="utf-8")
        return report_file

    def list_reports(self) -> List[Dict[str, str]]:
        """List all research reports available in the vault."""
        reports = []
        for file in sorted(self.reports_dir.glob("*.md"), reverse=True):
            reports.append({
                "title": file.stem.replace("_", " "),
                "path": str(file),
                "modified": datetime.datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            })
        return reports

    def extract_wikilinks(self, content: str) -> List[Dict[str, str]]:
        """
        T1.1: Extract structured wikilinks containing target and optional alias.
        Supports [[Target]], [[Target|Alias]], [[Target#Header]], [[Target#Header|Alias]].
        """
        links = []
        for match in self.WIKILINK_PATTERN.finditer(content):
            target = match.group("target").strip()
            if target.lower().endswith(".md"):
                target = target[:-3]
            alias = match.group("alias").strip() if match.group("alias") else target
            links.append({"target": target, "alias": alias})
        return links

    def get_backlinks_index(self) -> Dict[str, Any]:
        """
        T1.2: Build a complete bidirectional backlink index for all markdown files in the vault.
        Returns:
            {
                "outbound": { "NoteA": ["NoteB", "NoteC"] },
                "inbound":  { "NoteB": ["NoteA"], "NoteC": ["NoteA"] },
                "aliases":  { "NoteB": ["Görünen Ad"] }
            }
        """
        outbound: Dict[str, List[str]] = {}
        inbound: Dict[str, List[str]] = {}
        aliases_map: Dict[str, Set[str]] = {}

        for file in self.entropy_dir.rglob("*.md"):
            source_stem = file.stem
            outbound.setdefault(source_stem, [])
            inbound.setdefault(source_stem, [])

            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                extracted = self.extract_wikilinks(content)
                for item in extracted:
                    target = item["target"]
                    alias = item["alias"]
                    if target not in outbound[source_stem]:
                        outbound[source_stem].append(target)

                    inbound.setdefault(target, [])
                    if source_stem not in inbound[target]:
                        inbound[target].append(source_stem)

                    if alias and alias != target:
                        aliases_map.setdefault(target, set()).add(alias)
            except Exception:
                continue

        return {
            "outbound": outbound,
            "inbound": inbound,
            "aliases": {k: sorted(list(v)) for k, v in aliases_map.items()}
        }

    def sync_map_of_content(self) -> Path:
        """
        T1.3: Generate or refresh the master Map of Content (BELLEK_HARITASI.md) in the vault root.
        Catalogues directives, reports, inbound link counts, and detects orphaned notes.
        """
        moc_file = self.entropy_dir / "BELLEK_HARITASI.md"
        backlinks = self.get_backlinks_index()
        inbound = backlinks["inbound"]

        today_str = datetime.date.today().isoformat()
        lines = [
            "# 🗺️ Entropy AI - Master Bellek Haritası (Map of Content)\n",
            f"*Son Güncelleme: {today_str} | Otomatik MOC Senkronizasyonu*\n",
            "Bu doküman, Entropy AI'ın Obsidian exocortex'indeki tüm bilgi düğümlerinin ve bağlantı ağının canlı indeksidir.\n",
            "## 🧭 1. Çekirdek Sistem & Ego Direktifleri",
            "- [[MEMORY|Global Bellek & Mimari Kararlar]] (Kalıcı direktifler ve öğrenilmiş tercihler)",
            "",
            "## 📚 2. Araştırma Raporları & Teknik Dosyalar",
        ]

        reports = self.list_reports()
        if reports:
            lines.append("| Rapor Başlığı | Dosya | Gelen Bağlantı (Inbound) | Son Değişiklik |")
            lines.append("| :--- | :--- | :---: | :--- |")
            for rep in reports:
                stem = Path(rep["path"]).stem
                in_count = len(inbound.get(stem, []))
                lines.append(f"| [[{stem}|{rep['title']}]] | `{stem}.md` | **{in_count}** | {rep['modified']} |")
        else:
            lines.append("*Henüz kayıtlı araştırma raporu bulunmuyor.*")

        lines.append("\n## 📅 3. Günlük Oturum Notları (Daily Notes)")
        daily_files = sorted(self.daily_notes_dir.glob("*.md"), reverse=True)
        if daily_files:
            for df in daily_files[:7]:
                d_stem = df.stem
                in_count = len(inbound.get(d_stem, []))
                lines.append(f"- [[{d_stem}]] (Gelen Bağlantılar: {in_count})")
        else:
            lines.append("*Henüz günlük oturum notu kaydedilmedi.*")

        # Orphaned notes check
        orphans = [
            f.stem for f in self.entropy_dir.rglob("*.md")
            if f.stem != "MEMORY" and f.stem != "BELLEK_HARITASI" and len(inbound.get(f.stem, [])) == 0
        ]
        if orphans:
            lines.append("\n## ⚠️ 4. Yalıtılmış Düğümler (Orphaned Notes - 0 Gelen Bağlantı)")
            for o in sorted(orphans):
                lines.append(f"- [[{o}]]")

        moc_content = "\n".join(lines) + "\n"
        moc_file.write_text(moc_content, encoding="utf-8")
        return moc_file

    def build_knowledge_graph(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Parse all markdown files in the Entropy folder and extract nodes & links.
        Uses normalized wikilink targets and alias mappings.
        """
        nodes = []
        links = []
        node_ids: Set[str] = set()
        stem_to_id: Dict[str, str] = {}

        for file in self.entropy_dir.rglob("*.md"):
            name = file.stem
            category = file.parent.name
            node_id = f"{category}/{name}"
            stem_to_id[name] = node_id

            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "name": name,
                    "group": category,
                    "path": str(file)
                })

        for file in self.entropy_dir.rglob("*.md"):
            source_id = stem_to_id.get(file.stem, f"{file.parent.name}/{file.stem}")
            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                extracted = self.extract_wikilinks(content)
                for item in extracted:
                    target_stem = item["target"]
                    # If target matches an existing note stem, link to its full node_id
                    target_id = stem_to_id.get(target_stem, target_stem)
                    links.append({
                        "source": source_id,
                        "target": target_id,
                        "alias": item["alias"]
                    })
            except Exception:
                continue

        return {"nodes": nodes, "links": links}
