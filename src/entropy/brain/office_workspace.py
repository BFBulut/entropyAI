"""
Dosya tabanlı ortak çalışma belleği (Faz 10-A / 1).

Ofisteki ajanlar birbirleriyle görünmez API'lerle değil, ofis kökündeki düz
dosyalarla konuşur. Bir ajan doğduğunda ilk komutu "BOARD ve ARCHITECTURE
dosyalarını oku"dur; iş bitince kontrol noktası yazar. Böylece durum ne sohbet
geçmişinde ne de bellekte kalır — çökmeden sağ çıkar ve kullanıcı da aynı
dosyaları Obsidian'da okuyabilir.

Neden ofis kökü, kullanıcının depo klasörü değil: depo dosyaları kullanıcıya
aittir, ajanların iç panosu orayı kirletmemelidir. Bu yüzden dosyalar

    <kasa>/Desk/Offices/<ofis>/workspace/
        BOARD.md            <- kartlardan üretilir (türev, elle düzenlenmez)
        ARCHITECTURE.md     <- orkestratör doldurur (kaynak)
        RULES.md            <- onaylı kurallardan üretilir (türev)
        checkpoints/<kart-id>.md

altında durur ve alt ajanlara **mutlak yolla** verilir.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from entropy.core import paths as _paths

__all__ = [
    "WORKSPACE_DIRNAME",
    "SPAWN_INSTRUCTION_MAX_CHARS",
    "ARCHITECTURE_SECTIONS",
    "workspace_dir",
    "ensure_workspace",
    "render_board",
    "board_markdown",
    "update_architecture",
    "spawn_instruction",
]

DESK_OFFICES_SUBDIR = _paths.DESK_SUBDIR
WORKSPACE_DIRNAME = "workspace"

# Doğuş talimatının karakter tavanı: bu metin her alt ajan koşusunda isteme
# girer, uzarsa asıl görev için yer kalmaz.
SPAWN_INSTRUCTION_MAX_CHARS = 1200

ARCHITECTURE_SECTIONS = ("Amaç", "Bileşenler", "Kararlar", "Açık sorular")
CHANGELOG_SECTION = "Değişiklik günlüğü"

BOARD_COLUMNS = ("Durum", "Ajan", "Başlık", "Hedef", "Son not")

# Pano hücrelerinin tavanı: tablo tek ekranda okunabilir kalmalı.
_CELL_MAX = 80
_BOARD_ROW_LIMIT = 60


def _safe(name: str) -> str:
    cleaned = "".join(
        c if c.isalnum() or c in " -_" else "_" for c in (name or "")
    ).strip()
    return cleaned or "office"


def _vault_root(vault_path: Optional[Path] = None) -> Path:
    if vault_path is not None:
        return Path(vault_path)
    from entropy.core.config import config

    return Path(config.obsidian_vault_path)


def office_root(office: str, vault_path: Optional[Path] = None) -> Path:
    return _vault_root(vault_path) / DESK_OFFICES_SUBDIR / _safe(office)


def workspace_dir(office: str, vault_path: Optional[Path] = None) -> Path:
    """Ofisin ortak çalışma klasörü (mutlak)."""
    return office_root(office, vault_path) / WORKSPACE_DIRNAME


def workspace_paths(office: str, vault_path: Optional[Path] = None) -> Dict[str, Path]:
    root = workspace_dir(office, vault_path)
    return {
        "workspace": root,
        "board": root / "BOARD.md",
        "architecture": root / "ARCHITECTURE.md",
        "rules": root / "RULES.md",
        "checkpoints": root / "checkpoints",
    }


# ------------------------------------------------------------------ pano


def _cell(value: str) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > _CELL_MAX:
        text = text[: _CELL_MAX - 1].rstrip() + "…"
    # Tablo hücresinde boru işareti sütunu bozar.
    return text.replace("|", "/") or "-"


def _cards(office: str, vault_path: Optional[Path] = None) -> List[object]:
    """Ofis kartları; kart katmanı yoksa boş liste (memory katmanı ona bağımlı değil)."""
    try:
        from entropy.agents.tasks import TaskBoard
    except Exception:
        return []
    try:
        board = TaskBoard(vault_path) if vault_path is not None else TaskBoard()
        return list(board.list(office=office) or [])
    except Exception:
        return []


def _last_note(card) -> str:
    for attr in ("summary", "notes", "result"):
        value = getattr(card, attr, "") or ""
        if value:
            return str(value).splitlines()[0]
    return ""


def board_markdown(office: str, cards: Optional[List[object]] = None,
                   vault_path: Optional[Path] = None) -> str:
    """
    BOARD.md gövdesi. Deterministiktir: tarih/saat içermez, aynı kart kümesi
    aynı metni verir (idempotentlik testinin dayanağı budur).
    """
    rows = cards if cards is not None else _cards(office, vault_path)
    ordered = sorted(
        rows,
        key=lambda c: (
            _STATUS_ORDER.get((getattr(c, "status", "") or "").lower(), 9),
            str(getattr(c, "id", "")),
        ),
    )[:_BOARD_ROW_LIMIT]
    out: List[str] = [
        f"# Pano — {office}",
        "",
        "> Kartlardan üretilir; elle düzenleme bir sonraki güncellemede kaybolur.",
        "",
        "| " + " | ".join(BOARD_COLUMNS) + " |",
        "|" + "|".join([" --- "] * len(BOARD_COLUMNS)) + "|",
    ]
    for card in ordered:
        out.append(
            "| "
            + " | ".join(
                [
                    _cell(getattr(card, "status", "")),
                    _cell(getattr(card, "agent", "")),
                    _cell(getattr(card, "title", "") or getattr(card, "id", "")),
                    _cell(getattr(card, "goal", "")),
                    _cell(_last_note(card)),
                ]
            )
            + " |"
        )
    if not ordered:
        out.append("| - | - | (kart yok) | - | - |")
    out.append("")
    return "\n".join(out)


_STATUS_ORDER = {
    "running": 0,
    "review": 1,
    "backlog": 2,
    "failed": 3,
    "done": 4,
}


def render_board(
    office: str,
    cards: Optional[List[object]] = None,
    vault_path: Optional[Path] = None,
) -> Path:
    """
    Panoyu diske yazar ve yolunu döndürür.

    İçerik değişmediyse dosyaya DOKUNULMAZ: kasa OneDrive'da olduğu için her
    kart okumasında mtime değiştirmek gereksiz eşitleme trafiği demektir.
    """
    path = workspace_paths(office, vault_path)["board"]
    text = board_markdown(office, cards, vault_path)
    try:
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            return path
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ------------------------------------------------------------------ mimari


def _architecture_skeleton(office: str, project_path: Optional[str] = None) -> str:
    lines = [f"# Mimari — {office}", ""]
    if project_path:
        lines += [f"- Proje dizini: {project_path}", ""]
    lines += [
        "> Bu dosyanın sahibi orkestratördür. Alt ajanlar okur, yazmaz.",
        "",
    ]
    for section in ARCHITECTURE_SECTIONS:
        lines += [f"## {section}", "", "-", ""]
    lines += [f"## {CHANGELOG_SECTION}", "", "-", ""]
    return "\n".join(lines)


def _split_sections(text: str):
    head: List[str] = []
    order: List[str] = []
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for line in (text or "").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            if current not in sections:
                sections[current] = []
                order.append(current)
            continue
        if current is None:
            head.append(line)
        else:
            sections[current].append(line)
    return head, order, sections


def _join_sections(head: List[str], order: List[str], sections: Dict[str, List[str]]) -> str:
    parts = ["\n".join(head).rstrip()]
    for name in order:
        body = "\n".join(sections.get(name, [])).strip()
        parts.append(f"## {name}\n\n{body or '-'}")
    return "\n\n".join(p for p in parts if p).rstrip() + "\n"


def update_architecture(
    office: str,
    text: str,
    author: str = "",
    section: Optional[str] = None,
    replace: bool = False,
    vault_path: Optional[Path] = None,
) -> Path:
    """
    ARCHITECTURE.md'yi günceller.

    `section` verilmezse metin "Kararlar" bölümüne eklenir. `replace=True` ise
    bölümün gövdesi değiştirilir, aksi halde satır olarak eklenir. Her çağrı
    dosya içindeki "Değişiklik günlüğü" bölümüne bir satır düşer; ayrı `_archive`
    klasörü YOKTUR — tarihçe belgeyle aynı dosyada kalsın ki devralan ajan tek
    okumada neyin neden değiştiğini görsün.
    """
    paths = workspace_paths(office, vault_path)
    path = paths["architecture"]
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
    except OSError:
        current = ""
    if not current.strip():
        current = _architecture_skeleton(office)

    target = (section or "Kararlar").strip()
    head, order, sections = _split_sections(current)
    if target not in sections:
        sections[target] = []
        insert_at = order.index(CHANGELOG_SECTION) if CHANGELOG_SECTION in order else len(order)
        order.insert(insert_at, target)

    body = [ln for ln in sections[target] if ln.strip() and ln.strip() != "-"]
    new_lines = [ln.rstrip() for ln in str(text or "").strip().splitlines() if ln.strip()]
    formatted = [ln if ln.startswith(("-", "*", "#", "|", ">")) else f"- {ln}" for ln in new_lines]
    sections[target] = formatted if replace else body + formatted

    stamp = datetime.now().isoformat(timespec="seconds")
    who = author or "-"
    entry = f"- {stamp} — {who} — {target}: {' '.join(new_lines)[:120]}"
    if CHANGELOG_SECTION not in sections:
        sections[CHANGELOG_SECTION] = []
        order.append(CHANGELOG_SECTION)
    log = [ln for ln in sections[CHANGELOG_SECTION] if ln.strip() and ln.strip() != "-"]
    sections[CHANGELOG_SECTION] = (log + [entry])[-50:]

    path.write_text(_join_sections(head, order, sections), encoding="utf-8")
    return path


# ------------------------------------------------------------------ kurulum


def ensure_workspace(
    office: str,
    project_path: Optional[str] = None,
    vault_path: Optional[Path] = None,
) -> Dict[str, Path]:
    """
    Çalışma klasörünü ve dosyalarını kurar; yol sözlüğünü döndürür.

    Idempotenttir: var olan ARCHITECTURE.md'nin üzerine YAZMAZ (orkestratörün
    yazdığı içerik kaybolmasın), BOARD.md ile RULES.md ise türev oldukları için
    her çağrıda yeniden üretilir.
    """
    paths = workspace_paths(office, vault_path)
    paths["workspace"].mkdir(parents=True, exist_ok=True)
    paths["checkpoints"].mkdir(parents=True, exist_ok=True)

    if not paths["architecture"].is_file():
        paths["architecture"].write_text(
            _architecture_skeleton(office, project_path), encoding="utf-8"
        )
    render_board(office, vault_path=vault_path)

    from entropy.memory import promoted_rules

    try:
        rules_md = promoted_rules.render_rules_markdown(office, vault_path=vault_path)
    except Exception:
        rules_md = "# Kurallar\n"
    if not paths["rules"].is_file() or paths["rules"].read_text(encoding="utf-8") != rules_md:
        paths["rules"].write_text(rules_md, encoding="utf-8")
    return paths


# ------------------------------------------------------------------ doğuş talimatı


def spawn_instruction(
    office: str,
    card_id: Optional[str] = None,
    agent: Optional[str] = None,
    vault_path: Optional[Path] = None,
    max_chars: int = SPAWN_INSTRUCTION_MAX_CHARS,
) -> str:
    """
    Bir ajan doğduğunda isteminin başına konan talimat.

    Sıra sabittir: (1) okunacak dosyalar MUTLAK yolla, (2) varsa kontrol noktası
    özeti, (3) onaylı kurallar. Metinde ürünün adı GEÇMEZ: alt ajanlar hangi
    uygulamanın içinde koştuklarını bilmez, yalnızca ofislerini bilir.
    (Yolların içindeki klasör adları teknik bir zorunluluktur.)
    """
    paths = workspace_paths(office, vault_path)
    limit = max(0, int(max_chars))
    blocks: List[str] = []
    head = [
        "İşe başlamadan önce şu dosyaları oku:",
        f"1. {paths['board']}  (pano: kimin hangi kartta olduğu)",
        f"2. {paths['architecture']}  (mimari: amaç, bileşenler, kararlar)",
    ]
    if paths["rules"].is_file():
        head.append(f"3. {paths['rules']}  (onaylı kurallar)")
    head.append(
        "Bu dosyalar ofisin ortak belleğidir; işin bitince kontrol noktası yaz."
    )
    blocks.append("\n".join(head))

    if card_id:
        from entropy.memory import checkpoints as _checkpoints

        try:
            resume = _checkpoints.resume_section(office, card_id, vault_path)
        except Exception:
            resume = ""
        if resume:
            blocks.append(resume)

    from entropy.memory import promoted_rules

    try:
        rules = promoted_rules.rules_section(office, agent, vault_path=vault_path)
    except Exception:
        rules = ""
    if rules:
        blocks.append(rules)

    text = "\n\n".join(blocks)
    while len(text) > limit and len(blocks) > 1:
        blocks.pop()  # önce kurallar, sonra kontrol noktası düşer; dosya listesi kalır
        text = "\n\n".join(blocks)
    if len(text) > limit:
        cut = text[:limit]
        nl = cut.rfind("\n")
        text = (cut[:nl] if nl > limit * 0.6 else cut).rstrip()
    return text
