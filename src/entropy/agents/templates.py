"""
Ekip şablonları (Faz 10-C / 10.10).

Şablon = **adı olmayan bir ofis klasörü**:

    Desk/Templates/<şablon>/
        OFFICE.md              ofis ön bilgisi + tüzük
        agents/<ajan>/AGENT.md alt ajan tanımı (orkestratör YOK)

Bu yüzden yeni bir ayrıştırıcı yazılmaz: `OFFICE.md` ve `AGENT.md`
`registry.parse_frontmatter` ile okunur, defterin kendi şemasına çevrilir.

Üç kural:

1. **Tohum ofis yok.** Şablon bir ofis yaratmaz; yalnızca kullanıcı bir ofis
   açarken uygulanır. Orkestratör her ofiste zaten otomatik doğar
   (`DeskRegistry.create` → `ensure_orchestrator`), şablon onun YANINA alt
   ajanları koyar.
2. **Sağlayıcı şablondan gelmez.** Şablon dosyaları `provider:` alanını BOŞ
   bırakır; sağlayıcı ofisin `default_provider`'ından, o da `config.provider`
   üstünden gelir. Aksi hâlde "agy sabiti" şablonlar üzerinden geri sızardı.
3. **Var olan ad ezilmez.** Aynı şablon iki kez uygulanınca ajanlar çoğalmaz ve
   kullanıcının elle düzelttiği istem korunur (`_apply_new_agents` deseni).

Paket içi varsayılan dört şablon (`entropy/desk/templates/`) ilk kullanımda
kasaya KOPYALANIR ki kullanıcı düzenleyebilsin; kasada zaten varsa dokunulmaz.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional

from entropy.core import paths as _paths
from entropy.agents.registry import AgentSpec, VALID_PROVIDERS, default_provider, parse_frontmatter

logger = logging.getLogger(__name__)

__all__ = [
    "BUILTIN_TEMPLATES",
    "packaged_templates_dir",
    "templates_dir",
    "ensure_templates",
    "list_templates",
    "read_template",
    "template_model",
    "apply_template",
    "create_office_from_template",
]

OFFICE_FILENAME = "OFFICE.md"
AGENT_FILENAME = "AGENT.md"
AGENTS_DIRNAME = "agents"

# Paketten gelen dört varsayılan şablon (klasör adları).
BUILTIN_TEMPLATES = ("arastirma", "refaktor", "qa", "medya")


def packaged_templates_dir() -> Path:
    """Paket içindeki şablon kökü (PyInstaller `datas` ile birlikte taşınır)."""
    return Path(__file__).resolve().parent.parent / "desk" / "templates"


def templates_dir(vault_path: Optional[Path | str] = None) -> Path:
    return _paths.desk_templates_dir(vault_path)


def ensure_templates(vault_path: Optional[Path | str] = None) -> List[str]:
    """
    Paketteki varsayılan şablonları kasaya kopyalar; VAR OLANA DOKUNMAZ.

    Dönüş: bu çağrıda kasaya yazılan şablon adları.
    """
    src_root = packaged_templates_dir()
    dst_root = templates_dir(vault_path)
    written: List[str] = []
    if not src_root.is_dir():
        return written
    for name in BUILTIN_TEMPLATES:
        src = src_root / name
        dst = dst_root / name
        if not src.is_dir() or dst.exists():
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst)
            written.append(name)
        except OSError:
            logger.warning("Şablon kasaya kopyalanamadı: %s", name)
    return written


def _read_office_front(path: Path) -> Dict[str, object]:
    try:
        front, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    data = dict(front)
    data["charter"] = body
    return data


def read_template(name: str, vault_path: Optional[Path | str] = None) -> Optional[Dict[str, object]]:
    """Tek şablonun okunmuş hâli: ofis ön bilgisi + alt ajan tanımları."""
    ensure_templates(vault_path)
    root = templates_dir(vault_path) / name
    if not root.is_dir():
        root = packaged_templates_dir() / name
        if not root.is_dir():
            return None
    office = _read_office_front(root / OFFICE_FILENAME)
    if not office:
        return None
    agents: List[Dict[str, object]] = []
    agents_root = root / AGENTS_DIRNAME
    if agents_root.is_dir():
        for child in sorted(agents_root.iterdir()):
            file = child / AGENT_FILENAME if child.is_dir() else child
            if not file.is_file() or file.suffix.lower() != ".md":
                continue
            try:
                front, body = parse_frontmatter(file.read_text(encoding="utf-8"))
            except OSError:
                continue
            row = dict(front)
            row["prompt"] = body
            row.setdefault("name", child.stem)
            agents.append(row)
    return {"name": name, "path": root, "office": office, "agents": agents}


def list_templates(vault_path: Optional[Path | str] = None) -> List[Dict[str, object]]:
    """Kasadaki (ve pakettekiler kopyalandıktan sonra tüm) şablonların künyesi."""
    ensure_templates(vault_path)
    root = templates_dir(vault_path)
    out: List[Dict[str, object]] = []
    if not root.is_dir():
        return out
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        data = read_template(child.name, vault_path)
        if data is None:
            continue
        office = data["office"]  # type: ignore[index]
        out.append({
            "name": child.name,
            "title": str(office.get("title") or child.name),  # type: ignore[union-attr]
            "purpose": str(office.get("purpose") or ""),  # type: ignore[union-attr]
            "agents": [str(a.get("name") or "") for a in data["agents"]],  # type: ignore[index]
        })
    return out


def template_model(front: Dict[str, object], provider: str) -> str:
    """
    Şablonun o sağlayıcı için önerdiği model (`models: {claude: …, agy: …}`).

    Neden: şablonların `default_model` alanı boştu ve ofisten doğan orkestratör
    modelsiz koşuyordu — yani üst çubuktaki model neyse (çoğu kez en pahalı
    olan) planlamayı o yapıyordu. Kota dostu varsayılan artık şablonda yazılı;
    kullanıcı ofis düzenleme formundan değiştirebilir.

    Düz `model_claude` / `model_agy` anahtarları da okunur (PyYAML yoksa iç içe
    eşleme ayrıştırılamıyor, `registry` ile aynı geri düşüş).
    """
    p = (provider or "").strip().lower()
    if p not in VALID_PROVIDERS:
        return ""
    models: Dict[str, str] = {}
    nested = front.get("models")
    if isinstance(nested, dict):
        for key, value in nested.items():
            key = str(key).strip().lower()
            if key in VALID_PROVIDERS and value:
                models[key] = str(value).strip()
    for name in VALID_PROVIDERS:
        value = front.get(f"model_{name}")
        if value:
            models[name] = str(value).strip()
    model = models.get(p, "")
    if not model:
        return ""
    # Sağlayıcıya ait olmayan ad (ör. şablon güncellenmemiş) sessizce
    # bırakılmaz: geçersiz `--model` CLI'ı `unrecognized_model` ile öldürüyordu.
    try:
        from entropy.core.config import is_valid_model_for

        if not is_valid_model_for(p, model):
            return ""
    except Exception:
        pass
    return model


def _spec_from_row(row: Dict[str, object], office_name: str, provider: str,
                   model: str) -> AgentSpec:
    name = str(row.get("name") or "").strip()
    role = str(row.get("role") or "worker").strip().lower()
    if role == "orchestrator":
        # Ofisin tek orkestratörü vardır ve o `ensure_orchestrator` ile doğar.
        role = "worker"
    return AgentSpec(
        name=name,
        role=role,
        description=str(row.get("description") or ""),
        provider=provider,
        model=model,
        effort=str(row.get("effort") or ""),
        tools_policy=str(row.get("tools_policy") or "read-write").strip().lower(),
        memory_path=f"memory/{name}.md",
        prompt=str(row.get("prompt") or "").strip(),
        office=office_name,
    )


def apply_template(desk, office_name: str, template: str,
                   provider: Optional[str] = None) -> List[str]:
    """
    Şablonun kadrosunu var olan bir ofise uygular; var olan adı EZMEZ.

    Dönüş: bu çağrıda gerçekten yazılan ajan adları.
    """
    data = read_template(template, getattr(desk, "vault_path", None))
    if data is None:
        raise ValueError(f"'{template}' adında şablon yok.")
    office = desk.get(office_name)
    if office is None:
        raise ValueError(f"'{office_name}' adında ofis yok.")
    resolved = (provider or office.default_provider or default_provider()).strip().lower()
    if resolved not in VALID_PROVIDERS:
        resolved = default_provider()
    agents = desk.agents(office_name)
    created: List[str] = []
    for row in data["agents"]:  # type: ignore[index]
        name = str(row.get("name") or "").strip()
        if not name or name == (office.orchestrator or ""):
            continue
        if agents.get(name) is not None:
            continue
        spec = _spec_from_row(
            row, office_name, resolved,
            office.default_model or template_model(data["office"], resolved),  # type: ignore[arg-type]
        )
        try:
            agents.update(spec)
        except Exception:
            logger.warning("Şablon ajanı yazılamadı: %s/%s", template, name)
            continue
        created.append(name)
    return created


def create_office_from_template(
    template: str,
    office_name: str,
    provider: Optional[str] = None,
    desk=None,
    vault_path: Optional[Path | str] = None,
):
    """
    Şablondan ofis açar: orkestratör + şablonun alt ajanları.

    Var olan bir ofis adını EZMEZ (`FileExistsError`). Ofisin amacı, tüzüğü,
    paralelliği ve bütçesi şablondan gelir; sağlayıcı `provider` ya da
    `config.provider` üstünden çözülür — şablon dosyası sağlayıcı dayatmaz.
    """
    from entropy.agents.desk_registry import DeskOffice, DeskRegistry

    desk = desk or DeskRegistry(vault_path=vault_path)
    data = read_template(template, getattr(desk, "vault_path", None))
    if data is None:
        raise ValueError(f"'{template}' adında şablon yok.")
    front = data["office"]  # type: ignore[index]
    resolved = (provider or "").strip().lower()
    if resolved not in VALID_PROVIDERS:
        resolved = default_provider()

    def _int(key: str, fallback: int) -> int:
        try:
            return int(str(front.get(key) or fallback).strip() or fallback)  # type: ignore[union-attr]
        except (TypeError, ValueError):
            return fallback

    spec = DeskOffice(
        name=office_name,
        purpose=str(front.get("purpose") or ""),  # type: ignore[union-attr]
        evaluator=str(front.get("evaluator") or ""),  # type: ignore[union-attr]
        default_provider=resolved,
        # Model şablondan: boş bırakılırsa ofis (ve orkestratörü) üst çubuğun
        # modeliyle koşuyordu; kota dostu varsayılan şablonda yazılı.
        default_model=(
            str(front.get("default_model") or "").strip()  # type: ignore[union-attr]
            or template_model(front, resolved)  # type: ignore[arg-type]
        ),
        default_effort=str(front.get("default_effort") or ""),  # type: ignore[union-attr]
        max_parallel=_int("max_parallel", 2),
        budget_tokens=_int("budget_tokens", 120000),
        charter=str(front.get("charter") or ""),  # type: ignore[union-attr]
    )
    office = desk.create(spec)
    apply_template(desk, office_name, template, provider=resolved)
    return desk.get(office_name) or office
