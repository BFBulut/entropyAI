"""
`artifact_archive` — üretim hafızasındaki test/hata artıklarını **arşivler** (Faz 14-D).

Neden
-----
Denetimde (A notu §1 satır 3c) gerçek veritabanında ölçüldü: `provenance`
alanında `pytest-of-…` geçici dizin izi taşıyan **12 düğüm** ve başarısız turun
hata metnini içeren düğümler (`'list_iterator' object has no attribute`,
`[Otonom Görev Hata]`) etkin hafızada duruyordu. Bunlar geri çağırmaya
karışıyor ve K10/K12 ölçümünü kirletiyor.

Sözleşme
--------
* **Silme yok.** Yalnızca `archived=1` ve `metadata.archived_reason`.
* Graf kenarlarına dokunulmaz (`nodes`/`edges` tabloları okunmaz bile).
* Yazmadan önce veritabanının tam kopyası `~/.entropy/backups/p14d-<zaman>/`.
* Varsayılan **kuru koşum**: sayı verir, yazmaz. `--apply` ile uygulanır.
* Her koşum kasadaki `Entropy/Memory/archive_log.md` dosyasına tek satır yazar.

Kullanım::

    python -m entropy.brain.artifact_archive                 # kuru koşum
    python -m entropy.brain.artifact_archive --apply
    python -m entropy.brain.artifact_archive --db <yol> --apply --no-log
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ARCHIVE_REASON = "phase14d_artifact"

#: İçerikte aranan hata/otonom hata izleri.
CONTENT_PATTERNS = (
    re.compile(r"list_iterator", re.IGNORECASE),
    re.compile(r"\[Otonom\s+Görev\s+Hata\]", re.IGNORECASE),
    re.compile(r"object has no attribute", re.IGNORECASE),
    re.compile(r"\bTraceback\b", re.IGNORECASE),
)

#: Kaynak/metadata'da aranan test artığı izleri.
ARTIFACT_PATTERNS = (
    re.compile(r"pytest-of-", re.IGNORECASE),
    re.compile(r"[\\/]pytest-\d+[\\/]", re.IGNORECASE),
    re.compile(r"Temp[\\/]+pytest", re.IGNORECASE),
)


def default_db_path() -> Path:
    from entropy.brain.supabase.cognitive_memory import default_cognitive_db_path

    return Path(default_cognitive_db_path())


def backups_root() -> Path:
    return Path.home() / ".entropy" / "backups"


def find_candidates(db_path: Path, extra_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Arşiv adaylarını döndürür. **Salt okunur.**

    `extra_ids`: kalıba uymayan ama aynı artığın TÜREVİ olan düğümler
    (ör. arşivlenen kümenin konsolidasyon özeti) elle eklenebilir.
    """
    forced = set(extra_ids or [])
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT id, category, content, provenance, metadata_json, archived "
            "FROM cognitive_nodes"
        )]
    finally:
        conn.close()

    out: List[Dict[str, Any]] = []
    for row in rows:
        if int(row.get("archived") or 0) == 1:
            continue
        content = row.get("content") or ""
        blob = f"{row.get('provenance') or ''} {row.get('metadata_json') or ''}"
        reasons: List[str] = []
        if any(p.search(content) for p in CONTENT_PATTERNS):
            reasons.append("hata_metni")
        if any(p.search(blob) for p in ARTIFACT_PATTERNS):
            reasons.append("pytest_izi")
        if row["id"] in forced:
            reasons.append("artik_turevi")
        if reasons:
            row["_reasons"] = reasons
            out.append(row)
    return out


def backup_db(db_path: Path, stamp: str = "") -> Path:
    """Veritabanının tam kopyasını `~/.entropy/backups/p14d-<zaman>/` altına alır."""
    stamp = stamp or _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    target_dir = backups_root() / f"p14d-{stamp}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / db_path.name
    shutil.copy2(db_path, target)
    return target


def apply_archive(db_path: Path, candidates: List[Dict[str, Any]]) -> int:
    """Adayları `archived=1` yapar ve metadata'ya nedeni işler. Silme yok."""
    conn = sqlite3.connect(str(db_path))
    try:
        for row in candidates:
            try:
                meta = json.loads(row.get("metadata_json") or "{}")
                if not isinstance(meta, dict):
                    meta = {}
            except (json.JSONDecodeError, ValueError):
                meta = {}
            meta["archived_reason"] = ARCHIVE_REASON
            meta["archived_patterns"] = row.get("_reasons", [])
            conn.execute(
                "UPDATE cognitive_nodes SET archived = 1, metadata_json = ? WHERE id = ?",
                (json.dumps(meta, ensure_ascii=False), row["id"]),
            )
        conn.commit()
    finally:
        conn.close()
    return len(candidates)


def write_log(vault_path: Optional[Path], line: str) -> Optional[Path]:
    """`<kasa>/Entropy/Memory/archive_log.md` dosyasına tek satır ekler."""
    try:
        from entropy.core.paths import vault_root

        base = Path(vault_path) if vault_path else vault_root()
        target = base / "Entropy" / "Memory" / "archive_log.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text("# Hafıza arşiv günlüğü\n\n", encoding="utf-8")
        with target.open("a", encoding="utf-8") as fh:
            fh.write(line.rstrip() + "\n")
        return target
    except Exception as exc:  # pragma: no cover - kasa yoksa sessiz düş
        print(f"[uyarı] arşiv günlüğü yazılamadı: {exc}", file=sys.stderr)
        return None


def run(
    db_path: Optional[Path] = None,
    apply: bool = False,
    vault_path: Optional[Path] = None,
    write_vault_log: bool = True,
    extra_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Kuru koşum (varsayılan) ya da uygulama. Döner: sayım özeti."""
    db = Path(db_path) if db_path else default_db_path()
    candidates = find_candidates(db, extra_ids=extra_ids)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    result: Dict[str, Any] = {
        "db": str(db),
        "dry_run": not apply,
        "candidates": len(candidates),
        "ids": [c["id"] for c in candidates],
        "reasons": {c["id"]: c["_reasons"] for c in candidates},
        "backup": "",
        "archived": 0,
        "log": "",
    }
    if apply and candidates:
        result["backup"] = str(backup_db(db, stamp))
        result["archived"] = apply_archive(db, candidates)
    if write_vault_log:
        line = (
            f"- {_dt.datetime.now().isoformat(timespec='seconds')} · Faz 14-D · "
            f"{'UYGULANDI' if apply else 'kuru koşum'} · aday {len(candidates)} · "
            f"arşivlenen {result['archived']} · yedek `{result['backup'] or '-'}`"
        )
        path = write_log(vault_path, line)
        result["log"] = str(path or "")
    return result


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Faz 14-D hafıza artığı arşivleyici (silme yok)")
    ap.add_argument("--db", default=None)
    ap.add_argument("--apply", action="store_true", help="gerçekten arşivle (varsayılan kuru koşum)")
    ap.add_argument("--vault", default=None)
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--id", action="append", default=[],
                    help="kalıba uymayan ama artığın türevi olan düğüm kimliği (tekrarlanabilir)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    result = run(
        db_path=Path(args.db) if args.db else None,
        apply=args.apply,
        vault_path=Path(args.vault) if args.vault else None,
        write_vault_log=not args.no_log,
        extra_ids=list(args.id or []),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"DB        : {result['db']}")
        print(f"Kip       : {'KURU KOŞUM' if result['dry_run'] else 'UYGULANDI'}")
        print(f"Aday      : {result['candidates']}")
        print(f"Arşivlenen: {result['archived']}")
        print(f"Yedek     : {result['backup'] or '-'}")
        for node_id in result["ids"]:
            print(f"  - {node_id} ({', '.join(result['reasons'][node_id])})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
