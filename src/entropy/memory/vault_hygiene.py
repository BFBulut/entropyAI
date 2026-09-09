"""
Kasa hijyeni: artık klasörleri BULUR, silmez.

Neyi çözüyor
------------
Kasada iki tür çöp birikiyor:

1. `Entropy/AgentDesk/office_*` — Faz 6'da Desk ayrıldığında (tek kaynak
   `Entropy/Desk/Offices`) geride kalan eski ofis klasörleri. Rapor taraması
   bunları zaten atlıyor (`vault_manager._REPORT_SCAN_SKIP_DIRS`), ama kasa
   gezgininde ve graf kurmada gürültü yapıyorlar.
2. `Entropy/Desk/Offices/<ad>` altında `OFFICE.md` künyesi olmayan klasörler
   ("hayalet ofis"): genelde yalnız `layout.json` taşırlar, ofis grafı boştur.

Kural: bu modül **hiçbir şeyi silmez**. `archive_stale()` seçilen klasörleri
`Entropy/_archive/<tarih>/` altına TAŞIR ve varsayılan olarak kuru koşumdadır
(`dry_run=True`). Kullanıcının kasası bizim değil; geri alınamayan işlem yok.
"""

from __future__ import annotations

import datetime
import fnmatch
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from entropy.core.config import config

logger = logging.getLogger(__name__)

# Arşiv kökü (kasa içinde kalır ki kullanıcı Obsidian'dan görebilsin).
ARCHIVE_DIRNAME = "_archive"

# Eski AgentDesk artıklarının ad kalıbı. Kullanıcının elle açtığı klasörler
# ("global_template" gibi) varsayılan kalıba takılmaz.
STALE_AGENTDESK_PATTERN = "office_*"


def _entropy_dir(vault_path: Optional[Path] = None) -> Path:
    root = Path(vault_path) if vault_path else Path(config.obsidian_vault_path)
    return root / "Entropy"


def _dir_stats(path: Path) -> Dict[str, Any]:
    """Klasörün dosya sayısı ve toplam boyutu (rapor için, karar için değil)."""
    files = 0
    size = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                files += 1
                try:
                    size += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return {"files": files, "bytes": size}


def find_stale_agentdesk_dirs(
    vault_path: Optional[Path] = None,
    pattern: str = STALE_AGENTDESK_PATTERN,
) -> List[Dict[str, Any]]:
    """
    `Entropy/AgentDesk/` altındaki artık ofis klasörleri.

    Ad kalıbı `pattern` ile eşleşen ve `OFFICE.md` künyesi olmayan doğrudan
    alt klasörler döner. Künyesi olan klasör "artık" sayılmaz: kullanıcının
    henüz taşımadığı gerçek bir ofis olabilir.
    """
    base = _entropy_dir(vault_path) / "AgentDesk"
    if not base.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for child in sorted(p for p in base.iterdir() if p.is_dir()):
        if pattern and not fnmatch.fnmatch(child.name, pattern):
            continue
        if (child / "OFFICE.md").exists():
            continue
        entry = {"name": child.name, "path": str(child), "reason": "legacy_agentdesk"}
        entry.update(_dir_stats(child))
        out.append(entry)
    return out


def find_ghost_offices(vault_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    `Entropy/Desk/Offices/` altında `OFFICE.md` künyesi olmayan klasörler.

    Bunlar Desk yüzeyinde ofis gibi görünür ama künyesiz oldukları için
    `desk_roster()` onları eksik doldurur ve ofis grafı boş kalır.
    """
    from entropy.memory.office_graph import desk_offices_dir

    base = desk_offices_dir(vault_path)
    if not base.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for child in sorted(p for p in base.iterdir() if p.is_dir()):
        if (child / "OFFICE.md").exists():
            continue
        entry = {
            "name": child.name,
            "path": str(child),
            "reason": "missing_OFFICE.md",
            "entries": sorted(p.name for p in child.iterdir()),
        }
        entry.update(_dir_stats(child))
        out.append(entry)
    return out


def archive_stale(
    paths: Sequence[Any],
    vault_path: Optional[Path] = None,
    dry_run: bool = True,
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Verilen klasörleri `Entropy/_archive/<tarih>/` altına TAŞIR (silmez).

    `paths` öğeleri yol ya da `find_*` çıktısındaki sözlük olabilir.
    `dry_run=True` (varsayılan) hiçbir şeye dokunmaz, yalnızca planı döndürür.
    Kasa dışındaki ya da zaten arşivdeki yollar reddedilir (`skipped`).
    """
    root = _entropy_dir(vault_path)
    stamp = date or datetime.date.today().isoformat()
    archive_dir = root / ARCHIVE_DIRNAME / stamp

    planned: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    for item in paths or []:
        raw = item.get("path") if isinstance(item, dict) else item
        src = Path(str(raw or ""))
        if not str(raw or "").strip():
            continue
        try:
            src_resolved = src.resolve()
            inside = src_resolved.is_relative_to(root.resolve())
        except (OSError, ValueError):
            inside = False
            src_resolved = src
        if not inside:
            skipped.append({"path": str(src), "reason": "kasa_disi"})
            continue
        if ARCHIVE_DIRNAME in src_resolved.parts:
            skipped.append({"path": str(src), "reason": "zaten_arsivde"})
            continue
        if not src.is_dir():
            skipped.append({"path": str(src), "reason": "klasor_degil"})
            continue

        dst = archive_dir / src.name
        n = 2
        while dst.exists() or any(p["dst"] == str(dst) for p in planned):
            dst = archive_dir / f"{src.name}-{n}"
            n += 1
        planned.append({"src": str(src), "dst": str(dst)})

    moved: List[Dict[str, str]] = []
    if not dry_run:
        archive_dir.mkdir(parents=True, exist_ok=True)
        for plan in planned:
            try:
                shutil.move(plan["src"], plan["dst"])
                moved.append(plan)
            except OSError as exc:  # pragma: no cover - dosya kilidi/izin
                logger.warning("Arşive taşınamadı (%s): %s", plan["src"], exc)
                skipped.append({"path": plan["src"], "reason": f"tasima_hatasi: {exc}"})

    return {
        "archive_dir": str(archive_dir),
        "dry_run": bool(dry_run),
        "planned": planned,
        "moved": moved,
        "skipped": skipped,
        "count": len(moved) if not dry_run else len(planned),
    }
