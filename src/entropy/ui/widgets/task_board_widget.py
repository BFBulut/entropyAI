"""
Ajan görev panosu — kanban görünümü.

Faz 11-C: sütunlar pano durum makinesinin 8 durumuna göre (`board_fsm`):
Bekliyor / Atandı / Çalışıyor / İnceleme / Bitti / Başarısız / İptal.
`taken` ayrı sütun değil — Çalışıyor sütununda "sahiplenildi" rozetiyle durur
(iki durum arasındaki fark kart üzerinde okunur, sütun sayısı şişmez).
`failed` ve `canceled` sütunları boşken gizlenir ki pano tek ekrana sığsın.
Kart seçilince sağda detay paneli açılır.

Veri kaynağı `entropy.agents.tasks.TaskBoard`; modül henüz yoksa pano boş
görünür (import guard). Testler yapıcıya sahte pano verebilir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSplitter, QVBoxLayout, QWidget
)

from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.ui_polish import BODY_PX, LABEL_PX, apply_no_hscroll

# Kanban sütunu için en küçük okunur genişlik (kart başlığı + kenar boşlukları).
# Faz 11-C: yedi sütun olunca 190 px pano genişliğini 1.400 px'e zorluyordu.
COLUMN_MIN_WIDTH = 168

#: `board_state_changed` yenileme gecikmesi (ms) — olay salvosu tek turda toplanır.
BOARD_DEBOUNCE_MS = 150
from entropy.ui.widgets.agents_widget import (
    STATUS_COLORS, STATUS_LABELS, call_flex, list_cards_for, load_board,
    model_belongs_to, models_for_provider, spec_field
)

# Kanban sütunları: (anahtar, başlık). `taken` ayrı sütun değil, Çalışıyor'da rozet.
COLUMNS = [
    ("backlog", "Bekliyor"),
    ("assigned", "Atandı"),
    ("running", "Çalışıyor"),
    ("review", "İnceleme"),
    ("done", "Bitti"),
    ("failed", "Başarısız"),
    ("canceled", "İptal"),
]

#: Boşken gizlenen sütunlar — uç durumlar panoyu sürekli işgal etmesin.
COLLAPSIBLE_COLUMNS = {"failed", "canceled"}

#: Durum → sütun anahtarı (8 durum, 7 sütun). Tek kaynak: `agents/board_fsm`.
STATUS_TO_COLUMN = {
    "backlog": "backlog",
    "assigned": "assigned",
    "taken": "running",
    "running": "running",
    "review": "review",
    "done": "done",
    "failed": "failed",
    "canceled": "canceled",
}

#: Kart ayarlarının (efor/model/sağlayıcı) düzenlenebildiği durumlar.
#: Koşan/biten kartın modelini değiştirmek yalanı diske yazmak olurdu.
EDITABLE_STATUSES = {"backlog", "assigned"}

#: Öncelik rozeti tonları (belirteç sistemi `tone` özelliği).
PRIORITY_TONES = {"P0": "danger", "P1": "warn", "P2": "accent"}


def card_proof(card: Any) -> Optional[Dict[str, Any]]:
    """
    Kartın kanıt kaydı (`proof`): komut, sonuç (`green`/`red`/`unknown`), özet.

    Harness ekler; alan yoksa None döner. "Kanıt yok" ile "kanıt kırmızı"
    ayrı şeylerdir — None ile `{"result": "red"}` karıştırılmamalıdır.
    """
    proof = spec_field(card, "proof", None)
    if isinstance(proof, dict) and proof:
        return dict(proof)
    return None


def card_checkpoint(card: Any, office: str = "") -> Optional[Dict[str, Any]]:
    """
    Kartın kontrol noktası: önce kart alanı, yoksa kasadaki dosya.

    Bellek katmanı (`entropy.memory.checkpoints`) paralel ajanda; modül ya da
    dosya yoksa None (panel bölümü gizlenir, uydurma özet yazılmaz).
    """
    data = spec_field(card, "checkpoint", None)
    if isinstance(data, dict) and data:
        return dict(data)
    card_id = str(spec_field(card, "id", ""))
    office = office or str(spec_field(card, "office", ""))
    if not card_id or not office:
        return None
    try:
        from entropy.memory.checkpoints import read_checkpoint  # type: ignore

        result = read_checkpoint(office, card_id)
    except Exception:
        return None
    return dict(result) if isinstance(result, dict) and result else None


def proof_is_missing(card: Any) -> bool:
    """
    Kart "kanıt eksik" mi? (İnceleme sütununda etiketlenir.)

    İşçi testsiz "bitti" diyemez: kanıt hiç yoksa ya da kırmızıysa kart
    incelemede işaretlenir. Bekleyen/koşan kartlar için etiket yok.
    """
    status = str(spec_field(card, "status", ""))
    if column_for_status(status) != "review":
        return False
    proof = card_proof(card)
    if not proof:
        return True
    return str(proof.get("result") or "").lower() != "green"


def column_for_status(status: str) -> str:
    """Durumu sütun anahtarına eşler; bilinmeyen durumlar Bekliyor'a düşer."""
    return STATUS_TO_COLUMN.get((status or "").strip(), "backlog")


def card_badges(card: Any) -> List[tuple]:
    """
    Kart rozetleri: `[(metin, ton)]` — öncelik, sahiplenme, efor, ajan.

    Ton adları belirteç sistemindeki `tone` değerleridir (`accent/ok/warn/
    danger/muted`); renk burada değil, `_tone_color` üzerinden belirteçten
    çözülür. Boş alan rozet üretmez — uydurma etiket basılmaz.
    """
    badges: List[tuple] = []
    priority = str(spec_field(card, "priority", "") or "").strip().upper()
    if priority:
        badges.append((priority, PRIORITY_TONES.get(priority, "muted")))
    status = str(spec_field(card, "status", "") or "").strip()
    if status == "taken":
        badges.append(("sahiplenildi", "accent"))
    claimed_by = str(spec_field(card, "claimed_by", "") or "").strip()
    if claimed_by:
        badges.append((f"sahip: {claimed_by}", "accent"))
    effort = str(spec_field(card, "effort", "") or "").strip()
    if effort:
        badges.append((f"efor {effort}", "muted"))
    agent = str(spec_field(card, "agent", "") or "").strip()
    if agent:
        badges.append((agent, "ok"))
    return badges


def _tone_color(tone: str) -> str:
    """Ton adını tasarım belirtecine çevirir (yerel onaltılık renk yazılmaz)."""
    from entropy.ui.design import TOKENS

    colors = TOKENS["color"]
    return {
        "accent": colors["accent"],
        "ok": colors["ok"],
        "warn": colors["warn"],
        "danger": colors["danger"],
    }.get(tone, colors["text.muted"])


def card_is_editable(card: Any) -> bool:
    """Koşum ayarları yalnızca `backlog`/`assigned` kartlarda değiştirilebilir."""
    return str(spec_field(card, "status", "")).strip() in EDITABLE_STATUSES


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
        self.setProperty("role", "panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 7, 9, 7)
        layout.setSpacing(3)

        title_text = str(spec_field(card, "title", "(başlıksız)"))
        header = title_text
        if self.status == "failed":
            header = (
                f"<span style='background:#4A1A1F; color:#FF6B6B; font-size:11px; "
                f"padding:1px 5px; border-radius:3px;'>BAŞARISIZ</span> {title_text}"
            )
        self.title_label = QLabel(
            f"<span style='color:{RT['text']}; font-size:{BODY_PX}px; font-weight:600;'>{header}</span>"
        )
        self.title_label.setWordWrap(True)
        self.title_label.setToolTip(title_text)
        layout.addWidget(self.title_label)

        # Faz 11-C: kart üzerinde ajan, öncelik, sahiplenen, efor rozetleri.
        self.badges = card_badges(card)
        if self.badges:
            badge_row = QLabel(" ".join(
                f"<span style='background:{RT['surface_soft']}; color:{_tone_color(tone)};"
                f" font-size:{LABEL_PX}px; padding:1px 5px; border-radius:3px;'>{text}</span>"
                for text, tone in self.badges
            ))
            badge_row.setWordWrap(True)
            badge_row.setToolTip(" · ".join(text for text, _ in self.badges))
            layout.addWidget(badge_row)

        meta_bits = [str(spec_field(card, "agent", "")) or "—"]
        provider = str(spec_field(card, "provider", ""))
        model = str(spec_field(card, "model", ""))
        if provider or model:
            meta_bits.append(f"{provider}/{model}".strip("/"))
        duration = format_duration(card)
        if duration:
            meta_bits.append(duration)
        meta_text = ' · '.join(b for b in meta_bits if b)
        meta_label = QLabel(
            f"<span style='color:{RT['text_dim']}; font-size:{LABEL_PX}px;'>{meta_text}</span>"
        )
        meta_label.setToolTip(meta_text)
        # Dar sütunda tek satır kırpılıyordu; sağlayıcı/model okunur kalsın.
        meta_label.setWordWrap(True)
        layout.addWidget(meta_label)

        # Faz 10-B: kanıtsız/kırmızı kanıtlı kart incelemede etiketlenir.
        # İşçi testsiz "bitti" diyemez; etiket kartı gözden kaçırılmaz kılar.
        self.proof_missing = proof_is_missing(card)
        if self.proof_missing:
            proof_label = QLabel(
                f"<span style='background:#4A3A12; color:#FFC24D; "
                f"font-size:{LABEL_PX}px; padding:1px 5px; border-radius:3px;'>"
                f"kanıt eksik</span>"
            )
            proof_label.setToolTip(
                "Kartta yeşil kanıt (komut + sonuç) yok; iş bitti sayılmaz."
            )
            layout.addWidget(proof_label)

        summary = str(spec_field(card, "summary", ""))
        if summary:
            short = summary if len(summary) <= 110 else summary[:107] + "…"
            summary_label = QLabel(
                f"<span style='color:{RT['text_body']}; font-size:{LABEL_PX}px;'>{short}</span>"
            )
            summary_label.setWordWrap(True)
            # Kısaltılan özetin tamamı ipucunda kalır (bilgi kaybı olmasın).
            summary_label.setToolTip(summary)
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
        self.body_label.setProperty("role", "label")
        layout.addWidget(self.body_label)

        # Faz 10-B: "Kaldığı yer" (kontrol noktası) ve "Kanıt" bölümleri.
        # Ajan koşusu yarıda kalınca kullanıcı nereden devam edileceğini,
        # bittiğinde ise hangi komutun neyi doğruladığını burada görür.
        self.checkpoint_label = QLabel("")
        self.checkpoint_label.setWordWrap(True)
        self.checkpoint_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.checkpoint_label.setProperty("role", "label")
        self.checkpoint_label.setVisible(False)
        layout.addWidget(self.checkpoint_label)

        self.proof_label = QLabel("")
        self.proof_label.setWordWrap(True)
        self.proof_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.proof_label.setProperty("role", "label")
        self.proof_label.setVisible(False)
        layout.addWidget(self.proof_label)

        self.outputs_container = QWidget()
        self.outputs_layout = QVBoxLayout(self.outputs_container)
        self.outputs_layout.setContentsMargins(0, 0, 0, 0)
        self.outputs_layout.setSpacing(3)
        layout.addWidget(self.outputs_container)

        # Faz 7: kart detayında koşum ayarları (sağlayıcı/model/efor/bütçe).
        # Kart panoda dururken bunlar değiştirilemiyordu; kullanıcı pahalı bir
        # kartı ucuz modelle yeniden koşmak için kartı silip yeniden yaratıyordu.
        settings = QHBoxLayout()
        settings.setSpacing(4)
        self.provider_combo = QComboBox()
        self.provider_combo.setAccessibleName("Sağlayıcı (boş = ajanın varsayılanı)")
        self.provider_combo.addItems(["", "agy", "claude"])
        self.provider_combo.setToolTip("Sağlayıcı (boş = ajanın varsayılanı)")
        self.model_combo = QComboBox()
        self.model_combo.setAccessibleName("Model (boş = oturumun modelini miras al)")
        self.model_combo.setEditable(True)
        self.model_combo.setToolTip("Model (boş = oturumun modelini miras al)")
        # Faz 9: model listesi seçili sağlayıcıya bağlı. Kutuda her iki
        # sağlayıcının adları birlikte durunca kullanıcı agy kartına Claude
        # modeli yazıyor, koşu geçersiz `--model` ile başlıyordu.
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.effort_combo = QComboBox()
        self.effort_combo.setAccessibleName("Efor düzeyi")
        self.effort_combo.addItems(["", "low", "medium", "high"])
        self.effort_combo.setToolTip("Efor düzeyi")
        # HOTFIX v0.7.1: efor seçenekleri sağlayıcı + modele bağlı (agy'de efor
        # model adının son ekidir, ayrı bayrak değil).
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.budget_input = QLineEdit()
        self.budget_input.setAccessibleName("Kart token bütçesi (0 = ofis bütçesi)")
        self.budget_input.setPlaceholderText("bütçe")
        self.budget_input.setFixedWidth(72)
        self.budget_input.setToolTip("Kart token bütçesi (0 = ofis bütçesi)")
        self.apply_btn = QPushButton("Uygula")
        self.apply_btn.setAccessibleName("Uygula")
        self.apply_btn.setToolTip("Koşum ayarlarını karta yaz")
        self.apply_btn.clicked.connect(self._on_apply_settings)
        for widget in (self.provider_combo, self.model_combo, self.effort_combo,
                       self.budget_input, self.apply_btn):
            settings.addWidget(widget)
        settings.addStretch()
        layout.addLayout(settings)

        layout.addStretch()

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.run_btn = QPushButton("▶ Çalıştır")
        self.run_btn.setAccessibleName("▶ Çalıştır")
        self.run_btn.setToolTip("Kartı ajana gönder")
        self.run_btn.clicked.connect(self._on_run)
        actions.addWidget(self.run_btn)

        self.stop_btn = QPushButton("■ Durdur")
        self.stop_btn.setAccessibleName("■ Durdur")
        self.stop_btn.setToolTip("Çalışan görevi sonlandır")
        self.stop_btn.clicked.connect(self._on_stop)
        actions.addWidget(self.stop_btn)

        self.done_btn = QPushButton("Bitti")
        self.done_btn.setAccessibleName("Bitti")
        self.done_btn.setToolTip("Görevi bitti olarak işaretle")
        self.done_btn.clicked.connect(self._on_done)
        actions.addWidget(self.done_btn)

        self.contract_btn = QPushButton("Sözleşme")
        self.contract_btn.setAccessibleName("Sözleşme")
        self.contract_btn.setToolTip("Kartın sözleşme dosyasını rapor okuyucuda aç")
        self.contract_btn.clicked.connect(self._on_open_contract)
        actions.addWidget(self.contract_btn)

        self.delete_btn = QPushButton("Sil")
        self.delete_btn.setAccessibleName("Sil")
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
        for widget in (self.provider_combo, self.model_combo, self.effort_combo,
                       self.budget_input, self.apply_btn):
            widget.setEnabled(has_card)
        if has_card:
            self.provider_combo.setCurrentText(str(spec_field(card, "provider", "") or ""))
            self._on_provider_changed(self.provider_combo.currentText())
            self.model_combo.setCurrentText(str(spec_field(card, "model", "") or ""))
            # Faz 11-C: `effort` artık gerçek kart alanı. Eski kartlarda
            # `notes: "effort: X"` hilesi kalmış olabilir; okurken hâlâ
            # anlaşılır, ama yazarken ARTIK KULLANILMAZ.
            effort = str(spec_field(card, "effort", "") or "")
            if not effort:
                notes = str(spec_field(card, "notes", "") or "")
                if "effort:" in notes:
                    tail = notes.split("effort:", 1)[1].strip()
                    effort = tail.split()[0] if tail else ""
            # Kartta kayıtlı efor, yeni sağlayıcı/model kümesinde olmasa bile
            # kaybolmaz: kutuya eklenip seçilir.
            if effort and self.effort_combo.findText(effort) < 0:
                self.effort_combo.addItem(effort)
            self.effort_combo.setCurrentText(effort)
            self.budget_input.setText(str(int(spec_field(card, "budget_tokens", 0) or 0)))
            # Koşum ayarları yalnızca iş başlamadan değiştirilebilir.
            self._apply_editability(card)
        while self.outputs_layout.count():
            item = self.outputs_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        if not has_card:
            self.title_label.setText(
                f"<b style='color:{RT['accent']}; font-size:13px;'>GÖREV DETAYI</b>"
            )
            self.body_label.setText("Bir görev kartı seçin.")
            self.checkpoint_label.setVisible(False)
            self.proof_label.setVisible(False)
            return
        self._render_checkpoint(card)
        self._render_proof(card)

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
            btn = QPushButton(f"{Path(str(out)).name}")
            btn.setToolTip(str(out))
            btn.setProperty("output_path", str(out))
            btn.clicked.connect(self._on_open_output)
            self.outputs_layout.addWidget(btn)

    def _apply_editability(self, card: Any) -> None:
        """
        Ayar formunu kartın durumuna göre kilitler.

        Koşan/inceleme/bitmiş kartın sağlayıcısını değiştirmek diske yalan
        yazmak olurdu: koşu zaten başka modelle yapıldı. Kilit sebebi ipucunda.
        """
        editable = card_is_editable(card)
        for widget in (self.provider_combo, self.model_combo, self.effort_combo,
                       self.budget_input, self.apply_btn):
            widget.setEnabled(editable and widget is not self.effort_combo)
        if editable:
            self._refresh_effort()
        else:
            self.effort_combo.setEnabled(False)
        if not editable:
            status = str(spec_field(card, "status", ""))
            tip = (
                f"Kart '{STATUS_LABELS.get(status, status)}' durumunda; koşum "
                "ayarları yalnızca Bekliyor/Atandı kartlarda değiştirilebilir."
            )
            for widget in (self.provider_combo, self.model_combo, self.effort_combo,
                           self.budget_input, self.apply_btn):
                widget.setToolTip(tip)

    def settings_editable(self) -> bool:
        """Test için: form şu an düzenlenebilir mi?"""
        return bool(self.apply_btn.isEnabled())

    # ------------------------------------------------ kontrol noktası / kanıt

    def _render_checkpoint(self, card: Any) -> None:
        """"Kaldığı yer": kontrol noktası özeti + sonraki adımlar."""
        data = card_checkpoint(card, str(spec_field(card, "office", "")))
        if not data:
            self.checkpoint_label.setVisible(False)
            self.checkpoint_label.setText("")
            return
        summary = str(data.get("summary") or data.get("done") or "").strip()
        nxt = str(data.get("next_steps") or "").strip()
        updated = str(data.get("updated_at") or "")
        parts = [f"<b style='color:{RT['text']};'>Kaldığı yer</b>"]
        if updated:
            parts.append(
                f" <span style='color:{RT['text_dim']};'>· {updated}</span>"
            )
        parts.append("<br>")
        parts.append(summary or "<i>özet yok</i>")
        if nxt:
            parts.append(
                f"<br><span style='color:{RT['text_dim']};'>Sonraki:</span> {nxt}"
            )
        files = list(data.get("files_touched") or [])
        if files:
            parts.append(
                f"<br><span style='color:{RT['text_dim']};'>Dosyalar: "
                f"{', '.join(str(f) for f in files[:6])}</span>"
            )
        self.checkpoint_label.setText("".join(parts))
        self.checkpoint_label.setVisible(True)

    def _render_proof(self, card: Any) -> None:
        """"Kanıt": komut + yeşil/kırmızı rozet + özet; yoksa "kanıt yok"."""
        proof = card_proof(card)
        if not proof:
            missing = proof_is_missing(card)
            self.proof_label.setText(
                f"<b style='color:{RT['text']};'>Kanıt</b> "
                f"<span style='background:#4A3A12; color:#FFC24D; padding:1px 5px;"
                f" border-radius:3px;'>kanıt yok</span>"
                + ("<br><span style='color:" + RT["text_dim"] + ";'>"
                   "İşçi testsiz 'bitti' diyemez.</span>" if missing else "")
            )
            self.proof_label.setVisible(True)
            return
        result = str(proof.get("result") or "unknown").lower()
        badge = {
            "green": ("#12331F", "#3DE8A8", "yeşil"),
            "red": ("#4A1A1F", "#FF6B6B", "kırmızı"),
        }.get(result, ("#33302A", "#FFC24D", "belirsiz"))
        command = str(proof.get("command") or "")
        summary = str(proof.get("summary") or "")
        html_parts = [
            f"<b style='color:{RT['text']};'>Kanıt</b> ",
            f"<span style='background:{badge[0]}; color:{badge[1]}; padding:1px 5px;"
            f" border-radius:3px;'>{badge[2]}</span>",
        ]
        if command:
            html_parts.append(
                f"<br><code style='color:{RT['text_body']};'>{command}</code>"
            )
        if summary:
            html_parts.append(
                f"<br><span style='color:{RT['text_dim']};'>{summary}</span>"
            )
        self.proof_label.setText("".join(html_parts))
        self.proof_label.setVisible(True)

    # --------------------------------------------------------- eylemler

    def _on_provider_changed(self, provider: str) -> None:
        """Sağlayıcıya ait model listesi (ilk girdi boş = oturumun modeli)."""
        current = self.model_combo.currentText().strip()
        bridge = getattr(self.board_widget, "bridge", None)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem("")
        provider = (provider or "").strip()
        if provider:
            for m in models_for_provider(provider, bridge):
                self.model_combo.addItem(m)
        if current and (not provider or model_belongs_to(provider, current)):
            self.model_combo.setCurrentText(current)
        else:
            self.model_combo.setCurrentText("")
        self.model_combo.blockSignals(False)
        self._refresh_effort()

    def _on_model_changed(self, _model: str) -> None:
        self._refresh_effort()

    def _refresh_effort(self) -> None:
        combo = getattr(self, "effort_combo", None)
        if combo is None:
            return
        from entropy.ui.widgets.agents_widget import populate_effort_combo

        levels = populate_effort_combo(
            combo,
            self.provider_combo.currentText().strip(),
            self.model_combo.currentText().strip(),
            getattr(self.board_widget, "bridge", None),
            allow_empty=True,
        )
        # Kart seçili değilken panel bütünüyle pasif kalır.
        combo.setEnabled(bool(levels) and getattr(self, "card", None) is not None)

    def effort_choices(self) -> List[str]:
        """Test için: efor kutusundaki seçenekler (boş girdi hariç)."""
        return [self.effort_combo.itemText(i) for i in range(self.effort_combo.count())
                if self.effort_combo.itemText(i)]

    def model_choices(self) -> List[str]:
        """Test için: kutudaki model adları (boş girdi hariç)."""
        return [self.model_combo.itemText(i) for i in range(self.model_combo.count())
                if self.model_combo.itemText(i)]

    def settings_payload(self) -> Dict[str, Any]:
        """Formdaki koşum ayarları (test ve uygulama için tek kaynak)."""
        try:
            budget = max(0, int(str(self.budget_input.text()).strip() or "0"))
        except ValueError:
            budget = 0
        return {
            "provider": self.provider_combo.currentText().strip(),
            "model": self.model_combo.currentText().strip(),
            "effort": self.effort_combo.currentText().strip(),
            "budget_tokens": budget,
        }

    def _on_apply_settings(self):
        if self.card is None:
            return False
        return self.board_widget.update_card_settings(
            str(spec_field(self.card, "id", "")), self.settings_payload()
        )

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

    def __init__(self, parent=None, board: Any = None, compact: bool = False,
                 office: str = "", bridge: Any = None):
        """
        `office` verilirse pano yalnızca o ofise ait kartları gösterir (Agent Desk
        Kartlar sekmesi) ve kartlar üst/alt (parent/children) ağacı olarak sıralanır.
        Boşsa eski davranış: tüm kartlar.
        """
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.board = board if board is not None else load_board()
        self.compact = compact
        self.office = office or ""
        # Etkin köprü (varsa): detay panelindeki model listesi canlı okunur.
        self.bridge = bridge
        self.selected_id: str = ""
        # Faz 7: Projeler sekmesinin kart süzgeci ("" = süzgeç yok).
        self.project_filter: str = ""
        self.column_layouts: Dict[str, QVBoxLayout] = {}
        self.column_headers: Dict[str, QLabel] = {}
        self.column_frames: Dict[str, QFrame] = {}
        self.card_widgets: List[TaskCardWidget] = []
        self._cards: List[Any] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        header = QHBoxLayout()
        self.title_label = QLabel(
            f"<b style='color:{RT['accent']}; font-size:13px;'>AJAN GÖREV PANOSU</b>"
            + (f" <span style='color:{RT['text_dim']}; font-size:11px;'>{self.office}</span>"
               if self.office else "")
        )
        self.title_label.setProperty("role", "label")
        header.addWidget(self.title_label)
        header.addStretch()
        # Faz 11-C: `TASKBOARD.md` türetilmiş panonun kendisi; kullanıcı
        # ajanların gördüğü metni doğrudan okuyabilmeli.
        self.taskboard_btn = QPushButton("Pano dosyası")
        self.taskboard_btn.setAccessibleName("Pano dosyası")
        self.taskboard_btn.setProperty("variant", "ghost")
        self.taskboard_btn.setToolTip(
            "Entropy/Board/TASKBOARD.md — ajanların okuduğu türetilmiş pano"
        )
        self.taskboard_btn.clicked.connect(self.open_taskboard_file)
        header.addWidget(self.taskboard_btn)
        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.setAccessibleName("Yenile")
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
            column.setProperty("role", "panel")
            col_layout = QVBoxLayout(column)
            col_layout.setContentsMargins(6, 6, 6, 6)
            col_layout.setSpacing(5)
            head = QLabel("")
            head.setProperty("role", "label")
            col_layout.addWidget(head)
            self.column_headers[key] = head

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            # Kartlar sütun genişliğine uyar; yatay çubuk sütunun altında
            # gereksiz bir şerit bırakıyordu (Faz 2 kozmetik notu).
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.viewport().setAutoFillBackground(False)
            inner = QWidget()
            inner.setAutoFillBackground(False)
            inner_layout = QVBoxLayout(inner)
            inner_layout.setContentsMargins(0, 0, 0, 0)
            inner_layout.setSpacing(5)
            inner_layout.addStretch()
            scroll.setWidget(inner)
            col_layout.addWidget(scroll, 1)
            self.column_layouts[key] = inner_layout
            # Faz 2-3 notu: sütunlar yalnızca esneme katsayısıyla paylaşılınca
            # dar pencerede kartlar okunamayacak kadar sıkışıyordu. Her sütuna
            # alt sınır verilir; dört sütun sığmazsa gövde yatay değil, splitter
            # üzerinden yeniden boyutlanır.
            column.setMinimumWidth(COLUMN_MIN_WIDTH)
            columns_layout.addWidget(column, 1)
            self.column_frames[key] = column

        # Faz 7: dört sütunun örtük asgarisi (4x190 + detay) panoyu 1400 px'e
        # zorluyordu; yarım ekran Desk'te (≈900 px) orta sütun kırpılıyordu.
        # Sütunlar yatay kaydırılabilir bir alana konur: dar pencerede pano
        # daralır, sütunlar okunur genişliğini korur.
        self.columns_scroll = QScrollArea()
        self.columns_scroll.setWidgetResizable(True)
        self.columns_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.columns_scroll.setWidget(columns_host)
        self.columns_scroll.setMinimumWidth(200)
        splitter.addWidget(self.columns_scroll)

        self.detail_panel = TaskDetailPanel(self)
        self.detail_panel.setMinimumWidth(180)
        # Pano da dar sütunda yaşayabilsin: örtük asgari yerine açık asgari.
        self.setMinimumWidth(220)
        if not compact:
            splitter.addWidget(self.detail_panel)
            splitter.setSizes([700, 320])
        else:
            self.detail_panel.setVisible(False)
        root.addWidget(splitter, 1)

        signal = getattr(bus, "task_cards_updated", None)
        if signal is not None:
            signal.connect(self._on_cards_updated)

        # Faz 11-C: pano durum makinesi her geçişte `board_state_changed`
        # yayar. Bir tetikleme turunda onlarca olay gelebilir; her birinde
        # tüm kartları yeniden kurmak arayüzü kilitliyordu → debounce.
        self._board_debounce = QTimer(self)
        self._board_debounce.setSingleShot(True)
        self._board_debounce.setInterval(BOARD_DEBOUNCE_MS)
        self._board_debounce.timeout.connect(self.refresh_cards)
        self.last_board_event: Dict[str, Any] = {}
        board_signal = getattr(bus, "board_state_changed", None)
        if board_signal is not None:
            board_signal.connect(self._on_board_state_changed)

        self.refresh_cards()

    # ------------------------------------------------------------ veri

    def _on_cards_updated(self, _payload: str = "") -> None:
        """Sözleşme sinyali alıcısı (QObject metodu, lambda değil)."""
        self.refresh_cards()

    def _on_board_state_changed(self, payload: dict) -> None:
        """
        `bus.board_state_changed` alıcısı (QObject metodu, lambda değil).

        Yük `{card_id, status, event, agent, office, title}`. Ofisli pano
        yalnızca kendi ofisinin olaylarını dinler. Yenileme debounce ile
        toplanır; `flush_board_events()` testte beklemeyi gereksiz kılar.
        """
        data = payload if isinstance(payload, dict) else {}
        office = str(data.get("office") or "")
        if self.office and office and office != self.office:
            return
        self.last_board_event = dict(data)
        self._board_debounce.start()

    def flush_board_events(self) -> None:
        """Bekleyen debounce'u hemen uygular (test ve pencere odaklanması)."""
        if self._board_debounce.isActive():
            self._board_debounce.stop()
            self.refresh_cards()

    def open_taskboard_file(self) -> str:
        """`TASKBOARD.md` dosyasını rapor okuyucuda açar; yolu döner ('' = yok)."""
        try:
            from entropy.core.paths import board_taskboard_path

            path = Path(board_taskboard_path())
        except Exception:
            return ""
        if not path.exists():
            bus.terminal_output_received.emit(
                "[Pano] TASKBOARD.md henüz üretilmedi (pano olayı yok).\n"
            )
            return ""
        bus.report_created.emit(str(path))
        return str(path)

    def list_cards(self) -> List[Any]:
        # Faz 9: kartlar iki kökte. Ofissiz pano = Entropy kapsamı (Zen
        # "Görevler" sekmesi), ofisli pano = yalnızca o ofisin kart klasörü.
        cards = list_cards_for(self.board, self.office)
        if self.office:
            cards = [c for c in cards if str(spec_field(c, "office", "")) == self.office]
        # Faz 7: Projeler sekmesinden gelen süzgeç. Boşsa tüm kartlar görünür.
        if getattr(self, "project_filter", ""):
            cards = [c for c in cards
                     if str(spec_field(c, "project", "")) == self.project_filter]
        return cards

    def set_project_filter(self, project: str) -> None:
        """Kartları tek projeye süzer ('' = süzgeç yok)."""
        self.project_filter = project or ""
        self.selected_id = ""
        self.refresh_cards()

    def set_office(self, office: str) -> None:
        self.office = office or ""
        self.selected_id = ""
        self.project_filter = ""
        self.title_label.setText(
            f"<b style='color:{RT['accent']}; font-size:13px;'>AJAN GÖREV PANOSU</b>"
            + (f" <span style='color:{RT['text_dim']}; font-size:11px;'>{self.office}</span>"
               if self.office else "")
        )
        self.refresh_cards()

    def card_depth(self, card: Any) -> int:
        """
        Kartın ağaçtaki derinliği (0 = üst kart).

        Derinlik `parent` zinciri izlenerek bulunur; döngüsel bir zincir
        (dosyalar elle düzenlenebiliyor) sonsuz döngüye girmesin diye adım
        sayısı kart sayısıyla sınırlanır.
        """
        depth = 0
        seen = set()
        current = card
        for _ in range(len(self._cards) + 1):
            parent_id = str(spec_field(current, "parent", ""))
            if not parent_id or parent_id in seen:
                break
            seen.add(parent_id)
            parent = self.get_card(parent_id)
            if parent is None:
                break
            depth += 1
            current = parent
        return depth

    def ordered_cards(self, cards: List[Any]) -> List[Any]:
        """Üst kartları önce, altlarını hemen ardından sıralar (ağaç görünümü)."""
        by_id = {str(spec_field(c, "id", "")): c for c in cards}
        roots = [c for c in cards if str(spec_field(c, "parent", "")) not in by_id]
        ordered: List[Any] = []
        emitted = set()

        def walk(card: Any) -> None:
            card_id = str(spec_field(card, "id", ""))
            if card_id in emitted:
                return
            emitted.add(card_id)
            ordered.append(card)
            for child in cards:
                if str(spec_field(child, "parent", "")) == card_id:
                    walk(child)

        for root in roots:
            walk(root)
        for card in cards:  # sarkan (ebeveyni aynı sütunda olmayan) kartlar
            if str(spec_field(card, "id", "")) not in emitted:
                ordered.append(card)
        return ordered

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
            # Uç durum sütunları (Başarısız/İptal) boşken gizlenir: pano tek
            # ekrana sığsın, ama bir kart düştüğü an sütun geri gelsin.
            frame = self.column_frames.get(key)
            if frame is not None and key in COLLAPSIBLE_COLUMNS:
                frame.setVisible(bool(column_cards))
            self.column_headers[key].setText(
                f"<span style='color:{RT['text_dim']}; font-size:11px; font-weight:600; "
                f"letter-spacing:0.4px;'>{label.upper()}</span>"
                f" <span style='color:{RT['text_dim']}; font-size:11px;'>({len(column_cards)})</span>"
            )
            for card in self.ordered_cards(column_cards):
                widget = TaskCardWidget(card, self)
                # Alt kartlar girintili: ağaç ilişkisi kanbanda da görünsün.
                depth = self.card_depth(card)
                if depth:
                    widget.setContentsMargins(min(depth, 3) * 12, 0, 0, 0)
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

    def update_card_settings(self, card_id: str, settings: Dict[str, Any]) -> bool:
        """
        Kartın koşum ayarlarını (sağlayıcı/model/efor/bütçe) yazar.

        Faz 11-C: `effort` GERÇEK kart alanı (`TaskCard.effort`); eski
        `notes: "effort: X"` hilesi kaldırıldı — o satırı hiçbir koşum yolu
        okumuyordu, seçim sessizce kayboluyordu. Dataclass'ta olmayan
        anahtarlar yine sessizce atılır ki sözleşme değişince arayüz kırılmasın.

        Yalnızca `backlog`/`assigned` kartlar yazılabilir; başlamış bir kartın
        modelini değiştirmek diske yalan yazmak olurdu.
        """
        if self.board is None or not card_id:
            return False
        try:
            current = self.board.get(card_id)
        except Exception:
            current = self.get_card(card_id)
        target = current if current is not None else self.get_card(card_id)
        if target is not None and not card_is_editable(target):
            bus.terminal_output_received.emit(
                f"[Pano] '{card_id}' başlamış bir kart; koşum ayarları değiştirilmedi.\n"
            )
            return False
        payload = {k: v for k, v in (settings or {}).items() if v not in ("", None)}
        payload["budget_tokens"] = int((settings or {}).get("budget_tokens", 0) or 0)
        try:
            if current is not None and hasattr(current, "__dataclass_fields__"):
                from dataclasses import replace

                fields = getattr(current, "__dataclass_fields__", {})
                clean = {k: v for k, v in payload.items() if k in fields}
                self.board.update(replace(current, **clean))
            else:
                call_flex(self.board.update, payload, card_id)
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Pano] Kart ayarı yazılamadı: {exc}\n")
            return False
        self._emit_updated(card_id)
        return True

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

    def __init__(self, parent=None, board: Any = None, office: str = ""):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.board = board if board is not None else load_board()
        # Chat kipinde kompakt liste Entropy kapsamındadır (office=""); Desk
        # bir gün bu listeyi kullanırsa ofis adı geçilir.
        self.office = office or ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        head = QHBoxLayout()
        head.addWidget(QLabel(
            f"<b style='color:{RT['accent']}; font-size:13px;'>AJAN GÖREVLERİ</b>"
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
        # Kompakt listede satırlar zaten sütun genişliğine sığar; yatay çubuk
        # yalnızca listenin altında gereksiz bir şerit bırakıyordu.
        apply_no_hscroll(scroll)
        scroll.setWidget(self.list_container)
        layout.addWidget(scroll, 1)

        signal = getattr(bus, "task_cards_updated", None)
        if signal is not None:
            signal.connect(self._on_cards_updated)
        self.refresh_cards()

    def _on_cards_updated(self, _payload: str = "") -> None:
        self.refresh_cards()

    def list_cards(self) -> List[Any]:
        return list_cards_for(self.board, self.office)

    def open_count(self) -> int:
        cards = self.list_cards()
        return sum(
            1 for c in cards
            # Faz 11-C: "açık" = kapanmamış her durum (`done`/`canceled` hariç).
            if str(spec_field(c, "status", "")) in {
                "backlog", "assigned", "taken", "running", "review", "failed"
            }
        )

    def refresh_cards(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        cards = self.list_cards()
        open_n = self.open_count()
        color = RT["accent_warn"] if open_n else RT["text_dim"]
        self.count_badge.setText(
            f"<span style='color:{color}; font-size:11px; font-weight:600;'>{open_n} açık</span>"
        )
        for card in cards[:12]:
            status = str(spec_field(card, "status", "backlog"))
            title_text = str(spec_field(card, 'title', ''))
            row = QLabel(
                f"<span style='color:{STATUS_COLORS.get(status, RT['text_dim'])}; font-size:{LABEL_PX}px;'>●</span> "
                f"<span style='color:{RT['text_body']}; font-size:{BODY_PX}px;'>"
                f"{title_text}</span> "
                f"<span style='color:{RT['text_dim']}; font-size:{LABEL_PX}px;'>"
                f"{spec_field(card, 'agent', '')} · {STATUS_LABELS.get(status, status)}</span>"
            )
            row.setProperty("role", "label")
            row.setToolTip(
                f"{title_text}\n"
                f"{spec_field(card, 'agent', '')} · {STATUS_LABELS.get(status, status)}"
            )
            self.list_layout.addWidget(row)
        if not cards:
            empty = QLabel(
                f"<span style='color:{RT['text_dim']}; font-size:{BODY_PX}px;'>"
                "Ajan görevi yok. Bir ajana görev verdiğinizde kartlar burada listelenir.</span>"
            )
            empty.setProperty("role", "label")
            self.list_layout.addWidget(empty)
