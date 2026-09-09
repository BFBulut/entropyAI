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


def office_residue(
    office: str, vault_path: Optional[Path] = None
) -> Dict[str, List[str]]:
    """
    Bir ofisin, ofis klasörü DIŞINDA kalan izleri: wiki sorgu sayfaları + posta.

    Teşhis §8: `dogrulama` ofisi arşive taşındıktan sonra
    `Entropy/Wiki/queries/2026-09-09-dogrulama-readme-ozeti.md` geride kaldı ve
    rapor taraması onu hâlâ rapor sayıyordu (wiki sorgu sayfaları `query`
    türünde künye üretir). Ofis arşivlenirken bu izler de taşınmalı.

    Eşleşme kuralı bilerek dar: dosya adı **tire ile ayrılmış bir alan** olarak
    ofis adını içermeli (`-<ofis>-`, `<ofis>-…`, `…-<ofis>`). Kullanıcının elle
    yazdığı, ofis adını cümle içinde geçiren sayfalar taşınmaz.
    """
    root = _entropy_dir(vault_path)
    name = str(office or "").strip().lower()
    out: Dict[str, List[str]] = {"queries": [], "mail": []}
    if not name:
        return out

    queries_dir = root / "Wiki" / "queries"
    if queries_dir.is_dir():
        for page in sorted(queries_dir.glob("*.md")):
            if f"-{name}-" in f"-{page.stem.lower()}-":
                out["queries"].append(str(page))

    inbox_dir = root / "Inbox"
    if inbox_dir.is_dir():
        import json as _json

        for msg in sorted(inbox_dir.glob("*.json")):
            try:
                data = _json.loads(msg.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            parties = {
                str(data.get("from") or "").strip().lower(),
                str(data.get("to") or "").strip().lower(),
            }
            if name in parties:
                out["mail"].append(str(msg))
    return out


def archive_office(
    office: Any,
    vault_path: Optional[Path] = None,
    dry_run: bool = True,
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Bir ofisi arşive alır: ofis klasörü + wiki sorgu sayfaları + posta kayıtları.

    `office` ofis adı ya da `find_*` çıktısındaki sözlük olabilir. Ofis klasörü
    `archive_stale` ile taşınır (kuralları aynen geçerli: kasa dışı yol, zaten
    arşivde olan yol ve künyesi doğan "gerçek ofis" reddedilir). Dosya izleri
    ise `_archive/<tarih>/<ofis>-residue/{queries,mail}/` altına taşınır —
    ofisin klasörünün İÇİNE değil, çünkü ofis klasörü hiç taşınmamış olabilir
    (künyesi varsa `archive_stale` onu atlar) ve izler o durumda da temizlenmeli.
    """
    from entropy.memory.office_graph import desk_offices_dir

    if isinstance(office, dict):
        name = str(office.get("name") or "").strip()
        office_path = Path(str(office.get("path") or "")) if office.get("path") else None
    else:
        name = str(office or "").strip()
        office_path = None
    if not name:
        return {
            "office": "",
            "dry_run": bool(dry_run),
            "folder": {"planned": [], "moved": [], "skipped": []},
            "residue": {"planned": [], "moved": [], "skipped": []},
            "count": 0,
        }
    if office_path is None:
        office_path = desk_offices_dir(vault_path) / name

    folder = archive_stale(
        [str(office_path)] if office_path.is_dir() else [],
        vault_path=vault_path,
        dry_run=dry_run,
        date=date,
    )

    root = _entropy_dir(vault_path)
    stamp = date or datetime.date.today().isoformat()
    residue_root = root / ARCHIVE_DIRNAME / stamp / f"{name}-residue"

    residue = office_residue(name, vault_path=vault_path)
    planned: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    for bucket, files in (("queries", residue["queries"]), ("mail", residue["mail"])):
        for raw in files:
            src = Path(raw)
            if not src.is_file():
                skipped.append({"path": raw, "reason": "dosya_degil"})
                continue
            if ARCHIVE_DIRNAME in src.resolve().parts:
                skipped.append({"path": raw, "reason": "zaten_arsivde"})
                continue
            dst = residue_root / bucket / src.name
            n = 2
            while dst.exists() or any(p["dst"] == str(dst) for p in planned):
                dst = residue_root / bucket / f"{src.stem}-{n}{src.suffix}"
                n += 1
            planned.append({"src": str(src), "dst": str(dst), "bucket": bucket})

    moved: List[Dict[str, str]] = []
    if not dry_run:
        for plan in planned:
            try:
                Path(plan["dst"]).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(plan["src"], plan["dst"])
                moved.append(plan)
            except OSError as exc:  # pragma: no cover - dosya kilidi/izin
                logger.warning("İz arşive taşınamadı (%s): %s", plan["src"], exc)
                skipped.append({"path": plan["src"], "reason": f"tasima_hatasi: {exc}"})
        # Wiki dizini taşınan sorgu sayfalarına ATIFTA bulunmayı sürdürüyordu:
        # `Entropy/Wiki/index.md` içindeki `[[...]]` bağı arşive giden dosyaya
        # işaret ediyor, Obsidian'da kırık bağ olarak duruyordu. `log.md` bir
        # OLAY günlüğüdür (geçmiş kayıt), bilerek dokunulmaz.
        pruned = prune_wiki_index(
            [Path(m["src"]).stem for m in moved if m["bucket"] == "queries"],
            vault_path=vault_path,
        )
        if pruned:
            logger.info("Wiki dizininden %d kırık bağ temizlendi.", len(pruned))

    return {
        "office": name,
        "archive_dir": str(root / ARCHIVE_DIRNAME / stamp),
        "dry_run": bool(dry_run),
        "folder": folder,
        "residue": {"planned": planned, "moved": moved, "skipped": skipped},
        "count": (len(folder.get("moved") or []) if not dry_run else len(folder.get("planned") or []))
        + (len(moved) if not dry_run else len(planned)),
    }


def prune_wiki_index(slugs: Sequence[str], vault_path: Optional[Path] = None) -> List[str]:
    """
    `Entropy/Wiki/index.md` icinden verilen sorgu sayfalarinin baglarini siler.

    Sorgu sayfasi arsive tasindiginda dizindeki `[[slug]]` satiri kaliyor ve
    Obsidian'da kirik bag uretiyordu. Yalnizca ILGILI satirlar silinir; dosya
    yoksa ya da eslesme yoksa hicbir sey yazilmaz.
    """
    wanted = {str(s).strip() for s in (slugs or []) if str(s).strip()}
    if not wanted:
        return []
    index = _entropy_dir(vault_path) / "Wiki" / "index.md"
    if not index.is_file():
        return []
    try:
        lines = index.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return []
    kept, removed = [], []
    for line in lines:
        hit = next((w for w in wanted if f"[[{w}]]" in line), None)
        if hit is not None:
            removed.append(hit)
            continue
        kept.append(line)
    if not removed:
        return []
    try:
        index.write_text("".join(kept), encoding="utf-8")
    except OSError:
        return []
    return removed


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
        # Kuru koşumla gerçek taşıma arasında ofis canlanmış olabilir: liste
        # `find_ghost_offices()` ile üretilip dakikalar sonra uygulandığında,
        # bu arada künyesi yazılan (yani ARTIK gerçek olan) bir ofis arşive
        # gidiyordu. Taşımadan hemen önce künye yeniden doğrulanır.
        if (src / "OFFICE.md").is_file():
            skipped.append({"path": str(src), "reason": "artik_gercek_ofis"})
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
