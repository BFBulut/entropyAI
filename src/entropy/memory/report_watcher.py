"""
Kasadaki rapor klasörlerini canlı izler ve rapor-yetenek indeksini artımlı tutar.

Neden gerekli
-------------
Rapor yazan tek yol uygulamanın kendisi değil: agy CLI, arka plan görevleri,
başka bir Entropy penceresi ya da kullanıcının kendisi kasaya dosya bırakabilir.
İndeks yalnızca `/distill index` ile yenilendiği sürece bu raporlar hiçbir
yeteneğin kaynağı sayılmıyor, yetenek kartındaki damıtma sayacı da uygulama
yeniden başlatılana kadar donuk kalıyordu.

`SkillWatcher` ile aynı iki katman:
  1. QFileSystemWatcher — Reports/, Skills/*/Reports/, Projects/*/Reports/
  2. 5 sn yoklama — OneDrive/ağ sürücülerinde olay düşerse yedek

Yoklama ucuzdur: dosya İÇERİĞİ okunmaz, yalnızca (yol, boyut) imzası karşılaştırılır.
mtime imzaya girmez; kasa OneDrive'da ve senkron dosyalara dokunduğunda mtime
değişip her yoklamada yalancı "değişti" üretiyordu.

Değişim görüldüğünde yalnızca indekste OLMAYAN dosyalar okunur ve eşlenir
(`index_new_reports`), ardından `bus.reports_updated` yayınlanır.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import FrozenSet, List, Optional, Set, Tuple

from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtCore import QFileSystemWatcher

from entropy.core.event_bus import bus
from entropy.memory.playbook import PlaybookStore, clear_file_facts_cache, index_new_reports

logger = logging.getLogger(__name__)


class ReportWatcher(QObject):
    """Rapor klasörlerini izler, indeksi artımlı günceller, `bus.reports_updated` yayar."""

    def __init__(
        self,
        vault_path: Optional[Path] = None,
        poll_interval_ms: int = 5000,
        store: Optional[PlaybookStore] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.store = store or PlaybookStore(vault_path=vault_path)
        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.directoryChanged.connect(self._schedule_check)

        # Bir araştırma turu biterken rapor, ek ve günlük art arda yazılır;
        # her biri ayrı olay üretir. Tek gecikmeli kontrole indirilir.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(400)
        self._debounce.timeout.connect(self._check_now)

        self._poll = QTimer(self)
        self._poll.setInterval(max(1000, int(poll_interval_ms)))
        self._poll.timeout.connect(self._check_now)

        self._known_skills: Set[str] = set()
        self._signature = self._compute_signature()

    # -- kamu API'si ---------------------------------------------------------

    def start(self) -> "ReportWatcher":
        self._sync_watch_paths()
        self._poll.start()
        return self

    def stop(self) -> None:
        self._poll.stop()
        self._debounce.stop()
        paths = self._fs_watcher.directories() + self._fs_watcher.files()
        if paths:
            self._fs_watcher.removePaths(paths)

    def watched_dirs(self) -> List[str]:
        return list(self._fs_watcher.directories())

    def set_known_skills(self, names) -> None:
        """Sınıflandırmanın hedef kümesi; boşsa etiket adı olduğu gibi kabul edilir."""
        self._known_skills = {str(n) for n in (names or ())}

    # -- iç işleyiş ----------------------------------------------------------

    def _report_dirs(self) -> List[Path]:
        entropy_dir = self.store.vault_path / "Entropy"
        dirs: List[Path] = list(self.store.tag_scan_dirs())
        skills = entropy_dir / "Skills"
        if skills.is_dir():
            try:
                for child in sorted(skills.iterdir()):
                    rep = child / "Reports"
                    if rep.is_dir():
                        dirs.append(rep)
            except OSError:
                pass
        return dirs

    def _compute_signature(self) -> FrozenSet[Tuple[str, int]]:
        sig: List[Tuple[str, int]] = []
        for d in self._report_dirs():
            try:
                for p in d.glob("*.md"):
                    try:
                        sig.append((str(p), p.stat().st_size))
                    except OSError:
                        continue
            except OSError:
                continue
        return frozenset(sig)

    def _sync_watch_paths(self) -> None:
        wanted = {str(d) for d in self._report_dirs()}
        entropy_dir = self.store.vault_path / "Entropy"
        # Üst klasörler de izlenir: henüz var olmayan Skills/google-flow/Reports
        # sonradan oluşturulduğunda izleyici yok olan bir yolu izleyemez.
        for parent in (entropy_dir, entropy_dir / "Skills", entropy_dir / "Projects"):
            if parent.is_dir():
                wanted.add(str(parent))

        current = set(self._fs_watcher.directories())
        stale = current - wanted
        if stale:
            self._fs_watcher.removePaths(sorted(stale))
        fresh = wanted - current
        if fresh:
            self._fs_watcher.addPaths(sorted(fresh))

    @Slot()
    def _schedule_check(self, *_args) -> None:
        self._debounce.start()

    def _classifier(self):
        """Etiketsiz raporlar için anlamsal sınıflandırıcı; kurulamazsa None."""
        try:
            from entropy.skills.manager import SkillManager

            sm = SkillManager()
            if not self._known_skills:
                self._known_skills = {s.name for s in sm.list_skills() if s.enabled}

            def classify(title: str, head_text: str):
                hit = sm.auto_detect_skill_for_prompt(f"{title} {head_text[:1500]}")
                return hit.name if hit else None

            return classify
        except Exception:
            return None

    @Slot()
    def _check_now(self) -> None:
        self._sync_watch_paths()
        new_sig = self._compute_signature()
        if new_sig == self._signature:
            return
        self._signature = new_sig
        # İçerik önbelleği (yol, boyut, mtime) anahtarlı; üzerine yazılan bir
        # raporun boyutu aynı kalırsa eski içerik okunmuş sayılırdı.
        clear_file_facts_cache()
        added = {}
        try:
            added = index_new_reports(self.store, self._known_skills, self._classifier())
        except Exception as exc:
            logger.warning("Rapor indeksi artımlı güncellenemedi: %s", exc)
        if added:
            for skill in sorted(added):
                bus.reports_updated.emit(skill)
        else:
            bus.reports_updated.emit("")


_report_watcher: Optional[ReportWatcher] = None


def start_report_watcher(vault_path: Optional[Path] = None, poll_interval_ms: int = 5000) -> ReportWatcher:
    """Süreç genelinde tek bir rapor izleyicisi başlatır (yeniden çağrı güvenli)."""
    global _report_watcher
    if _report_watcher is None:
        _report_watcher = ReportWatcher(vault_path=vault_path, poll_interval_ms=poll_interval_ms).start()
    return _report_watcher


def stop_report_watcher() -> bool:
    """İzleyiciyi durdurur; durdurulduysa True. Kapanışta zamanlayıcılar dirilmesin diye gerekli."""
    global _report_watcher
    if _report_watcher is None:
        return False
    try:
        _report_watcher.stop()
    except Exception:
        pass
    _report_watcher = None
    return True
