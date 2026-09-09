"""Obsidian Vault integration for Entropy AI exocortex & memory graph."""

import datetime
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

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

# Grafik verisi surumu. Dugum alanlari degistiginde artirilir; imzanin onune
# eklendigi icin eski onbellek girdileri (eksik alanli) otomatik gecersiz olur.
# v2 (Faz 5.1/5.2): dugumlere type, importance, t_valid_from, t_valid_to.
# v4 (Faz 8): kod blogu ayiklama, test kalintisi ve arsiv dizinlerinin haric
# tutulmasi, rapor dugumlerine on bilgi etiketleri (`tags`, `skill`).
_GRAPH_SCHEMA_VERSION = "v4"

# Kasa kategorisi -> birlesik graf dugum turu (graph_store.NODE_TYPES).
_VAULT_GROUP_TO_TYPE: Dict[str, str] = {
    "Reports": "report",
    "reports": "report",
    "query": "report",
    "office": "office",
    "agent": "agent",
    "skill": "procedure",
    "concept": "entity",
    "entity": "entity",
    "Daily": "episode",
    "community": "community",
}


# --- rapor akışı: türe göre toplama ------------------------------------------
#
# Faz 7/A2: rapor toplama YOLA değil TÜRE bağlıdır. Eskiden `list_reports`
# yalnızca `"Reports" in p.parts` filtresini uyguluyordu; bu yüzden
# `wiki.write_query_page` ile yazılan sorgu sayfaları (`.../wiki/queries/`) ve
# ofis raporları (`Desk/Offices/<ofis>/reports/`, KÜÇÜK harf) Rapor Merkezi'ne
# hiç girmiyordu. Artık tür şu sırayla belirlenir:
#   1) YAML ön bilgisindeki `type:` alanı (query | office_report | session | report)
#   2) dizin kuralı (Reports/, reports/, wiki/queries/, Desk/Offices/*/reports/)
REPORT_KINDS: Tuple[str, ...] = ("report", "query", "office_report", "session")

# Ön bilgideki `type:` değeri -> rapor türü. Bilinmeyen değer normal rapordur.
_FM_TYPE_TO_KIND: Dict[str, str] = {
    "query": "query",
    "sorgu": "query",
    "office_report": "office_report",
    "ofis_raporu": "office_report",
    "session": "session",
    "daily": "session",
    "gunluk": "session",
    "report": "report",
    "rapor": "report",
}

# Tür -> taban önem. `graph_store` aynı dosya için bir düğüm tutuyorsa onun
# `importance` değeri bu tabanı ezer (bkz. `_importance_by_provenance`).
KIND_IMPORTANCE: Dict[str, float] = {
    "office_report": 0.80,
    "query": 0.60,
    "report": 0.45,
    "session": 0.40,
}

# Rapor taramasının hiç girmediği alt ağaçlar: arşiv, eski AgentDesk artıkları
# ve ofis grafının kendi not deposu (bunlar rapor değildir).
_REPORT_SCAN_SKIP_DIRS = frozenset({"_archive", "AgentDesk", ".obsidian", ".trash"})
# Graf taramasında küçük harfe indirgenmiş karşılaştırma yapılır.
_GRAPH_SCAN_SKIP_DIRS = frozenset(d.lower() for d in _REPORT_SCAN_SKIP_DIRS)


def _report_kind_from_path(file: Path) -> str:
    """Dizin kuralından rapor türü; kural tutmazsa boş dizge."""
    parts = [p for p in file.parts]
    lower = [p.lower() for p in parts]
    parent = lower[-2] if len(lower) >= 2 else ""
    grand = lower[-3] if len(lower) >= 3 else ""
    if parent == "queries" and grand in ("wiki",):
        return "query"
    if parent == "reports" and "offices" in lower:
        return "office_report"
    if parent == "reports":
        return "report"
    if "reports" in lower:
        return "report"
    # DailyNotes dizin kuralıyla rapor sayılmaz: günlük oturum notları rapor
    # akışını boğardı. Bir oturum notunun akışa girmesi isteniyorsa ön bilgide
    # `type: session` yazması yeterlidir (aşağıdaki tür eşlemesi yakalar).
    return ""


def _read_frontmatter(file: Path, limit: int = 4096) -> Dict[str, str]:
    """Dosyanın ilk `limit` baytındaki YAML ön bilgisi (yoksa boş sözlük)."""
    try:
        with open(file, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(limit)
    except OSError:
        return {}
    head = head.lstrip("﻿")
    if not head.startswith("---"):
        return {}
    body = head[3:]
    end = body.find("\n---")
    if end == -1:
        return {}
    out: Dict[str, str] = {}
    for line in body[:end].splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, _, value = line.partition(":")
        out[key.strip().lower()] = value.strip().strip('"').strip("'")
    return out


def _graph_node_type(group: str) -> str:
    """Kasa grubundan graf dugum turu; bilinmeyen grup anlamsal olgudur."""
    return _VAULT_GROUP_TO_TYPE.get(group, "fact")


def _graph_node_fields(group: str, file: Optional[Path]) -> Dict[str, Any]:
    """
    UI'nin zaman kaydiricisi ve filtreleri icin ortak alanlar.

    `t_valid_from`: dosyanin olusturulma/degistirilme zamani (epoch). Kasa
    OneDrive'da oldugu icin mtime'a icerik dogrulugu icin degil, YALNIZCA
    zaman ekseni icin guvenilir kabul edilir. `t_valid_to` None = hala gecerli.
    `importance`: kaynak turunden taban puan (graph_store.SOURCE_IMPORTANCE ile
    ayni tablodan gelir).
    """
    node_type = _graph_node_type(group)
    t_from = 0.0
    if file is not None:
        try:
            t_from = float(file.stat().st_mtime)
        except OSError:
            t_from = 0.0
    base = {
        "report": 0.6, "session": 0.4, "fact": 0.5, "episode": 0.4,
        "procedure": 0.55, "entity": 0.35, "task": 0.5, "agent": 0.5,
        "office": 0.5, "community": 0.5,
    }.get(node_type, 0.5)
    return {
        "type": node_type,
        "importance": base,
        "t_valid_from": t_from,
        "t_valid_to": None,
    }


def _query_page_skill(file: Path) -> Optional[str]:
    """
    Dosya bir wiki sorgu sayfasiysa ait oldugu yetenegi dondurur.

    Yetenek disi (kasa geneli) sorgular icin bos dize, sorgu sayfasi degilse
    None doner. Yol kurali: Skills/<yetenek>/wiki/queries/*.md ya da
    Wiki/queries/*.md (bkz. entropy.memory.wiki).
    """
    parents = file.parents
    if len(parents) < 2 or parents[0].name.lower() != "queries":
        return None
    if parents[1].name.lower() != "wiki":
        return None
    if len(parents) >= 3 and parents[2].name.lower() not in ("entropy", "skills"):
        return parents[2].name
    return ""


def _wiki_generated_role(file: Path) -> Optional[Tuple[str, str]]:
    """
    Dosya uretilmis bir wiki sayfasiysa (grup, yetenek) dondurur.

    Grup "concept" ya da "entity"; yetenek disi (kasa geneli) sayfalarda yetenek
    bos dizedir. Yol kurali: Skills/<yetenek>/wiki/concepts|entities/*.md ya da
    Wiki/concepts|entities/*.md (bkz. entropy.memory.wiki).
    """
    parents = file.parents
    if len(parents) < 2:
        return None
    kind = parents[0].name.lower()
    if kind not in ("concepts", "entities"):
        return None
    if parents[1].name.lower() != "wiki":
        return None
    group = "concept" if kind == "concepts" else "entity"
    if len(parents) >= 3 and parents[2].name.lower() not in ("entropy", "skills"):
        return group, parents[2].name
    return group, ""


def _office_page_role(file: Path) -> Optional[Tuple[str, str]]:
    """
    Dosya `Entropy/Offices/<ofis>/...` altindaysa (ofis, rol) dondurur.

    Rol: "office" (OFFICE.md kayit defteri), "report" (reports/*.md ofis raporu
    ozeti), "other" (MEMORY.md, log.md gibi ic dosyalar). Ofis disi dosyalarda
    None doner.
    """
    parts = [p.name for p in file.parents]
    lower = [p.lower() for p in parts]
    if "offices" not in lower:
        return None
    idx = lower.index("offices")
    if idx == 0:
        return None
    office = parts[idx - 1]
    if file.name.upper() == "OFFICE.MD" and idx == 1:
        return office, "office"
    if idx >= 1 and lower[0] == "reports":
        return office, "report"
    return office, "other"


def _agent_page_name(file: Path) -> Optional[str]:
    """`Entropy/Agents/<ajan>/AGENT.md` ise ajan adini dondurur."""
    if file.name.upper() != "AGENT.MD":
        return None
    parents = file.parents
    if len(parents) < 2 or parents[1].name.lower() != "agents":
        return None
    return parents[0].name


def _frontmatter_list(text: str, key: str) -> List[str]:
    """
    On bilgideki `key`'i tek deger ya da liste olarak okur.

    Satir ici liste (`members: [a, b]`), YAML madde listesi ve tek deger
    (`orchestrator: a`) desteklenir; OFFICE.md'yi kullanici elle yazabildigi
    icin tek bir bicime bagli kalinmaz.
    """
    m = re.search(rf"(?m)^{re.escape(key)}\s*:\s*(.*)$", text or "")
    if not m:
        return []
    inline = m.group(1).strip()
    if inline.startswith("[") and inline.endswith("]"):
        return [v.strip().strip('"').strip("'") for v in inline[1:-1].split(",") if v.strip()]
    if inline:
        return [inline.strip('"').strip("'")]
    out: List[str] = []
    for line in (text or "")[m.end():].splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            out.append(stripped[2:].strip().strip('"').strip("'"))
            continue
        if stripped:
            break
    return [v for v in out if v]


# Faz 8/M1: kod bloklari ve satir ici kod. Raporlarin govdesinde `[[wikilink]]`
# ORNEKLERI geciyor (sozdizimi anlatan bolumler); bunlar gercek bag sanilip
# 376 sarkan kenar uretiyordu (olcum 2026-09-09). Ayikamadan once kod
# bolgeleri metinden dusurulur.
_CODE_FENCE_RE = re.compile(r"(?ms)^[ \t]*(```|~~~).*?(?:^[ \t]*\1[ \t]*$|\Z)")
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_INDENTED_CODE_RE = re.compile(r"(?m)^(?: {4}|\t).*$")

# Faz 8/M2: pytest kalintisi proje dizinleri (`Projects/test_*`). Kasada gercek
# proje gibi duruyor ve 196 yaprak tasiyordu.
_TEST_ARTIFACT_PREFIXES = ("test_", "tmp_", "pytest-")


def strip_code_spans(text: str) -> str:
    """Cit'li/girintili kod bloklarini ve satir ici kodu bosluga cevirir."""
    if not text:
        return ""
    out = _CODE_FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    out = _INLINE_CODE_RE.sub(" ", out)
    out = _INDENTED_CODE_RE.sub("", out)
    return out


def is_test_artifact_name(name: str) -> bool:
    """Ad bir test kalintisi proje/dizin adi mi (graftan haric tutulur)."""
    low = (name or "").strip().lower()
    return any(low.startswith(p) for p in _TEST_ARTIFACT_PREFIXES)


def is_test_artifact_path(file: Path) -> bool:
    """`Projects/test_*` (ya da tmp_/pytest-) altindaki dosyalar graftan cikar."""
    parts = [p for p in file.parts]
    lower = [p.lower() for p in parts]
    for anchor in ("projects", "skills"):
        idx = 0
        while anchor in lower[idx:]:
            i = lower.index(anchor, idx)
            if i + 1 < len(parts) and is_test_artifact_name(parts[i + 1]):
                return True
            idx = i + 1
    return False


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

    def _importance_by_provenance(self) -> Dict[str, float]:
        """
        Graf deposundaki dosya kaynaklı düğümlerin önem değerleri (yol -> puan).

        Tek SQL ile alınır; graf yoksa/okunamıyorsa boş sözlük döner (rapor
        listesi bir veritabanı hatasında çökmemeli, yalnızca taban puana düşer).
        """
        try:
            import sqlite3

            # Veritabanı yolu doğrudan kurulur: `CognitiveMemorySystem()`
            # kurmak gömme modelini yüklüyor (yüzlerce ms) — rapor listesi için
            # tek bir salt-okunur SQL sorgusu yeter.
            db_path = Path.home() / ".entropy" / "cognitive_memory.db"
            if not db_path.exists():
                return {}
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                rows = conn.execute(
                    "SELECT provenance, importance FROM nodes"
                    " WHERE provenance IS NOT NULL AND provenance LIKE '%.md'"
                ).fetchall()
            return {
                str(prov): float(imp)
                for prov, imp in rows
                if prov and imp is not None
            }
        except Exception:
            return {}

    def iter_report_files(self) -> List[Tuple[Path, str]]:
        """
        Kasadaki rapor benzeri dosyalar ve türleri: `(yol, kind)`.

        Tür önce ön bilgideki `type:` alanından, o yoksa dizin kuralından
        gelir. Ön bilgi yalnızca dizin kuralı tutan ya da `type:` taşıyabilecek
        dosyalar için okunur (OneDrive'da her dosyayı açmak pahalıdır).
        """
        if not self.entropy_dir.exists():
            return []
        out: List[Tuple[Path, str]] = []
        for file in self.entropy_dir.rglob("*.md"):
            if _REPORT_SCAN_SKIP_DIRS.intersection(file.parts):
                continue
            path_kind = _report_kind_from_path(file)
            in_daily = "DailyNotes" in file.parts
            if not path_kind and not in_daily:
                continue
            fm_type = _read_frontmatter(file).get("type", "").strip().lower()
            kind = _FM_TYPE_TO_KIND.get(fm_type, path_kind)
            if not kind:
                # Günlük not yalnızca kendini `type:` ile ilan ederse akışa girer.
                continue
            out.append((file, kind))
        return out

    def get_research_reports(
        self, kinds: Optional[Sequence[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Kasadaki tüm rapor benzeri künyeleri toplar (genel, proje, yetenek,
        ofis raporu ve wiki sorgu sayfaları dahil).

        `kinds` verilmezse hepsi döner (geriye uyumlu). Her künye:
        `title, path, modified, mtime, kind, office, skill, importance`.
        """
        wanted = {str(k).strip().lower() for k in kinds} if kinds else None
        importance_map = self._importance_by_provenance()

        entries: List[Dict[str, Any]] = []
        seen: Set[Path] = set()
        for file, kind in self.iter_report_files():
            if file in seen or not file.is_file():
                continue
            if wanted is not None and kind not in wanted:
                continue
            seen.add(file)
            try:
                mtime = file.stat().st_mtime
            except OSError:
                mtime = 0.0
            parts = file.parts
            office = ""
            skill = ""
            if "Offices" in parts:
                idx = parts.index("Offices")
                if len(parts) > idx + 1:
                    office = parts[idx + 1]
            if "Skills" in parts:
                idx = parts.index("Skills")
                if len(parts) > idx + 1:
                    skill = parts[idx + 1]
            entries.append({
                "title": file.stem.replace("_", " "),
                "path": str(file),
                "modified": datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                "mtime": mtime,
                "kind": kind,
                "office": office,
                "skill": skill,
                "importance": round(
                    importance_map.get(str(file), KIND_IMPORTANCE.get(kind, 0.45)), 3
                ),
            })

        entries.sort(key=lambda e: e["mtime"], reverse=True)
        return entries

    def list_reports(
        self, kinds: Optional[Sequence[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Kasadaki rapor künyeleri. İmza geriye uyumlu: `list_reports()` eskisi
        gibi hepsini döndürür, `list_reports(kinds=["office_report"])` süzer.
        """
        return self.get_research_reports(kinds=kinds)

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
        for match in self.WIKILINK_PATTERN.finditer(strip_code_spans(content)):
            target = match.group("target").strip()
            if not target or "\n" in target:
                continue
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
        # Surum oneki: dugum alanlari degisince eski onbellek girdileri duser.
        return f"{_GRAPH_SCHEMA_VERSION}-{h.hexdigest()}", files

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

        query_skill_links: List[Tuple[str, str]] = []
        # Ofis kayit defterlerinden gelen (ofis_id, ajan_adi, rol) uclulari;
        # ajan dugumleri tarama bittikten sonra baglanir cunku AGENT.md dosyasi
        # OFFICE.md'den sonra da gorulebilir.
        office_member_links: List[Tuple[str, str, str]] = []
        office_report_links: List[Tuple[str, str]] = []
        agent_ids: Dict[str, str] = {}
        skipped: Set[Path] = set()
        file_ids: Dict[Path, str] = {}

        node_by_id: Dict[str, Dict[str, Any]] = {}
        for file in files:
            if _GRAPH_SCAN_SKIP_DIRS.intersection(p.lower() for p in file.parts):
                # Faz 8/M2: arşiv ve eski AgentDesk artıkları grafa girmez;
                # `_archive/<tarih>/office_*/` altında 24 kez tekrar eden aynı
                # adlı not grafikte tek düğüm gibi görünüyordu (ölçüm: 2 grup ×24).
                skipped.add(file)
                continue
            if is_test_artifact_path(file):
                # Faz 8/M2: pytest kalintisi projeler graftan cikar.
                skipped.add(file)
                continue
            name = file.stem
            category = file.parent.name
            skill_of_query = _query_page_skill(file)
            office_role = _office_page_role(file)
            agent_of_page = _agent_page_name(file)
            wiki_role = _wiki_generated_role(file)
            if wiki_role is not None:
                # Uretilmis wiki sayfalari kendi gruplarinda: kavram acik yesil,
                # varlik acik mavi. Yetenege baglanmalari sorgu sayfalariyla
                # ayni mekanizmadan gecer (aidiyet dosya yolundan gelir).
                category = wiki_role[0]
                skill_of_query = wiki_role[1]
            elif file.parent.name.lower() == "wiki" and file.stem.lower() in ("index", "log", "lint"):
                # Wiki'nin defter dosyalari (indeks, gunluk, denetim) bilgi
                # dugumu degildir; indeks her sayfaya baglandigi icin grafige
                # girseydi tum wiki'yi tek bir yildiza cokertirdi.
                skipped.add(file)
                continue
            elif skill_of_query is not None:
                # Wiki sorgu sayfalari kendi grubunda gosterilir; boylece UI
                # onlari rapor/yetenek dugumlerinden ayirt edebilir.
                category = "query"
            elif office_role is not None:
                office_name, role = office_role
                if role == "office":
                    category = "office"
                    name = office_name
                elif role == "report":
                    # Ofis raporu ozeti de bir sorgu sayfasidir: ayni grup,
                    # ayni renk; farki ofise bagli olmasi.
                    category = "query"
                else:
                    # MEMORY.md / log.md gibi ic dosyalar grafige girmez:
                    # kullanicinin okudugu bellek dosyasi bir bilgi dugumu
                    # degil, defterdir. Bunlar wikilink taramasindan da cikar.
                    skipped.add(file)
                    continue
            elif agent_of_page is not None:
                category = "agent"
                name = agent_of_page
            node_id = f"{category}/{name}"
            if office_role is not None and office_role[1] == "report":
                # Ofis raporu ozeti wiki sayfasiyla AYNI dosya adini tasir
                # (tarih-slug); ofis adiyla ayristirilmazsa ikisi tek dugume
                # duserdi ve ozet grafikte hic gorunmezdi.
                node_id = f"{category}/office-{office_role[0]}-{name}"
            elif category not in ("office", "agent") or name not in stem_to_id:
                # Wikilink hedefi olarak stem daima TAM sayfaya isaret etsin:
                # ozet zaten `[[tam sayfa]]` diye bagliyor.
                stem_to_id[name] = node_id
            file_ids[file] = node_id
            if category == "agent":
                # Kategori "agent" olsa da sayfa adi ajan sablonundan gelmemis
                # olabilir (ornegin klasor adindan turemis); o durumda dosya
                # adini kullan, aksi halde None.strip() cokerdi.
                agent_key = (agent_of_page or name or "").strip().lower()
                if agent_key:
                    agent_ids[agent_key] = node_id

            if node_id not in node_ids:
                node_ids.add(node_id)
                node = {
                    "id": node_id,
                    "name": name,
                    "group": category,
                    "path": str(file),
                    **_graph_node_fields(category, file),
                }
                nodes.append(node)
                node_by_id[node_id] = node

            if office_role is not None and office_role[1] == "office":
                try:
                    fm_text = file.read_text(encoding="utf-8", errors="ignore")[:2000]
                except OSError:
                    fm_text = ""
                for key, role_label in (("orchestrator", "orkestrator"),
                                        ("evaluator", "degerlendirici"),
                                        ("members", "uye")):
                    for member in _frontmatter_list(fm_text, key):
                        office_member_links.append((node_id, member, role_label))
            elif office_role is not None and office_role[1] == "report":
                office_report_links.append((node_id, f"office/{office_role[0]}"))

            if skill_of_query:
                skill_id = f"skill/{skill_of_query}"
                if skill_id not in node_ids:
                    node_ids.add(skill_id)
                    nodes.append({
                        "id": skill_id,
                        "name": skill_of_query,
                        "group": "skill",
                        "path": str(file.parents[2]),
                        **_graph_node_fields("skill", None),
                    })
                query_skill_links.append((node_id, skill_id))

        for file in files:
            if file in skipped:
                continue
            source_id = file_ids.get(file) or stem_to_id.get(file.stem, f"{file.parent.name}/{file.stem}")
            is_heavy_catalog = (file.stem in ["BELLEK_HARITASI", "MEMORY"])
            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                # Faz 8/M6: on bilgideki `tags`/`skill` rapor siniflandirmasinda
                # kullanilir; icerik zaten burada okundugu icin ek G/C yok.
                node = node_by_id.get(source_id)
                if node is not None and content.lstrip("﻿").startswith("---"):
                    fm = _read_frontmatter(file)
                    tag_line = fm.get("tags", "")
                    tags = [
                        t.strip().strip("[]").strip('"').strip("'")
                        for t in tag_line.split(",")
                    ]
                    tags = [t for t in tags if t]
                    if tags:
                        node["tags"] = tags
                    if fm.get("skill"):
                        node["skill"] = fm["skill"]
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

        # Sorgu sayfasi -> yetenek dugumu baglantilari. Wikilink taramasindan
        # bagimsizdir: sayfa yetenege dosya yolundan aittir, metinden degil.
        for source_id, skill_id in query_skill_links:
            links.append({
                "source": source_id,
                "target": skill_id,
                "alias": "skill",
                "is_catalog_link": False,
            })

        # Ofis -> ajan baglari. Uye AGENT.md ile kayitliysa MEVCUT dugume
        # baglanir; degilse sentetik bir `agent` dugumu uretilir: ofis kartinda
        # adi gecen ama kasada dosyasi olmayan ajan da grafikte gorunmelidir.
        for office_id, member, role_label in office_member_links:
            key = member.strip().lower()
            if not key:
                continue
            agent_id = agent_ids.get(key)
            if agent_id is None:
                agent_id = f"agent/{member.strip()}"
                agent_ids[key] = agent_id
                if agent_id not in node_ids:
                    node_ids.add(agent_id)
                    nodes.append({
                        "id": agent_id,
                        "name": member.strip(),
                        "group": "agent",
                        "path": "",
                        **_graph_node_fields("agent", None),
                    })
            links.append({
                "source": office_id,
                "target": agent_id,
                "alias": role_label,
                "is_catalog_link": False,
            })

        # Ofis raporu -> ofis baglari (sorgu -> yetenek ile ayni mantik: aidiyet
        # dosya yolundan gelir, metinden degil).
        for report_id, office_id in office_report_links:
            if office_id not in node_ids:
                node_ids.add(office_id)
                nodes.append({
                    "id": office_id,
                    "name": office_id.split("/", 1)[1],
                    "group": "office",
                    "path": "",
                    **_graph_node_fields("office", None),
                })
            links.append({
                "source": report_id,
                "target": office_id,
                "alias": "office",
                "is_catalog_link": False,
            })

        data = {"nodes": nodes, "links": links}
        _GRAPH_MEMORY_CACHE[vault_key] = (signature, data)
        self._save_graph_disk_cache(signature, data)
        return {"nodes": list(nodes), "links": list(links)}

    def build_graph_with_communities(
        self,
        graph_store: Any = None,
        scopes: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Kasa grafigi + birlesik graftan gelen topluluk dugumleri.

        UI (Faz 5.6) acilista topluluk dugumlerini gosterip tiklayinca uyeleri
        acar; zaman kaydiricisi `t_valid_from`/`t_valid_to`, filtreler `type` ve
        `importance` alanlarini kullanir. `graph_store` verilmezse yalnizca kasa
        grafigi doner (yeni alanlar yine vardir) - bellek katmani yoksa UI
        bozulmaz.
        """
        base = self.build_knowledge_graph()
        nodes: List[Dict[str, Any]] = list(base["nodes"])
        links: List[Dict[str, Any]] = list(base["links"])
        if graph_store is None:
            return {"nodes": nodes, "links": links}

        known = {n["id"] for n in nodes}
        try:
            communities = graph_store.list_communities()
        except Exception:
            return {"nodes": nodes, "links": links}

        for comm in communities:
            if comm.id in known:
                continue
            known.add(comm.id)
            node = graph_store.get_node(comm.id)
            nodes.append({
                "id": comm.id,
                "name": comm.label or comm.id,
                "group": "community",
                "path": "",
                "type": "community",
                "importance": float(getattr(node, "importance", 0.5) or 0.5),
                "t_valid_from": float(getattr(node, "created_at", 0.0) or 0.0),
                "t_valid_to": None,
                "member_count": comm.member_count,
                "summary": comm.summary,
            })
            for edge in graph_store.get_edges(dst=comm.id, edge_type="member_of", valid_only=True):
                if edge.src not in known:
                    continue
                links.append({
                    "source": edge.src,
                    "target": comm.id,
                    "alias": "community",
                    "type": "member_of",
                    "is_catalog_link": False,
                    "t_valid_from": edge.t_valid_from,
                    "t_valid_to": edge.t_valid_to,
                })
        if scopes is not None:
            allowed = set(scopes)
            keep = {
                n["id"] for n in nodes
                if n.get("scope", "general") in allowed or "scope" not in n
            }
            nodes = [n for n in nodes if n["id"] in keep]
            links = [l for l in links if l["source"] in keep and l["target"] in keep]
        return {"nodes": nodes, "links": links}
