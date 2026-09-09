"""Antigravity-compliant Skills & Self-Tooling Management Engine."""

import json
import logging
import re
import sys
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Slot

from entropy.core.config import APP_ROOT, config
from entropy.core.event_bus import bus

logger = logging.getLogger(__name__)

# İçe aktarılan yetenekler dış kaynaklıdır (rastgele URL, GitHub deposu, yerel arşiv).
# Aşağıdaki sınırlar kötü niyetli ya da kazara devasa bir kaynağın belleği veya diski
# tüketmesini engeller. Yol kaçışı (Zip Slip) için ayrı bir önlem gerekmez:
# zipfile.extractall() üye adlarındaki '..' ve mutlak yol bileşenlerini kendisi ayıklar.
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024        # 32 MB indirme tavanı
MAX_ARCHIVE_MEMBERS = 2000                   # arşivdeki azami dosya sayısı
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024         # açılmış toplam boyut tavanı


# --- Evrensel yetenek keşfi -------------------------------------------------
#
# SKILL.md tek bir standarttır (YAML ön bilgisi + markdown gövde) ama her CLI
# onu başka bir dizinde arar. İnternetten indirilen bir yeteneğin "bütün
# CLI'ların gördüğü" yerde durması için hepsinin köklerini tek katalogda
# birleştiriyoruz. Aşağıdaki yollar yerel kurulumdan ve agy.EXE içindeki
# belge dizgelerinden doğrulandı:
#   - Antigravity/agy : "<workspace>/.agents/skills/<name>/" ve
#                       "~/.gemini/config/skills/<name>/"; çalışma alanı kökü
#                       .agents | _agents | .agent | _agent olabiliyor.
#   - Claude Code     : ".claude/skills/", "~/.claude/skills/"
#   - agent-skills    : ".agents/skills/", "~/.agents/skills/"
#   - Gemini CLI      : ".gemini/skills/", "~/.gemini/skills/"
#   - Cursor          : ".cursor/skills/"
PROJECT_SKILL_SUBDIRS = (
    ("skills",),
    (".agents", "skills"),
    ("_agents", "skills"),
    (".agent", "skills"),
    ("_agent", "skills"),
    (".claude", "skills"),
    (".gemini", "skills"),
    (".cursor", "skills"),
    (".entropy", "skills"),
)

USER_SKILL_SUBDIRS = (
    (".entropy", "skills"),
    (".agents", "skills"),
    (".claude", "skills"),
    (".gemini", "skills"),
    (".gemini", "config", "skills"),
    (".gemini", "antigravity", "builtin", "skills"),
    (".gemini", "antigravity-cli", "builtin", "skills"),
    (".cursor", "skills"),
)

# İçe aktarılan yeteneğin yazıldığı proje-içi kök. .agents/skills seçildi çünkü
# agy çalışma alanı yeteneklerini oradan, agent-skills standardı da aynı yerden
# okur; yani indirilen dosya hem Entropy'de hem de CLI'da anında görünür.
IMPORT_SUBDIR = (".agents", "skills")


def discover_skill_dirs(project_dir: Optional[Path] = None) -> List[Path]:
    """
    Yeteneklerin aranacağı tüm dizinleri, öncelik sırasıyla döndürür.

    Tek kaynak olması önemli: bu liste hem yetenek paneli hem de `/` komut
    tamamlaması tarafından kullanılır. Daha önce ikisi ayrı ayrı keşif yapıyordu;
    panel yalnızca <APP_ROOT>/skills'e bakarken `/` ev dizinindeki Gemini ve
    Antigravity dizinlerini de tarıyordu. Sonuç olarak orada oluşturulan bir
    yetenek `/` ile seçilebiliyor ama panelde hiç görünmüyordu.

    Sıra önceliktir: aynı ada sahip yetenekte listede önce gelen kazanır
    (proje kökü > kullanıcı dizinleri > uygulama içi skills/). Uygulamayla
    gelen yerleşik yetenekler en sona alındı: kullanıcının kendi indirdiği
    aynı adlı sürüm, paketle gelen kopyayı ezebilmeli.
    """
    dirs: List[Path] = []

    def _add(p: Optional[Path]):
        if p and p.is_dir() and p not in dirs:
            dirs.append(p)

    def _add_project_root(root) -> None:
        if not root:
            return
        try:
            base = Path(root)
        except (TypeError, ValueError):
            return
        for parts in PROJECT_SKILL_SUBDIRS:
            _add(base.joinpath(*parts))

    # 1. Proje kökleri: aktif proje, yapılandırılmış varsayılan proje, çalışma dizini
    _add_project_root(project_dir)
    _add_project_root(config.default_project_path)
    _add_project_root(Path.cwd())

    # 2. Kullanıcı geneli kökler (tüm CLI'ların ev dizini yerleşimleri)
    home = Path.home()
    for parts in USER_SKILL_SUBDIRS:
        _add(home.joinpath(*parts))

    # 3. Gemini/Antigravity eklenti yetenekleri
    #    (Claude eklenti pazar yeri bilerek taranmıyor: ~/.claude/plugins/marketplaces
    #     altında kurulmamış onlarca eklentinin yeteneği duruyor; kurulu olanlar zaten
    #     ~/.claude/skills içine düşüyor.)
    plugins_root = home / ".gemini" / "config" / "plugins"
    if plugins_root.is_dir():
        try:
            for sub in sorted(plugins_root.iterdir()):
                if not sub.is_dir():
                    continue
                if (sub / "skills").is_dir():
                    _add(sub / "skills")
                elif (sub / "SKILL.md").is_file():
                    _add(sub)
        except OSError:
            pass

    # 4. Uygulamayla gelen yerleşik yetenekler (en düşük öncelik)
    _add(GLOBAL_SKILLS_DIR)

    return dirs


def _normalize_tags(raw) -> List[str]:
    """
    SKILL.md frontmatter'ındaki `tags` alanını her iki geçerli YAML biçiminden de okur.

    YAML iki yazımı da kabul eder:
        tags: a, b, c              -> str
        tags: [a, b, c]            -> list
    Önceki kod yalnızca str varsayıp .split(',') çağırıyordu; liste biçimi
    AttributeError fırlatıp parse_skill_file'ın geniş except'ine düşüyor ve
    yetenek sessizce kataloğdan siliniyordu.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(t).strip() for t in raw if str(t).strip()]
    return [str(raw).strip()] if str(raw).strip() else []


def sanitize_skill_name(name: str, fallback: str = "imported-skill") -> str:
    """
    Yetenek adını dizin adı olarak güvenli hale getirir.

    Ad, yeteneğin yazılacağı dizinin adıdır; nokta ve bölü işaretleri elenerek
    hedef dizinin dışına çıkılması önlenir. Tamamen elenen bir ad (örn. '...')
    boş string üretip hedefi yetenek kökünün kendisine kaydırırdı; bu durumda
    fallback kullanılır.
    """
    clean = re.sub(r'[^a-zA-Z0-9_\-]', '-', (name or "").lower().strip()).strip('-')
    return clean or fallback


def read_url_limited(req: "urllib.request.Request", timeout: int) -> bytes:
    """İçeriği MAX_DOWNLOAD_BYTES sınırıyla okur; sınır aşılırsa hata verir."""
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ValueError(
            f"İndirilen içerik {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB sınırını aşıyor."
        )
    return data


def safe_extract_zip(zf, dest_dir) -> None:
    """Arşivi, sıkıştırma bombalarına karşı üye sayısı ve boyut sınırı uygulayarak açar."""
    members = zf.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ValueError(
            f"Arşiv çok fazla dosya içeriyor ({len(members)} > {MAX_ARCHIVE_MEMBERS})."
        )

    total = 0
    for info in members:
        if info.is_dir():
            continue
        total += info.file_size
        if total > MAX_ARCHIVE_BYTES:
            raise ValueError(
                f"Arşivin açılmış boyutu {MAX_ARCHIVE_BYTES // (1024 * 1024)} MB sınırını aşıyor."
            )

    zf.extractall(dest_dir)

@dataclass
class SkillDefinition:
    name: str
    description: str
    instructions: str
    path: str
    scripts: List[Dict[str, str]]
    enabled: bool = True
    version: str = "1.0.0"
    tags: List[str] = None

GLOBAL_SKILLS_DIR = APP_ROOT / "skills"
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _mei_skills = Path(sys._MEIPASS) / "skills"
    if _mei_skills.exists():
        GLOBAL_SKILLS_DIR = _mei_skills
elif not GLOBAL_SKILLS_DIR.exists():
    _cand = Path(__file__).resolve().parents[3] / "skills"
    if _cand.exists():
        GLOBAL_SKILLS_DIR = _cand

class SkillManager:
    """Discovers, parses, synthesizes, and executes Antigravity-compatible skills."""

    def __init__(self, root_skills_dir: Optional[Path] = None, project_dir: Optional[Path] = None):
        self.global_skills_dir = GLOBAL_SKILLS_DIR
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            _mei_skills = Path(sys._MEIPASS) / "skills"
            if _mei_skills.exists():
                self.global_skills_dir = _mei_skills
        elif not self.global_skills_dir.exists():
            _cand = Path(__file__).resolve().parents[3] / "skills"
            if _cand.exists():
                self.global_skills_dir = _cand

        # Dual-mode resolution:
        # 1. When root_skills_dir is explicitly provided (isolated tests/workspaces), isolate to that directory
        # 2. When project_dir is provided or default: Global system skills from GLOBAL_SKILLS_DIR (always active)
        #    plus optional project skills if and only if (project_dir / "skills").exists()
        # list_skills() bu ikisine bakar: izole kök verilmişse yalnızca orası taranır,
        # aksi hâlde discover_skill_dirs(project_dir) ile tüm konumlar taranır.
        self._isolated_root: Optional[Path] = Path(root_skills_dir) if root_skills_dir is not None else None
        self._project_dir: Optional[Path] = Path(project_dir) if project_dir is not None else None

        if root_skills_dir is not None:
            p_skills = Path(root_skills_dir)
            self.global_skills_dir = None
            self.project_skills_dir = p_skills if p_skills.exists() else None
            self.root_skills_dir = p_skills
        elif project_dir is not None:
            p_skills = Path(project_dir) / "skills"
            self.project_skills_dir = p_skills if p_skills.exists() else None
            self.root_skills_dir = self.project_skills_dir or self.global_skills_dir
        else:
            self.project_skills_dir = None
            self.root_skills_dir = self.global_skills_dir

        # Etkin/pasif durumu: yalıtılmış bir kök verildiyse (testler, izole çalışma
        # alanı) o kökün içinde tutulur. Aksi hâlde kullanıcının uygulamada bir
        # yeteneği pasife alması yalıtılmış testleri de etkiliyordu.
        if self._isolated_root is not None:
            self.state_file = self._isolated_root / ".skills_state.json"
        else:
            self.state_file = Path.home() / ".entropy" / "skills_state.json"
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self._enabled_cache: Dict[str, bool] = self._load_state()

    def import_base_dir(self) -> Path:
        """
        İçe aktarılan / oluşturulan yeteneğin yazılacağı kök dizin.

        Yalıtılmış bir kök verildiyse (testler, izole çalışma alanı) yalnızca
        orası kullanılır — yoksa test dosyaları kullanıcının gerçek dizinlerine
        sızardı. Aksi hâlde aktif projenin `.agents/skills` dizinine yazılır:
        SKILL.md oraya düştüğü anda hem Entropy paneli hem agy hem de
        agent-skills uyumlu diğer CLI'lar yeteneği görür.
        """
        if self._isolated_root is not None:
            return self._isolated_root
        for root in (self._project_dir, config.default_project_path):
            if root:
                return Path(root).joinpath(*IMPORT_SUBDIR)
        if self.project_skills_dir:
            return self.project_skills_dir
        return self.global_skills_dir or self.root_skills_dir or GLOBAL_SKILLS_DIR

    def _load_state(self) -> Dict[str, bool]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_state(self):
        try:
            self.state_file.write_text(json.dumps(self._enabled_cache, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _scan_dir(self, directory: Path, into: Dict[str, SkillDefinition], overwrite: bool):
        """Bir dizindeki SKILL.md dosyalarını ayrıştırıp katalog sözlüğüne ekler."""
        if not directory or not directory.is_dir():
            return
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            return

        # Dizinin kendisi doğrudan bir yetenek olabilir (eklenti yerleşimi)
        direct = directory / "SKILL.md"
        if direct.is_file():
            parsed = self.parse_skill_file(direct)
            if parsed and (overwrite or parsed.name not in into):
                into[parsed.name] = parsed

        for skill_dir in entries:
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            parsed = self.parse_skill_file(skill_file)
            if parsed and (overwrite or parsed.name not in into):
                into[parsed.name] = parsed

    def list_skills(self) -> List[SkillDefinition]:
        """
        Yetenek kataloğunu üretir.

        `root_skills_dir` açıkça verildiyse (izole testler/çalışma alanları) yalnızca
        o dizin taranır. Aksi hâlde discover_skill_dirs() ile bulunan tüm konumlar
        taranır; böylece panel ile `/` komut listesi aynı kataloğu görür.
        """
        skills_dict: Dict[str, SkillDefinition] = {}

        if self._isolated_root is not None:
            self._scan_dir(self._isolated_root, skills_dict, overwrite=True)
            return list(skills_dict.values())

        # Öncelik sırası tersten uygulanır: sonra taranan öncekini ezmez,
        # böylece discover_skill_dirs()'in sırası (proje > kök > kullanıcı) korunur.
        for directory in discover_skill_dirs(self._project_dir):
            self._scan_dir(directory, skills_dict, overwrite=False)

        return list(skills_dict.values())

    def parse_skill_file(self, skill_file: Path) -> Optional[SkillDefinition]:
        """Extract YAML frontmatter and markdown body from SKILL.md."""
        try:
            text = skill_file.read_text(encoding="utf-8", errors="replace")
            frontmatter = {}
            body = text

            # Frontmatter regex: between --- and ---
            fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
            if fm_match:
                fm_text = fm_match.group(1)
                body = fm_match.group(2).strip()
                try:
                    import yaml
                    loaded_fm = yaml.safe_load(fm_text)
                    if isinstance(loaded_fm, dict):
                        frontmatter = {str(k).lower(): v for k, v in loaded_fm.items()}
                except Exception:
                    for line in fm_text.splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            frontmatter[k.strip().lower()] = v.strip().strip('"').strip("'")

            name = frontmatter.get("name") or skill_file.parent.name
            raw_desc = frontmatter.get("description")
            description = str(raw_desc).strip() if raw_desc else f"{name} yetenek uzmanlığı"
            version = frontmatter.get("version") or "1.0.0"

            # Check scripts directory
            scripts_dir = skill_file.parent / "scripts"
            scripts = []
            if scripts_dir.exists():
                for s_file in scripts_dir.iterdir():
                    if s_file.is_file() and s_file.suffix in [".py", ".sh", ".bat"]:
                        scripts.append({
                            "name": s_file.name,
                            "path": str(s_file.resolve()),
                            "type": s_file.suffix
                        })

            is_enabled = self._enabled_cache.get(name, True)

            return SkillDefinition(
                name=name,
                description=description,
                instructions=body,
                path=str(skill_file.resolve()),
                scripts=scripts,
                enabled=is_enabled,
                version=version,
                tags=_normalize_tags(frontmatter.get("tags")),
            )
        except Exception as e:
            # Sessizce None dönmek, tek bir bozuk alan yüzünden yeteneğin tamamen
            # kaybolmasına yol açıyordu (yetenek hiç yokmuş gibi davranılıyordu).
            logger.warning("SKILL.md ayrıştırılamadı (%s): %s", skill_file, e)
            return None

    def toggle_skill(self, name: str, enabled: bool) -> bool:
        """Enable or disable a skill."""
        self._enabled_cache[name] = enabled
        self._save_state()
        bus.skills_updated.emit()
        return True

    def delete_skill(self, name: str) -> bool:
        """Permanently delete a skill directory."""
        candidates = []
        if self.project_skills_dir:
            candidates.append(self.project_skills_dir / name)
        if self.root_skills_dir:
            candidates.append(self.root_skills_dir / name)
        if self.global_skills_dir:
            candidates.append(self.global_skills_dir / name)

        deleted = False
        import shutil
        for skill_dir in candidates:
            if skill_dir.exists() and skill_dir.is_dir():
                shutil.rmtree(skill_dir, ignore_errors=True)
                deleted = True

        if deleted:
            if name in self._enabled_cache:
                del self._enabled_cache[name]
                self._save_state()
            bus.terminal_output_received.emit(f"[Yetenek Merkezi] '{name}' yeteneği silindi.\n")
            bus.skills_updated.emit()
            return True
        return False

    def create_skill(
        self,
        name: str,
        description: str,
        instructions: str,
        scripts: Optional[Dict[str, str]] = None
    ) -> SkillDefinition:
        """Create a new skill folder with SKILL.md and optional executable scripts."""
        clean_name = sanitize_skill_name(name, fallback="custom-skill")
        base_dir = self.import_base_dir()
        base_dir.mkdir(parents=True, exist_ok=True)
        skill_dir = base_dir / clean_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        content = f"---\nname: {clean_name}\ndescription: >-\n  {description}\n---\n\n{instructions}\n"
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(content, encoding="utf-8")

        created_scripts = []
        if scripts:
            scripts_dir = skill_dir / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            for s_name, s_code in scripts.items():
                s_file = scripts_dir / s_name
                s_file.write_text(s_code, encoding="utf-8")
                created_scripts.append({
                    "name": s_name,
                    "path": str(s_file.resolve()),
                    "type": s_file.suffix
                })

        # Register procedural memory in SQLite
        try:
            from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
            cog = CognitiveMemorySystem()
            cog.store_node(
                category="procedural",
                content=f"Yetenek / Araç: [{clean_name}] - {description}. Talimatlar: {instructions[:300]}",
                importance=0.90,
                metadata={"source": "skill_synthesis", "skill_name": clean_name}
            )
        except Exception:
            pass

        self._enabled_cache[clean_name] = True
        self._save_state()
        bus.terminal_output_received.emit(f"[Yetenek Merkezi] '{clean_name}' yeteneği sisteme eklendi.\n")
        bus.skills_updated.emit()

        return SkillDefinition(
            name=clean_name,
            description=description,
            instructions=instructions,
            path=str(skill_file.resolve()),
            scripts=created_scripts,
            enabled=True
        )

    def download_skill_from_url(self, url: str, override_name: Optional[str] = None) -> Optional[SkillDefinition]:
        """Download raw SKILL.md or GitHub repo/zip from a web URL and register it."""
        return self.import_skill_from_source(url, override_name)

    def import_skill_from_source(self, source: str, custom_name: Optional[str] = None) -> Optional[SkillDefinition]:
        """
        Universal skill importer accepting:
        - GitHub repo URL (e.g. https://github.com/owner/repo)
        - GitHub blob / raw file URL
        - Direct HTTP/HTTPS link to SKILL.md or .zip archive
        - Local file path to SKILL.md or .zip archive
        - Local directory containing SKILL.md
        """
        source = source.strip()
        if not source:
            return None

        # 1. URL Source
        if source.startswith("http://") or source.startswith("https://"):
            return self._import_from_url(source, custom_name)

        # 2. Local File / Directory Source
        p = Path(source).resolve()
        if p.exists():
            return self._import_from_local_path(p, custom_name)

        bus.terminal_output_received.emit(f"[Yetenek İçe Aktarma] Kaynak bulunamadı: {source}\n")
        return None

    def _import_from_url(self, url: str, custom_name: Optional[str] = None) -> Optional[SkillDefinition]:
        import zipfile
        import tempfile
        import shutil

        # Normalize GitHub blob URL to raw URL
        if "github.com" in url and "/blob/" in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

        # Check for GitHub repository URL
        github_repo_match = re.match(
            r'https?://github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)(?:/tree/([a-zA-Z0-9_\-\.]+)(?:/(.*))?)?/?$',
            url
        )
        if github_repo_match and "raw.githubusercontent.com" not in url:
            owner, repo, branch, subpath = github_repo_match.groups()
            repo_clean = repo.removesuffix(".git")
            skill_name = custom_name or (subpath.split("/")[-1] if subpath else repo_clean)

            # Try raw candidate paths first
            branches = [branch] if branch else ["main", "master"]
            for br in branches:
                raw_urls = []
                if subpath:
                    raw_urls.append(f"https://raw.githubusercontent.com/{owner}/{repo_clean}/{br}/{subpath.rstrip('/')}/SKILL.md")
                raw_urls.extend([
                    f"https://raw.githubusercontent.com/{owner}/{repo_clean}/{br}/SKILL.md",
                    f"https://raw.githubusercontent.com/{owner}/{repo_clean}/{br}/skills/{repo_clean}/SKILL.md",
                ])
                for candidate_url in raw_urls:
                    try:
                        req = urllib.request.Request(candidate_url, headers={"User-Agent": "EntropyAI/1.0"})
                        raw_text = read_url_limited(req, timeout=8).decode("utf-8", errors="replace")
                        return self._create_skill_from_text(raw_text, skill_name)
                    except Exception:
                        continue

            # Fallback: Download repo zip archive
            try:
                zip_branch = branch or "main"
                archive_url = f"https://github.com/{owner}/{repo_clean}/archive/refs/heads/{zip_branch}.zip"
                with tempfile.TemporaryDirectory() as tmp_dir:
                    zip_path = Path(tmp_dir) / "repo.zip"
                    req = urllib.request.Request(archive_url, headers={"User-Agent": "EntropyAI/1.0"})
                    try:
                        zip_path.write_bytes(read_url_limited(req, timeout=15))
                    except Exception:
                        if not branch:
                            archive_url = f"https://github.com/{owner}/{repo_clean}/archive/refs/heads/master.zip"
                            req = urllib.request.Request(archive_url, headers={"User-Agent": "EntropyAI/1.0"})
                            zip_path.write_bytes(read_url_limited(req, timeout=15))

                    if zip_path.exists():
                        with zipfile.ZipFile(zip_path, 'r') as zf:
                            safe_extract_zip(zf, tmp_dir)
                        return self._import_from_extracted_dir(Path(tmp_dir), skill_name)
            except Exception as e:
                bus.terminal_output_received.emit(f"[GitHub Yetenek İndirme Hatası] {e}\n")

        # Direct HTTP/HTTPS download
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EntropyAI/1.0"})
            data = read_url_limited(req, timeout=12)

            if url.endswith(".zip") or data.startswith(b"PK\x03\x04"):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    zip_path = Path(tmp_dir) / "skill.zip"
                    zip_path.write_bytes(data)
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        safe_extract_zip(zf, tmp_dir)
                    return self._import_from_extracted_dir(Path(tmp_dir), custom_name)
            else:
                raw_text = data.decode("utf-8", errors="replace")
                return self._create_skill_from_text(raw_text, custom_name)
        except Exception as e:
            bus.terminal_output_received.emit(f"[URL Yetenek İndirme Hatası] {e}\n")
            return None

    def _import_from_local_path(self, p: Path, custom_name: Optional[str] = None) -> Optional[SkillDefinition]:
        import zipfile
        import tempfile
        import shutil

        if p.is_dir():
            return self._import_from_extracted_dir(p, custom_name)

        elif p.suffix.lower() == ".zip":
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(p, 'r') as zf:
                    safe_extract_zip(zf, tmp_dir)
                return self._import_from_extracted_dir(Path(tmp_dir), custom_name or p.stem)

        elif p.suffix.lower() in [".md", ".markdown"]:
            raw_text = p.read_text(encoding="utf-8", errors="replace")
            res = self._create_skill_from_text(raw_text, custom_name or p.stem)
            scripts_dir = p.parent / "scripts"
            if res and scripts_dir.exists() and scripts_dir.is_dir():
                dest_scripts = Path(res.path).parent / "scripts"
                shutil.copytree(scripts_dir, dest_scripts, dirs_exist_ok=True)
            return res

        return None

    def _import_from_extracted_dir(self, root_dir: Path, custom_name: Optional[str] = None) -> Optional[SkillDefinition]:
        import shutil
        # 1. Look for explicit SKILL.md (case-insensitive)
        skill_files = [f for f in root_dir.rglob("*.md") if f.name.lower() == "skill.md"]
        if skill_files:
            skill_file = skill_files[0]
            fm_name = None
            try:
                fm_text = skill_file.read_text(encoding="utf-8", errors="replace")
                name_m = re.search(r'name:\s*([a-zA-Z0-9_\-]+)', fm_text)
                if name_m:
                    fm_name = name_m.group(1)
            except Exception:
                pass
            name = custom_name or fm_name or skill_file.parent.name
            clean_name = sanitize_skill_name(name)
            target_base = self.import_base_dir()
            target_dir = target_base / clean_name
            shutil.copytree(skill_file.parent, target_dir, dirs_exist_ok=True)
            bus.skills_updated.emit()
            return self.parse_skill_file(target_dir / "SKILL.md")

        # 2. Synthesize SKILL.md from README.md or scripts if no SKILL.md exists
        readme_files = [f for f in root_dir.rglob("*.md") if "readme" in f.name.lower()]
        if not readme_files:
            readme_files = list(root_dir.rglob("*.md"))
        
        name = custom_name or root_dir.name or "custom-tool"
        clean_name = sanitize_skill_name(name, fallback="custom-tool")
        target_base = self.import_base_dir()
        target_dir = target_base / clean_name
        target_dir.mkdir(parents=True, exist_ok=True)

        readme_text = readme_files[0].read_text(encoding="utf-8", errors="replace") if readme_files else ""
        desc = "GitHub deposundan otomatik sentezlenen yetenek"
        if readme_text:
            paras = [p.strip() for p in readme_text.split("\n\n") if p.strip() and not p.startswith("#")]
            if paras:
                desc = paras[0][:200].replace("\n", " ")

        py_scripts = list(root_dir.rglob("*.py"))
        script_docs = ""
        if py_scripts:
            scripts_dest = target_dir / "scripts"
            scripts_dest.mkdir(parents=True, exist_ok=True)
            script_docs = "\n\n## Çalıştırılabilir Araçlar\n"
            for sc in py_scripts:
                try:
                    shutil.copy2(sc, scripts_dest / sc.name)
                    script_docs += f"- `python skills/{clean_name}/scripts/{sc.name}`\n"
                except Exception:
                    pass

        skill_content = (
            f"---\n"
            f"name: {clean_name}\n"
            f"description: >-\n  {desc}\n"
            f"tags: imported, github, tools\n"
            f"version: 1.0.0\n"
            f"---\n\n"
            f"# {clean_name.replace('-', ' ').title()} Yeteneği\n\n"
            f"{readme_text if readme_text else desc}\n"
            f"{script_docs}\n"
        )
        (target_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")
        # Copy remaining files
        for item in root_dir.iterdir():
            if item.name.lower() not in ["skill.md"]:
                try:
                    if item.is_dir():
                        shutil.copytree(item, target_dir / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, target_dir / item.name)
                except Exception:
                    pass

        bus.skills_updated.emit()
        return self.parse_skill_file(target_dir / "SKILL.md")

    def _create_skill_from_text(self, raw_text: str, override_name: Optional[str] = None) -> Optional[SkillDefinition]:
        name_match = re.search(r'name:\s*([a-zA-Z0-9_\-]+)', raw_text)
        skill_name = override_name or (name_match.group(1) if name_match else "imported-skill")
        clean_name = sanitize_skill_name(skill_name)

        desc_match = re.search(r'description:\s*(?:>-|>)?\s*([^\n]+)', raw_text)
        description = desc_match.group(1).strip() if desc_match else f"İçe aktarılan yetenek: {clean_name}"

        body_match = re.search(r'^---\s*\n.*?\n---\s*\n(.*)$', raw_text, re.DOTALL)
        instructions = body_match.group(1).strip() if body_match else raw_text
        return self.create_skill(clean_name, description, instructions)

    # Kısa, göndermeli takip mesajları: "bunu slayt yap", "aynısını şuna uygula".
    # Bu mesajlar tek başına hangi yeteneğe ait olduklarını söylemez; cevap bir
    # önceki turdadır. Bu işaretlerden biri geçen kısa mesajlarda son kullanılan
    # yetenek öncelik kazanır.
    _ANAPHORA_MARKERS = (
        "bunu", "bunun", "buna", "bundan", "sunu", "sunun", "onu", "onun",
        "aynisini", "ayni", "devam", "simdi de", "bir de", "sonra", "peki",
    )
    # Ölçümle ayarlandı (çok dilli MiniLM): alakasız çiftler 0.08–0.39, alakalı
    # çiftler 0.45–0.66 arasında çıktı. Taban 0.30 alakasızları sıfırlar; tavan 3.0
    # ile yalnızca sim ≥ 0.55 olan çok güçlü bir anlamsal eşleşme tek başına eşiği
    # (2.5) geçebilir — anahtar kelimesi olmayan yeni yetenekler için gerekli.
    _SEMANTIC_FLOOR = 0.30
    _SEMANTIC_GAIN = 10.0
    _SEMANTIC_CAP = 3.0
    # Tek bir kelime token'ların yarısından fazlaysa ("proje proje proje") gömme o
    # kelimeye kilitlenir ve benzerlik yapay şişer; böyle prompt'larda anlamsal
    # bonus uygulanmaz, karar yalnızca sözcüksel kanıta bırakılır.
    _SEMANTIC_MAX_DOMINANT_RATIO = 0.5
    _SEMANTIC_MIN_TOKENS = 3
    # Göndermeli takipte ("bunu slayt yap") son yeteneğe eklenen öncelik ve
    # bir yeteneğin seçilmesi için gereken asgari skor. Sınıf özniteliği
    # olmalarının sebebi ölçülebilirlik: scripts/routing_eval.py bunları
    # --set ile değiştirip doğruluk farkını raporlayabiliyor.
    _ANAPHORA_PRIOR = 3.0
    # Karar eşiği 2.5 → 3.0 (2026-09-08, scripts/routing_eval.py, 75 örnek):
    # 2.5'te alakasız 11 mesajın 2'si yeteneğe düşüyordu (yanlış pozitif %18,2);
    # 3.0'da hiçbiri düşmüyor. Doğruluk %77,3 → %78,7, makro F1 0,766 → 0,789.
    # Izgara aramada en iyi kombinasyon (taban 0,34 / kazanç 15 / tavan 4,0 / eşik
    # 3,0) %80,0 veriyordu ama üç eşiği birden 75 örneğe göre oynatmak aşırı uydurma
    # riski taşıdığı için yalnızca tek parametrelik bu değişiklik alındı.
    _DECISION_THRESHOLD = 3.0

    def _skill_vector(self, skill: "SkillDefinition"):
        """
        Yeteneğin anlamsal imzası: ad + açıklama + (varsa) playbook'un başı.

        Playbook eklenir çünkü "bu yetenek neyi nasıl yapar" bilgisi açıklamadan
        çok daha ayırt edicidir; damıtıldıkça yönlendirme de kendiliğinden iyileşir.
        Gömme, (ad, dosya mtime) anahtarıyla önbelleğe alınır.
        """
        cache = getattr(self, "_skill_vec_cache", None)
        if cache is None:
            cache = self._skill_vec_cache = {}
        try:
            mtime = Path(skill.path).stat().st_mtime_ns
        except OSError:
            mtime = 0
        key = (skill.name, mtime)
        hit = cache.get(skill.name)
        if hit and hit[0] == key:
            return hit[1]

        from entropy.memory.supabase.cognitive_memory import LocalEmbeddingEngine

        text = f"{skill.name.replace('-', ' ')}. {skill.description or ''}"
        kws = getattr(self, "_domain_keywords_cache", {}).get(skill.name)
        if kws:
            text += "\nAnahtar konular: " + ", ".join(kws)
        try:
            from entropy.memory.playbook import PlaybookStore

            pb = PlaybookStore().load(skill.name)
            if pb and pb.procedure:
                text += "\n" + pb.procedure[:600]
        except Exception:
            pass
        vec = LocalEmbeddingEngine.get_instance().embed_text(text)
        cache[skill.name] = (key, vec)
        return vec

    def rank_skills_for_prompt(
        self,
        prompt: str,
        last_skill: Optional[str] = None,
        history: Optional[List[str]] = None,
    ) -> List[Tuple[SkillDefinition, float]]:
        """
        Etkin yetenekleri mesaja uygunluk skoruna göre sıralar (yüksekten düşüğe).

        Karar (`auto_detect_skill_for_prompt`) ve güven puanı
        (`score_skill_for_prompt`) bu tek sıralamadan türer; böylece rozet ile
        gerçek yönlendirme asla birbirinden ayrışmaz.

        Üç sinyal harmanlanır:
          1. Sözcüksel: yetenek adı, alan anahtar kelimeleri, etiketler, açıklama
             (kesin terimlerde yüksek isabet; yeni yeteneklerde anahtar kelime yok).
          2. Anlamsal: sorgu ile yeteneğin ad+açıklama+playbook gömmesinin kosinüs
             benzerliği (çok dilli model; farklı kelimelerle aynı niyeti yakalar).
          3. Konuşma önceliği: kısa ve göndermeli takip mesajlarında ("bunu slayt
             yap") son kullanılan yetenek öne çıkar; `history` verilirse son turlar
             anlamsal sorguya eklenir.

        Önceki sürüm yalnızca (1)'i kullanıyor ve tek mesaja bakıyordu; bu yüzden
        "canivopets sitesini incele ve büyüme önerisi çıkar" hiçbir yeteneğe
        düşmüyor, "bunu slayt yap" ise bağlamsız kalıyordu.
        """
        def normalize_str(s: str) -> str:
            tr_trans = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
            return s.translate(tr_trans).lower()

        p_norm = normalize_str(prompt)

        # Anlamsal sorgu: mevcut mesaj + son iki kullanıcı turu (yalnızca gömme
        # için; anahtar kelime skoruna karıştırılmaz, aksi hâlde önceki turun
        # terimleri her yeni mesajı eski yeteneğe çekerdi).
        semantic_query = prompt
        if history:
            tail = [h for h in history[-2:] if isinstance(h, str) and h.strip()]
            if tail:
                semantic_query = " ".join(tail + [prompt])
        query_vec = None
        try:
            from entropy.memory.supabase.cognitive_memory import LocalEmbeddingEngine, cosine_similarity

            query_vec = LocalEmbeddingEngine.get_instance().embed_text(semantic_query)
        except Exception:
            cosine_similarity = None

        all_tokens = re.findall(r"\w+", p_norm)
        p_token_count = len(all_tokens)
        use_semantic = query_vec is not None and p_token_count >= self._SEMANTIC_MIN_TOKENS
        if use_semantic:
            dominant = max(all_tokens.count(t) for t in set(all_tokens))
            if dominant / p_token_count > self._SEMANTIC_MAX_DOMINANT_RATIO:
                use_semantic = False
        is_anaphoric_followup = (
            bool(last_skill)
            and p_token_count <= 8
            and any(re.search(rf"\b{re.escape(m)}\b", p_norm) for m in self._ANAPHORA_MARKERS)
        )
        # 1. Use a set of tokens to eliminate unfair score inflation from duplicate words
        p_tokens = set(w for w in re.findall(r'\w+', p_norm) if len(w) >= 3)

        skills = [s for s in self.list_skills() if s.enabled]
        if not skills:
            return []

        # Pre-configured semantic keywords for core skills
        domain_keywords: Dict[str, List[str]] = {
            # Genişletildi (2026-09-08): tutma kümesi ve 75'lik değerlendirme
            # kümesindeki kaçırılan örnekler tek tek incelendi. Eksik olanlar
            # "borsa dili" (yatırım/hisse/temettü/halka arz) ile kantitatif
            # finans terminolojisiydi (VaR, oynaklık, faktör modelleri, getiri
            # eğrisi). Terimler kasadaki finans raporlarının başlıklarından ve
            # denetim raporlarının yönetici özetlerinden çıkarıldı.
            "financial-auditor": [
                "bilanco", "gelir tablosu", "nakit akim", "mali tablo", "finansal",
                "rasyo", "dupont", "z-score", "beneish", "altman", "kar kalitesi",
                "degerleme", "valuation", "forensic", "audit", "denetim", "portfoy",
                "hisse", "tahvil", "bilancolar", "finans", "ebitda", "favok",
                # Borsa ve yatırım dili
                "yatirim", "yatirimci", "yatirimcilik", "borsa", "endeks", "temettu",
                "halka arz", "halka acik", "sermaye", "sermaye piyasa", "piyasa degeri",
                "hisse basina", "kar payi", "karlilik", "kaldiracli", "kaldirac",
                "short", "long", "adil deger", "hedef fiyat", "getiri", "carpan",
                "fiyat kazanc", "f/k", "pd/dd", "net aktif deger", "holding",
                # Kantitatif finans / risk
                # "var" bilinçli olarak yok: Türkçede "ne var", "hangileri var"
                # gibi gündelik kullanımı yanlış pozitif üretir. Aynı sebeple
                # "alfa" da yok (alfabetik/alfa sürüm).
                "cvar", "riske maruz", "oynaklik", "volatilite", "beta",
                "sharpe", "faiz egrisi", "getiri egrisi", "faiz orani",
                "risk primi", "sermaye maliyeti", "wacc", "iskonto orani",
                "faktor modeli", "momentum", "arbitraj", "opsiyon", "turev",
                "serbest nakit", "iflas riski", "finansal sikinti", "kredi riski",
                "capm", "garch", "monte carlo", "backtest", "risk butceleme",
                "piyasa zamanlamasi", "varlik fiyatlama", "cape", "ceyreklik",
                "konsolide", "denetim raporu", "mali denetim"
            ],
            "autonomous-agent": [
                "otonom", "autonomous", "agent", "ajan", "gorev", "task",
                "harness", "agentdesk", "agent desk", "ofis", "space", "pixel agent",
                "pixelagent", "orkestrator", "orkestrasyon", "faz", "letta", "microkernel",
                "subagent", "sub-agent", "alt ajan", "teamwork", "boost", "teamwork preview",
                "coklu ajan", "proje gelistir", "proje gelistirme", "token fizigi", "token fiziği",
                "supervision", "self-supervision"
            ],
            "pdf-analyzer": [
                "pdf", "dokuman", "belge", "sayfa", "evrak",
                "tablo ayikla", "dokuman incele", "pdf incele", "pdf oku", "pdf analiz"
            ],
            "skill-creator": [
                "yetenek olustur", "yeni yetenek", "yeni arac", "tool olustur",
                "script yaz", "yetenek ekle", "yetenek yap", "yetenek sentezle",
                "self-synthesis", "yeni skill", "skill yap", "yetenek olusturma"
            ],
            "slide-deck-architect": [
                "slayt", "slide", "sunum", "sunu", "presentation", "deck",
                "slayt destesi", "slide deck", "powerpoint", "keynote",
                "sunum hazirla", "slayt yap", "sunum yap", "reveal", "katex"
            ],
            # media-agency-researcher bu yeteneğe katıldı (2026-09-07): iki ayrı medya
            # yeteneği bilgiyi bölüyordu — yönlendirme birini seçiyor, playbook ve
            # raporlar öbüründe duruyordu.
            "media-agency-soldier": [
                "medya", "ajans", "pazarlama", "reklam", "seo", "rakip analizi",
                "marka", "kampanya", "kitle", "competitor", "marketing", "branding",
                "web sitesi", "web site", "site", "sitesi", "siteyi", "website",
                "buyume", "büyüme", "trafik", "donusum", "dönüşüm", "optimizasyon",
                "landing", "e-ticaret", "eticaret", "magaza", "mağaza",
                "reklam kampanyasi", "google ads", "meta ads", "tiktok ads", "cro",
                "donusum orani", "landing page", "reklam metni", "ad copy", "medya plani"
            ]
        }
        # Anlamsal imza için de kullanılır (_skill_vector): açıklamalar çoğunlukla
        # kısa ya da İngilizce; Türkçe anahtar kelimeler yeteneğin Türkçe niyet
        # uzayındaki asıl çıpasıdır.
        self._domain_keywords_cache = domain_keywords

        ranked: List[Tuple[SkillDefinition, float]] = []

        for s in skills:
            score = 0.0
            s_name_norm = normalize_str(s.name.replace('-', ' '))
            s_clean_name = normalize_str(s.name)

            if re.search(rf"\b{re.escape(s_name_norm)}\b", p_norm) or re.search(rf"\b{re.escape(s_clean_name)}\b", p_norm):
                score += 8.0

            # Autonomous agent high priority concept boost
            if s.name in ["autonomous-agent", "autonomous_agent"]:
                agent_triggers = [
                    r"\bajan(?![s])\w*\b",
                    r"\balt\s*ajan\w*\b",
                    r"\bsub[-_]?agent\w*\b",
                    r"\borkestrat[oö]r\w*\b",
                    r"\bteamwork\w*\b",
                    r"\bagent\s*desk\w*\b",
                    r"\bofis\w*\b",
                    r"\bspace\w*\b",
                    r"\bpixel\s*agent\w*\b"
                ]
                for trig in agent_triggers:
                    if re.search(trig, p_norm):
                        score += 8.0
                        break

            # Check domain keywords with word boundaries and Turkish agglutinative suffixes
            kw_list = domain_keywords.get(s.name, [])
            for kw in kw_list:
                kw_norm = normalize_str(kw)
                if re.search(rf"\b{re.escape(kw_norm)}\b", p_norm):
                    score += 5.0
                    break
                elif kw_norm == "ajan":
                    if re.search(r"\bajan(?![s])\w*\b", p_norm):
                        score += 4.5
                        break
                elif len(kw_norm) >= 4 and re.search(rf"\b{re.escape(kw_norm)}\w*\b", p_norm):
                    score += 4.5
                    break

            # Check tags with strict word boundary enforcement (\b) to prevent short tags (e.g. 'erc')
            # from falsely triggering inside unrelated words (e.g. 'gerçekleştirecek')
            if s.tags:
                for tag in s.tags:
                    tag_norm = normalize_str(tag.replace('-', ' '))
                    tag_clean = normalize_str(tag)
                    if re.search(rf"\b{re.escape(tag_norm)}\b", p_norm) or re.search(rf"\b{re.escape(tag_clean)}\b", p_norm):
                        score += 4.0
                    elif len(tag_clean) > 3 and (re.search(rf"\b{re.escape(tag_norm)}\b", p_norm) or re.search(rf"\b{re.escape(tag_clean)}\b", p_norm)):
                        score += 3.0
                    elif len(tag_norm) >= 4 and any(
                        (tag_norm == pt or (len(pt) >= 5 and tag_norm.startswith(pt))) for pt in p_tokens if len(pt) >= 4
                    ):
                        score += 2.0

            # Check description words
            desc_score = 0.0
            desc_norm = normalize_str(s.description or "")
            desc_words = set(w for w in re.findall(r'\w+', desc_norm) if len(w) >= 4)
            for pt in p_tokens:
                if re.search(rf"\b{re.escape(pt)}\b", desc_norm):
                    desc_score += 2.0
                elif any(dw.startswith(pt) or pt.startswith(dw) for dw in desc_words if min(len(dw), len(pt)) >= 4):
                    desc_score += 1.0

            # BM25 uzunluk cezası YALNIZCA açıklamadan gelen puana uygulanır.
            #
            # Neden: ceza, uzun bir açıklamanın rastgele kelime çakışmasıyla puan
            # şişirmesini engellemek için var. Ama önceki sürüm cezayı toplam
            # puana uyguluyordu; ad, alan anahtar kelimesi ve etiket eşleşmeleri
            # açıklama uzunluğundan tamamen bağımsız olmasına rağmen onlar da
            # bölünüyordu. Sonuç ölçüldü: financial-auditor'ın SKILL.md açıklaması
            # damıtmayla 3.877 karaktere büyüdüğü için bölen 2,94'e çıkmıştı;
            # "hisse" gibi tam bir anahtar kelime eşleşmesi (+5,0) karar eşiğinin
            # (3,0) altına, 1,70'e düşüyordu. pdf-analyzer'ın böleni 1,07 olduğu
            # için aynı mesajı o kazanıyordu. Yani yeteneğin dokümantasyonunu
            # zenginleştirmek yönlendirilebilirliğini cezalandırıyordu.
            norm_score = score + desc_score / (1.0 + 0.0005 * len(s.description or ""))

            # 2. Anlamsal benzerlik bonusu (taban altı sıfır, tavanla sınırlı).
            if use_semantic and cosine_similarity is not None:
                try:
                    sim = cosine_similarity(query_vec, self._skill_vector(s))
                    norm_score += min(self._SEMANTIC_CAP, max(0.0, sim - self._SEMANTIC_FLOOR) * self._SEMANTIC_GAIN)
                except Exception:
                    pass

            # 3. Göndermeli takipte son yetenek önceliği: açık ve güçlü bir anahtar
            # kelime eşleşmesini ezmeyecek, ama boşlukta ya da eşitlikte kazanacak kadar.
            if is_anaphoric_followup and s.name == last_skill:
                norm_score += self._ANAPHORA_PRIOR

            ranked.append((s, norm_score))

        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked

    def auto_detect_skill_for_prompt(
        self,
        prompt: str,
        last_skill: Optional[str] = None,
        history: Optional[List[str]] = None,
    ) -> Optional[SkillDefinition]:
        """Mesaj için seçilen yetenek; eşiğin altındaysa None (yetenek zorlanmaz)."""
        return self.score_skill_for_prompt(prompt, last_skill=last_skill, history=history)[0]

    def score_skill_for_prompt(
        self,
        prompt: str,
        last_skill: Optional[str] = None,
        history: Optional[List[str]] = None,
    ) -> Tuple[Optional[SkillDefinition], float]:
        """
        Seçilen yetenek ve kararın güven puanı (0–1).

        Güven iki şeyi birleştirir: skorun karar eşiğine göre gücü ve ikinciyle
        arasındaki fark. İkisi de gerekli — tek başına yüksek skor iki yeteneğin
        başa baş olduğu durumu gizler, tek başına fark ise iki zayıf adaydan
        birinin öne çıkmasını güçlü karar gibi gösterir.

        Ölçek kasıtlı olarak eşikte 0,5'ten kırılır: eşiğin altındaki (yetenek
        seçilmeyen) durumlar 0–0,5 aralığında kalır, seçilen kararlar 0,5–1,0.
        Böylece arayüz tek bir sayıya bakarak "yetenek yok" ile "zayıf eşleşme"yi
        ayırt edebilir.
        """
        ranked = self.rank_skills_for_prompt(prompt, last_skill=last_skill, history=history)
        if not ranked:
            return None, 0.0

        threshold = float(self._DECISION_THRESHOLD) or 1.0
        best_skill, best_score = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0.0

        if best_score < threshold:
            return None, max(0.0, min(0.5, (best_score / threshold) * 0.5))

        strength = min(1.0, (best_score - threshold) / (2.0 * threshold))
        margin = min(1.0, max(0.0, best_score - second) / threshold)
        return best_skill, round(0.5 + 0.25 * strength + 0.25 * margin, 4)

    # Katalogda her yeteneğe ayrılan azami açıklama uzunluğu.
    MANIFEST_DESC_CHARS = 130
    # Genişletilmiş yetenekte listelenecek azami araç sayısı.
    MANIFEST_MAX_SCRIPTS = 12

    # --- Yetenek enjeksiyon bütçesi (Hotfix 0.7.1) --------------------------
    # Tek bir yeteneğin isteme yazabileceği azami karakter. SKILL.md gövdeleri
    # 45 KB'a kadar çıkıyor (financial-auditor); tam gövde ASLA yapıştırılmaz,
    # "özet + ilgili bölüm" kırpılır ve tam metnin YOLU verilir — model gerekirse
    # `Read` ile kendisi açar. 12.000 karakter ≈ 3.000 token.
    SKILL_INJECTION_CHAR_BUDGET = 12_000
    # Kataloğun tamamı (tüm yetenekler + seçili yeteneğin ayrıntısı) için tavan.
    SKILLS_INJECTION_TOTAL_BUDGET = 20_000

    def skill_injection_text(self, skill, query: str = "") -> str:
        """
        Bir yeteneğin isteme yazılacak, BÜTÇELİ gövdesi.

        Sıra: özet -> sorguya en yakın başlık bölümleri -> "tam metin şurada"
        satırı. Bütçe aşılırsa bölüm eklemesi durur; kesilen metin hiçbir zaman
        sessizce kaybolmaz, çünkü SKILL.md yolu her zaman istemde yer alır.
        """
        if skill is None:
            return ""
        body = (getattr(skill, "instructions", "") or "").strip()
        head = f"[YETENEK: {getattr(skill, 'name', '')}]\nÖzet: {getattr(skill, 'description', '')}"
        tail = f"\nTam yönergeler: {getattr(skill, 'path', '')} (gerekirse Read ile aç)."
        budget = self.SKILL_INJECTION_CHAR_BUDGET - len(head) - len(tail)
        if budget <= 0 or not body:
            return head + tail
        if len(body) <= budget:
            return f"{head}\n{body}{tail}"
        # Kırpma: markdown başlıklarına göre bölüp sorguyla örtüşen bölümleri
        # önceliklendir. Sıraya göre kesmek (ilk N karakter) yordamın ortasını
        # kaybettiriyordu; alaka sırası en azından ilgili adımları getirir.
        blocks = re.split(r"\n(?=#{1,6}\s)", body)
        words = {w for w in re.findall(r"\w+", (query or "").lower()) if len(w) > 3}

        def score(block: str) -> int:
            low = block.lower()
            return sum(1 for w in words if w in low)

        ordered = sorted(range(len(blocks)), key=lambda i: (-score(blocks[i]), i))
        chosen: List[int] = []
        used = 0
        for i in ordered:
            b = blocks[i]
            if used + len(b) + 1 > budget:
                continue
            chosen.append(i)
            used += len(b) + 1
        if not chosen:
            return f"{head}\n{body[:budget].rstrip()}\n[…kırpıldı…]{tail}"
        parts = [blocks[i] for i in sorted(chosen)]
        note = "\n[…SKILL.md kısaltıldı; eksik bölümler için dosyayı okuyun…]"
        return f"{head}\n" + "\n".join(parts) + note + tail

    def _script_label(self, script: Dict[str, str]) -> str:
        path = Path(script.get("path", ""))
        try:
            if config.default_project_path in path.parents:
                return f"python {path.relative_to(config.default_project_path)}"
        except (ValueError, TypeError):
            pass
        return script.get("name", path.name)

    def get_skills_manifest(self, active_skill: Optional[str] = None) -> str:
        """
        Yetenek kataloğunu prompt önsözü olarak üretir (kademeli açığa çıkarma).

        Katalog her turda enjekte edildiği için kısa olmalıdır. Önceki sürüm her
        yeteneğin tam açıklamasını ve TÜM script yollarını yazıyordu; 15 yetenekte
        bu 12.000 karakteri (~3.000 token) buluyor ve bütçeli bilişsel bağlamın
        tamamından daha fazla yer tutuyordu — üstelik içeriğin çoğu o turla ilgisiz.

        Bu yüzden: tüm yetenekler tek satırlık özetle listelenir, yalnızca o tur
        için seçilmiş yetenek araçlarıyla birlikte genişletilir.
        """
        skills = [s for s in self.list_skills() if s.enabled]
        if not skills:
            return ""

        lines = ["\n[AKTİF YETENEKLER & ARAÇ KÜTÜPHANESİ (SKILLS)]"]
        lines.append("Kullanımınıza sunulan uzmanlaşmış yetenekler:")

        for s in sorted(skills, key=lambda x: x.name):
            desc = " ".join((s.description or "").split())
            if len(desc) > self.MANIFEST_DESC_CHARS:
                desc = desc[: self.MANIFEST_DESC_CHARS].rstrip() + "…"
            tool_hint = f" [{len(s.scripts)} araç]" if s.scripts else ""
            lines.append(f"- 🎯 {s.name}: {desc}{tool_hint}")

        # Seçili yetenek tam ayrıntısıyla açılır: ajanın o turda gerçekten
        # kullanacağı araçların çağrılabilir adlarını görmesi gerekir.
        if active_skill:
            target = next((s for s in skills if s.name == active_skill), None)
            if target and target.scripts:
                shown = [self._script_label(sc) for sc in target.scripts[: self.MANIFEST_MAX_SCRIPTS]]
                extra = len(target.scripts) - len(shown)
                suffix = f" (+{extra} araç daha)" if extra > 0 else ""
                lines.append(f"\n[SEÇİLİ YETENEK: {target.name}] Çalıştırılabilir araçlar:")
                lines.extend(f"  • {label}" for label in shown)
                if suffix:
                    lines.append(f"  {suffix.strip()}")

        lines.append(
            "\nKURAL: Kullanıcının talebi için mevcut bir yetenek gerekiyorsa onun yönergelerine uyun. "
            "Bir yeteneğin ayrıntısına ihtiyacınız varsa 'skills/<yetenek_adi>/SKILL.md' dosyasını okuyun. "
            "Gereken yetenek yoksa, SKILL.md ve Python scripti oluşturarak kendinize yeni bir yetenek kazandırabilirsiniz."
        )
        text = "\n".join(lines)
        # Sert tavan: katalog her turda enjekte edilir, sınırsız büyümemeli.
        # 20.000 karakter ≈ 5.000 token; aşılırsa kural satırı korunarak kesilir.
        if len(text) > self.SKILLS_INJECTION_TOTAL_BUDGET:
            keep = self.SKILLS_INJECTION_TOTAL_BUDGET - len(lines[-1]) - 40
            text = (
                text[: max(0, keep)].rstrip()
                + "\n[…katalog kısaltıldı…]\n"
                + lines[-1]
            )
        return text


class SkillWatcher(QObject):
    """
    Yetenek dizinlerini canlı izler ve değişimde `bus.skills_updated` yayar.

    İnternetten indirilen ya da başka bir CLI tarafından yazılan bir SKILL.md,
    uygulamayı yeniden başlatmadan görünmeli. İki katmanlı çalışır:
      1. QFileSystemWatcher — keşfedilen her yetenek kökü ve onun birinci
         seviye alt dizinleri izlenir; dosya sistemi olayı anında tetikler.
      2. Hafif yoklama (varsayılan 5 sn) — henüz var olmayan bir kök sonradan
         oluşturulduğunda (izleyici yok olan yolu izleyemez) ya da olayın
         düştüğü ağ/senkron sürücülerde yedek olarak çalışır.

    Yoklama diski yormaz: yalnızca keşfedilen köklerin bir seviyesindeki
    SKILL.md dosyalarının (yol, mtime) imzası karşılaştırılır.
    """

    def __init__(self, project_dir: Optional[Path] = None, poll_interval_ms: int = 5000, parent=None):
        super().__init__(parent)
        self._project_dir: Optional[Path] = Path(project_dir) if project_dir else None
        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.directoryChanged.connect(self._schedule_check)
        self._fs_watcher.fileChanged.connect(self._schedule_check)

        # Toplu kopyalamalarda (zip açma, git checkout) onlarca olay art arda
        # gelir; borç biriktirmemek için tek bir gecikmeli kontrole indirilir.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(400)
        self._debounce.timeout.connect(self._check_now)

        self._poll = QTimer(self)
        self._poll.setInterval(max(1000, int(poll_interval_ms)))
        self._poll.timeout.connect(self._check_now)

        self._signature = self._compute_signature()

    # -- kamu API'si ---------------------------------------------------------
    def start(self) -> "SkillWatcher":
        self._sync_watch_paths()
        self._poll.start()
        try:
            bus.project_changed.connect(self.set_project_dir)
        except Exception:
            pass
        return self

    def stop(self) -> None:
        self._poll.stop()
        self._debounce.stop()
        paths = self._fs_watcher.directories() + self._fs_watcher.files()
        if paths:
            self._fs_watcher.removePaths(paths)
        try:
            bus.project_changed.disconnect(self.set_project_dir)
        except Exception:
            pass

    @Slot(str)
    def set_project_dir(self, project_dir) -> None:
        self._project_dir = Path(project_dir) if project_dir else None
        self._sync_watch_paths()
        self._schedule_check()

    def watched_dirs(self) -> List[str]:
        return list(self._fs_watcher.directories())

    # -- iç işleyiş ----------------------------------------------------------
    def _skill_roots(self) -> List[Path]:
        try:
            return discover_skill_dirs(self._project_dir)
        except Exception:
            return []

    def _compute_signature(self):
        sig = []
        for root in self._skill_roots():
            direct = root / "SKILL.md"
            candidates = [direct]
            try:
                candidates.extend(child / "SKILL.md" for child in root.iterdir() if child.is_dir())
            except OSError:
                pass
            for f in candidates:
                try:
                    sig.append((str(f), f.stat().st_mtime_ns))
                except OSError:
                    continue
        return frozenset(sig)

    def _sync_watch_paths(self) -> None:
        wanted = set()
        for root in self._skill_roots():
            wanted.add(str(root))
            # Kökün üstü de izlenir: `.agents/skills` henüz yokken `.agents`
            # içine açılan yeni bir klasör de olay üretsin.
            if root.parent.is_dir():
                wanted.add(str(root.parent))
            try:
                for child in root.iterdir():
                    if child.is_dir():
                        wanted.add(str(child))
            except OSError:
                pass

        current = set(self._fs_watcher.directories())
        stale = current - wanted
        if stale:
            self._fs_watcher.removePaths(sorted(stale))
        fresh = wanted - current
        if fresh:
            self._fs_watcher.addPaths(sorted(fresh))

    @Slot()
    def _schedule_check(self, *_args) -> None:
        self._debounce.start()

    @Slot()
    def _check_now(self) -> None:
        self._sync_watch_paths()
        new_sig = self._compute_signature()
        if new_sig != self._signature:
            self._signature = new_sig
            bus.skills_updated.emit()


_skill_watcher: Optional[SkillWatcher] = None


def start_skill_watcher(project_dir: Optional[Path] = None, poll_interval_ms: int = 5000) -> SkillWatcher:
    """Süreç genelinde tek bir yetenek izleyicisi başlatır (yeniden çağrı güvenli)."""
    global _skill_watcher
    if _skill_watcher is None:
        _skill_watcher = SkillWatcher(project_dir=project_dir, poll_interval_ms=poll_interval_ms)
        _skill_watcher.start()
    elif project_dir:
        _skill_watcher.set_project_dir(project_dir)
    return _skill_watcher


def stop_skill_watcher() -> bool:
    """
    Süreç genelindeki yetenek izleyicisini durdurur; durdurulduysa True.

    Kapanışta gerekli: QFileSystemWatcher ve iki QTimer, Qt olay döngüsü sona
    ererken hâlâ diriyse yetenek dizinlerinde açık tanıtıcı tutar ve zamanlayıcı
    yıkım sırasında ateşlenebilir. Yeniden çağrı güvenli.
    """
    global _skill_watcher
    if _skill_watcher is None:
        return False
    try:
        _skill_watcher.stop()
    except Exception:
        pass
    _skill_watcher = None
    return True


def extract_skill_source_from_text(text: str) -> Optional[str]:
    """Detect if a user prompt or message contains a skill URL, repo link, or local path to import."""
    text_clean = text.strip()
    # 1. URL pattern: GitHub repo, tree, or raw/direct file
    url_m = re.search(r'(https?://(?:github\.com/[^\s]+|[^\s]+\.(?:md|zip)))', text_clean, re.IGNORECASE)
    if url_m:
        return url_m.group(1).rstrip('>)"\'.,;')
    # 2. Local path ending in SKILL.md, .zip, or .md
    path_m = re.search(r'([A-Za-z]:[\\/][^\s\r\n"\'<>]+(?:[sS][kK][iI][lL][lL]\.[mM][dD]|\.zip|\.md))', text_clean)
    if path_m:
        return path_m.group(1).strip()
    # 3. Any existing local absolute directory or file mentioned in prompt
    for cand_m in re.finditer(r'([A-Za-z]:[\\/][^\s\r\n"\'<>]+)', text_clean):
        cand = cand_m.group(1).rstrip('.,;:')
        try:
            p_cand = Path(cand)
            if p_cand.exists() and (p_cand.is_dir() or p_cand.suffix.lower() in [".zip", ".md"]):
                return str(p_cand)
        except Exception:
            pass
    return None


