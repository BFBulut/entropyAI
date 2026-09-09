"""
İnceleme ve PR akışı (Faz 10-C / 10.5).

Mimarinin tersi kurulur: **yerel yol birincildir.** Ölçüm (araştırma notu §1.1)
`gh`'nin kurulu olmadığını gösterdi; bu yüzden "gh yoksa yedek" değil, "her
zaman yerel dal + diff özeti, `gh` varsa ÜSTÜNE taslak PR" sözleşmesi geçerli.
Kart hiçbir senaryoda PR yüzünden başarısız olmaz.

İki sert kural:

1. **Push kullanıcı eylemidir.** `push_branch` yalnızca açık kullanıcı
   komutundan çağrılır (`/desk push <kart>`); harness ve `prepare_review`
   onu ASLA çağırmaz. Uzak depoya yazma kullanıcının deposunda kalıcı iz
   bırakır.
2. **`gh` çıktısı loglanmaz.** `gh auth status` çıktısı jeton ipucu içerebilir;
   yalnızca dönüş kodu okunur, metin hiçbir yere yazılmaz.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from entropy.agents import worktrees as _wt

logger = logging.getLogger(__name__)

__all__ = [
    "gh_available",
    "remote_exists",
    "prepare_review",
    "changes_section",
    "pr_body",
    "push_branch",
    "create_draft_pr",
]

_NO_GH = "gh yok"


def _run(args: List[str], cwd: Optional[Path | str] = None,
         timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )


def gh_available() -> bool:
    """`gh` kurulu VE oturum açık mı. Çıktı okunmaz, yalnızca rc."""
    if shutil.which("gh") is None:
        return False
    try:
        return _run(["gh", "auth", "status"], timeout=30).returncode == 0
    except Exception:
        return False


def remote_exists(path: Path | str, name: str = "origin") -> bool:
    try:
        proc = _wt._git(path, "remote")
    except _wt.WorktreeError:
        return False
    return name in (proc.stdout or "").split()


# ---------------------------------------------------------------------------
# yerel yol (her zaman)
# ---------------------------------------------------------------------------


def prepare_review(card, base_branch: str = "") -> Dict[str, object]:
    """
    Kart `review`'a geçerken üretilen inceleme künyesi.

    Model çağrısı YOK, push YOK, ağ erişimi YOK: yalnızca yerel git okuması.
    Dönüş `_finalize` tarafından raporun `## Değişiklikler` bölümüne çevrilir.
    """
    out: Dict[str, object] = {
        "branch": "",
        "worktree": "",
        "files": [],
        "file_count": 0,
        "added": 0,
        "removed": 0,
        "summary": "",
        "pr_url": str(getattr(card, "pr_url", "") or ""),
    }
    wt = str(getattr(card, "worktree", "") or "").strip()
    if not wt or not Path(wt).is_dir():
        out["summary"] = "Bu kartın izole çalışma ağacı yok; değişiklik özeti üretilmedi."
        return out
    branch = str(getattr(card, "branch", "") or "") or _wt.branch_name(
        str(getattr(card, "id", ""))
    )
    out["branch"] = branch
    out["worktree"] = wt
    rows = _wt.diff_stat(wt, base=(base_branch or "").strip())
    out["files"] = rows
    out["file_count"] = len(rows)
    out["added"] = sum(int(r.get("added") or 0) for r in rows)
    out["removed"] = sum(int(r.get("removed") or 0) for r in rows)
    out["summary"] = (
        f"Dal: {branch} · {out['file_count']} dosya, "
        f"+{out['added']}/-{out['removed']} satır"
    )
    return out


def changes_section(review: Optional[Dict[str, object]]) -> str:
    """`## Değişiklikler` bölümünün gövdesi (rapor = makbuz)."""
    if not review:
        return "(değişiklik özeti üretilmedi)"
    rows = list(review.get("files") or [])
    if not rows:
        return str(review.get("summary") or "(değişiklik yok)")
    lines = [str(review.get("summary") or ""), "", "| Dosya | + | - | Durum |", "|---|---|---|---|"]
    for row in rows[:60]:
        lines.append(
            f"| `{row.get('file')}` | {row.get('added')} | {row.get('removed')} | "
            f"{row.get('status')} |"
        )
    if len(rows) > 60:
        lines.append(f"| … | | | ({len(rows) - 60} dosya daha) |")
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# uzak yol (yalnızca açık kullanıcı eylemiyle)
# ---------------------------------------------------------------------------


def push_branch(card, confirm: bool = True) -> Dict[str, object]:
    """
    Kartın dalını `origin`'e gönderir. **Yalnızca kullanıcı eylemiyle.**

    `confirm=False` ile çağrı reddedilir: bu, otomatik çağrıya karşı kodun
    içindeki emniyet mandalıdır (testte de bu şekilde doğrulanıyor).
    """
    if not confirm:
        return {"pushed": False, "skipped": "onay yok"}
    wt = str(getattr(card, "worktree", "") or "").strip()
    if not wt or not Path(wt).is_dir():
        return {"pushed": False, "skipped": "worktree yok"}
    if not remote_exists(wt):
        return {"pushed": False, "skipped": "uzak depo yok"}
    branch = str(getattr(card, "branch", "") or "") or _wt.branch_name(
        str(getattr(card, "id", ""))
    )
    try:
        proc = _wt._git(wt, "push", "-u", "origin", branch)
    except _wt.WorktreeError as exc:
        return {"pushed": False, "error": str(exc), "branch": branch}
    if proc.returncode != 0:
        return {
            "pushed": False,
            "branch": branch,
            "error": (proc.stderr or proc.stdout or "").strip()[:300],
        }
    return {"pushed": True, "branch": branch}


def pr_body(card, office: str = "", review: Optional[Dict[str, object]] = None,
            report_path: str = "", cost: str = "") -> str:
    """Taslak PR gövdesi. `--body-file` ile geçilir (argv sınırı sorunu doğmasın)."""
    lines = [
        "## Ne yapıldı",
        (getattr(card, "goal", "") or getattr(card, "title", "") or "").strip(),
        "",
        "## Kart",
        f"- Kart: `{getattr(card, 'id', '')}` — {getattr(card, 'title', '')}",
        f"- Ofis: `{office or getattr(card, 'office', '')}`",
        f"- Ajan: `{getattr(card, 'agent', '') or '-'}`",
        f"- Dal: `{getattr(card, 'branch', '') or ''}`",
        "",
        "## Kanıt",
        (getattr(card, "proof", "") or "(kanıt bloğu yok)").strip(),
        "",
        "## Değişiklikler",
        changes_section(review),
        "",
        "## Rapor",
        f"`{report_path}`" if report_path else "(rapor yolu yok)",
        "",
        "## Maliyet",
        cost or "(ölçülmedi)",
        "",
        "---",
        "Agent Desk tarafından üretildi. **Taslak** — insan incelemesi bekliyor.",
    ]
    return "\n".join(lines)


def create_draft_pr(card, office: str = "", base_branch: str = "",
                    review: Optional[Dict[str, object]] = None,
                    report_path: str = "", cost: str = "") -> Dict[str, object]:
    """
    Taslak PR açar. `gh` yoksa `{"skipped": "gh yok"}` döner ve kart etkilenmez.

    Push çağrısı BURADA YAPILMAZ: dal uzakta değilse `gh` kendisi hata verir ve
    o hata kullanıcıya "önce dalı gönder" olarak döner. Otomatik push yok.
    """
    if not gh_available():
        return {"skipped": _NO_GH, "url": ""}
    wt = str(getattr(card, "worktree", "") or "").strip()
    if not wt or not Path(wt).is_dir():
        return {"skipped": "worktree yok", "url": ""}
    branch = str(getattr(card, "branch", "") or "") or _wt.branch_name(
        str(getattr(card, "id", ""))
    )
    body = pr_body(card, office=office, review=review, report_path=report_path, cost=cost)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(body)
            tmp = fh.name
        args = ["gh", "pr", "create", "--draft", "--head", branch,
                "--title", (getattr(card, "title", "") or branch), "--body-file", tmp]
        if (base_branch or "").strip():
            args[3:3] = ["--base", base_branch.strip()]
        proc = _run(args, cwd=wt)
    except Exception as exc:
        return {"skipped": "", "url": "", "error": str(exc)[:300]}
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    if proc.returncode != 0:
        # `gh` çıktısı kimlik ipucu içerebilir: yalnızca kısa hata satırı
        # taşınır, günlüğe tam metin yazılmaz.
        return {"skipped": "", "url": "", "error": "PR açılamadı (gh)."}
    url = ""
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("http"):
            url = line
            break
    return {"skipped": "", "url": url}
