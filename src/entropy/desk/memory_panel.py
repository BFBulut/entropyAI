"""
Desk "Bellek" sekmesi: ofis belleğinin mini grafı + MEMORY.md metni.

Faz 7: sekme yalnızca MEMORY.md gösteriyordu; ofis belleğinin düğüm/kenar
yapısı (kim neyi nereye bağladı) görünmüyordu. Artık üstte
`OfficeGraph(office).to_view_data()` verisinden QPainter ile çizilen bir mini
graf, sağında seçilen düğümün notu, altta MEMORY.md durur.

Neden QPainter (QtWebEngine değil): Desk penceresi ikinci monitörde sürekli
açık kalıyor; her ofis değişiminde bir web görünümü kurmak hem yavaş hem de
bellek maliyetli. Graf küçük (onlarca düğüm), 2B kanvas yeter.

Düzen: `ofis` düğümü merkezde, diğerleri türlerine göre halkalara dağılır.
Konumlar düğüm kimliğinden türetilir (deterministik): aynı ofis her açılışta
aynı yerleşimi verir, kullanıcı "graf her seferinde başka" demesin.

İş parçacığı: veri okuma senkron ve yereldir (kasadaki JSON); Qt'ye yalnızca
ana iş parçacığından dokunulur.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QLabel, QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

from entropy.ui.widgets.rules_panel import RuleCandidatesPanel
from entropy.ui.design import TOKENS
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT

# Düğüm türü -> renk. Faz 11-E adım 6: `viz.*` belirteç ailesi; bilinmeyen
# tür nötr. Renk yalnızca türü kodlar, vurgu görevi görmez.
KIND_COLORS: Dict[str, str] = {
    "ofis": TOKENS["viz"]["kind1"],
    "ajan": TOKENS["viz"]["kind2"],
    "rapor": TOKENS["viz"]["kind3"],
    "karar": TOKENS["viz"]["kind4"],
    "bulgu": TOKENS["viz"]["kind5"],
    "gorev": TOKENS["viz"]["kind6"],
    "proje": TOKENS["viz"]["kind7"],
}
KIND_FALLBACK = TOKENS["viz"]["neutral"]

NODE_RADIUS = 7.0
HIT_RADIUS = 12.0


def kind_color(kind: str) -> str:
    """Tür rengi; bilinmeyen tür için gri."""
    return KIND_COLORS.get((kind or "").strip().lower(), KIND_FALLBACK)


def load_office_view_data(office: str) -> Dict[str, List[Dict[str, Any]]]:
    """`OfficeGraph.to_view_data()`; modül/kasa yoksa boş graf (çökme yok)."""
    if not office:
        return {"nodes": [], "links": []}
    try:
        from entropy.memory.office_graph import OfficeGraph  # type: ignore

        data = OfficeGraph(office).to_view_data() or {}
    except Exception:
        return {"nodes": [], "links": []}
    return {
        "nodes": list(data.get("nodes") or []),
        "links": list(data.get("links") or []),
    }


def compute_positions(nodes: List[Dict[str, Any]]) -> Dict[str, Tuple[float, float]]:
    """
    Düğüm kimliği -> (-1..1, -1..1) birim konum.

    `ofis` türü merkezde; kalanlar tür bloklarına ayrılıp iki halkaya dağılır.
    Derecesi yüksek düğüm iç halkaya gelir (merkez, ilişki yoğunluğudur).
    """
    out: Dict[str, Tuple[float, float]] = {}
    others: List[Dict[str, Any]] = []
    for node in nodes:
        if (node.get("kind") or node.get("group")) == "ofis":
            out[str(node.get("id"))] = (0.0, 0.0)
        else:
            others.append(node)
    if not others:
        return out

    others.sort(key=lambda n: (-int(n.get("degree", 0) or 0),
                               str(n.get("kind") or n.get("group") or ""),
                               str(n.get("id"))))
    inner = others[: max(1, len(others) // 2)] if len(others) > 8 else others
    outer = others[len(inner):]
    for ring, radius in ((inner, 0.55), (outer, 0.95)):
        count = len(ring)
        for index, node in enumerate(ring):
            angle = (2 * math.pi * index / count) - math.pi / 2 if count else 0.0
            out[str(node.get("id"))] = (radius * math.cos(angle), radius * math.sin(angle))
    return out


class MiniGraphCanvas(QWidget):
    """Ofis belleği mini grafı: kenarlar + renkli düğümler, tıklanabilir."""

    node_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setMinimumWidth(180)
        self.nodes: List[Dict[str, Any]] = []
        self.links: List[Dict[str, Any]] = []
        self.selected_id: str = ""
        self._positions: Dict[str, Tuple[float, float]] = {}
        self.setMouseTracking(False)

    # ------------------------------------------------------------- veri

    def set_data(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        self.nodes = list(data.get("nodes") or [])
        self.links = list(data.get("links") or [])
        self._positions = compute_positions(self.nodes)
        if self.selected_id not in {str(n.get("id")) for n in self.nodes}:
            self.selected_id = ""
        self.update()

    def node(self, node_id: str) -> Optional[Dict[str, Any]]:
        for node in self.nodes:
            if str(node.get("id")) == node_id:
                return node
        return None

    # ---------------------------------------------------------- geometri

    def _screen_pos(self, node_id: str) -> Optional[QPointF]:
        pos = self._positions.get(node_id)
        if pos is None:
            return None
        cx, cy = self.width() / 2.0, self.height() / 2.0
        span = max(20.0, min(cx, cy) - 18.0)
        return QPointF(cx + pos[0] * span, cy + pos[1] * span)

    def node_at(self, point) -> Optional[str]:
        best: Optional[str] = None
        best_d = HIT_RADIUS
        for node in self.nodes:
            nid = str(node.get("id"))
            sp = self._screen_pos(nid)
            if sp is None:
                continue
            d = math.hypot(sp.x() - point.x(), sp.y() - point.y())
            if d <= best_d:
                best_d = d
                best = nid
        return best

    # ------------------------------------------------------------ olaylar

    def mousePressEvent(self, event):  # noqa: N802 (Qt)
        nid = self.node_at(event.position() if hasattr(event, "position") else event.pos())
        if nid:
            self.selected_id = nid
            self.update()
            self.node_clicked.emit(nid)
        super().mousePressEvent(event)

    def paintEvent(self, event):  # noqa: N802 (Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(RT["surface_base"]))

        if not self.nodes:
            painter.setPen(QPen(QColor(RT["text_dim"])))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Bu ofis için bellek grafı henüz boş.")
            painter.end()
            return

        # Kenarlar
        pen = QPen(QColor(RT["divider_soft"]))
        pen.setWidthF(1.2)
        painter.setPen(pen)
        for link in self.links:
            a = self._screen_pos(str(link.get("source")))
            b = self._screen_pos(str(link.get("target")))
            if a is None or b is None:
                continue
            painter.drawLine(a, b)

        # Düğümler
        # Faz 12-D.1: tasarım sistemi fontları QSS'ten PİKSEL boyutlu gelir;
        # böyle bir fontta `pointSizeF()` -1 döner. Nokta boyutu API'siyle
        # karıştırmak hem etiketi 13 px'ten 7 pt'ye sıçratıyor hem de Qt'nin
        # içinde `QFont::setPointSize: Point size <= 0 (-1)` uyarısına yol
        # açıyordu (Faz 11 kapanış bulgusu 10). Ölçü birimi korunur.
        font = QFont(painter.font())
        pixel = font.pixelSize()
        if pixel > 0:
            font.setPixelSize(max(7, pixel - 2))
        elif font.pointSizeF() > 0:
            font.setPointSizeF(max(7.0, font.pointSizeF() - 1.5))
        else:
            font.setPixelSize(11)
        painter.setFont(font)
        for node in self.nodes:
            nid = str(node.get("id"))
            sp = self._screen_pos(nid)
            if sp is None:
                continue
            kind = str(node.get("kind") or node.get("group") or "")
            color = QColor(kind_color(kind))
            radius = NODE_RADIUS + min(4.0, int(node.get("degree", 0) or 0) * 0.6)
            if node.get("virtual"):
                # Sanal düğüm (henüz belleğe yazılmamış): içi boş halka.
                painter.setBrush(QBrush(QColor(RT["surface_base"])))
                painter.setPen(QPen(color, 1.6))
            else:
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color.darker(160), 1.0))
            painter.drawEllipse(sp, radius, radius)
            if nid == self.selected_id:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(RT["accent"]), 2.0))
                painter.drawEllipse(sp, radius + 4.0, radius + 4.0)

            label = str(node.get("name") or nid)[:18]
            painter.setPen(QPen(QColor(RT["text_dim"])))
            painter.drawText(
                QRectF(sp.x() - 55, sp.y() + radius + 1, 110, 14),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                label,
            )
        painter.end()


class OfficeMemoryPanel(QFrame):
    """Bellek sekmesi: mini graf + düğüm notu (üst), MEMORY.md (alt)."""

    def __init__(self, parent=None, office: str = ""):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.office = office or ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.split = QSplitter(Qt.Orientation.Vertical)

        top = QSplitter(Qt.Orientation.Horizontal)
        graph_box = QWidget()
        graph_layout = QVBoxLayout(graph_box)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(2)
        self.graph_title = QLabel("Ofis bellek grafı")
        self.graph_title.setProperty("role", "label")
        self.canvas = MiniGraphCanvas(self)
        self.canvas.node_clicked.connect(self._on_node_clicked)
        graph_layout.addWidget(self.graph_title)
        graph_layout.addWidget(self.canvas, 1)
        top.addWidget(graph_box)

        self.note_view = QTextBrowser()
        self.note_view.setMinimumWidth(140)
        self.note_view.setProperty("role", "reader")
        top.addWidget(self.note_view)
        top.setSizes([420, 260])
        self.split.addWidget(top)

        self.memory_view = QTextBrowser()
        self.memory_view.setProperty("role", "reader")
        self.split.addWidget(self.memory_view)

        # Faz 10-B: kural adayları bölümü. Ajanın keşfettiği kural burada
        # kullanıcıya sorulur; onaylanmadan sistem istemine GİRMEZ.
        self.rules_panel = RuleCandidatesPanel(parent=self, office=self.office)
        self.rules_panel.setMinimumHeight(90)
        self.split.addWidget(self.rules_panel)
        self.split.setSizes([260, 220, 180])
        layout.addWidget(self.split, 1)

        self.setMinimumWidth(240)
        self.set_office(self.office)

    @staticmethod
    def _text_style() -> str:
        return (
            f"QTextBrowser {{ background-color:{RT['surface_base']};"
            f" border:1px solid {RT['divider_soft']}; border-radius:{RT['radius']};"
            f" color:{RT['text_body']}; padding:8px; font-size:{RT['font_size_small']}; }}"
        )

    # ------------------------------------------------------------- veri

    def set_office(self, office: str) -> None:
        self.office = office or ""
        self.rules_panel.set_office(self.office)
        self.refresh()

    def refresh(self) -> None:
        data = load_office_view_data(self.office)
        self.canvas.set_data(data)
        self.graph_title.setText(
            f"Ofis bellek grafı · {len(data['nodes'])} düğüm / {len(data['links'])} bağ"
        )
        self._show_placeholder()
        self.refresh_memory_text()

    def _show_placeholder(self) -> None:
        self.note_view.setHtml(
            f"<div style='color:{RT['text_dim']};'>Bir düğüme tıklayın: notu burada görünür.</div>"
        )

    def _on_node_clicked(self, node_id: str) -> None:
        self.show_node(node_id)

    def show_node(self, node_id: str) -> str:
        """
        Düğüm notunu sağ bölmede gösterir; gösterilen düz metni döndürür.

        Sanal düğümün (henüz `graph.json`'a yazılmamış ajan/rapor) notu yoktur;
        yalnızca ADI gösterilir — uydurma içerik göstermek, belleğin dolu
        olduğu izlenimini verirdi.
        """
        node = self.canvas.node(node_id)
        if node is None:
            self._show_placeholder()
            return ""
        name = str(node.get("name") or node_id)
        kind = str(node.get("kind") or node.get("group") or "")
        color = kind_color(kind)
        head = (
            f"<div><b style='color:{color};'>{name}</b>"
            f" <span style='color:{RT['text_dim']};'>· {kind}</span></div>"
        )
        if node.get("virtual"):
            self.note_view.setHtml(head)
            return name
        note = str(node.get("note") or "").strip()
        body = note or "(not boş)"
        self.note_view.setHtml(
            head + f"<hr><div style='color:{RT['text_body']}; white-space:pre-wrap;'>{body}</div>"
        )
        return body

    def refresh_memory_text(self) -> None:
        from entropy.desk.window import load_office_memory

        text = load_office_memory(self.office)
        if not text:
            self.memory_view.setHtml(
                f"<div style='color:{RT['text_dim']};'>Bu ofis için MEMORY.md henüz yok. "
                "Ofis bir kart tamamladığında bellek yazılır.</div>"
            )
            return
        try:
            from entropy.ui.widgets.markdown_renderer import render_markdown_to_html

            self.memory_view.setHtml(render_markdown_to_html(text))
        except Exception:
            self.memory_view.setPlainText(text)
