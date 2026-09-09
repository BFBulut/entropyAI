"""
Ofisler: bir orkestratör, bir değerlendirici ve birkaç üye ajandan oluşan ekip.

Neden ayrı bir kavram: tek ajan bir kartı baştan sona yapmak zorunda kalınca ya
bağlamı taşıyamıyor ya da kendi çıktısını kendi notluyordu. Ofis üç şeyi ayırır:
planlama (orkestratör), üretim (üyeler, paralel) ve değerlendirme (ayrı ajan).

Kaynak — ajanlar ve kartlar gibi — kasadaki düz markdown:

    <kasa>/Entropy/Offices/<ofis>/OFFICE.md
    ---
    name: arastirma-ofisi
    purpose: Bir soruyu kaynaklarıyla araştırıp rapora çevirir.
    orchestrator: orkestrator
    evaluator: degerlendirici
    members: [arastirmaci, analist, yazar]
    default_provider: agy
    default_model: gemini-3.8-flash-high
    max_parallel: 2
    budget_tokens: 120000
    ---
    # arastirma-ofisi
    <ofis tüzüğü: ne yapar, kabul standartları>

Gövde (tüzük) planlama ve değerlendirme prompt'larının başına konur; ofisin
"kabul standardı" tek yerde yazılı olsun diye. `MEMORY.md` bu modülün işi değil,
bellek katmanı (entropy.memory) yazar.
"""

from __future__ import annotations

import datetime
import shutil
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional

from entropy.agents.registry import parse_frontmatter, render_frontmatter

OFFICES_SUBDIR = "Entropy/Offices"
OFFICE_FILENAME = "OFFICE.md"

# Manifest bölümü üst sınırı (karakter). ~4 karakter ≈ 1 token; 480 karakter
# ≈ 120 token — sözleşmedeki bütçe. Her turda enjekte edildiği için sert sınır.
OFFICE_MANIFEST_CHAR_BUDGET = 480

DEFAULT_MAX_PARALLEL = 2
DEFAULT_BUDGET_TOKENS = 120000


@dataclass
class OfficeSpec:
    """Tek bir ofis tanımı (OFFICE.md dosyasının bellek içi karşılığı)."""

    name: str
    purpose: str = ""
    orchestrator: str = ""
    evaluator: str = ""
    members: List[str] = field(default_factory=list)
    default_provider: str = "agy"
    default_model: str = ""
    max_parallel: int = DEFAULT_MAX_PARALLEL
    budget_tokens: int = DEFAULT_BUDGET_TOKENS
    charter: str = ""
    path: Optional[Path] = None
    updated_at: str = ""

    def to_frontmatter(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "orchestrator": self.orchestrator,
            "evaluator": self.evaluator,
            "members": list(self.members or []),
            "default_provider": self.default_provider or "agy",
            "default_model": self.default_model,
            "max_parallel": self.max_parallel,
            "budget_tokens": self.budget_tokens,
        }

    def roster(self) -> List[str]:
        """Ofiste görevi olan tüm ajanlar (yinelenmeden, sıralı)."""
        out: List[str] = []
        for name in [self.orchestrator, self.evaluator, *(self.members or [])]:
            if name and name not in out:
                out.append(name)
        return out


DEFAULT_OFFICES: List[OfficeSpec] = [
    OfficeSpec(
        name="arastirma-ofisi",
        purpose="Bir soruyu kaynaklarıyla araştırır, çözümler ve rapora çevirir.",
        orchestrator="orkestrator",
        evaluator="degerlendirici",
        members=["arastirmaci", "analist", "yazar"],
        default_provider="agy",
        default_model="gemini-3.8-flash-high",
        max_parallel=DEFAULT_MAX_PARALLEL,
        budget_tokens=DEFAULT_BUDGET_TOKENS,
        charter=(
            "Bu ofis bir soruyu uçtan uca araştırır ve tek bir rapora bağlar.\n\n"
            "Kabul standartları:\n"
            "- Her iddianın kaynağı ya da hesabı gösterilir; kaynaksız cümle "
            "'doğrulanmadı' diye işaretlenir.\n"
            "- Alt görevler birbirinin işini tekrarlamaz; her biri tek bir "
            "soruya yanıt verir.\n"
            "- Son çıktı Türkçe, başlıklı markdown; sonunda açık işler listesi "
            "bulunur.\n"
            "- Yapılamayan madde sessizce atlanmaz, 'yapılamadı' diye yazılır."
        ),
    ),
]


class OfficeRegistry:
    """
    Kasadaki ofis tanımlarının CRUD'u.

    `AgentRegistry` ile aynı ilke: durum tutmaz, her okuma diski görür. Ofis
    dosyalarını kullanıcı da (Obsidian) Entropy de yazabildiği için bellek içi
    önbellek hızla bayatlardı.
    """

    def __init__(self, vault_path: Optional[Path | str] = None):
        if vault_path is None:
            from entropy.core.config import config

            vault_path = config.obsidian_vault_path
        self.vault_path = Path(vault_path)
        self.offices_dir = self.vault_path / OFFICES_SUBDIR

    # -- yollar --------------------------------------------------------

    def office_dir(self, name: str) -> Path:
        return self.offices_dir / name

    def office_file(self, name: str) -> Path:
        return self.office_dir(name) / OFFICE_FILENAME

    # -- okuma ---------------------------------------------------------

    def list(self) -> List[OfficeSpec]:
        specs: List[OfficeSpec] = []
        try:
            if not self.offices_dir.is_dir():
                return specs
            for child in sorted(self.offices_dir.iterdir()):
                if not child.is_dir():
                    continue
                spec = self._read(child / OFFICE_FILENAME)
                if spec is not None:
                    specs.append(spec)
        except OSError:
            return specs
        return specs

    def get(self, name: str) -> Optional[OfficeSpec]:
        return self._read(self.office_file(name))

    @staticmethod
    def _int(value, fallback: int) -> int:
        try:
            out = int(str(value).strip())
        except (TypeError, ValueError):
            return fallback
        return out if out > 0 else fallback

    def _read(self, path: Path) -> Optional[OfficeSpec]:
        try:
            if not path.is_file():
                return None
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        front, body = parse_frontmatter(text)
        name = str(front.get("name") or path.parent.name).strip()
        if not name:
            return None
        members = front.get("members") or []
        if isinstance(members, str):
            members = [m.strip() for m in members.split(",") if m.strip()]
        provider = str(front.get("default_provider") or "agy").strip().lower()
        try:
            updated = datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            updated = ""
        return OfficeSpec(
            name=name,
            purpose=str(front.get("purpose") or ""),
            orchestrator=str(front.get("orchestrator") or ""),
            evaluator=str(front.get("evaluator") or ""),
            members=[str(m) for m in members],
            default_provider=provider if provider in ("agy", "claude") else "agy",
            default_model=str(front.get("default_model") or ""),
            max_parallel=self._int(front.get("max_parallel"), DEFAULT_MAX_PARALLEL),
            budget_tokens=self._int(front.get("budget_tokens"), DEFAULT_BUDGET_TOKENS),
            charter=body,
            path=path,
            updated_at=updated,
        )

    # -- yazma ---------------------------------------------------------

    def create(self, spec: OfficeSpec) -> OfficeSpec:
        if self.office_file(spec.name).exists():
            raise FileExistsError(f"'{spec.name}' adında bir ofis zaten var.")
        return self._write(spec)

    def update(self, spec: OfficeSpec) -> OfficeSpec:
        return self._write(spec)

    def _write(self, spec: OfficeSpec) -> OfficeSpec:
        if not (spec.name or "").strip():
            raise ValueError("Ofis adı boş olamaz.")
        path = self.office_file(spec.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        body = (spec.charter or "").strip()
        if not body.startswith("#"):
            body = f"# {spec.name}\n\n{body}".strip()
        content = f"{render_frontmatter(spec.to_frontmatter())}\n\n{body}\n"
        path.write_text(content, encoding="utf-8")
        self._notify(spec.name)
        return replace(spec, path=path)

    def delete(self, name: str) -> bool:
        target = self.office_dir(name)
        if not target.is_dir():
            return False
        shutil.rmtree(target, ignore_errors=True)
        self._notify(name)
        return not target.exists()

    @staticmethod
    def _notify(name: str) -> None:
        try:
            from entropy.core.event_bus import bus

            bus.offices_updated.emit(name)
        except Exception:
            pass

    # -- varsayılanlar --------------------------------------------------

    def ensure_defaults(self) -> List[str]:
        """
        Tohum ofisi yalnızca HİÇ ofis yoksa yazar; oluşturulan adları döndürür.

        Ajan tohumlamasıyla aynı gerekçe: kullanıcı `arastirma-ofisi`ni bilinçli
        sildiyse her açılışta geri gelmemeli.
        """
        if self.list():
            return []
        created: List[str] = []
        for spec in DEFAULT_OFFICES:
            try:
                self._write(spec)
                created.append(spec.name)
            except Exception:
                continue
        return created


# ---------------------------------------------------------------------------
# Manifest bölümü
# ---------------------------------------------------------------------------


def offices_manifest(registry: Optional[OfficeRegistry] = None) -> str:
    """
    Prompt'a enjekte edilen "Ofisler" bölümü (≤ ~120 token).

    Kural satırı kasıtlı: Entropy kapsamlı bir işi tek ajana vermek yerine ofise
    devredebilsin diye komutun tam biçimi manifeste yazılır.
    """
    try:
        registry = registry or OfficeRegistry()
        specs = registry.list()
    except Exception:
        return ""
    if not specs:
        return ""

    lines = ["[OFİSLER]"]
    for spec in specs:
        purpose = " ".join((spec.purpose or "").split())
        if len(purpose) > 70:
            purpose = purpose[:67] + "..."
        row = f"- 🏢 {spec.name} · {purpose or '-'} · orkestratör: {spec.orchestrator or '-'}"
        if len("\n".join(lines)) + len(row) > OFFICE_MANIFEST_CHAR_BUDGET:
            lines.append("- … (tam liste için /offices)")
            break
        lines.append(row)
    lines.append(
        "KURAL: Kapsamlı, çok adımlı işleri tek ajana verme; "
        "`/desk task <ofis> <başlık> :: <hedef>` ile ofise devret."
    )
    return "\n".join(lines)
