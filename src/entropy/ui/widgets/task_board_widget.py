"""
Ajan görev panosu — kanban görünümü.

Sütunlar: Bekliyor / Çalışıyor / İnceleme / Bitti. `failed` durumundaki kartlar
kırmızı rozetle İnceleme sütununda durur; başarısızlık gizlenmez, ele alınması
gereken bir iş olarak kalır. Kart seçilince sağda detay paneli açılır.

Veri kaynağı `entropy.agents.tasks.TaskBoard`; modül henüz yoksa pano boş
görünür (import guard). Testler yapıcıya sahte pano verebilir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
    QSplitter, QVBoxLayout, QWidget
)

from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.agents_widget import (
    STATUS_COLORS, STATUS_LABELS, call_flex, load_board, spec_field
)

# Kanban sütunları: (anahtar, başlık). `failed` ayrı sütun değil, İnceleme'de rozet.
COLUMNS = [
    ("backlog", "Bekliyor"),
    ("running", "Çalışıyor"),
    ("review", "İnceleme"),
    ("done", "Bitti"),
]


def column_for_status(status: str) -> str:
    """Durumu sütun anahtarına eşler; bilinmeyen durumlar Bekliyor'a düşer."""
    status = (status or "").strip()
    if status == "failed":
        return "review"
    if status in {key for key, _ in COLUMNS}:
        return status
    return "backlog"


def format_duration(card: Any) -> str:
    """started_at → finished_at aralığını insan okur biçimde döndürür."""
    from datetime import datetime

    def parse(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    start = parse(spec_field(card, "started_at", ""))
    end = parse(spec_field(card, "finished_at", ""))
    if start is None:
        return ""
    if end is None:
        return "sürüyor"
    seconds = max(0, int((end - start).total_seconds()))
    if seconds < 60:
        return f"{seconds} sn"
    if seconds < 3600:
        return f"{seconds // 60} dk {seconds % 60} sn"
    return f"{seconds // 3600} sa {(seconds % 3600) // 60} dk"


class TaskCardWidget(QFrame):
    """Kanban kartı: başlık, ajan, sağlayıcı/model, süre, özet."""

    def __init__(self, card: Any, board_widget: "TaskBoardWidget", parent=None):
        super().__init__(parent)
        self.card = card
        self.board_widget = board_widget
        self.card_id = str(spec_field(card, "id", ""))
        self.status = str(spec_field(card, "status", "backlog"))
        self.setObjectName("taskCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        accent = STATUS_COLORS.get(self.status, RT["text_dim"])
        self.setStyleSheet(
            f"""
            QFrame#taskCard {{
                background-color: {RT['surface_raised']};
                border: 1px solid {RT['divider_soft']};
                border-left: 3px solid {accent};
                border-radius: {RT['radius_small']};
            }}
            QFrame#taskCard:hover {{ border-color: {RT['accent']}; }}
            QLabel {{ background: transparent; border: none; }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 7, 9, 7)
        layout.setSpacing(3)

        title_text = str(spec_field(card, "title", "(başlıksız)"))
        header = title_text
        if self.status == "failed":
            header = (
                f"<span style='background:#4A1A1F; color:#FF6B6B; font-size:9px; "
                f"padding:1px 5px; border-radius:3px;'>BAŞARISIZ</span> {title_text}"
            )
        self.title_label = QLabel(
            f"<span style='color:{RT['text']}; font-size:12px; font-weight:600;'>{header}</span>"
        )
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        meta_bits = [str(spec_field(card, "agent", "")) or "—"]
        provider = str(spec_field(card, "provider", ""))
        model = str(spec_field(card, "model", ""))
        if provider or model:
            meta_bits.append(f"{provider}/{model}".strip("/"))
        duration = format_duration(card)
        if duration:
            meta_bits.append(duration)
        meta_label = QLabel(
            f"<span style='color:{RT['text_dim']}; font-size:10px;'>"
            f"{' · '.join(b for b in meta_bits if b)}</span>"
        )
        # Dar sütunda tek satır kırpılıyordu; sağlayıcı/model okunur kalsın.
        meta_label.setWordWrap(True)
        layout.addWidget(meta_label)

        summary = str(spec_field(card, "summary", ""))
        if summary:
            short = summary if len(summary) <= 110 else summary[:107] + "…"
            summary_label = QLabel(
                f"<span style='color:{RT['text_body']}; font-size:11px;'>{short}</span>"
            )
            summary_label.setWordWrap(True)
            layout.addWidget(summary_label)

    def mousePressEvent(self, event):
        self.board_widget.select_card(self.card_id)
        super().mousePressEvent(event)


class TaskDetailPanel(QFrame):
    """Seçili kartın hedefi, ölçütleri, çıktıları ve eylemleri."""

    def __init__(self, board_widget: "TaskBoardWidget", parent=None):
        super().__init__(parent)
        self.board_widget = board_widget
        self.card: Any = None
        self.setObjectName("cardFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        self.title_label = QLabel("")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.body_label = QLabel("Bir görev kartı seçin.")
        self.body_label.setWordWrap(True)
        self.body_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.body_label.setStyleSheet(
            f"color:{RT['text_body']}; font-size:12px; background:transparent; border:none;"
        )
        layout.addWidget(self.body_label)

        self.outputs_container = QWidget()
        self.outputs_layout = QVBoxLayout(self.outputs_container)
        self.outputs_layout.setContentsMargins(0, 0, 0, 0)
        self.outputs_layout.setSpacing(3)
        layout.addWidget(self.outputs_container)

        layout.addStretch()

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.run_btn = QPushButton("▶ Çalıştır")
        self.run_btn.setToolTip("Kartı ajana gönder")
        self.run_btn.clicked.connect(self._on_run)
        actions.addWidget(self.run_btn)

        self.stop_btn = QPushButton("■ Durdur")
        self.stop_btn.setToolTip("Çalışan görevi sonlandır")
        self.stop_btn.clicked.connect(self._on_stop)
        actions.addWidget(self.stop_btn)

        self.done_btn = QPushButton("✓ Bitti")
        self.done_btn.setToolTip("Görevi bitti olarak işaretle")
        self.done_btn.clicked.connect(self._on_done)
        actions.addWidget(self.done_btn)

        self.contract_btn = QPushButton("📄 Sözleşme")
        self.contract_btn.setToolTip("Kartın sözleşme dosyasını rapor okuyucuda aç")
        self.contract_btn.clicked.connect(self._on_open_contract)
        actions.addWidget(self.contract_btn)

        self.delete_btn = QPushButton("🗑 Sil")
        self.delete_btn.setToolTip("Kartı panodan sil")
        self.delete_btn.clicked.connect(self._on_delete)
        actions.addWidget(self.delete_btn)
        actions.addStretch()
        layout.addLayout(actions)

        self.set_card(None)

    def set_card(self, card: Any) -> None:
        self.card = card
        has_card = card is not None
        for btn in (self.run_btn, self.stop_btn, self.done_btn, self.contract_btn, self.delete_btn):
            btn.setEnabled(has_card)
        while self.outputs_layout.count():
            item = self.outputs_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        if not has_card:
            self.title_label.setText(
                f"<b style='color:{RT['accent']}; font-size:12px;'>GÖREV DETAYI</b>"
            )
            self.body_label.setText("Bir görev kartı seçin.")
            return

        status = str(spec_field(card, "status", "backlog"))
        color = STATUS_COLORS.get(status, RT["text_dim"])
        self.title_label.setText(
            f"<b style='color:{RT['text']}; font-size:13px;'>{spec_field(card, 'title', '')}</b>"
            f" <span style='color:{color}; font-size:11px;'>"
            f"[{STATUS_LABELS.get(status, status)}]</span>"
        )
        criteria = list(spec_field(card, "criteria", []) or [])
        criteria_html = (
            "<ul style='margin:4px 0 0 0;'>"
            + "".join(f"<li>{c}</li>" for c in criteria)
            + "</ul>"
            if criteria
            else "<i>ölçüt tanımlanmadı</i>"
        )
        self.body_label.setText(
            f"<b>Ajan:</b> {spec_field(card, 'agent', '—')} · "
            f"{spec_field(card, 'provider', '')}/{spec_field(card, 'model', '')}<br>"
            f"<b>Hedef:</b><br>{spec_field(card, 'goal', '—')}<br>"
            f"<b>Kabul ölçütleri:</b>{criteria_html}"
        )
        for out in list(spec_field(card, "output_paths", []) or []):
            btn = QPushButton(f"📄 {Path(str(out)).name}")
            btn.setToolTip(str(out))
            btn.setProperty("output_path", str(out))
            btn.clicked.connect(self._on_open_output)
            self.outputs_layout.addWidget(btn)

    # --------------------------------------------------------- eylemler

    def _on_run(self):
        self.board_widget.run_card(str(spec_field(self.card, "id", "")))

    def _on_stop(self):
        self.board_widget.stop_card(str(spec_field(self.card, "id", "")))

    def _on_done(self):
        self.board_widget.mark_done(str(spec_field(self.card, "id", "")))

    def _on_delete(self):
        self.board_widget.delete_card(str(spec_field(self.card, "id", "")))

    def _on_open_contract(self):
        path = str(spec_field(self.card, "path", ""))
        if path:
            bus.report_created.emit(path)

    def _on_open_output(self):
        sender = self.sender()
        path = sender.property("output_path") if sender is not None else None
        if path:
            bus.report_created.emit(str(path))


class TaskBoardWidget(QFrame):
    """Kanban panosu + detay paneli."""

    card_selected = Signal(str)

    def __init__(self, parent=None, board: Any = None, compact: bool = False):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.board = board if board is not None else load_board()
        self.compact = compact
        self.selected_id: str = ""
        self.column_layouts: Dict[str, QVBoxLayout] = {}
        self.column_headers: Dict[str, QLabel] = {}
        self.card_widgets: List[TaskCardWidget] = []
        self._cards: List[Any] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.addWidget(QLabel(
            f"<b style='color:{RT['accent']}; font-size:13px;'>🗂 AJAN GÖREV PANOSU</b>"
        ))
        header.addStretch()
        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.setFixedHeight(22)
        self.refresh_btn.clicked.connect(self.refresh_cards)
        header.addWidget(self.refresh_btn)
        root.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        columns_host = QWidget()
        columns_layout = QHBoxLayout(columns_host)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(6)
        for key, label in COLUMNS:
            column = QFrame()
            column.setStyleSheet(
                f"background-color:{RT['surface_base']}; border:1px solid {RT['divider_soft']};"
                f" border-radius:{RT['radius']};"
            )
            col_layout = QVBoxLayout(column)
            col_layout.setContentsMargins(6, 6, 6, 6)
            col_layout.setSpacing(5)
            head = QLabel("")
            head.setStyleSheet("background:transparent; border:none;")
            col_layout.addWidget(head)
            self.column_headers[key] = head

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
            inner = QWidget()
            inner_layout = QVBoxLayout(inner)
            inner_layout.setContentsMargins(0, 0, 0, 0)
            inner_layout.setSpacing(5)
            inner_layout.addStretch()
            scroll.setWidget(inner)
            col_layout.addWidget(scroll, 1)
            self.column_layouts[key] = inner_layout
            columns_layout.addWidget(column, 1)
        splitter.addWidget(columns_host)

        self.detail_panel = TaskDetailPanel(self)
        if not compact:
            splitter.addWidget(self.detail_panel)
            splitter.setSizes([700, 320])
        else:
            self.detail_panel.setVisible(False)
        root.addWidget(splitter, 1)

        signal = getattr(bus, "task_cards_updated", None)
        if signal is not None:
            signal.connect(self._on_cards_updated)

        self.refresh_cards()

    # ------------------------------------------------------------ veri

    def _on_cards_updated(self, _payload: str = "") -> None:
        """Sözleşme sinyali alıcısı (QObject metodu, lambda değil)."""
        self.refresh_cards()

    def list_cards(self) -> List[Any]:
        if self.board is None:
            return []
        try:
            return list(self.board.list() or [])
        except Exception:
            return []

    def get_card(self, card_id: str) -> Optional[Any]:
        for card in self._cards:
            if str(spec_field(card, "id", "")) == card_id:
                return card
        return None

    def cards_in_column(self, key: str) -> List[Any]:
        return [c for c in self._cards if column_for_status(str(spec_field(c, "status", ""))) == key]

    def refresh_cards(self) -> None:
        self._cards = self.list_cards()
        self.card_widgets = []
        for key, layout in self.column_layouts.items():
            while layout.count() > 1:
                item = layout.takeAt(0)
                widget = item.widget() if item else None
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
            column_cards = self.cards_in_column(key)
            label = dict(COLUMNS)[key]
            self.column_headers[key].setText(
                f"<span style='color:{RT['text_dim']}; font-size:11px; font-weight:600; "
                f"letter-spacing:0.4px;'>{label.upper()}</span>"
                f" <span style='color:{RT['text_dim']}; font-size:10px;'>({len(column_cards)})</span>"
            )
            for card in column_cards:
                widget = TaskCardWidget(card, self)
                self.card_widgets.append(widget)
                layout.insertWidget(layout.count() - 1, widget)
        current = self.get_card(self.selected_id) if self.selected_id else None
        self.detail_panel.set_card(current)

    # ------------------------------------------------------------ eylemler

    def select_card(self, card_id: str) -> None:
        self.selected_id = card_id
        self.detail_panel.set_card(self.get_card(card_id))
        self.card_selected.emit(card_id)

    def _emit_updated(self, card_id: str) -> None:
        signal = getattr(bus, "task_cards_updated", None)
        if signal is not None:
            signal.emit(card_id)
        else:
            self.refresh_cards()

    def _set_status(self, card_id: str, status: str) -> Any:
        """
        Kart durumunu günceller.

        Gerçek pano `update(card)` biçiminde tam kart nesnesi ister (dataclass);
        sahte panolar ise `update(id, **alanlar)` kabul eder. Önce nesne yolu
        denenir, olmazsa sözlük yoluna düşülür.
        """
        current = None
        try:
            current = self.board.get(card_id)
        except Exception:
            current = self.get_card(card_id)
        if current is not None and hasattr(current, "__dataclass_fields__"):
            from dataclasses import replace

            return self.board.update(replace(current, status=status))
        return call_flex(self.board.update, {"status": status}, card_id)

    def run_card(self, card_id: str) -> bool:
        if self.board is None or not card_id:
            return False
        try:
            self.board.run(card_id)
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Görev Panosu] Çalıştırma hatası: {exc}\n")
            return False
        self.refresh_cards()
        self._emit_updated(card_id)
        return True

    def stop_card(self, card_id: str) -> bool:
        if self.board is None or not card_id:
            return False
        try:
            self.board.stop(card_id)
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Görev Panosu] Durdurma hatası: {exc}\n")
            return False
        self.refresh_cards()
        self._emit_updated(card_id)
        return True

    def mark_done(self, card_id: str) -> bool:
        if self.board is None or not card_id:
            return False
        try:
            self._set_status(card_id, "done")
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Görev Panosu] Güncelleme hatası: {exc}\n")
            return False
        self.refresh_cards()
        self._emit_updated(card_id)
        return True

    def delete_card(self, card_id: str, confirm: bool = True) -> bool:
        if self.board is None or not card_id:
            return False
        if confirm:
            answer = QMessageBox.question(
                self, "Görevi Sil", f"'{card_id}' görev kartı silinsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        try:
            self.board.delete(card_id)
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Görev Panosu] Silme hatası: {exc}\n")
            return False
        if self.selected_id == card_id:
            self.selected_id = ""
        self.refresh_cards()
        self._emit_updated(card_id)
        return True


class CompactTaskListWidget(QFrame):
    """Chat modu için kompakt görev listesi + açık görev rozeti."""

    def __init__(self, parent=None, board: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.board = board if board is not None else load_board()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        head = QHBoxLayout()
        head.addWidget(QLabel(
            f"<b style='color:{RT['accent']}; font-size:12px;'>🗂 AJAN GÖREVLERİ</b>"
        ))
        head.addStretch()
        self.count_badge = QLabel("")
        self.count_badge.setToolTip("Açık (bekleyen + çalışan + inceleme) görev sayısı")
        head.addWidget(self.count_badge)
        layout.addLayout(head)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(3)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        scroll.setWidget(self.list_container)
        layout.addWidget(scroll, 1)

        signal = getattr(bus, "task_cards_updated", None)
        if signal is not None:
            signal.connect(self._on_cards_updated)
        self.refresh_cards()

    def _on_cards_updated(self, _payload: str = "") -> None:
        self.refresh_cards()

    def open_count(self) -> int:
        cards = []
        if self.board is not None:
            try:
                cards = list(self.board.list() or [])
            except Exception:
                cards = []
        return sum(
            1 for c in cards
            if str(spec_field(c, "status", "")) in {"backlog", "running", "review", "failed"}
        )

    def refresh_cards(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        cards = []
        if self.board is not None:
            try:
                cards = list(self.board.list() or [])
            except Exception:
                cards = []
        open_n = self.open_count()
        color = RT["accent_warn"] if open_n else RT["text_dim"]
        self.count_badge.setText(
            f"<span style='color:{color}; font-size:11px; font-weight:600;'>{open_n} açık</span>"
        )
        for card in cards[:12]:
            status = str(spec_field(card, "status", "backlog"))
            row = QLabel(
                f"<span style='color:{STATUS_COLORS.get(status, RT['text_dim'])}; font-size:11px;'>●</span> "
                f"<span style='color:{RT['text_body']}; font-size:11px;'>"
                f"{spec_field(card, 'title', '')}</span> "
                f"<span style='color:{RT['text_dim']}; font-size:10px;'>"
                f"{spec_field(card, 'agent', '')} · {STATUS_LABELS.get(status, status)}</span>"
            )
            row.setStyleSheet("background:transparent; border:none;")
            self.list_layout.addWidget(row)
        if not cards:
            empty = QLabel(
                f"<span style='color:{RT['text_dim']}; font-size:11px;'>Ajan görevi yok.</span>"
            )
            empty.setStyleSheet("background:transparent; border:none;")
            self.list_layout.addWidget(empty)
