"""
Rapor Merkezi — "Gelen" şeridi (Faz 4 iskeleti, Faz 5'te büyüyecek).

Sorun: üretilen raporlar, /query sayfaları ve ofis raporları listenin içine
karışıyor; kullanıcı hangisinin yeni geldiğini göremiyordu. Bu modül son 24
saatte üretilenleri ayrı bir şeritte toplar ve okundu/pin/arşiv durumunu
kalıcı tutar.

Durum dosyası: `<STATE_DIR>/report_inbox.json`
    {
      "items": {
        "<mutlak yol>": {"read": bool, "pinned": bool, "archived": bool,
                          "first_seen": <unix ts>}
      }
    }

Neden yol anahtarı: rapor dosyaları kimlik taşımıyor; yol tek kararlı anahtar.
Dosya silinirse girdisi ölü kalır ama zararsızdır (liste yalnızca var olan
dosyalardan kurulur) ve `prune()` ile temizlenebilir.

İş parçacığı notu: depo (store) saf Python'dur, Qt nesnesi tutmaz; izleyiciler
işçi iş parçacığından çağırabilir. Widget tarafı yalnızca ana iş parçacığında
kullanılmalıdır.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from entropy.core.config import STATE_DIR
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.ui_polish import BODY_PX, LABEL_PX, apply_no_hscroll

# "Gelen" penceresi: son 24 saat. Daha uzun tutulsa şerit arşive dönerdi.
INBOX_WINDOW_HOURS = 24

DEFAULT_STATE_FILENAME = "report_inbox.json"

# Şeritte aynı anda gösterilen en fazla girdi (kalanı listede zaten var).
MAX_STRIP_ITEMS = 12


def inbox_state_path() -> Path:
    return Path(STATE_DIR) / DEFAULT_STATE_FILENAME


class ReportInboxStore:
    """Okundu / pin / arşiv durumunun kalıcı deposu (saf Python, Qt'siz)."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else inbox_state_path()
        self._items: Dict[str, Dict[str, Any]] = {}
        self._dirty = False
        self.load()

    # ------------------------------------------------------------ kalıcılık

    def load(self) -> Dict[str, Dict[str, Any]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            items = raw.get("items", {})
            if isinstance(items, dict):
                self._items = {str(k): dict(v) for k, v in items.items() if isinstance(v, dict)}
        except (OSError, ValueError, TypeError):
            # Dosya yok ya da bozuk: boş durumla devam edilir. Kullanıcıya hata
            # göstermek gereksiz; en kötü ihtimalle her şey "okunmadı" görünür.
            self._items = {}
        return self._items

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps({"items": self._items}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._dirty = False
            return True
        except OSError:
            return False

    # ------------------------------------------------------------ sorgular

    @staticmethod
    def _key(path: Any) -> str:
        return str(path)

    def entry(self, path: Any) -> Dict[str, Any]:
        return dict(self._items.get(self._key(path), {}))

    def is_read(self, path: Any) -> bool:
        return bool(self.entry(path).get("read", False))

    def is_pinned(self, path: Any) -> bool:
        return bool(self.entry(path).get("pinned", False))

    def is_archived(self, path: Any) -> bool:
        return bool(self.entry(path).get("archived", False))

    # ------------------------------------------------------------ değişimler

    def _set(self, path: Any, autosave: bool = True, **changes: Any) -> Dict[str, Any]:
        key = self._key(path)
        item = self._items.setdefault(key, {"first_seen": time.time()})
        item.update(changes)
        if autosave:
            self.save()
        else:
            self._dirty = True
        return dict(item)

    # ------------------------------------------------- toplu (tek yazımlı) işlemler

    def set_many(self, paths: Any, **changes: Any) -> int:
        """Faz 9: N girdiyi tek dosya yazımıyla günceller.

        Eskiden `mark_all_read` her üye için tam JSON yazıyordu (yüzlerce yazım,
        arayüz kilitleniyordu). Artık tek `save()` var.
        """
        count = 0
        for path in paths:
            if path is None:
                continue
            self._set(path, autosave=False, **changes)
            count += 1
        if count:
            self.save()
        return count

    def mark_paths_read(self, paths: Any, read: bool = True) -> int:
        return self.set_many(paths, read=bool(read))

    def flush(self) -> bool:
        """Bekleyen (autosave=False) değişiklikleri diske yazar."""
        if not getattr(self, "_dirty", False):
            return True
        return self.save()

    def mark_read(self, path: Any, read: bool = True) -> Dict[str, Any]:
        return self._set(path, read=bool(read))

    def mark_unread(self, path: Any) -> Dict[str, Any]:
        return self.mark_read(path, False)

    def set_pinned(self, path: Any, pinned: bool = True) -> Dict[str, Any]:
        return self._set(path, pinned=bool(pinned))

    def toggle_pinned(self, path: Any) -> bool:
        state = not self.is_pinned(path)
        self.set_pinned(path, state)
        return state

    def set_archived(self, path: Any, archived: bool = True) -> Dict[str, Any]:
        # Arşivlenen girdi şeritten düşer ama okunmamışsa sayaçtan da düşmeli:
        # kullanıcı "sonra bakarım" demeden kaldırdıysa rozet artık uyarmasın.
        changes: Dict[str, Any] = {"archived": bool(archived)}
        if archived:
            changes["read"] = True
        return self._set(path, **changes)

    def prune(self, existing_paths) -> int:
        """Artık var olmayan dosyaların girdilerini siler; silinen sayısını döner."""
        keep = {self._key(p) for p in existing_paths}
        dead = [k for k in self._items if k not in keep]
        for key in dead:
            self._items.pop(key, None)
        if dead:
            self.save()
        return len(dead)

    # ------------------------------------------------------------ gelen kutusu

    def inbox_entries(
        self,
        entries: List[Dict[str, Any]],
        hours: int = INBOX_WINDOW_HOURS,
        now: Optional[float] = None,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Rapor künyelerinden "Gelen" listesini süzer.

        Girdi, `reports_viewer.read_report_meta` künyeleriyle aynı biçimdedir:
        en azından `path` ve `mtime` alanları beklenir. Pinlenen girdi 24 saat
        penceresi dolsa da listede kalır (kullanıcı bilerek sabitlemiştir).
        Sıralama: önce pinliler, sonra en yeni.
        """
        cutoff = (now if now is not None else time.time()) - hours * 3600
        result: List[Dict[str, Any]] = []
        for entry in entries or []:
            path = entry.get("path")
            if not path:
                continue
            state = self.entry(path)
            archived = bool(state.get("archived", False))
            if archived and not include_archived:
                continue
            pinned = bool(state.get("pinned", False))
            try:
                mtime = float(entry.get("mtime") or 0.0)
            except (TypeError, ValueError):
                mtime = 0.0
            if mtime < cutoff and not pinned:
                continue
            merged = dict(entry)
            merged["read"] = bool(state.get("read", False))
            merged["pinned"] = pinned
            merged["archived"] = archived
            merged["mtime"] = mtime
            result.append(merged)
        result.sort(key=lambda e: (not e["pinned"], -e["mtime"]))
        return result

    def unread_count(
        self,
        entries: List[Dict[str, Any]],
        hours: int = INBOX_WINDOW_HOURS,
        now: Optional[float] = None,
    ) -> int:
        """Gelen şeridindeki okunmamış girdi sayısı (Zen/Chat rozeti bunu gösterir)."""
        return sum(1 for e in self.inbox_entries(entries, hours=hours, now=now) if not e["read"])


#: Faz 9 — süreç genelinde TEK depo.
#: Zen (`reports_viewer`) ve Chat (`chat_mode`) ayrı `ReportInboxStore()`
#: örnekleri kuruyordu; her `save()` tüm sözlüğü ezdiği için "son yazan kazanır"
#: yarışı oluşuyor ve Chat'te "okundu / tümünü okundu / temizle" geri alınıyordu.
_SHARED_STORE: Optional["ReportInboxStore"] = None


def get_shared_store() -> "ReportInboxStore":
    """Tüm rapor yüzeylerinin paylaştığı tekil okundu/pin/arşiv deposu."""
    global _SHARED_STORE
    if _SHARED_STORE is None:
        _SHARED_STORE = ReportInboxStore()
    return _SHARED_STORE


def reset_shared_store(store: Optional["ReportInboxStore"] = None) -> "ReportInboxStore":
    """Testler için: tekil depoyu değiştirir/sıfırlar."""
    global _SHARED_STORE
    _SHARED_STORE = store if store is not None else ReportInboxStore()
    return _SHARED_STORE


#: Kunye onbellegi: (yol, mtime, boyut) -> `read_report_meta` sonucu.
_META_CACHE: Dict[tuple, Dict[str, Any]] = {}
_META_CACHE_MAX = 4000


def collect_recent_entries(limit: int = 60) -> List[Dict[str, Any]]:
    """
    Kasadan rapor künyelerini toplar (Chat kipi gibi rapor okuyucusu olmayan
    yüzeyler için).

    Raporlar sekmesi zaten kendi listesini kuruyor; burada aynı iş ikinci kez
    yapılmaz, yalnızca kasadaki rapor dosyaları taranır. Kasa okunamazsa boş
    liste döner (Chat üst çubuğu rozeti göstermez, çökmez).
    """
    try:
        from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
        from entropy.ui.widgets.reports_viewer import read_report_meta

        vault = ObsidianVaultManager()
        entries: List[Dict[str, Any]] = []
        for report in list(vault.list_reports() or [])[: max(1, int(limit))]:
            path = Path(str(report.get("path", "")))
            try:
                st = path.stat()
            except OSError:
                continue
            # Faz 9 - artimli tazeleme: imzasi (mtime, boyut) degismeyen kunye
            # yeniden okunmaz. Eskiden her `reports_updated` sinyalinde 703
            # dosya bastan okunuyordu.
            sig = (str(path), st.st_mtime, st.st_size)
            cached = _META_CACHE.get(sig)
            if cached is not None:
                merged = dict(report)
                merged.update(cached)
                for key in ("kind", "office", "importance"):
                    if not merged.get(key) and report.get(key) is not None:
                        merged[key] = report.get(key)
                entries.append(merged)
                continue
            # `read_report_meta` dosyayi kendi basina okur ve `kind`/`office`
            # gibi YALNIZCA kasa taramasinin bildigi alanlari uretmez. Kunyeyi
            # `list_reports()` sozlugunun uzerine bindiriyoruz: dosyadan okunan
            # baslik/etiket kazanir, tarama alanlari (kind, office, importance)
            # korunur. Duz `read_report_meta(path)` bunlari dusuruyordu.
            meta = read_report_meta(path)
            merged: Dict[str, Any] = dict(report)
            merged.update(meta)
            for key in ("kind", "office", "importance"):
                if not merged.get(key) and report.get(key) is not None:
                    merged[key] = report.get(key)
            if len(_META_CACHE) > _META_CACHE_MAX:
                _META_CACHE.clear()
            _META_CACHE[sig] = dict(meta)
            entries.append(merged)
        return entries
    except Exception:
        return []


# --------------------------------------------------------------------- rozet

class InboxBadge(QLabel):
    """
    Üst çubuktaki küçük okunmadı rozeti.

    Sıfırken gizlenir: her zaman görünen "0" üst çubukta gürültü yaratıyordu.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.count = 0
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setVisible(False)

    def set_count(self, count: int) -> None:
        self.count = max(0, int(count or 0))
        if not self.count:
            self.setText("")
            self.setToolTip("")
            self.setVisible(False)
            return
        self.setText(
            f"<span style='background:{RT['accent_soft']}; color:{RT['accent_warn']};"
            f" border-radius:9px; padding:2px 9px; font-size:{LABEL_PX}px;"
            f" font-weight:600;'>{self.count}</span>"
        )
        self.setToolTip(
            f"Son {INBOX_WINDOW_HOURS} saatte gelen {self.count} okunmamış rapor."
            " Raporlar sekmesindeki “Gelen” şeridinden açabilirsiniz."
        )
        self.setVisible(True)


# --------------------------------------------------------------------- şerit

class InboxItemWidget(QFrame):
    """Gelen şeridindeki tek girdi: başlık + pin + arşiv düğmeleri."""

    def __init__(self, entry: Dict[str, Any], strip: "ReportInboxStrip", parent=None):
        super().__init__(parent)
        self.entry = entry
        self.strip = strip
        self.path = str(entry.get("path", ""))
        self.setObjectName("inboxItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        unread = not entry.get("read", False)
        accent = RT["accent_warn"] if unread else RT["divider"]
        self.setProperty("role", "panel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(6)

        title = str(entry.get("title") or entry.get("label") or Path(self.path).stem)
        weight = "600" if unread else "400"
        color = RT["text"] if unread else RT["text_dim"]
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "label")
        # Uzun rapor başlıkları şeridi genişletmesin; kırpma + tam metin ipucu.
        self.title_label.setMaximumWidth(280)
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.title_label.setToolTip(f"{title}\n{self.path}")
        layout.addWidget(self.title_label, 1)

        self.pin_btn = QPushButton("")
        self.pin_btn.setProperty("role", "icon")
        self.pin_btn.setToolTip(
            "Sabitlemeyi kaldır" if entry.get("pinned") else "Sabitle (24 saat dolsa da listede kalsın)"
        )
        self.pin_btn.clicked.connect(self._on_pin)
        layout.addWidget(self.pin_btn)

        self.archive_btn = QPushButton("")
        self.archive_btn.setAccessibleName("Arşivle (şeritten kaldır; rapor listesinde kalır)")
        self.archive_btn.setProperty("role", "icon")
        self.archive_btn.setToolTip("Arşivle (şeritten kaldır; rapor listesinde kalır)")
        self.archive_btn.clicked.connect(self._on_archive)
        layout.addWidget(self.archive_btn)

    @staticmethod
    def _btn_style(active: bool) -> str:
        color = RT["accent_warn"] if active else RT["text_dim"]
        return (
            f"QPushButton {{ background:transparent; border:none; color:{color};"
            f" font-size:{LABEL_PX}px; padding:0px; }}"
            f" QPushButton:hover {{ color:{RT['accent']}; }}"
        )

    def _on_pin(self) -> None:
        self.strip.toggle_pin(self.path)

    def _on_archive(self) -> None:
        self.strip.archive(self.path)

    def mousePressEvent(self, event):  # noqa: N802
        # Düğmeler kendi tıklamalarını yutar; buraya gelen tıklama gövdedendir.
        self.strip.open_report(self.path)
        super().mousePressEvent(event)


class ReportInboxStrip(QFrame):
    """
    Raporlar sekmesinin üstündeki "Gelen" şeridi.

    Kullanım: `set_entries(...)` rapor künyelerini verir; şerit son 24 saatlik
    olanları gösterir. Girdiye tıklanınca `report_opened` yayılır (okuyucu
    raporu açar) ve girdi okundu işaretlenir; `unread_changed` rozeti günceller.
    """

    report_opened = Signal(str)   # açılacak rapor yolu
    unread_changed = Signal(int)  # okunmadı sayısı

    def __init__(self, parent=None, store: Optional[ReportInboxStore] = None):
        super().__init__(parent)
        self.setObjectName("inboxStrip")
        self.setMinimumWidth(240)  # dar panelde şerit daralsın, paneli itmesin
        self.store = store if store is not None else get_shared_store()
        self._entries: List[Dict[str, Any]] = []
        self._now_override: Optional[float] = None

        self.setProperty("role", "panel")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(5)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.header_label = QLabel("")
        self.header_label.setProperty("role", "label")
        # Zengin metin başlığın doğal minimumu (~540 px) şeridi ve onu barındıran
        # Zen sol sekmesini dar panelde kırpıyordu; daralmaya izin ver.
        self.header_label.setMinimumWidth(110)
        head.addWidget(self.header_label, 1)
        head.addStretch()
        self.mark_all_btn = QPushButton("Tümünü okundu say")
        self.mark_all_btn.setAccessibleName("Tümünü okundu say")
        self.mark_all_btn.setToolTip("Gelen şeridindeki bütün raporları okundu işaretle")
        self.mark_all_btn.setProperty("variant", "ghost")
        self.mark_all_btn.clicked.connect(self.mark_all_read)
        head.addWidget(self.mark_all_btn)
        root.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setFixedHeight(48)
        self.scroll.viewport().setAutoFillBackground(False)
        # Şerit yatay: burada dikey çubuk gereksiz, yatay çubuk gerekli.
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.items_host = QWidget()
        self.items_layout = QHBoxLayout(self.items_host)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(6)
        self.items_layout.addStretch()
        self.scroll.setWidget(self.items_host)
        root.addWidget(self.scroll)

        self.empty_label = QLabel("")
        self.empty_label.setProperty("role", "label")
        root.addWidget(self.empty_label)

        self.item_widgets: List[InboxItemWidget] = []
        self.set_entries([])

    # ------------------------------------------------------------ veri

    def set_now(self, now: Optional[float]) -> None:
        """Testler için sabit "şimdi" (24 saat penceresini deterministik yapar)."""
        self._now_override = now

    def set_entries(self, entries: List[Dict[str, Any]]) -> None:
        self._entries = list(entries or [])
        self.refresh()

    def visible_entries(self) -> List[Dict[str, Any]]:
        return self.store.inbox_entries(self._entries, now=self._now_override)

    def unread_count(self) -> int:
        return sum(1 for e in self.visible_entries() if not e["read"])

    # ------------------------------------------------------------ görünüm

    def refresh(self) -> None:
        while self.items_layout.count() > 1:
            item = self.items_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.item_widgets = []

        visible = self.visible_entries()
        unread = sum(1 for e in visible if not e["read"])
        self.header_label.setText(
            f"<b style='color:{RT['accent']}; font-size:{BODY_PX}px;'>GELEN</b>"
            f" <span style='color:{RT['text_dim']}; font-size:{LABEL_PX}px;'>"
            f"son {INBOX_WINDOW_HOURS} saat · {len(visible)} rapor"
            + (f" · {unread} okunmadı" if unread else "") + "</span>"
        )
        if not visible:
            self.empty_label.setText(
                f"Son {INBOX_WINDOW_HOURS} saatte yeni rapor gelmedi."
                " Bir araştırma ya da ofis kartı tamamlandığında burada belirir."
            )
            self.empty_label.setVisible(True)
            self.scroll.setVisible(False)
        else:
            self.empty_label.setVisible(False)
            self.scroll.setVisible(True)
            for entry in visible[:MAX_STRIP_ITEMS]:
                widget = InboxItemWidget(entry, self)
                self.item_widgets.append(widget)
                self.items_layout.insertWidget(self.items_layout.count() - 1, widget)
        self.mark_all_btn.setEnabled(bool(unread))
        self.unread_changed.emit(unread)

    # ------------------------------------------------------------ eylemler

    def open_report(self, path: str) -> None:
        """Girdiyi okundu işaretler ve okuyucuya açtırır."""
        if not path:
            return
        self.store.mark_read(path, True)
        self.refresh()
        self.report_opened.emit(str(path))

    def toggle_pin(self, path: str) -> bool:
        state = self.store.toggle_pinned(path)
        self.refresh()
        return state

    def archive(self, path: str) -> None:
        self.store.set_archived(path, True)
        self.refresh()

    def mark_all_read(self) -> None:
        for entry in self.visible_entries():
            self.store.mark_read(entry["path"], True)
        self.refresh()
