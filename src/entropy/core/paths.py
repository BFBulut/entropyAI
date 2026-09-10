"""
Kasa içi yolların tek kaynağı — özellikle Agent Desk'in veri kökü (Faz 10-B).

Neden taşıdık
-------------
Desk ofislerinin verisi Faz 6'dan beri `<kasa>/Entropy/Desk/Offices/<ofis>/`
altındaydı. Bu teknik olarak çalışıyordu ama bir sözleşmeyi deliyordu: ofis
ajanları (orkestratör ve altları) çağıran uygulamanın varlığını bilmemeli.
Doğuş talimatı (`office_workspace.spawn_instruction`) alt ajanlara MUTLAK yol
verdiği için o yolun içindeki klasör adı istemin içine sızıyordu; testler bunu
"yol satırlarını ölçme" istisnasıyla geçiştiriyordu. İstisna yerine kökü
değiştirmek daha temiz: Desk'in kendi kasası kasa KÖKÜNDE `Desk/` olur.

    <kasa>/Desk/Offices/<ofis>/...     Desk'in verisi (ofisler, kartlar, posta)
    <kasa>/Desk/_migrations.log        kendiliğinden yapılan onarımların günlüğü
    <kasa>/Desk/Templates/             (ileride)

Uygulamanın KENDİ verisi yerinde kalır: `Entropy/Agents`, `Entropy/Tasks`,
`Entropy/Inbox`, `Entropy/Memory`, `Entropy/_archive`.

Geçiş
-----
`migrate_desk_root()` eski kökü yeni köke taşır. Sözleşmesi: **kopyala →
doğrula → sil**. Hedefte aynı adlı ofis varsa içerik birebir aynıysa kaynak
silinir, farklıysa hiçbir şeye dokunulmaz ve çakışma günlüğe düşer — iki
kaynaklı gerçeği sessizce çözmek veri kaybı riskidir. İdempotenttir: eski kök
yoksa çağrı bedavaya döner. `dry_run=True` (varsayılan) diske yazmaz.
"""

from __future__ import annotations

import datetime
import filecmp
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "DESK_ROOT_SUBDIR",
    "DESK_SUBDIR",
    "DESK_TEMPLATES_SUBDIR",
    "WORKTREE_ROOT_DIRNAME",
    "MIGRATION_LOG_SUBPATH",
    "BOARD_SUBDIR",
    "BOARD_TASKBOARD_SUBPATH",
    "BOARD_EVENTS_SUBPATH",
    "BOARD_EVENTS_ARCHIVE_SUBDIR",
    "BOARD_CLAIMS_SUBDIR",
    "BOARD_AGENTS_SUBDIR",
    "BOARD_PROJECTION_SUBPATH",
    "board_root",
    "board_events_path",
    "board_events_archive_dir",
    "board_taskboard_path",
    "board_claims_dir",
    "board_agents_dir",
    "board_projection_path",
    "agent_session_path",
    "LEGACY_DESK_ROOT_SUBDIRS",
    "LEGACY_DESK_SUBDIRS",
    "LEGACY_MIGRATION_LOG_SUBPATHS",
    "vault_root",
    "desk_root",
    "desk_offices_dir",
    "desk_templates_dir",
    "worktree_root_for",
    "migrations_log_path",
    "legacy_desk_roots",
    "legacy_desk_offices_dirs",
    "migrate_desk_root",
]

# --- sözleşme ---------------------------------------------------------------

# Desk'in veri kökü ve ofis kökü (kasaya göreli, POSIX ayraçlı).
DESK_ROOT_SUBDIR = "Desk"
DESK_SUBDIR = "Desk/Offices"
MIGRATION_LOG_SUBPATH = "Desk/_migrations.log"
# Ekip şablonları (Faz 10-C). Ofis DEĞİL: şablon yalnızca kullanıcı bir ofis
# açarken uygulanır; tohum ofis yasağı ihlal edilmez.
DESK_TEMPLATES_SUBDIR = "Desk/Templates"

# Kart başına git worktree kökünün klasör adı; depoya KOMŞU açılır.
WORKTREE_ROOT_DIRNAME = ".entropy-worktrees"

# --- Entropy Board (Faz 11-C) ------------------------------------------------
# Panonun ad alanı. KARTLAR TAŞINMAZ: `Entropy/Tasks/<id>.md` yerinde kalır
# (üçüncü bir kart göçü `TasksWatcher`'ın iki kökünü, `card_file()` arama
# sırasını ve kullanıcının Obsidian yer imlerini birden kırardı). `Board/`
# yalnızca PANONUN kendi verisini taşır: olay günlüğü, türetilmiş insan
# panosu, sahiplenme kiraları ve ajan oturum kimlikleri.
BOARD_SUBDIR = "Entropy/Board"
BOARD_TASKBOARD_SUBPATH = "Entropy/Board/TASKBOARD.md"
BOARD_EVENTS_SUBPATH = "Entropy/Board/events.jsonl"
BOARD_EVENTS_ARCHIVE_SUBDIR = "Entropy/Board/events"
BOARD_CLAIMS_SUBDIR = "Entropy/Board/claims"
BOARD_AGENTS_SUBDIR = "Entropy/Board/agents"
BOARD_PROJECTION_SUBPATH = "Entropy/Board/projection.json"

# Eski kökler. Sıra önemlidir: geçiş bunları bu sırayla tüketir.
LEGACY_DESK_ROOT_SUBDIRS = ("Entropy/Desk",)
LEGACY_DESK_SUBDIRS = ("Entropy/Desk/Offices",)
LEGACY_MIGRATION_LOG_SUBPATHS = ("Entropy/Desk/_migrations.log",)

# Geçiş günlüğüne düşen satırın etiketi.
_MIGRATION_TAG = "desk-kökü"

# Kasa başına bir kez koşma işareti (süreç ömrü).
_migrated_vaults: set = set()


# --- yollar -----------------------------------------------------------------


def vault_root(vault_path: Optional[Path | str] = None) -> Path:
    if vault_path is not None:
        return Path(vault_path)
    from entropy.core.config import config

    return Path(config.obsidian_vault_path)


def desk_root(vault_path: Optional[Path | str] = None) -> Path:
    """`<kasa>/Desk` — Desk'in kendi veri kökü."""
    return vault_root(vault_path) / DESK_ROOT_SUBDIR


def desk_offices_dir(vault_path: Optional[Path | str] = None) -> Path:
    """`<kasa>/Desk/Offices` — ofis klasörlerinin kökü."""
    return vault_root(vault_path) / DESK_SUBDIR


def migrations_log_path(vault_path: Optional[Path | str] = None) -> Path:
    """`<kasa>/Desk/_migrations.log`."""
    return vault_root(vault_path) / MIGRATION_LOG_SUBPATH


def desk_templates_dir(vault_path: Optional[Path | str] = None) -> Path:
    """`<kasa>/Desk/Templates` — ekip şablonlarının kasadaki kökü (Faz 10-C)."""
    return vault_root(vault_path) / DESK_TEMPLATES_SUBDIR


def board_root(vault_path: Optional[Path | str] = None) -> Path:
    """`<kasa>/Entropy/Board` — panonun ad alanı (kartlar burada DEĞİL)."""
    return vault_root(vault_path) / BOARD_SUBDIR


def board_events_path(vault_path: Optional[Path | str] = None) -> Path:
    """`<kasa>/Entropy/Board/events.jsonl` — yalnızca eklenen olay günlüğü."""
    return vault_root(vault_path) / BOARD_EVENTS_SUBPATH


def board_events_archive_dir(vault_path: Optional[Path | str] = None) -> Path:
    """`<kasa>/Entropy/Board/events/` — aylık döndürülmüş günlük arşivi."""
    return vault_root(vault_path) / BOARD_EVENTS_ARCHIVE_SUBDIR


def board_taskboard_path(vault_path: Optional[Path | str] = None) -> Path:
    """`<kasa>/Entropy/Board/TASKBOARD.md` — TÜRETİLMİŞ pano, elle yazılmaz."""
    return vault_root(vault_path) / BOARD_TASKBOARD_SUBPATH


def board_claims_dir(vault_path: Optional[Path | str] = None) -> Path:
    """`<kasa>/Entropy/Board/claims/` — kart başına sahiplenme kirası."""
    return vault_root(vault_path) / BOARD_CLAIMS_SUBDIR


def board_agents_dir(vault_path: Optional[Path | str] = None) -> Path:
    """`<kasa>/Entropy/Board/agents/` — ajan başına kalıcı oturum kimliği."""
    return vault_root(vault_path) / BOARD_AGENTS_SUBDIR


def agent_session_path(agent: str, vault_path: Optional[Path | str] = None) -> Path:
    """`<kasa>/Entropy/Board/agents/<ad>/session.json`."""
    safe = "".join(ch if (ch.isalnum() or ch in "-_") else "-"
                   for ch in str(agent or "").strip()) or "agent"
    return board_agents_dir(vault_path) / safe / "session.json"


def board_projection_path(vault_path: Optional[Path | str] = None) -> Path:
    """`<kasa>/Entropy/Board/projection.json` — son seq + projeksiyon karması."""
    return vault_root(vault_path) / BOARD_PROJECTION_SUBPATH


def worktree_root_for(repo_path: Path | str) -> Path:
    """
    Bir deponun kart worktree'lerinin kökü: `<repo>/../.entropy-worktrees`.

    İki ölçüme dayanıyor (Faz 10 araştırma notu §1.3): depo İÇİNDEKİ bir kök
    (`<repo>/.worktrees`) üst deponun `git status` çıktısını `?? .worktrees/`
    ile kirletiyor; 358 karakterlik bir yol ise `core.longpaths` kapalıyken
    `Filename too long` ile ölüyor. Depoya KOMŞU kök ikisini de çözer: git
    durumu temiz kalır ve yol kısa olur.
    """
    repo = Path(repo_path)
    return repo.parent / WORKTREE_ROOT_DIRNAME


def legacy_desk_roots(vault_path: Optional[Path | str] = None) -> List[Path]:
    root = vault_root(vault_path)
    return [root / sub for sub in LEGACY_DESK_ROOT_SUBDIRS]


def legacy_desk_offices_dirs(vault_path: Optional[Path | str] = None) -> List[Path]:
    root = vault_root(vault_path)
    return [root / sub for sub in LEGACY_DESK_SUBDIRS]


# --- geçiş ------------------------------------------------------------------


def _tree_stats(path: Path) -> Dict[str, int]:
    """Bir ağacın klasör/dosya sayısı ve toplam boyutu (kuru koşum raporu)."""
    dirs = files = size = 0
    try:
        for p in path.rglob("*"):
            try:
                if p.is_dir():
                    dirs += 1
                elif p.is_file():
                    files += 1
                    size += p.stat().st_size
            except OSError:
                continue
    except OSError:
        pass
    return {"dirs": dirs, "files": files, "bytes": size}


def _same_tree(left: Path, right: Path) -> bool:
    """İki ağaç birebir aynı mı (ad kümesi + dosya içerikleri)."""
    try:
        cmp = filecmp.dircmp(str(left), str(right))
    except OSError:
        return False
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    match, mismatch, errors = filecmp.cmpfiles(
        str(left), str(right), cmp.common_files, shallow=False
    )
    if mismatch or errors:
        return False
    for name in cmp.common_dirs:
        if not _same_tree(left / name, right / name):
            return False
    return True


def _verify_copy(src: Path, dst: Path) -> bool:
    """Kopya doğrulaması: silmeden önce hedef kaynağın aynısı olmalı."""
    if src.is_dir():
        return dst.is_dir() and _same_tree(src, dst)
    return dst.is_file() and filecmp.cmp(str(src), str(dst), shallow=False)


def _append_log(vault: Path, rows: List[str]) -> None:
    if not rows:
        return
    path = migrations_log_path(vault)
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(f"{stamp}\t{_MIGRATION_TAG}\t{row}\n")
    except OSError:
        logger.warning("Desk geçiş günlüğü yazılamadı: %s", path)


def _merge_legacy_log(vault: Path, dry_run: bool) -> Optional[Dict[str, Any]]:
    """Eski `_migrations.log`'u yeni yere ekler ve eskisini kaldırır."""
    for sub in LEGACY_MIGRATION_LOG_SUBPATHS:
        old = vault / sub
        if not old.is_file():
            continue
        info = {"from": str(old), "to": str(migrations_log_path(vault))}
        if dry_run:
            return info
        try:
            text = old.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return info
        new = migrations_log_path(vault)
        try:
            new.parent.mkdir(parents=True, exist_ok=True)
            with new.open("a", encoding="utf-8") as fh:
                if text and not text.endswith("\n"):
                    text += "\n"
                fh.write(text)
            old.unlink()
        except OSError:
            logger.warning("Eski geçiş günlüğü birleştirilemedi: %s", old)
        return info
    return None


def migrate_desk_root(
    vault_path: Optional[Path | str] = None, dry_run: bool = True
) -> Dict[str, Any]:
    """
    `Entropy/Desk/**` -> `Desk/**` taşıması (kopyala-doğrula-sil, idempotent).

    Döner: `{"dry_run", "applied", "moves", "merged", "conflicts", "removed",
    "log", "offices", "dirs", "files", "bytes"}`. `moves`/`merged`/`conflicts`
    öğeleri `{"name", "from", "to", "dirs", "files", "bytes"}` künyeleridir:
    `moves` taşınacak (taşınan), `merged` hedefte birebir aynısı bulunduğu için
    kaynağı silinen, `conflicts` hedefi FARKLI olduğu için dokunulmayanlardır.
    """
    vault = vault_root(vault_path)
    plan: Dict[str, Any] = {
        "dry_run": bool(dry_run),
        "applied": False,
        "moves": [],
        "merged": [],
        "conflicts": [],
        "removed": [],
        "log": None,
        "offices": 0,
        "dirs": 0,
        "files": 0,
        "bytes": 0,
    }
    dst_base = desk_offices_dir(vault)
    rows: List[str] = []

    for src_base in legacy_desk_offices_dirs(vault):
        if not src_base.is_dir():
            continue
        try:
            children = sorted(src_base.iterdir())
        except OSError:
            continue
        for child in children:
            target = dst_base / child.name
            stats = _tree_stats(child) if child.is_dir() else {
                "dirs": 0, "files": 1,
                "bytes": (child.stat().st_size if child.is_file() else 0),
            }
            entry = {
                "name": child.name,
                "from": str(child),
                "to": str(target),
                **stats,
            }
            if target.exists():
                if _verify_copy(child, target):
                    plan["merged"].append(entry)
                    if not dry_run:
                        _remove(child)
                        rows.append(f"kaynak-silindi\t{child}\t{target}\tözdeş")
                else:
                    plan["conflicts"].append(entry)
                    if not dry_run:
                        rows.append(f"çakışma\t{child}\t{target}\tdokunulmadı")
                continue
            plan["moves"].append(entry)
            if child.is_dir():
                plan["offices"] += 1
            if dry_run:
                continue
            if _copy_verify_remove(child, target):
                rows.append(f"taşındı\t{child}\t{target}")
            else:
                rows.append(f"doğrulanamadı\t{child}\t{target}")
                plan["conflicts"].append(entry)

    if dry_run:
        plan["offices"] = sum(1 for m in plan["moves"] if Path(m["from"]).is_dir())

    for entry in plan["moves"]:
        plan["dirs"] += int(entry.get("dirs") or 0)
        plan["files"] += int(entry.get("files") or 0)
        plan["bytes"] += int(entry.get("bytes") or 0)

    plan["log"] = _merge_legacy_log(vault, dry_run)

    if not dry_run:
        _append_log(vault, rows)
        for legacy in legacy_desk_roots(vault):
            plan["removed"].extend(_remove_if_empty_tree(legacy))
        plan["applied"] = True
    return plan


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except OSError:
            pass


def _copy_verify_remove(src: Path, dst: Path) -> bool:
    """Kopyala → doğrula → sil. Doğrulama düşerse kaynak DURUR."""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        else:
            shutil.copy2(str(src), str(dst))
    except OSError:
        logger.warning("Desk kökü taşınamadı: %s -> %s", src, dst, exc_info=True)
        return False
    if not _verify_copy(src, dst):
        logger.warning("Desk kökü taşıması doğrulanamadı: %s -> %s", src, dst)
        return False
    _remove(src)
    return True


def _remove_if_empty_tree(root: Path) -> List[str]:
    """Eski kökü, yalnızca ağacında dosya kalmadıysa (boşsa) kaldırır."""
    if not root.is_dir():
        return []
    try:
        if any(p.is_file() for p in root.rglob("*")):
            return []
    except OSError:
        return []
    try:
        shutil.rmtree(root)
    except OSError:
        return []
    removed = [str(root)]
    # Kalan boş `Entropy/` gibi ara klasörler silinmez: onlar bizim değil.
    return removed


def migrate_desk_root_once(vault_path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Kasa başına bir kez koşan sarmalayıcı (`DeskRegistry.__init__` çağırır)."""
    vault = vault_root(vault_path)
    key = str(vault.resolve()) if vault.exists() else str(vault)
    if key in _migrated_vaults:
        return {"skipped": True}
    _migrated_vaults.add(key)
    try:
        return migrate_desk_root(vault, dry_run=False)
    except Exception:
        logger.warning("Desk kökü geçişi yapılamadı.", exc_info=True)
        return {"skipped": False, "error": True}
