"""Obsidian Vault integration for Entropy AI exocortex & memory graph."""

import datetime
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from entropy.core.config import STATE_DIR, config

# Kasa grafigi onbellegi.
# build_knowledge_graph() kasadaki her .md dosyasini iki kez tarayip hepsini
# okuyordu (865 dosya, ~211 ms). Kasa OneDrive'da oldugu icin okuma pahali.
# Gecersiz kilma imzasi dosya listesi + boyut + mtime'dan uretilir: bir dosya
# degistiginde imza degisir, degismediginde tek bir dizin taramasi yeter.
# ENTROPY_GRAPH_CACHE=0 ile disk onbellegi kapatilir (bellek ici onbellek kalir).
_GRAPH_CACHE_FILE = STATE_DIR / "cache" / "graph_data.json"
_GRAPH_CACHE_MAX_VAULTS = 3
_GRAPH_MEMORY_CACHE: Dict[str, Tuple[str, Dict[str, List[Dict[str, str]]]]] = {}


def _graph_disk_cache_enabled() -> bool:
    raw = (os.environ.get("ENTROPY_GRAPH_CACHE") or "").strip().lower()
    return raw not in ("0", "false", "no", "off")


def clear_graph_cache() -> None:
    """Bellek ici kasa grafigi onbellegini bosaltir (testler icin)."""
    _GRAPH_MEMORY_CACHE.clear()

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

    def save_research_report(
        self,
        title: str,
        content: str,
        tags: Optional[Any] = None,
        project_name: Optional[str] = None,
        skill_name: Optional[str] = None
    ) -> Path:
        """
        Save a research dossier in the Reports directory with wikilinks, sanitized body and frontmatter.
        Destination folders (skill wins over project):
        - If skill_name provided: Entropy/Skills/<skill_name>/Reports/<safe_title>.md
        - Else if project_name provided: Entropy/Projects/<project_name>/Reports/<safe_title>.md
        - Otherwise fallback: Entropy/Reports/<safe_title>.md

        Yetenek, projeden önce gelir: yordam damıtma kaynaklarını
        Skills/<yetenek>/Reports/ altından okur ve proje öncelikli olduğu sürece
        yetenek atıflı her rapor Projects/<proje>/Reports/ altına düşüyordu
        (ölçüm 2026-09-09: 77 etiketli rapor orada, yetenek klasörlerinde 11).
        Proje bağlamı `project:<ad>` etiketiyle korunur, kaybolmaz.
        """
        # Handle positional args: (title, content, project_name, skill_name)
        actual_tags = tags
        if isinstance(tags, str):
            if project_name is not None and skill_name is None:
                # Called as save_research_report(title, content, proj_name, skill_name)
                skill_name = project_name
                project_name = tags
                actual_tags = None
            elif project_name is None:
                # Called as save_research_report(title, content, proj_name)
                project_name = tags
                actual_tags = None
        elif tags is not None and not isinstance(tags, (list, tuple, set)):
            actual_tags = [str(tags)]

        safe_title = "".join([c if c.isalnum() or c in " -_" else "_" for c in title]).strip()
        if not safe_title:
            safe_title = "Arastirma_Raporu"

        clean_proj = "".join([c if c.isalnum() or c in " -_" else "_" for c in project_name]).strip() if project_name else None
        clean_skill = "".join([c if c.isalnum() or c in " -_" else "_" for c in skill_name]).strip() if skill_name else None

        if clean_skill:
            target_dir = self.entropy_dir / "Skills" / clean_skill / "Reports"
        elif clean_proj:
            target_dir = self.entropy_dir / "Projects" / clean_proj / "Reports"
        else:
            target_dir = self.reports_dir

        target_dir.mkdir(parents=True, exist_ok=True)
        report_file = target_dir / f"{safe_title}.md"
        
        # Sanitize ANSI escape codes, terminal control artifacts, carriage returns and BOM
        import re
        cleaned_content = content.lstrip("\ufeff")
        cleaned_content = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\([a-zA-Z]|\x1b\][^\x07\x1b]*\x07|\x1b.', '', cleaned_content)
        cleaned_content = cleaned_content.replace('\r\n', '\n').replace('\r', '\n')
        cleaned_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', cleaned_content).strip()

        tag_list = list(actual_tags or ["entropy-ai", "research-report"])
        if clean_proj and f"project:{clean_proj}" not in tag_list:
            tag_list.append(f"project:{clean_proj}")
        if clean_skill and f"skill:{clean_skill}" not in tag_list:
            tag_list.append(f"skill:{clean_skill}")

        tag_str = ", ".join(tag_list)
        frontmatter = (
            f"---\n"
            f"title: \"{title}\"\n"
            f"date: {datetime.date.today().isoformat()}\n"
            f"tags: [{tag_str}]\n"
            f"agent: Entropy AI\n"
            f"---\n\n"
        )
        report_file.write_text(frontmatter + cleaned_content, encoding="utf-8")
        self._register_report(report_file, clean_skill)
        return report_file

    def _register_report(self, report_file: Path, skill_name: Optional[str]) -> Optional[str]:
        """
        Yeni raporu yetenek-rapor indeksine ANINDA ekler ve arayüze haber verir.

        İndeks yalnızca `/distill index` ile yenileniyordu; aradaki her rapor,
        kullanıcı komutu elle çalıştırana kadar hiçbir yeteneğin kaynağı
        sayılmıyordu ("yeni raporlar damıtılacak öğelere düşmüyor"). Burada tek
        dosya eklenir — tam yeniden tarama yapılmaz.

        Yetenek biliniyorsa doğrudan kullanılır; bilinmiyorsa yalnızca BU dosya
        için anlamsal sınıflandırma çalıştırılır. Hata hiçbir koşulda rapor
        yazımını düşürmez: indeks türetilmiş veridir, yeniden üretilebilir.
        """
        try:
            from entropy.memory.playbook import PlaybookStore, classify_report

            store = PlaybookStore(vault_path=self.vault_path)
            skill = skill_name
            if not skill:
                known: Set[str] = set()
                classify = None
                try:
                    from entropy.skills.manager import SkillManager

                    sm = SkillManager()
                    known = {s.name for s in sm.list_skills() if s.enabled}

                    def classify(title: str, head_text: str):
                        hit = sm.auto_detect_skill_for_prompt(f"{title} {head_text[:1500]}")
                        return hit.name if hit else None
                except Exception:
                    classify = None
                skill = classify_report(report_file, known, classify)
            if not skill:
                return None
            # Yetenek klasöründeki rapor zaten doğrudan okunuyor; indekste ikinci
            # kez durması gereksiz. Yine de sinyal yayınlanır: sayaç artmalı.
            in_skill_dir = "Skills" in report_file.parts and "Reports" in report_file.parts
            if not in_skill_dir:
                store.index.add(skill, report_file)
            try:
                from entropy.core.event_bus import bus

                bus.reports_updated.emit(skill)
            except Exception:
                pass
            return skill
        except Exception:
            return None

    def get_research_reports(self) -> List[Dict[str, str]]:
        """Recursively collect all research reports across all subfolders (global, project-scoped, skill-scoped)."""
        reports = []
        seen_paths = set()

        candidate_files: List[Path] = []
        if self.entropy_dir.exists():
            for p in self.entropy_dir.rglob("*.md"):
                # Matches files in Reports/, Projects/*/Reports/, Skills/*/Reports/
                if "Reports" in p.parts:
                    candidate_files.append(p)

        # Sort by mtime descending
        candidate_files.sort(key=lambda f: f.stat().st_mtime if f.exists() else 0, reverse=True)

        for file in candidate_files:
            if file in seen_paths or not file.is_file():
                continue
            seen_paths.add(file)
            reports.append({
                "title": file.stem.replace("_", " "),
                "path": str(file),
                "modified": datetime.datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            })
        return reports

    def list_reports(self) -> List[Dict[str, str]]:
        """List all research reports available in the vault across all subfolders."""
        return self.get_research_reports()

    def list_all_notes(self) -> List[Path]:
        """List all markdown notes across all subdirectories of the Obsidian exocortex."""
        if not self.entropy_dir.exists():
            return []
        return list(self.entropy_dir.rglob("*.md"))

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

    def _vault_signature(self) -> Tuple[str, List[Path]]:
        """
        Kasanin parmak izi ve dosya listesi.

        Tek bir rglob taramasiyla uretilir; hem imza hem de sonraki adimlarin
        dosya listesi buradan gelir (eskiden iki ayri tarama yapiliyordu).
        """
        files = list(self.entropy_dir.rglob("*.md"))
        h = hashlib.sha1()
        for file in files:
            h.update(str(file).encode("utf-8", errors="ignore"))
            try:
                st = file.stat()
                h.update(f"|{st.st_size}|{st.st_mtime_ns}|".encode("ascii"))
            except OSError:
                h.update(b"|?|")
        return h.hexdigest(), files

    def _load_graph_disk_cache(self, signature: str) -> Optional[Dict[str, List[Dict[str, str]]]]:
        if not _graph_disk_cache_enabled():
            return None
        try:
            payload = json.loads(_GRAPH_CACHE_FILE.read_text(encoding="utf-8"))
            entry = payload.get(str(self.vault_path))
        except (OSError, ValueError):
            return None
        if not isinstance(entry, dict) or entry.get("signature") != signature:
            return None
        nodes, links = entry.get("nodes"), entry.get("links")
        if not isinstance(nodes, list) or not isinstance(links, list):
            return None
        return {"nodes": nodes, "links": links}

    def _save_graph_disk_cache(self, signature: str, data: Dict[str, List[Dict[str, str]]]) -> None:
        if not _graph_disk_cache_enabled():
            return
        try:
            payload: Dict[str, Any] = {}
            if _GRAPH_CACHE_FILE.is_file():
                try:
                    loaded = json.loads(_GRAPH_CACHE_FILE.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        payload = loaded
                except ValueError:
                    payload = {}
            payload[str(self.vault_path)] = {
                "signature": signature,
                "nodes": data["nodes"],
                "links": data["links"],
            }
            # Dosya sinirsiz buyumesin: en son kullanilan birkac kasa tutulur.
            if len(payload) > _GRAPH_CACHE_MAX_VAULTS:
                keep = list(payload)[-_GRAPH_CACHE_MAX_VAULTS:]
                payload = {k: payload[k] for k in keep}
            _GRAPH_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = _GRAPH_CACHE_FILE.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp.replace(_GRAPH_CACHE_FILE)
        except OSError:
            pass

    def build_knowledge_graph(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Parse all markdown files in the Entropy folder and extract nodes & links.
        Uses normalized wikilink targets and alias mappings.

        Sonuc, kasa imzasi (dosya listesi + boyut + mtime) degismedigi surece
        bellekten, surec yeniden basladiginda da diskten okunur; cikti her iki
        yolda da taramanin urettigiyle ayni olur.
        """
        signature, files = self._vault_signature()
        vault_key = str(self.vault_path)

        cached = _GRAPH_MEMORY_CACHE.get(vault_key)
        if cached is not None and cached[0] == signature:
            return {"nodes": list(cached[1]["nodes"]), "links": list(cached[1]["links"])}

        from_disk = self._load_graph_disk_cache(signature)
        if from_disk is not None:
            _GRAPH_MEMORY_CACHE[vault_key] = (signature, from_disk)
            return {"nodes": list(from_disk["nodes"]), "links": list(from_disk["links"])}

        nodes = []
        links = []
        node_ids: Set[str] = set()
        stem_to_id: Dict[str, str] = {}

        for file in files:
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

        for file in files:
            source_id = stem_to_id.get(file.stem, f"{file.parent.name}/{file.stem}")
            is_heavy_catalog = (file.stem in ["BELLEK_HARITASI", "MEMORY"])
            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                extracted = self.extract_wikilinks(content)
                is_catalog = is_heavy_catalog or (len(extracted) > 25)
                for item in extracted:
                    target_stem = item["target"]
                    # If target matches an existing note stem, link to its full node_id
                    target_id = stem_to_id.get(target_stem, target_stem)
                    links.append({
                        "source": source_id,
                        "target": target_id,
                        "alias": item["alias"],
                        "is_catalog_link": is_catalog
                    })
            except Exception:
                continue

        data = {"nodes": nodes, "links": links}
        _GRAPH_MEMORY_CACHE[vault_key] = (signature, data)
        self._save_graph_disk_cache(signature, data)
        return {"nodes": list(nodes), "links": list(links)}
