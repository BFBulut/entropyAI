"""Antigravity-compliant Skills & Self-Tooling Management Engine."""

import json
import re
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

from entropy.core.config import config
from entropy.core.event_bus import bus

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

class SkillManager:
    """Discovers, parses, synthesizes, and executes Antigravity-compatible skills."""

    def __init__(self, root_skills_dir: Optional[Path] = None):
        self.root_skills_dir = root_skills_dir or (config.default_project_path / "skills")
        self.root_skills_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = Path.home() / ".entropy" / "skills_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._enabled_cache: Dict[str, bool] = self._load_state()

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

    def list_skills(self) -> List[SkillDefinition]:
        """Scan skills directory and parse all SKILL.md specifications."""
        skills = []
        if not self.root_skills_dir.exists():
            return skills

        for skill_dir in sorted(self.root_skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            parsed = self.parse_skill_file(skill_file)
            if parsed:
                skills.append(parsed)

        return skills

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
                tags=[t.strip() for t in frontmatter.get("tags", "").split(",") if t.strip()]
            )
        except Exception as e:
            return None

    def toggle_skill(self, name: str, enabled: bool) -> bool:
        """Enable or disable a skill."""
        self._enabled_cache[name] = enabled
        self._save_state()
        return True

    def delete_skill(self, name: str) -> bool:
        """Permanently delete a skill directory."""
        skill_dir = self.root_skills_dir / name
        if skill_dir.exists():
            import shutil
            shutil.rmtree(skill_dir, ignore_errors=True)
            if name in self._enabled_cache:
                del self._enabled_cache[name]
                self._save_state()
            bus.terminal_output_received.emit(f"[Yetenek Merkezi] '{name}' yeteneği silindi.\n")
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
        clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '-', name.lower().strip()).strip('-')
        skill_dir = self.root_skills_dir / clean_name
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

        return SkillDefinition(
            name=clean_name,
            description=description,
            instructions=instructions,
            path=str(skill_file.resolve()),
            scripts=created_scripts,
            enabled=True
        )

    def download_skill_from_url(self, url: str, override_name: Optional[str] = None) -> Optional[SkillDefinition]:
        """Download raw SKILL.md from a web or GitHub URL and register it."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "EntropyAI/1.0"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw_text = resp.read().decode("utf-8", errors="replace")

            # Try to determine name from frontmatter
            name_match = re.search(r'name:\s*([a-zA-Z0-9_\-]+)', raw_text)
            skill_name = override_name or (name_match.group(1) if name_match else "downloaded-skill")
            clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '-', skill_name.lower()).strip('-')

            desc_match = re.search(r'description:\s*(?:>-|>)?\s*([^\n]+)', raw_text)
            description = desc_match.group(1).strip() if desc_match else f"İnternetten indirilen yetenek: {clean_name}"

            # Strip existing frontmatter for instructions body
            body_match = re.search(r'^---\s*\n.*?\n---\s*\n(.*)$', raw_text, re.DOTALL)
            instructions = body_match.group(1).strip() if body_match else raw_text

            return self.create_skill(clean_name, description, instructions)
        except Exception as e:
            bus.terminal_output_received.emit(f"[Yetenek İndirme Hatası] URL'den indirme başarısız oldu: {e}\n")
            return None

    def get_skills_manifest(self) -> str:
        """Generate a concise prompt preamble describing active skills and their tool scripts."""
        skills = [s for s in self.list_skills() if s.enabled]
        if not skills:
            return ""

        lines = ["\n[AKTİF YETENEKLER & ARAÇ KÜTÜPHANESİ (SKILLS)]"]
        lines.append("Şu anda kullanımınıza sunulan uzmanlaşmış yetenekler ve çalıştırılabilir scriptler:")
        for s in skills:
            script_info = ""
            if s.scripts:
                s_names = ", ".join([f"python {Path(sc['path']).relative_to(config.default_project_path)}" if config.default_project_path in Path(sc['path']).parents else sc['name'] for sc in s.scripts])
                script_info = f" (Araçlar: {s_names})"
            lines.append(f"- 🎯 {s.name}: {s.description}{script_info}")

        lines.append(
            "\nKURAL: Eğer kullanıcının talebi için mevcut bir yetenek gerekiyorsa, onun yönergelerine uyun. "
            "Eğer gereken yetenek veya araç sizde yoksa, 'skills/<yetenek_adi>/SKILL.md' ve Python scripti oluşturarak "
            "kendinize yeni bir araç/yetenek kazandırabilirsiniz."
        )
        return "\n".join(lines)
