"""
Ajan ve görev kartı izleyicileri: kasadaki dosya değişimini sinyale çevirir.

SkillWatcher ile aynı desen ve aynı gerekçe: kaynak dosyaları Entropy, kullanıcı
(Obsidian) ve harici CLI'lar birlikte yazıyor. İki katman:

  1. QFileSystemWatcher — kök ve birinci seviye alt dizinler izlenir; dosya
     sistemi olayı anında tetikler.
  2. Hafif yoklama (varsayılan 5 sn) — henüz VAR OLMAYAN bir kök sonradan
     oluşturulduğunda (izleyici yok olan yolu izleyemez) ve olayın düştüğü
     bulut/senkron sürücülerde (Obsidian kasaları çoğunlukla OneDrive'da)
     yedek olarak çalışır.

Yoklama diski yormaz: yalnızca ilgili markdown dosyalarının (yol, mtime) imzası
karşılaştırılır.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Slot

from entropy.agents.registry import AGENT_FILENAME, AGENTS_SUBDIR
from entropy.agents.tasks import TASKS_SUBDIR
from entropy.core.event_bus import bus


class _VaultWatcher(QObject):
    """İki izleyicinin ortak gövdesi; alt sınıflar yalnızca imzayı tanımlar."""

    #: kasaya göreli izlenen alt dizin
    subdir = ""
    #: değişimde yayılacak sinyalin adı (bus üzerinde)
    signal_name = ""

    def __init__(self, vault_path: Optional[Path | str] = None, poll_interval_ms: int = 5000, parent=None):
        super().__init__(parent)
        if vault_path is None:
            from entropy.core.config import config

            vault_path = config.obsidian_vault_path
        self.root = Path(vault_path) / self.subdir

        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.directoryChanged.connect(self._schedule_check)
        self._fs_watcher.fileChanged.connect(self._schedule_check)

        # Toplu yazımlarda (senkron, git checkout) onlarca olay art arda gelir;
        # tek bir gecikmeli kontrole indirilir.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(400)
        self._debounce.timeout.connect(self._check_now)

        self._poll = QTimer(self)
        self._poll.setInterval(max(1000, int(poll_interval_ms)))
        self._poll.timeout.connect(self._check_now)

        self._signature = self._compute_signature()

    # -- kamu API'si ---------------------------------------------------

    def start(self) -> "_VaultWatcher":
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

    # -- iç işleyiş ----------------------------------------------------

    def _watch_targets(self) -> List[Path]:
        targets = [self.root]
        try:
            targets.extend(c for c in self.root.iterdir() if c.is_dir())
        except OSError:
            pass
        return targets

    def _md_files(self) -> List[Path]:
        raise NotImplementedError

    def _compute_signature(self):
        sig = []
        for path in self._md_files():
            try:
                sig.append((str(path), path.stat().st_mtime_ns))
            except OSError:
                continue
        return tuple(sorted(sig))

    def _sync_watch_paths(self) -> None:
        current = set(self._fs_watcher.directories())
        wanted = {str(p) for p in self._watch_targets() if p.is_dir()}
        stale = current - wanted
        if stale:
            self._fs_watcher.removePaths(list(stale))
        fresh = wanted - current
        if fresh:
            self._fs_watcher.addPaths(list(fresh))

    @Slot()
    def _schedule_check(self, *_args) -> None:
        self._debounce.start()

    @Slot()
    def _check_now(self) -> None:
        self._sync_watch_paths()
        signature = self._compute_signature()
        if signature == self._signature:
            return
        self._signature = signature
        try:
            getattr(bus, self.signal_name).emit("")
        except Exception:
            pass


class AgentsWatcher(_VaultWatcher):
    """`<kasa>/Entropy/Agents/**/AGENT.md` → `bus.agents_updated`."""

    subdir = AGENTS_SUBDIR
    signal_name = "agents_updated"

    def _md_files(self) -> List[Path]:
        files = []
        try:
            for child in self.root.iterdir():
                if child.is_dir():
                    candidate = child / AGENT_FILENAME
                    if candidate.is_file():
                        files.append(candidate)
        except OSError:
            pass
        return files


class TasksWatcher(_VaultWatcher):
    """
    Görev kartı izleyicisi — İKİ kök (Faz 9 kart kökü ayrımı).

    1. `<kasa>/Entropy/Tasks/*.md`                       — Entropy kartları
    2. `<kasa>/Entropy/Desk/Offices/<ofis>/cards/*.md`   — ofis kartları

    Ofis kökü eklenmeseydi bir ofis kartı elle (Obsidian'dan ya da harness
    tarafından) düzenlendiğinde `task_cards_updated` yayılmaz, Desk'in Kartlar
    sekmesi kullanıcı "Yenile"ye basana kadar eski durumu gösterirdi.
    """

    subdir = TASKS_SUBDIR
    signal_name = "task_cards_updated"

    def __init__(self, vault_path=None, poll_interval_ms: int = 5000, parent=None):
        # `_VaultWatcher.__init__` imzayı hesaplarken `desk_offices_root`'a
        # bakacağı için kök, super() çağrısından ÖNCE kurulur.
        if vault_path is None:
            from entropy.core.config import config

            vault_path = config.obsidian_vault_path
        try:
            from entropy.agents.tasks import DESK_OFFICES_SUBDIR, OFFICE_CARDS_DIRNAME
        except Exception:  # sözleşme eski sürümdeyse tek kökle çalış
            DESK_OFFICES_SUBDIR, OFFICE_CARDS_DIRNAME = "Entropy/Desk/Offices", "cards"
        self.desk_offices_root = Path(vault_path) / DESK_OFFICES_SUBDIR
        self._office_cards_dirname = OFFICE_CARDS_DIRNAME
        super().__init__(vault_path, poll_interval_ms, parent)

    def office_card_dirs(self) -> List[Path]:
        """Diskte var olan ofis kart klasörleri."""
        out: List[Path] = []
        try:
            for child in sorted(self.desk_offices_root.iterdir()):
                cards = child / self._office_cards_dirname
                if cards.is_dir():
                    out.append(cards)
        except OSError:
            return out
        return out

    def _watch_targets(self) -> List[Path]:
        # Ofis kökünün KENDİSİ de izlenir: yeni bir ofis klasörü açıldığında
        # (henüz cards/ yokken) izleyici uyanıp listeyi tazelesin.
        targets = super()._watch_targets()
        targets.append(self.desk_offices_root)
        targets.extend(self.office_card_dirs())
        return targets

    def _md_files(self) -> List[Path]:
        files: List[Path] = []
        for root in [self.root] + self.office_card_dirs():
            try:
                files.extend(p for p in root.glob("*.md") if p.is_file())
            except OSError:
                continue
        return files


_agents_watcher: Optional[AgentsWatcher] = None
_tasks_watcher: Optional[TasksWatcher] = None


def start_agent_watchers(vault_path: Optional[Path | str] = None, poll_interval_ms: int = 5000):
    """Süreç genelinde tek bir çift izleyici başlatır (yeniden çağrı güvenli)."""
    global _agents_watcher, _tasks_watcher
    if _agents_watcher is None:
        _agents_watcher = AgentsWatcher(vault_path, poll_interval_ms).start()
    if _tasks_watcher is None:
        _tasks_watcher = TasksWatcher(vault_path, poll_interval_ms).start()
    return _agents_watcher, _tasks_watcher


def stop_agent_watchers() -> bool:
    """
    İzleyicileri durdurur; durdurulduysa True.

    Kapanışta gerekli: QFileSystemWatcher ve zamanlayıcılar Qt olay döngüsü sona
    ererken hâlâ diriyse kasa dizinlerinde açık tanıtıcı tutar.
    """
    global _agents_watcher, _tasks_watcher
    stopped = False
    for watcher in (_agents_watcher, _tasks_watcher):
        if watcher is not None:
            try:
                watcher.stop()
                stopped = True
            except Exception:
                pass
    _agents_watcher = None
    _tasks_watcher = None
    return stopped
