"""
Kart başına git worktree (Faz 10-C / 10.4).

Neden Entropy kuruyor
---------------------
`claude` CLI'sinde `--worktree` var, `agy`'de YOK. Worktree'yi sağlayıcıya
bırakmak, ofisin davranışını sağlayıcıya göre sessizce değiştirirdi. Bu yüzden
worktree'yi bu modül kurar: iki sağlayıcı da aynı sözleşmeyi görür.

Kök: `<repo>/../.entropy-worktrees/<ofis>/<kart-id>` (bkz. `paths.worktree_root_for`).
Dal: `desk/<kart-id>` — kart kimliğiyle BİREBİR. Ölçüm (araştırma notu §1.3):
aynı dal ikinci bir worktree'ye eklenemiyor, dolayısıyla dal adı türetilebilir
ve tekil olmak zorunda.

Windows'un dayattığı üç kural (hepsi ölçümle geldi):

1. **Uzun yol öldürür.** `core.longpaths` kapalıyken 358 karakterlik bir yol
   `fatal: could not create leading directories ... Filename too long` veriyor.
   Bu yüzden worktree açılmadan ÖNCE yol uzunluğu kontrol edilir
   (`MAX_WORKTREE_PATH`); aşılırsa worktree hiç açılmaz ve kart eski
   (tek dizinli) yolundan koşar.
2. **Silme atomik değil.** Dosya kilidi varken `git worktree remove --force`
   **rc=255** veriyor, yönetim kaydını siliyor ama DİZİNİ bırakıyor; `prune`
   kurtarmıyor ve aynı yola yeniden `add` "already exists" ile ölüyor. Bu
   yüzden temizlik doğrulamalı: dizin hâlâ duruyorsa kayıt ertelenmiş temizlik
   kuyruğuna (`Desk/_worktree_cleanup.json`) yazılır ve KART BAŞARISIZ SAYILMAZ.
3. **`remove` dalı silmez.** Dal silme ayrı bir adımdır ve başarısız olabilir
   (ör. dal başka bir worktree'de checkout'ta); başarısızlık günlüğe düşer,
   çağrının sonucunu değiştirmez.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional

from entropy.core import paths as _paths
from entropy.platform.proc import popen_kwargs

logger = logging.getLogger(__name__)

__all__ = [
    "WorktreeError",
    "MAX_WORKTREE_PATH",
    "BRANCH_PREFIX",
    "CLEANUP_QUEUE_SUBPATH",
    "git_available",
    "branch_name",
    "worktree_path_for",
    "path_length_ok",
    "create_worktree",
    "remove_worktree",
    "release_worktree",
    "list_orphans",
    "retry_orphans",
    "diff_stat",
    "file_diff",
    "worktree_status",
    "repo_of",
    "is_worktree",
]


class WorktreeError(RuntimeError):
    """Worktree açılamadı/kapatılamadı; çağıran kartı öldürmeden geri düşer."""


# Ölçülen sınır: bu depoda en derin göreli yol 99 karakter ve `core.longpaths`
# kapalı. Kök + kart kimliği + en derin göreli yol toplamı 260'ı aşmamalı;
# 200 eşiği ~60 karakterlik güvenlik payı bırakır.
MAX_WORKTREE_PATH = 200

BRANCH_PREFIX = "desk/"

# Ertelenmiş temizlik kuyruğu (kilitli dosya yüzünden silinemeyen worktree'ler).
CLEANUP_QUEUE_SUBPATH = "Desk/_worktree_cleanup.json"

_queue_lock = threading.Lock()

# `git worktree add` aynı depoda paralel çağrıldığında `.git/worktrees` kilidi
# üzerinden yarışıyor; ofis iki alt kartı aynı anda başlatabildiği için
# oluşturma süreç içinde serileştirilir.
_create_lock = threading.Lock()


# ---------------------------------------------------------------------------
# git yardımcıları
# ---------------------------------------------------------------------------


def git_available() -> bool:
    return shutil.which("git") is not None


def _git(cwd: Path | str, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """`git -C <cwd> <args>`; `git` yoksa açık hata."""
    if not git_available():
        raise WorktreeError("`git` bulunamadı: worktree özelliği kullanılamıyor.")
    cmd = ["git", "-C", str(cwd), *args]
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            **popen_kwargs(timeout=timeout),
        )
    except subprocess.TimeoutExpired as exc:
        raise WorktreeError(f"git komutu zaman aşımına uğradı: {' '.join(args)}") from exc
    except OSError as exc:
        raise WorktreeError(f"git çalıştırılamadı: {exc}") from exc


def is_repo(path: Path | str) -> bool:
    try:
        proc = _git(path, "rev-parse", "--is-inside-work-tree")
    except WorktreeError:
        return False
    return proc.returncode == 0 and (proc.stdout or "").strip() == "true"


def branch_exists(repo: Path | str, branch: str) -> bool:
    try:
        return _git(repo, "rev-parse", "--verify", "--quiet", branch).returncode == 0
    except WorktreeError:
        return False


def is_worktree(path: Path | str) -> bool:
    """Bağlı (linked) worktree mi: kökündeki `.git` bir DOSYA ise evet."""
    return (Path(path) / ".git").is_file()


def repo_of(worktree: Path | str) -> Optional[Path]:
    """Bir worktree'nin ana deposu (`--git-common-dir`'in ebeveyni)."""
    try:
        proc = _git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir")
    except WorktreeError:
        return None
    if proc.returncode != 0:
        return None
    common = (proc.stdout or "").strip()
    if not common:
        return None
    return Path(common).parent


# ---------------------------------------------------------------------------
# yollar
# ---------------------------------------------------------------------------


def branch_name(card_id: str) -> str:
    return f"{BRANCH_PREFIX}{card_id}"


def worktree_path_for(repo: Path | str, office: str, card_id: str,
                      root: Optional[Path | str] = None) -> Path:
    base = Path(root) if root else _paths.worktree_root_for(repo)
    return base / (office or "ofis") / card_id


def path_length_ok(path: Path | str, limit: int = MAX_WORKTREE_PATH) -> bool:
    """Yol uzunluğu eşiği; `core.longpaths` açıksa kontrol atlanır."""
    if _longpaths_enabled():
        return True
    return len(str(path)) <= limit


def _longpaths_enabled() -> bool:
    if os.name != "nt":
        return True
    try:
        proc = subprocess.run(
            ["git", "config", "--get", "core.longpaths"],
            capture_output=True, text=True,
            **popen_kwargs(timeout=15),
        )
    except Exception:
        return False
    return (proc.stdout or "").strip().lower() in ("true", "1", "yes", "on")


# ---------------------------------------------------------------------------
# oluşturma
# ---------------------------------------------------------------------------


def create_worktree(
    repo: Path | str,
    office: str,
    card_id: str,
    base_branch: str = "",
    root: Optional[Path | str] = None,
) -> Path:
    """
    Kartın izole çalışma ağacını açar ve yolunu döndürür.

    İdempotent: yol zaten kayıtlı bir worktree ise aynen döner; dal varsa
    `-b` OLMADAN yeniden bağlanır (ölçüm: aynı dal ikinci worktree'ye
    eklenemiyor ama boştaki bir dal yeni yola bağlanabiliyor).
    """
    repo_path = Path(repo)
    if not repo_path.is_dir():
        raise WorktreeError(f"Depo yolu bulunamadı: {repo_path}")
    if not is_repo(repo_path):
        raise WorktreeError(f"Bu klasör bir git deposu değil: {repo_path}")

    target = worktree_path_for(repo_path, office, card_id, root=root)
    if not path_length_ok(target):
        raise WorktreeError(
            f"Worktree yolu çok uzun ({len(str(target))} > {MAX_WORKTREE_PATH} karakter; "
            "uzun yol desteği kapalı)."
        )
    branch = branch_name(card_id)

    with _create_lock:
        if target.exists():
            if is_worktree(target):
                return target
            if any(target.iterdir()):
                # Yarım silinmiş yetim dizin: aynı yola `add` "already exists"
                # ile ölür. Kartı öldürmeden geri düşülür.
                raise WorktreeError(
                    f"Yol dolu ama git worktree'si değil (yetim): {target}"
                )
            try:
                target.rmdir()
            except OSError:
                pass
        target.parent.mkdir(parents=True, exist_ok=True)

        if branch_exists(repo_path, branch):
            args = ["worktree", "add", str(target), branch]
        else:
            args = ["worktree", "add", str(target), "-b", branch]
            if (base_branch or "").strip():
                args.append(base_branch.strip())
        proc = _git(repo_path, *args)
        if proc.returncode != 0:
            raise WorktreeError(
                f"Worktree açılamadı ({proc.returncode}): "
                f"{(proc.stderr or proc.stdout or '').strip()[:300]}"
            )
    return target


# ---------------------------------------------------------------------------
# temizlik
# ---------------------------------------------------------------------------


def remove_worktree(
    repo: Path | str,
    path: Path | str,
    branch: str = "",
    force: bool = False,
    vault_path: Optional[Path | str] = None,
) -> Dict[str, object]:
    """
    Worktree'yi DOĞRULAYARAK kaldırır.

    Sözleşme: dönen sözlükte `removed` yalnızca dizin GERÇEKTEN gittiyse
    `True`'dur. Aksi hâlde kayıt `orphans` listesine ve ertelenmiş temizlik
    kuyruğuna yazılır; çağıran kartı başarısız saymaz.
    """
    repo_path = Path(repo)
    target = Path(path)
    result: Dict[str, object] = {
        "removed": False,
        "branch_deleted": False,
        "orphans": [],
        "error": "",
    }
    if not target.exists():
        result["removed"] = True
    else:
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(target))
        try:
            proc = _git(repo_path, *args)
            rc, err = proc.returncode, (proc.stderr or proc.stdout or "").strip()
        except WorktreeError as exc:
            rc, err = 1, str(exc)
        if rc != 0:
            result["error"] = err[:300]
        # Doğrulama: rc ne olursa olsun DİZİNE bakılır. Ölçüm gösterdi ki
        # rc=255 olduğunda kayıt silinmiş ama dizin duruyor olabiliyor.
        if target.exists():
            entry = {
                "repo": str(repo_path),
                "path": str(target),
                "branch": branch or "",
                "error": result["error"],
            }
            result["orphans"] = [entry]
            _queue_orphan(entry, vault_path=vault_path)
        else:
            result["removed"] = True

    try:
        _git(repo_path, "worktree", "prune")
    except WorktreeError:
        pass

    if result["removed"] and (branch or "").strip():
        try:
            proc = _git(repo_path, "branch", "-D", branch)
            result["branch_deleted"] = proc.returncode == 0
            if proc.returncode != 0:
                logger.info(
                    "Dal silinemedi (%s): %s", branch,
                    (proc.stderr or "").strip()[:200],
                )
        except WorktreeError as exc:
            logger.info("Dal silinemedi (%s): %s", branch, exc)
    return result


def release_worktree(
    card, force: bool = True, vault_path: Optional[Path | str] = None
) -> Dict[str, object]:
    """Kartın worktree'sini kaldırır (kart silinince/arşivlenince çağrılır)."""
    wt = str(getattr(card, "worktree", "") or "").strip()
    if not wt:
        return {"removed": True, "branch_deleted": False, "orphans": [], "error": ""}
    target = Path(wt)
    branch = str(getattr(card, "branch", "") or "") or branch_name(getattr(card, "id", ""))
    repo = repo_of(target) if target.exists() else None
    if repo is None:
        if target.exists():
            entry = {"repo": "", "path": str(target), "branch": branch,
                     "error": "ana depo çözülemedi"}
            _queue_orphan(entry, vault_path=vault_path)
            return {"removed": False, "branch_deleted": False, "orphans": [entry],
                    "error": "ana depo çözülemedi"}
        return {"removed": True, "branch_deleted": False, "orphans": [], "error": ""}
    return remove_worktree(repo, target, branch=branch, force=force, vault_path=vault_path)


# --- ertelenmiş temizlik kuyruğu -------------------------------------------


def _queue_path(vault_path: Optional[Path | str] = None) -> Path:
    return _paths.vault_root(vault_path) / CLEANUP_QUEUE_SUBPATH


def _read_queue(vault_path: Optional[Path | str] = None) -> List[Dict[str, str]]:
    path = _queue_path(vault_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def _write_queue(rows: List[Dict[str, str]], vault_path: Optional[Path | str] = None) -> None:
    path = _queue_path(vault_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        logger.warning("Worktree temizlik kuyruğu yazılamadı: %s", path)


def _queue_orphan(entry: Dict[str, str], vault_path: Optional[Path | str] = None) -> None:
    with _queue_lock:
        rows = _read_queue(vault_path)
        if not any(r.get("path") == entry.get("path") for r in rows):
            rows.append(entry)
            _write_queue(rows, vault_path)
    logger.warning(
        "Yetim worktree kuyruğa alındı: %s (%s)", entry.get("path"), entry.get("error")
    )


def list_orphans(repo: Optional[Path | str] = None,
                 vault_path: Optional[Path | str] = None) -> List[Dict[str, str]]:
    """Ertelenmiş temizlik kuyruğu; `repo` verilirse yalnızca o deponunkiler."""
    rows = _read_queue(vault_path)
    if repo is None:
        return rows
    want = str(Path(repo))
    return [r for r in rows if str(r.get("repo") or "") == want]


def retry_orphans(vault_path: Optional[Path | str] = None) -> Dict[str, object]:
    """
    Kuyruktaki yetimleri yeniden dener (açılışta çağrılır).

    Sessiz başarısızlık kabul edilmez: temizlenemeyen kayıt kuyrukta KALIR,
    çağıran onu şeritte gösterebilsin.
    """
    with _queue_lock:
        rows = _read_queue(vault_path)
    cleared: List[str] = []
    remaining: List[Dict[str, str]] = []
    for row in rows:
        target = Path(str(row.get("path") or ""))
        repo = str(row.get("repo") or "")
        if not target.exists():
            cleared.append(str(target))
            continue
        ok = False
        if repo:
            try:
                res = remove_worktree(repo, target, branch=str(row.get("branch") or ""),
                                      force=True, vault_path=vault_path)
                ok = bool(res.get("removed"))
            except WorktreeError:
                ok = False
        if not ok and target.exists():
            shutil.rmtree(target, ignore_errors=True)
            ok = not target.exists()
        if ok:
            cleared.append(str(target))
        else:
            remaining.append(row)
    with _queue_lock:
        _write_queue(remaining, vault_path)
    return {"cleared": cleared, "remaining": remaining}


# ---------------------------------------------------------------------------
# okuma: diff ve durum
# ---------------------------------------------------------------------------


def diff_stat(path: Path | str, base: str = "") -> List[Dict[str, object]]:
    """
    Worktree'deki değişikliklerin dosya bazlı özeti.

    Üç kaynak birleşir: hazırlanmış (staged), hazırlanmamış ve İZLENMEYEN
    dosyalar. İzlenmeyenler `git diff`e hiç girmiyor; ajanın yeni yazdığı
    dosyalar tam olarak orada olduğu için onlarsız özet yanıltıcı olurdu.
    `base` verilirse `git diff --numstat <base>...HEAD` de eklenir (kartın
    dalında commit varsa).
    """
    root = Path(path)
    if not root.is_dir():
        return []
    rows: Dict[str, Dict[str, object]] = {}

    def _absorb(text: str, status: str) -> None:
        for line in (text or "").splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            add, dele, name = parts[0], parts[1], parts[-1]
            row = rows.setdefault(name.replace("\\", "/"),
                                  {"file": name.replace("\\", "/"), "added": 0,
                                   "removed": 0, "status": status})
            row["added"] = int(row["added"]) + (int(add) if add.isdigit() else 0)
            row["removed"] = int(row["removed"]) + (int(dele) if dele.isdigit() else 0)

    try:
        if (base or "").strip():
            _absorb(_git(root, "diff", "--numstat", f"{base}...HEAD").stdout, "committed")
        _absorb(_git(root, "diff", "--numstat", "--cached").stdout, "staged")
        _absorb(_git(root, "diff", "--numstat").stdout, "modified")
        untracked = _git(root, "ls-files", "--others", "--exclude-standard").stdout
    except WorktreeError:
        return []

    for name in (untracked or "").splitlines():
        name = name.strip().replace("\\", "/")
        if not name:
            continue
        added = 0
        try:
            added = sum(1 for _ in (root / name).open("r", encoding="utf-8",
                                                      errors="replace"))
        except OSError:
            added = 0
        rows[name] = {"file": name, "added": added, "removed": 0, "status": "new"}
    return [rows[k] for k in sorted(rows)]


def file_diff(path: Path | str, file: str) -> str:
    """Tek dosyanın diff metni; izlenmeyen dosyada `--no-index` ile üretilir."""
    root = Path(path)
    if not root.is_dir() or not (file or "").strip():
        return ""
    try:
        proc = _git(root, "diff", "HEAD", "--", file)
        text = (proc.stdout or "").strip()
        if text:
            return text
        proc = _git(root, "diff", "--no-index", "--", os.devnull, file)
        return (proc.stdout or "").strip()
    except WorktreeError:
        return ""


def worktree_status(path: Path | str) -> Dict[str, object]:
    """Worktree künyesi: dal, temiz mi, dosya sayısı, kayıtlı mı."""
    root = Path(path)
    out: Dict[str, object] = {
        "path": str(root),
        "exists": root.exists(),
        "registered": is_worktree(root),
        "branch": "",
        "clean": True,
        "files": 0,
    }
    if not out["registered"]:
        return out
    try:
        out["branch"] = (_git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout or "").strip()
        porcelain = (_git(root, "status", "--porcelain").stdout or "").strip()
    except WorktreeError:
        return out
    lines = [ln for ln in porcelain.splitlines() if ln.strip()]
    out["clean"] = not lines
    out["files"] = len(lines)
    return out
