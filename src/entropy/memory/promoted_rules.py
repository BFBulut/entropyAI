"""
Onaylı kalıcı kurallar (Faz 10-A / 3).

Ajanlar belleğe serbestçe yazamaz: bir alt ajan bir davranış kuralı keşfettiğinde
çıktısına `[KURAL] ...` satırı koyar, uygulama bunu **aday** olarak kaydeder ve
kullanıcıya sorar. Kullanıcı "kalıcı yap" derse kural `promoted` olur ve o günden
sonra HER koşuda ajanın sistem istemine enjekte edilir.

Neden ayrı depo: `agent_memory` (MEMORY.md) serbest metin bir günlüktür, kim ne
yazarsa girer. Kural deposu ise onay kapılı ve makine okunur olmalı — tek kaynak
`rules.json`, `RULES.md` ondan üretilen okunur bir kopyadır.

Yollar
------
Ofis:    <kasa>/Desk/Offices/<ofis>/memory/rules.json
Entropy: <kasa>/Entropy/Memory/rules.json          (office == "entropy")

Bu modül Qt bilmez: sinyal yaymaz, olay yollamaz. Kural değiştiğinde arayüzü
haberdar etmek harness'ın işidir.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from entropy.core import paths as _paths

__all__ = [
    "Rule",
    "RULE_MAX_CHARS",
    "RULES_SECTION_MAX_CHARS",
    "rules_path",
    "propose_rule",
    "list_rules",
    "promote",
    "reject",
    "rules_section",
    "render_rules_markdown",
    "parse_rule_candidates",
]

# Tek kuralın karakter tavanı. Bunu aşan metin kural değil, anlatıdır.
RULE_MAX_CHARS = 200
# Sistem istemine giren "Onaylı kurallar" bloğunun tavanı (ofis ajanları).
RULES_SECTION_MAX_CHARS = 1000
# Entropy'nin kendi isteminde bölüm 1'in sonuna eklenen blok daha dardır.
ENTROPY_RULES_MAX_CHARS = 600

STATUS_CANDIDATE = "candidate"
STATUS_PROMOTED = "promoted"
STATUS_REJECTED = "rejected"
STATUSES = (STATUS_CANDIDATE, STATUS_PROMOTED, STATUS_REJECTED)

# Entropy'nin kendi kural deposu ofis ağacında değil, kasanın kök belleğindedir.
ENTROPY_OFFICE = "entropy"

DESK_OFFICES_SUBDIR = _paths.DESK_SUBDIR
ENTROPY_MEMORY_SUBDIR = "Entropy/Memory"

# Alt ajan çıktısındaki kural satırı.
_RULE_LINE_RE = re.compile(r"^\s*(?:[-*]\s*)?\[KURAL\]\s*(.+?)\s*$", re.IGNORECASE)

# "Kural değil" süzgeci. Bir log satırı, yığın izi ya da dosya yolu kalıcı
# davranış kuralı olamaz; bunlar belleği çöple doldurup istemi şişirir.
_NOT_A_RULE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"traceback \(most recent call last\)", re.IGNORECASE),
    re.compile(r"\b\w*(Error|Exception|Warning)\b:"),
    re.compile(r"^\s*(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)\b", re.IGNORECASE),
    re.compile(r"\bfile\s+\"[^\"]+\",\s*line\s+\d+", re.IGNORECASE),
    re.compile(r"\bline\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bexit\s+code\s+\d+", re.IGNORECASE),
    # Mutlak yol ya da kaynak dosya adı: kurala değil kontrol noktasına aittir.
    re.compile(r"[A-Za-z]:\\\\|[A-Za-z]:[\\/]"),
    re.compile(r"(^|\s)/[\w./-]+\.\w{1,5}(\s|$)"),
    re.compile(r"\b[\w./\\-]+\.(py|md|json|log|txt|ts|tsx|js|yml|yaml)\b", re.IGNORECASE),
    re.compile(r"\bstack\s*trace\b", re.IGNORECASE),
    re.compile(r"\b(hata|istisna|çöktü|crash)\s*(ayrıntısı|mesajı|izi)?\s*:", re.IGNORECASE),
    re.compile(r"\blog(u|lar|ları|ları:)?\b\s*:", re.IGNORECASE),
)

# Kurala benzemeyen çok kısa parçalar da elenir.
_MIN_RULE_CHARS = 12


@dataclass
class Rule:
    """Tek bir kural kaydı."""

    id: str
    office: str
    text: str
    agent: str = ""
    source: str = ""
    status: str = STATUS_CANDIDATE
    # `office` -> ofisteki her ajana, `agent:<ad>` -> yalnızca o ajana.
    scope: str = "office"
    created_at: str = ""
    decided_at: str = ""
    extra: Dict[str, str] = field(default_factory=dict)

    def applies_to(self, agent: Optional[str]) -> bool:
        """Kural verilen ajan için geçerli mi? (`agent=None` -> ofis geneli)"""
        scope = (self.scope or "office").strip()
        if scope in ("", "office", "*"):
            return True
        if not scope.lower().startswith("agent:"):
            return True
        target = scope.split(":", 1)[1].strip().lower()
        return bool(agent) and target == str(agent).strip().lower()


# ------------------------------------------------------------------ yollar


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


def _is_entropy(office: str) -> bool:
    return str(office or "").strip().lower() == ENTROPY_OFFICE


def rules_path(office: str, vault_path: Optional[Path] = None) -> Path:
    """Kural deposunun dosya yolu (tek kaynak)."""
    root = _vault_root(vault_path)
    if _is_entropy(office):
        return root / ENTROPY_MEMORY_SUBDIR / "rules.json"
    return root / DESK_OFFICES_SUBDIR / _safe(office) / "memory" / "rules.json"


# ------------------------------------------------------------------ okuma/yazma


def _load(office: str, vault_path: Optional[Path] = None) -> List[Rule]:
    path = rules_path(office, vault_path)
    try:
        if not path.is_file():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = data.get("rules") if isinstance(data, dict) else data
    out: List[Rule] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            out.append(
                Rule(
                    id=str(row.get("id") or ""),
                    office=str(row.get("office") or office),
                    text=str(row.get("text") or ""),
                    agent=str(row.get("agent") or ""),
                    source=str(row.get("source") or ""),
                    status=str(row.get("status") or STATUS_CANDIDATE),
                    scope=str(row.get("scope") or "office"),
                    created_at=str(row.get("created_at") or ""),
                    decided_at=str(row.get("decided_at") or ""),
                    extra=dict(row.get("extra") or {}),
                )
            )
        except Exception:
            continue
    return [r for r in out if r.id and r.text]


def _save(office: str, rules: List[Rule], vault_path: Optional[Path] = None) -> Path:
    path = rules_path(office, vault_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"office": str(office), "rules": [asdict(r) for r in rules]}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp.replace(path)
    _sync_rules_markdown(office, rules, vault_path)
    return path


def _sync_rules_markdown(
    office: str, rules: List[Rule], vault_path: Optional[Path] = None
) -> None:
    """Onaylı kuralları ofis çalışma klasöründeki RULES.md'ye yansıtır."""
    if _is_entropy(office):
        return
    try:
        from entropy.memory import office_workspace

        target = office_workspace.workspace_dir(office, vault_path) / "RULES.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_rules_markdown(office, rules), encoding="utf-8")
    except Exception:
        # Markdown türevdir; yazılamazsa rules.json yine de doğrudur.
        return


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _dedupe_key(text: str) -> str:
    return _normalize(text).casefold().rstrip(". ")


def is_rule_like(text: str) -> bool:
    """Metin kalıcı bir davranış kuralı olabilir mi? (log/hata/yol -> hayır)"""
    cleaned = _normalize(text)
    if len(cleaned) < _MIN_RULE_CHARS:
        return False
    for pattern in _NOT_A_RULE_PATTERNS:
        if pattern.search(cleaned):
            return False
    return True


# ------------------------------------------------------------------ genel API


def propose_rule(
    office: str,
    agent: str,
    text: str,
    source: str = "",
    vault_path: Optional[Path] = None,
    scope: Optional[str] = None,
) -> Optional[Rule]:
    """
    Kural adayı kaydeder.

    Metin log/hata/yol içeriyorsa ya da çok kısaysa `None` döner (kural değildir).
    Aynı metin daha önce önerildiyse yeni kayıt açılmaz, var olan döner:
    tekilleştirme büyük/küçük harf ve boşluk farklarını yok sayar.
    `RULE_MAX_CHARS` üstü metin sözcük sınırından kırpılır.
    """
    cleaned = _normalize(text)
    if not is_rule_like(cleaned):
        return None
    if len(cleaned) > RULE_MAX_CHARS:
        cut = cleaned[:RULE_MAX_CHARS]
        space = cut.rfind(" ")
        cleaned = (cut[:space] if space > RULE_MAX_CHARS * 0.6 else cut).rstrip(" ,;")
    rules = _load(office, vault_path)
    key = _dedupe_key(cleaned)
    for existing in rules:
        if _dedupe_key(existing.text) == key:
            return existing
    rule = Rule(
        id=uuid.uuid4().hex[:12],
        office=str(office),
        text=cleaned,
        agent=str(agent or ""),
        source=str(source or ""),
        status=STATUS_CANDIDATE,
        scope=(scope or "office").strip() or "office",
        created_at=datetime.now().isoformat(timespec="seconds"),
    )
    rules.append(rule)
    _save(office, rules, vault_path)
    return rule


def list_rules(
    office: str, status: Optional[str] = None, vault_path: Optional[Path] = None
) -> List[Rule]:
    """Kurallar; `status` verilirse yalnızca o durumdakiler."""
    rules = _load(office, vault_path)
    if status is None:
        return rules
    wanted = str(status).strip().lower()
    return [r for r in rules if (r.status or "").lower() == wanted]


def _set_status(
    office: str, rule_id: str, status: str, vault_path: Optional[Path] = None
) -> Optional[Rule]:
    rules = _load(office, vault_path)
    hit: Optional[Rule] = None
    for rule in rules:
        if rule.id == rule_id:
            rule.status = status
            rule.decided_at = datetime.now().isoformat(timespec="seconds")
            hit = rule
            break
    if hit is None:
        return None
    _save(office, rules, vault_path)
    return hit


def promote(
    office: str, rule_id: str, vault_path: Optional[Path] = None
) -> Optional[Rule]:
    """Kullanıcı "kalıcı yap" dedi: kural onaylanır ve isteme enjekte edilir."""
    return _set_status(office, rule_id, STATUS_PROMOTED, vault_path)


def reject(
    office: str, rule_id: str, vault_path: Optional[Path] = None
) -> Optional[Rule]:
    """Kural reddedilir. Kayıt silinmez: aynı aday tekrar sorulmasın diye kalır."""
    return _set_status(office, rule_id, STATUS_REJECTED, vault_path)


def rules_section(
    office: str,
    agent: Optional[str] = None,
    vault_path: Optional[Path] = None,
    max_chars: int = RULES_SECTION_MAX_CHARS,
) -> str:
    """
    Sistem istemine giren "Onaylı kurallar" bloğu.

    YALNIZCA `promoted` kurallar girer; adaylar ve reddedilenler asla. `agent`
    verilirse ofis geneli kurallar + `agent:<ad>` kapsamlı kurallar döner.
    Boşsa boş dize döner (çağıran taraf ayırıcı eklemesin).
    """
    rules = [r for r in _load(office, vault_path) if r.status == STATUS_PROMOTED]
    rules = [r for r in rules if r.applies_to(agent)]
    if not rules:
        return ""
    head = "[ONAYLI KURALLAR]"
    lines: List[str] = []
    total = len(head)
    for rule in rules:
        line = f"- {rule.text}"
        if total + len(line) + 1 > max(0, int(max_chars)):
            break
        lines.append(line)
        total += len(line) + 1
    if not lines:
        return ""
    return "\n".join([head] + lines)


def render_rules_markdown(
    office: str, rules: Optional[List[Rule]] = None, vault_path: Optional[Path] = None
) -> str:
    """RULES.md gövdesi: onaylı kurallar + bekleyen adaylar (okunur türev)."""
    items = rules if rules is not None else _load(office, vault_path)
    promoted = [r for r in items if r.status == STATUS_PROMOTED]
    pending = [r for r in items if r.status == STATUS_CANDIDATE]
    out: List[str] = [
        "# Kurallar",
        "",
        "> Bu dosya `memory/rules.json` dosyasından üretilir; elle düzenleme"
        " bir sonraki güncellemede kaybolur.",
        "",
        "## Onaylı kurallar",
        "",
    ]
    if promoted:
        for rule in promoted:
            suffix = "" if rule.scope in ("", "office") else f"  _({rule.scope})_"
            out.append(f"- {rule.text}{suffix}")
    else:
        out.append("- (henüz onaylı kural yok)")
    out += ["", "## Bekleyen adaylar", ""]
    if pending:
        for rule in pending:
            out.append(f"- [ ] {rule.text}  `{rule.id}`")
    else:
        out.append("- (aday yok)")
    out.append("")
    return "\n".join(out)


def parse_rule_candidates(text: str) -> List[str]:
    """
    Alt ajan çıktısındaki `[KURAL] ...` satırlarını çıkarır.

    Süzgeçten geçmeyen (log/hata/yol) satırlar döndürülmez; böylece çağıran
    taraf kullanıcıya yalnızca gerçek aday sorar.
    """
    out: List[str] = []
    seen: set[str] = set()
    for line in (text or "").splitlines():
        m = _RULE_LINE_RE.match(line)
        if not m:
            continue
        candidate = _normalize(m.group(1))
        if not is_rule_like(candidate):
            continue
        key = _dedupe_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out
