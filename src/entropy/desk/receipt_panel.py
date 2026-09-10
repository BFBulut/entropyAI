"""
Desk "Makbuz" bölmesi: ofis raporunu bölümlere ayırıp katlanabilir başlıklarla
gösterir ve altına yorum kutusu koyar.

Faz 10-C. Ayrıştırma `desk/receipt.py` (Qt'siz saf modül); Zen Rapor Merkezi
aynı ayrıştırıcıyı salt-okuma modunda kullanır. Yorum `instruct_office(office,
text, task_id=card_id)` ile ofisin posta kutusuna düşer: kart DURMAZ, model
çağrılmaz, kota harcanmaz — orkestratör bir sonraki planından önce okur.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QToolButton, QTextBrowser, QVBoxLayout, QWidget,
)

from entropy.core.event_bus import bus
from entropy.desk.receipt import (
    RECEIPT_SECTIONS, SECTION_ICONS, load_receipt, parse_receipt, receipt_order,
    receipt_summary, section_body_html,
)
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.agents_widget import spec_field
from entropy.ui.widgets.lifecycle import discard_widget

# Açılışta açık gelen bölümler: kullanıcı önce "ne yapıldı / kanıt ne" diye
# bakıyor; Plan ve Yorumlar katlı başlar.
DEFAULT_OPEN = ("İlerleme", "Değerlendirme", "Kanıt", "Değişiklikler", "PR")


class CollapsibleSection(QWidget):
    """Tek makbuz bölümü: tıklanabilir başlık + katlanır gövde."""

    def __init__(self, title: str, body_html: str, expanded: bool = True, parent=None):
        super().__init__(parent)
        self.title = title
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setText(f"{SECTION_ICONS.get(title, '▪')}  {title}")
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.toggle.setProperty("variant", "ghost")
        self.toggle.toggled.connect(self._on_toggled)
        layout.addWidget(self.toggle)

        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(True)
        self.body.setHtml(body_html)
        self.body.setProperty("role", "reader")
        self.body.setMinimumHeight(48)
        self.body.setMaximumHeight(220)
        self.body.setVisible(expanded)
        layout.addWidget(self.body)

    @Slot(bool)
    def _on_toggled(self, checked: bool) -> None:
        self.body.setVisible(checked)
        self.toggle.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    def is_expanded(self) -> bool:
        return self.toggle.isChecked()


class ReceiptPanel(QFrame):
    """Kartın ofis raporu: bölümlü görünüm + yorum ekleme."""

    comment_sent = Signal(str)

    def __init__(self, parent=None, office: str = "", card: Any = None,
                 read_only: bool = False, vault_path: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.office = office or ""
        self.card: Any = None
        self.read_only = read_only
        self.vault_path = vault_path
        self.sections: Dict[str, str] = {}
        self.path: Optional[Path] = None
        self._sections_widgets: List[CollapsibleSection] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self.header_label = QLabel("")
        self.header_label.setWordWrap(True)
        self.header_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.header_label.setOpenExternalLinks(True)
        self.header_label.setProperty("role", "label")
        layout.addWidget(self.header_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(4)
        self.container_layout.addStretch()
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)

        comment = QHBoxLayout()
        comment.setSpacing(6)
        self.comment_input = QLineEdit()
        self.comment_input.setPlaceholderText(
            "Bu makbuza yorum… (kart durmaz, orkestratörün posta kutusuna düşer)"
        )
        self.comment_input.returnPressed.connect(self.send_comment)
        comment.addWidget(self.comment_input, 1)
        self.comment_btn = QPushButton("Yorum ekle")
        self.comment_btn.setAccessibleName("Yorum ekle")
        self.comment_btn.clicked.connect(self.send_comment)
        comment.addWidget(self.comment_btn)
        self.comment_row = comment
        layout.addLayout(comment)

        self.comment_status = QLabel("")
        self.comment_status.setProperty("role", "label")
        layout.addWidget(self.comment_status)

        if read_only:
            for widget in (self.comment_input, self.comment_btn):
                widget.setVisible(False)
            self.comment_status.setVisible(False)

        self.set_card(card, office)

    # ------------------------------------------------------------ veri

    def set_office(self, office: str) -> None:
        self.office = office or ""
        self.set_card(self.card, self.office)

    def set_card(self, card: Any, office: str = "") -> None:
        self.card = card
        if office:
            self.office = office
        card_id = str(spec_field(card, "id", "") or "") if card is not None else ""
        text = ""
        self.path = None
        if card_id and self.office:
            self.path, text = load_receipt(self.office, card_id, self.vault_path)
        self.set_text(text, title=str(spec_field(card, "title", "") or "") if card else "")
        has_card = card is not None and bool(self.office)
        self.comment_input.setEnabled(has_card)
        self.comment_btn.setEnabled(has_card)

    def set_text(self, text: str, title: str = "") -> None:
        """Ham makbuz metnini bölümlere ayırıp yeniden çizer (salt okuma yolu)."""
        self.sections = parse_receipt(text)
        self._rebuild(title)

    def section_titles(self) -> List[str]:
        return [w.title for w in self._sections_widgets]

    def section_text(self, name: str) -> str:
        return self.sections.get(name, "")

    # ------------------------------------------------------------ çizim

    def _clear(self) -> None:
        for widget in self._sections_widgets:
            self.container_layout.removeWidget(widget)
            discard_widget(widget)
        self._sections_widgets = []

    def _rebuild(self, title: str = "") -> None:
        self._clear()
        if not self.sections:
            self.header_label.setText(
                f"<b style='color:{RT['accent']}; font-size:13px;'>MAKBUZ</b>"
                f" <span style='color:{RT['text_dim']}; font-size:11px;'>"
                "bu kart için ofis raporu bulunamadı</span>"
            )
            return
        summary = receipt_summary(self.sections)
        badges = ["kanıt var" if summary["has_proof"] else "kanıt yok"]
        if summary["change_count"]:
            badges.append(f"{summary['change_count']} değişiklik")
        if summary["cost_text"]:
            badges.append(f"{summary['cost_text'][:32]}")
        head = (
            f"<b style='color:{RT['accent']}; font-size:13px;'>MAKBUZ</b>"
            f" <span style='color:{RT['text']}; font-size:11px;'>{title}</span><br/>"
            f"<span style='color:{RT['text_dim']}; font-size:11px;'>"
            + " · ".join(badges) + "</span>"
        )
        if summary["pr_url"]:
            head += (
                f" <a href='{summary['pr_url']}' style='color:{RT['accent']};"
                f" font-size:11px;'>PR</a>"
            )
        self.header_label.setText(head)

        css = {"body": RT["text_body"], "dim": RT["text_dim"],
               "line": RT["divider_soft"], "accent": RT["accent"], "text": RT["text"]}
        insert_at = max(0, self.container_layout.count() - 1)
        for name in receipt_order(self.sections):
            if name not in self.sections and name not in RECEIPT_SECTIONS:
                continue
            body = self.sections.get(name, "")
            widget = CollapsibleSection(
                name, section_body_html(name, body, css),
                expanded=(name in DEFAULT_OPEN and bool(body.strip())),
                parent=self.container,
            )
            self.container_layout.insertWidget(insert_at, widget)
            insert_at += 1
            self._sections_widgets.append(widget)

    # ------------------------------------------------------------ yorum

    @Slot()
    def send_comment(self) -> bool:
        """
        Yorumu ofis posta kutusuna bırakır (`instruct_office`, task_id=kart).
        Koşu başlatmaz; sözleşme yoksa açıklayıcı satır yazar.
        """
        text = self.comment_input.text().strip()
        card_id = str(spec_field(self.card, "id", "") or "") if self.card is not None else ""
        if not text or not self.office:
            return False
        try:
            from entropy.agents.mailbox import instruct_office  # type: ignore
        except Exception:
            self.comment_status.setText("Posta kutusu sözleşmesi bulunamadı; yorum gönderilmedi.")
            return False
        try:
            instruct_office(self.office, text, task_id=card_id)
        except Exception as exc:
            self.comment_status.setText(f"Yorum gönderilemedi: {exc}")
            return False
        self.comment_input.clear()
        self.comment_status.setText("Yorum ofisin posta kutusuna bırakıldı (kart durmadı).")
        bus.terminal_output_received.emit(
            f"[Makbuz] {self.office}/{card_id} kartına yorum bırakıldı.\n"
        )
        self.comment_sent.emit(text)
        return True
