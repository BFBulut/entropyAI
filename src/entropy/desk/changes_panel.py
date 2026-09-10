"""
Desk "Değişiklikler" bölmesi: seçili kartın worktree'sindeki fark listesi,
renkli birleşik diff ve dal gönderme / taslak PR eylemleri.

Faz 10-C. Ajan katmanı sözleşmeleri (`entropy.agents.worktrees`,
`entropy.agents.pr_flow`) PARALEL yazılıyor; hepsi `getattr`/try-except ile
yüklenir. Sözleşme yoksa panel çöker değil, açıklayıcı bir satırla pasif kalır.

Kurallar:
  * Diff TEMBEL yüklenir: liste kurulurken yalnızca `diff_stat` çağrılır,
    dosya gövdesi ancak satıra tıklanınca (`file_diff`) okunur. 900 dosyalık
    bir worktree'de hepsini önden okumak paneli saniyelerce kilitliyordu.
  * `DIFF_MAX_BYTES` üstü diff kısaltılır; kesildiği açıkça yazılır.
  * "Dalı gönder" ONAY olmadan hiçbir zaman `push_branch` çağırmaz
    (`push_branch(card, confirm=True)` uzak depoya yazar).
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout,
)

from entropy.core.event_bus import bus
from entropy.ui.design import TOKENS
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.agents_widget import spec_field

# Tek dosyalık diff için üst sınır (bayt). Üstü kesilir: 12 MB'lik bir üretim
# dosyası farkı QPlainTextEdit'i dakikalarca meşgul ediyordu.
DIFF_MAX_BYTES = 200 * 1024

# Diff satır renkleri — Faz 11-E adım 6: `viz.*` belirteç ailesi (tek kaynak).
COLOR_ADD = TOKENS["viz"]["add"]
COLOR_DEL = TOKENS["viz"]["del"]
COLOR_HUNK = TOKENS["viz"]["hunk"]
COLOR_META = TOKENS["viz"]["meta"]


def _module(name: str) -> Optional[Any]:
    """`entropy.agents.<name>`; yoksa None (sözleşme henüz yazılmamış olabilir)."""
    try:
        return importlib.import_module(f"entropy.agents.{name}")
    except Exception:
        return None


def worktree_of(card: Any) -> str:
    """Kartın worktree yolu (`worktree` alanı); yoksa boş."""
    if card is None:
        return ""
    return str(spec_field(card, "worktree", "") or "")


def branch_of(card: Any) -> str:
    return str(spec_field(card, "branch", "") or "") if card is not None else ""


def pr_url_of(card: Any) -> str:
    return str(spec_field(card, "pr_url", "") or "") if card is not None else ""


def diff_stat(path: str) -> List[Dict[str, Any]]:
    """`worktrees.diff_stat(path)` guard'lı; sözleşme yoksa boş liste."""
    mod = _module("worktrees")
    fn = getattr(mod, "diff_stat", None) if mod else None
    if fn is None or not path:
        return []
    try:
        return [dict(row) for row in (fn(path) or [])]
    except Exception:
        return []


def file_diff(path: str, file_name: str) -> str:
    """`worktrees.file_diff(path, file)` guard'lı; sözleşme yoksa boş metin."""
    mod = _module("worktrees")
    fn = getattr(mod, "file_diff", None) if mod else None
    if fn is None or not path or not file_name:
        return ""
    try:
        return str(fn(path, file_name) or "")
    except Exception as exc:
        return f"# diff okunamadı: {exc}"


def truncate_diff(text: str, limit: int = DIFF_MAX_BYTES) -> str:
    """200 KB üstü diff kesilir; kullanıcı kesildiğini görsün diye not düşülür."""
    raw = str(text or "")
    if len(raw.encode("utf-8", errors="ignore")) <= limit:
        return raw
    cut = raw.encode("utf-8", errors="ignore")[:limit].decode("utf-8", errors="ignore")
    return cut + (
        f"\n\n… fark {limit // 1024} KB sınırında kesildi; "
        "tamamı için worktree'yi kendi düzenleyicinizde açın."
    )


def prepare_review(card: Any) -> Dict[str, Any]:
    """
    `pr_flow.prepare_review(card)` guard'lı okuma.

    Sözleşme: {branch, worktree, files, file_count, added, removed, summary,
    pr_url}. Push'a hiç dokunmaz, uzak depoya YAZMAZ; yalnızca özet okur.
    Sözleşme yoksa boş sözlük döner ve başlıkta özet gösterilmez.
    """
    mod = _module("pr_flow")
    fn = getattr(mod, "prepare_review", None) if mod else None
    if fn is None or card is None:
        return {}
    try:
        return dict(fn(card) or {})
    except Exception:
        return {}


def review_headline(review: Dict[str, Any]) -> str:
    """
    Özetin başlık metni: "N dosya · +A −S · <dal>".

    Makbuzdaki `## Değişiklikler` bölümü (`pr_flow.changes_section`) AYNI
    sözlükten üretilir; sayılar burada yeniden hesaplanmaz ki iki yüzey
    birbirini tutsun.
    """
    if not review:
        return ""
    try:
        count = int(review.get("file_count") or len(review.get("files") or []))
    except (TypeError, ValueError):
        count = 0
    try:
        added = int(review.get("added") or 0)
        removed = int(review.get("removed") or 0)
    except (TypeError, ValueError):
        added = removed = 0
    bits = [f"{count} dosya", f"+{added} −{removed}"]
    branch = str(review.get("branch") or "")
    if branch:
        bits.append(branch)
    return " · ".join(bits)


class DiffHighlighter(QSyntaxHighlighter):
    """Birleşik diff vurgusu: + yeşil, − kırmızı, @@ mavi, künye satırları gri."""

    def __init__(self, document):
        super().__init__(document)
        self._fmt: Dict[str, QTextCharFormat] = {}
        for key, color in (("add", COLOR_ADD), ("del", COLOR_DEL),
                           ("hunk", COLOR_HUNK), ("meta", COLOR_META)):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if key == "hunk":
                fmt.setFontWeight(QFont.Weight.Bold)
            self._fmt[key] = fmt

    def kind_for(self, line: str) -> str:
        if line.startswith("@@"):
            return "hunk"
        if line.startswith(("+++", "---", "diff ", "index ", "new file", "deleted file")):
            return "meta"
        if line.startswith("+"):
            return "add"
        if line.startswith("-"):
            return "del"
        return ""

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt adı)
        kind = self.kind_for(text or "")
        if kind:
            self.setFormat(0, len(text), self._fmt[kind])


class ChangesPanel(QFrame):
    """Kartın worktree farkları + dal gönder / taslak PR eylemleri."""

    pushed = Signal(str)   # dal adı (başarılı gönderim)

    def __init__(self, parent=None, card: Any = None, confirm: bool = True):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.card: Any = None
        self._review: Dict[str, Any] = {}
        # Testler onay diyaloğunu açmadan akışı doğrulayabilsin diye:
        # `confirm=False` yalnızca test/otomasyon yolu içindir.
        self.confirm = confirm
        self._files: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(6)
        self.branch_label = QLabel("")
        self.branch_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.branch_label.setOpenExternalLinks(True)
        self.branch_label.setProperty("role", "label")
        head.addWidget(self.branch_label)
        head.addStretch()
        self.push_btn = QPushButton("Dalı gönder (onaylı)")
        self.push_btn.setAccessibleName("Dalı gönder (onaylı)")
        self.push_btn.setToolTip("Kartın dalını uzak depoya gönderir; önce onay sorar.")
        self.push_btn.clicked.connect(self._on_push)
        head.addWidget(self.push_btn)
        self.pr_btn = QPushButton("Taslak PR aç")
        self.pr_btn.setAccessibleName("Taslak PR aç")
        self.pr_btn.setToolTip("Dal için taslak PR açar (gh gerekir).")
        self.pr_btn.clicked.connect(self._on_draft_pr)
        head.addWidget(self.pr_btn)
        layout.addLayout(head)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setProperty("role", "label")
        layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.file_list = QListWidget()
        self.file_list.setMinimumWidth(160)
        # Qt varsayılanı beyaz zemindir; okuma temasında liste diff görünümüyle
        # aynı yüzeyde durmalı (offscreen görüntüde beyaz sütun olarak çıkıyordu).
        self.file_list.currentItemChanged.connect(self._on_file_changed)
        splitter.addWidget(self.file_list)

        self.diff_view = QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setProperty("role", "terminal")
        self.diff_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.highlighter = DiffHighlighter(self.diff_view.document())
        splitter.addWidget(self.diff_view)
        splitter.setSizes([220, 520])
        layout.addWidget(splitter, 1)

        self.set_card(card)

    # ------------------------------------------------------------ durum

    def set_card(self, card: Any) -> None:
        self.card = card
        self._files = []
        self.file_list.clear()
        self.diff_view.setPlainText("")
        path = worktree_of(card)
        branch = branch_of(card)
        pr_url = pr_url_of(card)

        self._review = prepare_review(card)
        if not pr_url:
            pr_url = str(self._review.get("pr_url") or "")
        bits = []
        if branch:
            bits.append(f"<b style='color:{RT['text']};'>{branch}</b>")
        headline = review_headline(self._review)
        if headline:
            bits.append(
                f"<span style='color:{RT['text_dim']}; font-size:11px;'>{headline}</span>"
            )
        if pr_url:
            bits.append(f"<a href='{pr_url}' style='color:{RT['accent']};'>PR</a>")
        self.branch_label.setText(
            " · ".join(bits) if bits else f"<span style='color:{RT['text_dim']};'>dal yok</span>"
        )

        has_worktree = bool(path)
        self.push_btn.setEnabled(bool(branch) and self._pr_flow_fn("push_branch") is not None)
        self.pr_btn.setEnabled(bool(branch) and self.gh_available()
                               and self._pr_flow_fn("create_draft_pr") is not None)
        self.pr_btn.setVisible(self.gh_available())

        if card is None:
            self.status_label.setText("Bir görev kartı seçin.")
            return
        if not has_worktree:
            self.status_label.setText(
                "Bu kart worktree kullanmıyor; değişiklik listesi yok."
            )
            return
        if _module("worktrees") is None:
            self.status_label.setText(
                "Fark sözleşmesi (entropy.agents.worktrees) bulunamadı; liste boş."
            )
            return
        self.refresh()

    def refresh(self) -> None:
        """Fark listesini yeniler (tembel: gövdeler okunmaz)."""
        path = worktree_of(self.card)
        if not path:
            return
        self._files = diff_stat(path)
        self.file_list.clear()
        added = sum(int(f.get("added", 0) or 0) for f in self._files)
        deleted = sum(int(f.get("deleted", 0) or 0) for f in self._files)
        for row in self._files:
            name = str(row.get("file", ""))
            status = str(row.get("status", ""))
            item = QListWidgetItem(
                f"{status or '·'} {name}  +{row.get('added', 0)} −{row.get('deleted', 0)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setToolTip(name)
            self.file_list.addItem(item)
        if not self._files:
            self.status_label.setText("Worktree'de değişiklik yok.")
        else:
            self.status_label.setText(
                f"{len(self._files)} dosya · +{added} −{deleted} · {path}"
            )

    def review(self) -> Dict[str, Any]:
        """Son okunan `prepare_review` özeti (test/makbuz karşılaştırması)."""
        return dict(self._review)

    def header_text(self) -> str:
        return self.branch_label.text()

    def file_names(self) -> List[str]:
        return [str(f.get("file", "")) for f in self._files]

    # ------------------------------------------------------------ diff

    @Slot(object, object)
    def _on_file_changed(self, current, _previous=None) -> None:
        if current is None:
            return
        self.show_file(str(current.data(Qt.ItemDataRole.UserRole) or ""))

    def show_file(self, file_name: str) -> str:
        """Dosyanın diff'ini tembel okur, kısaltır ve panele basar."""
        if not file_name:
            return ""
        text = truncate_diff(file_diff(worktree_of(self.card), file_name))
        if not text:
            text = f"# {file_name}: fark üretilemedi (sözleşme yok ya da dosya değişmemiş)."
        self.diff_view.setPlainText(text)
        return text

    def diff_text(self) -> str:
        return self.diff_view.toPlainText()

    # ------------------------------------------------------------ pr akışı

    @staticmethod
    def _pr_flow_fn(name: str) -> Optional[Any]:
        mod = _module("pr_flow")
        return getattr(mod, name, None) if mod else None

    def gh_available(self) -> bool:
        fn = self._pr_flow_fn("gh_available")
        if fn is None:
            return False
        try:
            return bool(fn())
        except Exception:
            return False

    def push_branch(self, confirm: Optional[bool] = None) -> Dict[str, Any]:
        """
        Dalı gönderir. ONAY zorunludur: `confirm` False ise (ya da kullanıcı
        diyalogda vazgeçerse) `push_branch` HİÇ çağrılmaz.
        """
        need_confirm = self.confirm if confirm is None else confirm
        branch = branch_of(self.card)
        if not branch:
            return {"ok": False, "reason": "dal yok"}
        fn = self._pr_flow_fn("push_branch")
        if fn is None:
            self.status_label.setText("Gönderme sözleşmesi (pr_flow) bulunamadı.")
            return {"ok": False, "reason": "sözleşme yok"}
        if need_confirm:
            answer = QMessageBox.question(
                self,
                "Dalı gönder",
                f"“{branch}” dalı uzak depoya gönderilsin mi?\n"
                "Bu işlem uzak depoya YAZAR.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.status_label.setText("Gönderme iptal edildi.")
                return {"ok": False, "reason": "iptal"}
        try:
            result = dict(fn(self.card, confirm=True) or {})
        except Exception as exc:
            self.status_label.setText(f"Gönderilemedi: {exc}")
            return {"ok": False, "reason": str(exc)}
        self.status_label.setText(
            f"Dal gönderildi: {branch}" if result.get("ok", True) else str(result)
        )
        self.pushed.emit(branch)
        return result

    @Slot()
    def _on_push(self) -> None:
        self.push_branch()

    def create_draft_pr(self) -> Dict[str, Any]:
        fn = self._pr_flow_fn("create_draft_pr")
        if fn is None or self.card is None:
            self.status_label.setText("Taslak PR sözleşmesi bulunamadı.")
            return {"ok": False}
        try:
            result = dict(fn(self.card) or {})
        except Exception as exc:
            self.status_label.setText(f"PR açılamadı: {exc}")
            return {"ok": False, "reason": str(exc)}
        url = str(result.get("url") or result.get("pr_url") or "")
        if url:
            self.branch_label.setText(
                f"<b style='color:{RT['text']};'>{branch_of(self.card)}</b>"
                f" · <a href='{url}' style='color:{RT['accent']};'>PR</a>"
            )
            self.status_label.setText(f"Taslak PR: {url}")
        bus.terminal_output_received.emit(f"[Değişiklikler] Taslak PR: {url or result}\n")
        return result

    @Slot()
    def _on_draft_pr(self) -> None:
        self.create_draft_pr()
