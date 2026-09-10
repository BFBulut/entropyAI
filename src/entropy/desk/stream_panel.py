"""
Akış paneli: seçili ajanın son çıktısı ve canlı akışı.

İki kaynak: `bus.token_chunk_received` (canlı) ve ledger/kart dosyaları (yedek).
Sahnedeki sprite'a tıklandığında `focus_agent()` çağrılır; panel o ajanın son
kart özetini basar ve o andan sonraki akış parçalarını eklemeye başlar.

Faz 10-B: ajan başına ayrıştırma `desk/terminals_panel.py`'ye taşındı
(`bus.agent_stream` ajan/ofis/kart etiketi taşıyor). Bu panel artık
"Terminaller" sekmesinin ÜST bölmesinde yalnızca seçili ajanın KART ÖZETİNİ ve
etiketsiz eski `token_chunk_received` akışını gösterir; geriye uyum için
`focus_agent`/`stream_text` sözleşmesi aynen korunur.
"""

from __future__ import annotations

import html
from typing import Any, List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout,
)

from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT, reading_css
from entropy.ui.widgets.agents_widget import list_cards_for, spec_field

# Akışta tutulan en fazla karakter: uzun koşularda panel sınırsız büyümesin.
MAX_STREAM_CHARS = 40_000


class StreamPanel(QFrame):
    """Seçili ajanın kart özeti + canlı token akışı."""

    def __init__(self, parent=None, board: Any = None, office: str = ""):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.board = board
        self.office = office or ""
        self.agent: str = ""
        self._buffer: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.title_label = QLabel("")
        self.title_label.setProperty("role", "label")
        header.addWidget(self.title_label)
        header.addStretch()
        self.clear_btn = QPushButton("Temizle")
        self.clear_btn.setAccessibleName("Temizle")
        self.clear_btn.setFixedHeight(22)
        self.clear_btn.clicked.connect(self.clear_stream)
        header.addWidget(self.clear_btn)
        layout.addLayout(header)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        self.view.setProperty("role", "terminal")
        # Faz 4 (2d): akış paneli, rapor okuyucu ve sohbet balonu tek tipografi
        # kaynağını paylaşır. `reading_css()` belge stil sayfası olarak
        # verilince başlık/tablo/liste ölçüleri üç yüzeyde de aynı olur.
        self.view.document().setDefaultStyleSheet(reading_css())
        layout.addWidget(self.view, 1)

        signal = getattr(bus, "token_chunk_received", None)
        if signal is not None:
            signal.connect(self._on_chunk)

        self.focus_agent("")

    # ------------------------------------------------------------ durum

    def set_office(self, office: str) -> None:
        self.office = office or ""
        self.focus_agent("")

    def focus_agent(self, agent: str) -> None:
        """Sprite tıklamasının hedefi: paneli bu ajana odaklar."""
        self.agent = agent or ""
        self._buffer = ""
        if not self.agent:
            self.title_label.setText(
                f"<b style='color:{RT['accent']}; font-size:13px;'>AKIŞ</b>"
                f" <span style='color:{RT['text_dim']}; font-size:11px;'>"
                f"sahnedeki bir masaya tıklayın</span>"
            )
            self.view.setHtml(self._placeholder_html())
            return
        self.title_label.setText(
            f"<b style='color:{RT['accent']}; font-size:13px;'>AKIŞ</b>"
            f" <span style='color:{RT['text']}; font-size:11px;'>{html.escape(self.agent)}</span>"
        )
        self.view.setHtml(self._summary_html())

    def _placeholder_html(self) -> str:
        return (
            f"<div style='color:{RT['text_dim']}; font-family:{RT['font_body']};'>"
            "Ofis sahnesinde bir ajanın masasına tıklayın; son çıktısı ve canlı "
            "akışı burada görünür.</div>"
        )

    # ------------------------------------------------------------ veri

    def cards_for_agent(self) -> List[Any]:
        if self.board is None or not self.agent:
            return []
        # Faz 9: ofis kartları ayrı kökte; ofis geçilmezse panel boş kalırdı.
        cards = list_cards_for(self.board, self.office)
        owned = [c for c in cards if str(spec_field(c, "agent", "")) == self.agent]
        if self.office:
            owned = [c for c in owned if str(spec_field(c, "office", "")) in ("", self.office)]
        return sorted(owned, key=lambda c: str(spec_field(c, "created_at", "")))

    def latest_card(self) -> Optional[Any]:
        cards = self.cards_for_agent()
        return cards[-1] if cards else None

    def _summary_html(self) -> str:
        card = self.latest_card()
        if card is None:
            return (
                f"<div style='color:{RT['text_dim']}; font-family:{RT['font_body']};'>"
                f"<b style='color:{RT['text']};'>{html.escape(self.agent)}</b> için kayıtlı "
                "görev kartı yok. Ajan çalışmaya başlayınca çıktısı buraya akar.</div>"
            )
        parts = [
            f"<div style='font-family:{RT['font_body']};'>",
            f"<div style='color:{RT['text']}; font-size:13px; font-weight:600;'>"
            f"{html.escape(str(spec_field(card, 'title', '')))}</div>",
            f"<div style='color:{RT['text_dim']}; font-size:11px; margin-bottom:6px;'>"
            f"{html.escape(str(spec_field(card, 'id', '')))} · "
            f"{html.escape(str(spec_field(card, 'status', '')))}",
        ]
        grade = spec_field(card, "grade", "")
        verdict = str(spec_field(card, "verdict", ""))
        if grade not in ("", None):
            parts.append(f" · not {html.escape(str(grade))}")
        if verdict:
            parts.append(f" · {html.escape(verdict)}")
        parts.append("</div>")
        goal = str(spec_field(card, "goal", ""))
        if goal:
            parts.append(
                f"<div style='color:{RT['text_body']}; font-size:12px;'>{html.escape(goal)}</div>"
            )
        summary = str(spec_field(card, "summary", ""))
        if summary:
            parts.append(
                f"<div style='color:{RT['text_body']}; font-size:12px; margin-top:6px;'>"
                f"{html.escape(summary)}</div>"
            )
        for path in (spec_field(card, "output_paths", []) or []):
            parts.append(
                f"<div style='color:{RT['accent']}; font-size:11px;'>{html.escape(str(path))}</div>"
            )
        parts.append("</div>")
        return "".join(parts)

    # ------------------------------------------------------------ canlı akış

    @Slot(str)
    def _on_chunk(self, chunk: str) -> None:
        """
        Canlı akış parçası. Alıcı QObject slotu (lambda değil) olduğu için
        köprünün işçi iş parçacığından gelen sinyal kuyruklanır.
        """
        if not self.agent or not chunk:
            return
        self._buffer += chunk
        if len(self._buffer) > MAX_STREAM_CHARS:
            self._buffer = self._buffer[-MAX_STREAM_CHARS:]
        self._render_stream()

    def _render_stream(self) -> None:
        body = html.escape(self._buffer).replace("\n", "<br/>")
        self.view.setHtml(
            self._summary_html()
            + f"<hr style='border:none; border-top:1px solid {RT['divider_soft']};'/>"
            + f"<div style='font-family:{RT['font_mono']}; font-size:12px; "
            f"color:{RT['text_body']}; white-space:pre-wrap;'>{body}</div>"
        )
        self.view.moveCursor(self.view.textCursor().MoveOperation.End)

    @Slot()
    def clear_stream(self) -> None:
        self._buffer = ""
        self.view.setHtml(self._summary_html() if self.agent else self._placeholder_html())

    def stream_text(self) -> str:
        """Test için: o ana kadar biriken ham akış."""
        return self._buffer
