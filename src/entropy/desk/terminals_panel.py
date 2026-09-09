"""
Desk "Terminaller" sekmesi: her ajan için AYRI bir terminal bölmesi.

Neden ayrı bölme: piksel ajanlar arka planda koşan gizli terminallerin
avatarıdır. Sprite'a tıklayan kullanıcı "o ajanın gerçek terminalini" görmek
ister. Eski `stream_panel` tek tampon tutuyordu (`token_chunk_received` ajan
etiketi taşımıyor); aynı anda iki ajan koşunca satırlar birbirine karışıyordu.
Faz 10-B'de köprü `bus.agent_stream` ile ajan/ofis/kart etiketli yük yayar;
burada yük ajan bazında tamponlanır.

Düzen melezi (kullanıcı tarifi): 1-3 ajan varken bölmeler yan yana bölünmüş
görünümde durur (hepsi aynı anda görünür); 4 ve üzeri ajanda sekmelere geçilir
(bölünmüş görünümde her bölme okunmaz genişliğe düşerdi).

Biten kartın bölmesi SİLİNMEZ: "arşiv" bölümüne taşınır. Kullanıcı koşu bitince
çıktıyı kaybetmesin.

İş parçacığı: `agent_stream` köprünün işçi iş parçacığından yayılabilir; alıcı
bir QObject slotudur (lambda değil), böylece bağlantı kuyruklanır ve Qt
nesnelerine yalnızca ana iş parçacığından dokunulur.
"""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSplitter,
    QStackedWidget, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT

# Bölmede tutulan en fazla olay: uzun koşu belleği şişirmesin.
MAX_EVENTS = 400
# Bu sayıdan itibaren bölünmüş görünüm yerine sekmeler.
SPLIT_LIMIT = 3

# Yük türü -> (renk, italik mi, önek). Ham metin her zaman görünür; renk
# yalnızca türü ayırt etmek içindir.
KIND_STYLE: Dict[str, tuple] = {
    "thinking": (RT["text_dim"], True, "…"),
    "text": (RT["text_body"], False, ""),
    "tool_call": ("#FFC24D", False, "⚙"),
    "tool_result": (RT["text_dim"], False, "↩"),
    "status": (RT["text_dim"], False, "•"),
    "result": ("#3DE8A8", False, "✓"),
    "error": ("#EF4444", False, "✗"),
}
KIND_FALLBACK = (RT["text_body"], False, "")

STATE_LABELS = {
    "thinking": "düşünüyor",
    "working": "çalışıyor",
    "idle": "boşta",
    "error": "hata",
}

# Faz 10-D: köprü etkileşimli beklemeyi `kind=status, state=idle` ve bu metinle
# duyurur. Metin köprüde sabittir; burada küçük harfe indirgenip aranır ki
# üç nokta karakteri (…/...) değişse de rozet kaybolmasın.
WAITING_MARKER = "takip mesajı bekliyor"
WAITING_BADGE = "bekliyor · mesaj yazabilirsin"


def is_waiting_payload(payload: Any) -> bool:
    """
    Yük etkileşimli beklemeyi mi duyuruyor?

    Sözleşme: `kind=status`, `state=idle`, `text="Takip mesajı bekliyor…"`.
    Üçü birden aranır: yalnız `state=idle` bakmak koşu sonundaki normal
    boşa düşüşü de "bekliyor" sanardı.
    """
    if not isinstance(payload, dict):
        return False
    if event_kind(payload) != "status":
        return False
    if str(payload.get("state") or "").strip().lower() != "idle":
        return False
    return WAITING_MARKER in event_text(payload).strip().lower()


def event_kind(payload: Any) -> str:
    """Yükün türü; bilinmeyen/boş tür `text` sayılır."""
    if not isinstance(payload, dict):
        return "text"
    kind = str(payload.get("kind") or "").strip().lower()
    return kind if kind in KIND_STYLE else "text"


def event_text(payload: Any) -> str:
    """Gösterilecek metin: araç çağrısında araç adı + özet, yoksa `text`."""
    if not isinstance(payload, dict):
        return str(payload or "")
    kind = event_kind(payload)
    tool = payload.get("tool") or None
    if kind == "tool_call" and isinstance(tool, dict):
        name = str(tool.get("name") or "araç")
        summary = str(tool.get("input_summary") or "")
        return f"{name}({summary})" if summary else name
    text = payload.get("full_text") or payload.get("text") or ""
    return str(text)


class AgentTerminalPane(QFrame):
    """Tek ajanın terminal bölmesi: başlık, olay akışı, tek satır giriş."""

    close_requested = Signal(str)   # ajan adı (etkileşimli koşu kapatıldı)

    def __init__(self, agent: str, parent=None, bridge: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.agent = agent or ""
        self.bridge = bridge
        self.task_id: str = ""
        self.card_id: str = ""
        self.card_title: str = ""
        self.state: str = "idle"
        self.archived: bool = False
        # Etkileşimli bekleme: köprü turu bitirdi ama süreç canlı, kullanıcıdan
        # takip mesajı bekliyor. `interactive` bir kez True olunca koşu
        # kapanana kadar True kalır (ilk `task_completed` bölmeyi arşive atmasın).
        self.waiting: bool = False
        self.interactive: bool = False
        self.turn: int = 0
        self._events: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        self.title_label = QLabel("")
        self.title_label.setStyleSheet("background: transparent; border: none;")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        self.view.setStyleSheet(
            f"""
            QTextBrowser {{
                background-color:{RT['surface_base']};
                border:1px solid {RT['divider_soft']};
                border-radius:{RT['radius']};
                color:{RT['text_body']};
                font-family:{RT['font_mono']};
                font-size:{RT['font_size_mono']};
                padding:8px;
            }}
            """
        )
        layout.addWidget(self.view, 1)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Koşan ajana mesaj… (Enter)")
        self.input.returnPressed.connect(self.send_followup)
        row.addWidget(self.input, 1)
        self.send_btn = QPushButton("Gönder")
        self.send_btn.setFixedHeight(24)
        self.send_btn.clicked.connect(self.send_followup)
        row.addWidget(self.send_btn)
        # "Kapat": etkileşimli koşuyu kullanıcı bitirir (`close_interactive`).
        # Görünürlüğü beklemeye bağlıdır; koşan bir ajanı yanlışlıkla kapatma
        # düğmesi her zaman ekranda durmasın.
        self.close_btn = QPushButton("Kapat")
        self.close_btn.setFixedHeight(24)
        self.close_btn.setToolTip("Etkileşimli koşuyu kapatır; bölme arşive gider.")
        self.close_btn.clicked.connect(self._on_close_clicked)
        self.close_btn.setVisible(False)
        row.addWidget(self.close_btn)
        layout.addLayout(row)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.status_label)

        self._refresh_header()
        self._refresh_input()

    # ------------------------------------------------------------ başlık

    def _refresh_header(self) -> None:
        color = {
            "thinking": "#FFC24D",
            "working": "#3DE8A8",
            "error": "#EF4444",
        }.get(self.state, RT["text_dim"])
        bits = [
            f"<b style='color:{RT['text']}; font-size:12px;'>"
            f"{html.escape(self.agent or '—')}</b>"
        ]
        if self.card_title:
            bits.append(
                f"<span style='color:{RT['text_dim']}; font-size:11px;'>"
                f"{html.escape(self.card_title)}</span>"
            )
        if self.waiting and not self.archived:
            # Bekleme rozeti durum etiketinin YERİNE geçer: "boşta" yazmak
            # kullanıcıya "koşu bitti" izlenimi veriyordu.
            bits.append(
                f"<span style='color:#FFC24D; font-size:11px; font-weight:600;'>"
                f"⏸ {WAITING_BADGE}</span>"
            )
        else:
            bits.append(
                f"<span style='color:{color}; font-size:11px;'>"
                f"{STATE_LABELS.get(self.state, self.state)}</span>"
            )
        if self.turn:
            bits.append(
                f"<span style='color:{RT['text_dim']}; font-size:11px;'>"
                f"tur {self.turn}</span>"
            )
        if self.archived:
            bits.append(
                f"<span style='color:{RT['text_dim']}; font-size:11px;'>arşiv</span>"
            )
        self.title_label.setText(" · ".join(bits))

    def header_text(self) -> str:
        """Test için: başlığın düz metni."""
        return self.title_label.text()

    # ------------------------------------------------------------ olaylar

    def append_event(self, payload: Dict[str, Any]) -> None:
        """Tek `agent_stream` yükünü bölmeye ekler."""
        if not isinstance(payload, dict):
            return
        self._events.append(dict(payload))
        if len(self._events) > MAX_EVENTS:
            self._events = self._events[-MAX_EVENTS:]
        for field, attr in (("task_id", "task_id"), ("card_id", "card_id")):
            value = str(payload.get(field) or "")
            if value:
                setattr(self, attr, value)
        state = str(payload.get("state") or "").strip().lower()
        if state in STATE_LABELS:
            self.state = state
        if is_waiting_payload(payload):
            self.waiting = True
            self.interactive = True
        elif state in ("thinking", "working"):
            # Yeni tur başladı: bekleme rozeti düşer, etkileşim bayrağı kalır.
            self.waiting = False
        self._render()
        self._refresh_header()
        self._refresh_input()

    def set_card_title(self, title: str) -> None:
        self.card_title = str(title or "")
        self._refresh_header()

    def set_archived(self, archived: bool = True) -> None:
        self.archived = bool(archived)
        if self.archived:
            self.state = "idle"
            self.waiting = False
            self.interactive = False
        self._refresh_header()
        self._refresh_input()

    def append_turn(self, payload: Dict[str, Any]) -> None:
        """
        `bus.task_followup_completed` turunu bölmeye yazar.

        Yük: {task_id, card_id, text, usage, turn, success}. Tur numarası ve
        token kullanımı görünür olsun diye ayrı bir `result`/`error` satırı
        eklenir; ham metin köprüden geldiği gibi basılır (özet uydurulmaz).
        """
        if not isinstance(payload, dict):
            return
        try:
            turn = int(payload.get("turn") or 0)
        except (TypeError, ValueError):
            turn = 0
        if turn:
            self.turn = turn
        success = bool(payload.get("success", True))
        head = f"Tur {turn or self.turn or 1}"
        usage = payload.get("usage")
        tokens = 0
        if isinstance(usage, dict):
            for key in ("total_tokens", "tokens", "total"):
                try:
                    tokens = int(usage.get(key) or 0)
                except (TypeError, ValueError):
                    tokens = 0
                if tokens:
                    break
            if not tokens:
                try:
                    tokens = int(usage.get("input_tokens") or 0) + int(
                        usage.get("output_tokens") or 0)
                except (TypeError, ValueError):
                    tokens = 0
        if tokens:
            head += " · " + f"{tokens:,}".replace(",", ".") + " token"
        text = str(payload.get("text") or "")
        self.append_event({
            "kind": "result" if success else "error",
            "text": head + (f"\n{text}" if text else ""),
            "task_id": str(payload.get("task_id") or self.task_id),
            "card_id": str(payload.get("card_id") or self.card_id),
        })
        self._refresh_header()

    def close_interactive(self, reason: str = "kullanıcı kapattı") -> bool:
        """Köprüdeki etkileşimli koşuyu kapatır ve bölmeyi arşive taşır."""
        fn = getattr(self.bridge, "close_interactive", None)
        if not callable(fn) or not self.task_id:
            self._set_status("Köprü kapatmayı desteklemiyor.", ok=False)
            return False
        try:
            ok = bool(fn(self.task_id, reason))
        except Exception as exc:
            self._set_status(f"Kapatılamadı: {exc}", ok=False)
            return False
        # Faz 10-C: köprü kapandıktan SONRA harness'taki takip turu kaydı da
        # bırakılır. Aksi hâlde yarım kalan bir turun proje yazma kilidi
        # harness üzerinde asılı kalıyor ve ofis bir daha yazamıyordu.
        # Guard: sözleşme yoksa (eski sürüm/test sahtesi) kapatma yine başarılı.
        try:
            import importlib

            _release = getattr(
                importlib.import_module("entropy.agents.harness"),
                "release_followup_for", None,
            )
            if callable(_release):
                _release(self.card_id or self.task_id)
        except Exception:
            pass
        self.set_archived(True)
        self._set_status("Etkileşimli koşu kapatıldı.", ok=True)
        # Kap yeniden düzenlensin: bölme sekmeler/bölünmüş görünümden arşive
        # taşınır. Bölme kap içinde yeniden ebeveynlendiği için `parent()`
        # güvenilmez; sinyalle haber verilir.
        self.close_requested.emit(self.agent)
        return ok

    @Slot()
    def _on_close_clicked(self) -> None:
        """Düğme `clicked(bool)` yayar; `reason` bozulmasın diye ayrı slot."""
        self.close_interactive()

    def events(self) -> List[Dict[str, Any]]:
        return list(self._events)

    def raw_text(self) -> str:
        """Test için: bölmedeki ham metin (renk/biçim olmadan)."""
        return "\n".join(event_text(e) for e in self._events)

    def _render(self) -> None:
        parts: List[str] = []
        for event in self._events:
            kind = event_kind(event)
            color, italic, prefix = KIND_STYLE.get(kind, KIND_FALLBACK)
            body = html.escape(event_text(event)).replace("\n", "<br/>")
            style = f"color:{color};"
            if italic:
                style += " font-style:italic;"
            head = f"{prefix} " if prefix else ""
            parts.append(
                f"<div style='{style} white-space:pre-wrap; margin:1px 0;'>"
                f"{html.escape(head)}{body}</div>"
            )
        self.view.setHtml(
            f"<div style='font-family:{RT['font_mono']}; font-size:12px;'>"
            + "".join(parts)
            + "</div>"
        )
        cursor = self.view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.view.setTextCursor(cursor)

    def clear_events(self) -> None:
        self._events = []
        self._render()

    # ------------------------------------------------------------ takip mesajı

    def can_send(self) -> bool:
        """Köprü `send_followup` sunuyor ve koşan bir görev var mı?"""
        if self.archived or not self.task_id:
            return False
        return callable(getattr(self.bridge, "send_followup", None))

    def _refresh_input(self) -> None:
        enabled = self.can_send()
        self.input.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)
        can_close = (
            not self.archived
            and self.interactive
            and bool(self.task_id)
            and callable(getattr(self.bridge, "close_interactive", None))
        )
        self.close_btn.setVisible(can_close)
        self.close_btn.setEnabled(can_close)
        if self.waiting and enabled:
            self.input.setPlaceholderText("Takip mesajı bekleniyor… (Enter)")
        else:
            self.input.setPlaceholderText("Koşan ajana mesaj… (Enter)")
        if enabled and self.waiting:
            hint = "Ajan takip mesajı bekliyor; yazıp Enter'a basın."
        elif enabled:
            hint = "Mesaj koşan ajanın girdisine yazılır."
        elif self.archived:
            hint = "Koşu bitti; arşiv bölmesine mesaj gönderilemez."
        elif not self.task_id:
            hint = "Ajanın koşan bir görevi yok."
        else:
            hint = "Köprü takip mesajını desteklemiyor."
        self.input.setToolTip(hint)
        self.send_btn.setToolTip(hint)

    @Slot()
    def send_followup(self) -> bool:
        """Kutudaki metni koşan ajanın girdisine yollar."""
        text = self.input.text().strip()
        if not text or not self.can_send():
            return False
        try:
            ok = bool(self.bridge.send_followup(self.task_id, text))
        except Exception as exc:
            self._set_status(f"Gönderilemedi: {exc}", ok=False)
            return False
        if ok:
            self.input.clear()
            self._set_status("Mesaj ajanın girdisine yazıldı.", ok=True)
        else:
            self._set_status("Köprü mesajı kabul etmedi.", ok=False)
        return ok

    def _set_status(self, text: str, ok: bool = True) -> None:
        color = RT["accent_alt"] if ok else RT["accent_warn"]
        self.status_label.setText(
            f"<span style='color:{color}; font-size:11px;'>{html.escape(text)}</span>"
        )


class TerminalsPanel(QFrame):
    """Ajan başına terminal bölmelerinin kabı (bölünmüş görünüm / sekmeler)."""

    agent_focused = Signal(str)
    # Takip turu işlendi: kart kimliği. Pencere makbuz/kart detayını tazeler.
    card_refresh_requested = Signal(str)

    def __init__(self, parent=None, office: str = "", bridge: Any = None,
                 board: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.office = office or ""
        self.bridge = bridge
        self.board = board
        self.panes: Dict[str, AgentTerminalPane] = {}
        self._focused: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.placeholder = QLabel(
            "Koşan ajan yok. Bir ajan çalışmaya başlayınca terminali burada açılır."
        )
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet(
            f"color:{RT['text_dim']}; font-size:12px; background:transparent; border:none;"
        )
        layout.addWidget(self.placeholder)

        self.stack = QStackedWidget()
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.stack.addWidget(self.split)   # 0: bölünmüş görünüm
        self.stack.addWidget(self.tabs)    # 1: sekmeler
        layout.addWidget(self.stack, 1)

        self.archive_label = QLabel("")
        self.archive_label.setStyleSheet(
            f"color:{RT['text_dim']}; font-size:11px; background:transparent; border:none;"
        )
        layout.addWidget(self.archive_label)
        self.archive_tabs = QTabWidget()
        self.archive_tabs.setDocumentMode(True)
        self.archive_tabs.setMaximumHeight(180)
        layout.addWidget(self.archive_tabs)

        self._sync_layout()

        signal = getattr(bus, "agent_stream", None)
        if signal is not None:
            try:
                signal.connect(self.handle_stream)
            except Exception:
                pass
        for name, handler in (
            ("task_completed", self._on_task_completed),
            ("task_followup_completed", self.handle_followup),
        ):
            sig = getattr(bus, name, None)
            if sig is not None:
                try:
                    sig.connect(handler)
                except Exception:
                    pass

    # ------------------------------------------------------------ ofis

    def set_office(self, office: str) -> None:
        """Ofis değişti: bölmeler ofise özgüdür, temizlenir."""
        if (office or "") == self.office:
            return
        self.office = office or ""
        for pane in list(self.panes.values()):
            pane.setParent(None)
            pane.deleteLater()
        self.panes = {}
        self._focused = ""
        self._sync_layout()

    def set_bridge(self, bridge: Any) -> None:
        self.bridge = bridge
        for pane in self.panes.values():
            pane.bridge = bridge
            pane._refresh_input()

    # ------------------------------------------------------------ bölmeler

    def pane_for(self, agent: str, create: bool = True) -> Optional[AgentTerminalPane]:
        """Ajanın bölmesi; yoksa (ve `create`) kurulur."""
        agent = str(agent or "")
        if not agent:
            return None
        pane = self.panes.get(agent)
        if pane is None and create:
            pane = AgentTerminalPane(agent, parent=self, bridge=self.bridge)
            pane.close_requested.connect(self._on_pane_closed)
            self.panes[agent] = pane
            self._sync_layout()
        return pane

    def active_agents(self) -> List[str]:
        return [a for a, p in self.panes.items() if not p.archived]

    def archived_agents(self) -> List[str]:
        return [a for a, p in self.panes.items() if p.archived]

    def is_tabbed(self) -> bool:
        """Sekme kipinde mi (4+ etkin bölme)?"""
        return self.stack.currentIndex() == 1

    def _sync_layout(self) -> None:
        """Etkin bölmeleri sayıya göre bölünmüş görünüme ya da sekmelere koyar."""
        active = [self.panes[a] for a in sorted(self.active_agents())]
        archived = [self.panes[a] for a in sorted(self.archived_agents())]

        # Kaplardan çıkar (aynı bölme iki kapta duramaz).
        while self.tabs.count():
            self.tabs.removeTab(0)
        while self.archive_tabs.count():
            self.archive_tabs.removeTab(0)
        for index in reversed(range(self.split.count())):
            widget = self.split.widget(index)
            widget.setParent(None)

        tabbed = len(active) > SPLIT_LIMIT
        for pane in active:
            if tabbed:
                self.tabs.addTab(pane, pane.agent)
            else:
                self.split.addWidget(pane)
            pane.setVisible(True)
        self.stack.setCurrentIndex(1 if tabbed else 0)
        self.stack.setVisible(bool(active))
        self.placeholder.setVisible(not active)

        for pane in archived:
            self.archive_tabs.addTab(pane, pane.agent)
            pane.setVisible(True)
        self.archive_tabs.setVisible(bool(archived))
        self.archive_label.setText(
            f"🗄 Arşiv · {len(archived)} biten koşu" if archived else ""
        )
        self.archive_label.setVisible(bool(archived))
        if self._focused:
            self._raise_pane(self._focused)

    def _raise_pane(self, agent: str) -> None:
        pane = self.panes.get(agent)
        if pane is None:
            return
        for container in (self.tabs, self.archive_tabs):
            index = container.indexOf(pane)
            if index >= 0:
                container.setCurrentIndex(index)
        if self.tabs.indexOf(pane) >= 0:
            self.stack.setCurrentIndex(1)

    # ------------------------------------------------------------ akış

    @Slot(dict)
    def handle_stream(self, payload: dict) -> None:
        """
        `bus.agent_stream` alıcısı (QObject slotu; işçi iş parçacığından
        gelirse kuyruklanır).
        """
        if not isinstance(payload, dict):
            return
        office = str(payload.get("office") or "")
        if self.office and office and office != self.office:
            return
        agent = str(payload.get("agent") or "")
        if not agent:
            return
        pane = self.pane_for(agent)
        if pane is None:
            return
        if pane.archived:
            # Ajan yeniden koşuyor: bölme arşivden etkinlere döner.
            pane.set_archived(False)
            self._sync_layout()
        if not pane.card_title:
            pane.set_card_title(self._card_title(str(payload.get("card_id") or "")))
        pane.append_event(payload)

    def _card_title(self, card_id: str) -> str:
        """Kart başlığı; pano yoksa kimlik döner (uydurma başlık yazılmaz)."""
        if not card_id:
            return ""
        board = self.board
        getter = getattr(board, "get", None)
        if callable(getter):
            try:
                card = getter(card_id)
                title = str(getattr(card, "title", "") or "")
                if title:
                    return title
            except Exception:
                pass
        return card_id

    @Slot(str, bool)
    def _on_task_completed(self, card_id: str, _success: bool) -> None:
        """
        Kart bitti: o kartın bölmesi arşive taşınır (silinmez).

        Köprüler `task_id`'yi yayar ve kart yolunda bu `card-<kart>` biçimindedir;
        bölmenin `card_id` alanı ise akış künyesinden çıplak kart kimliğidir.
        İkisi de denenir, yoksa hiçbir bölme arşivlenmiyordu.

        Faz 10-D: ETKİLEŞİMLİ koşuda ilk `task_completed` yalnızca ilk turun
        bittiğini söyler; süreç canlıdır ve takip mesajı bekler. O bölme
        arşive gitmez — arşive yalnızca `close_interactive` ile ya da köprü
        görevi etkileşimli listesinden düşürünce (süreç bitişi) taşınır.
        """
        self.archive_card(str(card_id or ""))

    def _bridge_interactive_ids(self) -> Optional[set]:
        """Köprünün canlı etkileşimli görev kimlikleri; sözleşme yoksa None."""
        fn = getattr(self.bridge, "interactive_task_ids", None)
        if not callable(fn):
            return None
        try:
            return {str(t) for t in (fn() or [])}
        except Exception:
            return None

    def archive_card(self, card_id: str, force: bool = False) -> bool:
        if not card_id:
            return False
        raw = str(card_id)
        bare = raw[5:] if raw.startswith("card-") else raw
        keys = {raw, bare}
        live = self._bridge_interactive_ids()
        changed = False
        for pane in self.panes.values():
            if pane.archived:
                continue
            if pane.card_id in keys or pane.task_id in keys:
                if not force and pane.interactive:
                    still_live = True if live is None else bool(
                        {pane.task_id, f"card-{pane.card_id}", pane.card_id} & live)
                    if still_live:
                        continue
                pane.set_archived(True)
                changed = True
        if changed:
            self._sync_layout()
        return changed

    @Slot(dict)
    def handle_followup(self, payload: dict) -> None:
        """
        `bus.task_followup_completed` alıcısı: turu ilgili bölmeye yazar ve
        kartın makbuz/detay tazelemesini ister.
        """
        if not isinstance(payload, dict):
            return
        task_id = str(payload.get("task_id") or "")
        card_id = str(payload.get("card_id") or "")
        pane = self.pane_for_task(task_id, card_id)
        if pane is None:
            return
        pane.interactive = True
        pane.append_turn(payload)
        if card_id:
            self.card_refresh_requested.emit(card_id)

    def pane_for_task(self, task_id: str, card_id: str = "") -> Optional[AgentTerminalPane]:
        """Görev/kart kimliğine göre bölme; `card-` öneki iki yönlü denenir."""
        keys = set()
        for raw in (str(task_id or ""), str(card_id or "")):
            if not raw:
                continue
            keys.add(raw)
            keys.add(raw[5:] if raw.startswith("card-") else f"card-{raw}")
        if not keys:
            return None
        for pane in self.panes.values():
            if pane.task_id in keys or (pane.card_id and pane.card_id in keys):
                return pane
        return None

    @Slot(str)
    def _on_pane_closed(self, _agent: str) -> None:
        """Bölme `close_interactive` ile kapandı: kaplar yeniden dizilir."""
        self._sync_layout()

    def archive_agent(self, agent: str) -> bool:
        pane = self.panes.get(str(agent or ""))
        if pane is None or pane.archived:
            return False
        pane.set_archived(True)
        self._sync_layout()
        return True

    # ------------------------------------------------------------ odak

    def focus_agent(self, agent: str) -> None:
        """
        Sprite tıklamasının hedefi (geriye uyumlu ad): o ajanın bölmesi öne
        gelir; bölme yoksa boş bir bölme açılır (ajanın terminali "henüz
        çıktı vermedi" hâliyle görünür).
        """
        agent = str(agent or "")
        self._focused = agent
        if not agent:
            return
        pane = self.pane_for(agent)
        if pane is None:
            return
        self._raise_pane(agent)
        pane.setFocus()
        self.agent_focused.emit(agent)

    @property
    def agent(self) -> str:
        """Geriye uyum: son odaklanılan ajan."""
        return self._focused

    def stream_text(self, agent: str = "") -> str:
        """Test için: bir ajanın (ya da odaktakinin) ham metni."""
        pane = self.panes.get(agent or self._focused)
        return pane.raw_text() if pane is not None else ""
