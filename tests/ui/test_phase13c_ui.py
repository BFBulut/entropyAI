"""Faz 13-C — arayüz kapanış dilimi (altı madde, altı kök neden).

1. Desk yapı değişiklikleri sohbette kuyruğa giriyordu ama arayüzde onay
   yüzeyi yoktu (kullanıcı `/desk approve <id>` yazmak zorundaydı).
2. "Sil" gerçekten siliyordu: kartın `.md` dosyası olay yazılmadan kayboluyor,
   pano onu projeksiyondan göstermeye devam ediyordu (R-13A2-1).
3. Dar pencerede kaydedilmiş bölücü konumu detay panelini büyük tutup panoyu
   taşırıyordu; kart önizlemesi üçüncü satırı ortadan KESİYORDU.
4. Eski raporların frontmatter `title` alanı yazma zamanında kırpılmıştı;
   kart başlığı yarım sözcükle bitiyordu.
5. `ui_audit` kapanışında `RuntimeError: EntropyEventBus already deleted`
   traceback'i düşüyordu (işçi iş parçacığı silinmiş C++ nesnesine dokunuyordu).
6. `ui_audit` Desk penceresini hiç taramıyordu.

Hepsi offscreen koşar; gerçek kasaya YAZILMAZ (sahte API / tmp yol).
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QAbstractButton, QPushButton

from entropy.ui.widgets import report_center as rc
from entropy.ui.widgets import task_board_widget as tbw
from entropy.ui.widgets.desk_approvals_panel import DeskApprovalsPanel


# --------------------------------------------------------------- 1) Desk onayları

class FakeDeskAdmin:
    """`entropy.agents.desk_admin` sözleşmesinin sahtesi (disk yok)."""

    def __init__(self, records=None, ok: bool = True):
        self.records = list(records if records is not None else [{
            "id": "req-1", "kind": "office",
            "payload": {"name": "arastirma", "purpose": "kaynak taraması"},
            "created_at": "2026-09-11T10:00:00", "source": "chat",
            "summary": "Yeni ofis: arastirma",
        }])
        self.ok = ok
        self.applied: list = []
        self.rejected: list = []

    def list_pending(self):
        return list(self.records)

    def apply_pending(self, request_id):
        self.applied.append(request_id)
        if not self.ok:
            return {"ok": False, "message": "Uygulanamadı", "created_paths": []}
        self.records = [r for r in self.records if r["id"] != request_id]
        return {"ok": True, "message": "Ofis açıldı", "created_paths": ["/x/ofis"]}

    def reject_pending(self, request_id, reason=""):
        self.rejected.append((request_id, reason))
        self.records = [r for r in self.records if r["id"] != request_id]
        return True


def _buttons(panel, label: str):
    return [b for b in panel.findChildren(QPushButton) if b.text() == label]


def test_desk_approvals_panel_lists_and_applies(qapp):
    api = FakeDeskAdmin()
    panel = DeskApprovalsPanel(api=api)
    assert panel.pending_count() == 1
    approve = _buttons(panel, "Onayla")
    reject = _buttons(panel, "Reddet")
    assert approve and reject
    # G13: birincil/hayalet ayrımı ve erişilebilir ad (WCAG 4.1.2).
    assert approve[0].property("variant") == "primary"
    assert reject[0].property("variant") == "ghost"
    assert approve[0].accessibleName() and reject[0].accessibleName()

    decided: list = []
    panel.request_decided.connect(lambda rid, ok: decided.append((rid, ok)))
    approve[0].click()
    assert api.applied == ["req-1"]
    assert decided == [("req-1", True)]
    assert panel.pending_count() == 0          # onay sonrası liste tazelendi
    assert "Ofis açıldı" in panel.last_message()
    panel.deleteLater()


def test_desk_approvals_reject_removes_without_creating(qapp):
    api = FakeDeskAdmin()
    panel = DeskApprovalsPanel(api=api)
    _buttons(panel, "Reddet")[0].click()
    assert api.applied == []                   # hiçbir yapı oluşmadı
    assert api.rejected and api.rejected[0][0] == "req-1"
    assert panel.pending_count() == 0
    panel.deleteLater()


def test_desk_approvals_failed_apply_keeps_request(qapp):
    api = FakeDeskAdmin(ok=False)
    panel = DeskApprovalsPanel(api=api)
    assert panel.approve("req-1") is False
    assert panel.pending_count() == 1          # başarısız uygulama kuyrukta kalır
    panel.deleteLater()


def test_desk_approvals_panel_survives_missing_module(qapp):
    class NoApi:
        pass

    panel = DeskApprovalsPanel(api=NoApi())
    assert panel.pending() == []
    assert panel.approve("x") is False and panel.reject("x") is False
    panel.deleteLater()


def test_zen_chat_receipt_is_wired_to_panel():
    """Sohbet makbuzunun ön eki ile `desk_admin`in yazdığı satır aynı olmalı."""
    from entropy.agents import desk_admin
    from entropy.ui.modes.zen_mode import ZenModeWindow

    source = desk_admin.consume_desk_calls.__doc__ or ""
    assert ZenModeWindow.DESK_APPROVAL_RECEIPT == "Desk düzenleme onayı bekliyor"
    # Sözleşme metni gerçekten o satırı üretiyor mu (kaynakta ara).
    import inspect

    assert ZenModeWindow.DESK_APPROVAL_RECEIPT in inspect.getsource(desk_admin)
    assert source is not None
    assert callable(ZenModeWindow.open_desk_approvals)
    assert callable(ZenModeWindow.show_desk_approval_prompt)


# --------------------------------------------------------------- 2) "Sil" = arşiv

def test_delete_card_calls_archive_contract(qapp, monkeypatch):
    calls: list = []

    class FakeBoard:
        def list(self, **_kw):
            return []

        def archive_card(self, card_id, reason=""):
            calls.append((card_id, reason))
            return {"ok": True, "archived_to": "/kasa/_archive/k1.md"}

    board = tbw.TaskBoardWidget(board=FakeBoard())
    monkeypatch.setattr(board, "refresh_cards", lambda: None)
    assert board.delete_card("k1", confirm=False) is True
    assert calls == [("k1", "kullanıcı arşivledi")]
    board.deleteLater()


def test_delete_card_without_contract_does_nothing(qapp):
    """Pano `archive_card` bilmiyorsa arayüz HİÇBİR ŞEY silmez."""

    class OldBoard:
        def __init__(self):
            self.deleted: list = []

        def list(self, **_kw):
            return []

        def delete(self, card_id):
            self.deleted.append(card_id)

    old = OldBoard()
    board = tbw.TaskBoardWidget(board=old)
    assert board.delete_card("k1", confirm=False) is False
    assert old.deleted == []                   # eski silme yolu çağrılmadı
    board.deleteLater()


def test_ui_has_no_direct_file_delete_path():
    """Arayüzde doğrudan silme YOLU kalmadı: `board.delete(` çağrısı yok."""
    from pathlib import Path

    source = Path(tbw.__file__).read_text(encoding="utf-8")
    assert "self.board.delete(" not in source
    assert "Arşivle" in source


def test_archive_button_is_disabled_without_contract(qapp, monkeypatch):
    monkeypatch.setattr(tbw, "archive_card_api", lambda: None)
    board = tbw.TaskBoardWidget()
    board.board = None
    panel = tbw.TaskDetailPanel(board)
    assert panel.delete_btn.isEnabled() is False
    assert panel.delete_btn.accessibleName()
    panel.deleteLater()


def test_report_note_is_archived_not_unlinked(qapp, tmp_path):
    """Hafıza gözlemcisindeki "Notu arşivle" dosyayı SİLMEZ, taşır."""
    from entropy.ui.widgets.memory_inspector_dialog import MemoryInspectorDialog

    note = tmp_path / "not.md"
    note.write_text("# Not\n", encoding="utf-8")
    dialog = MemoryInspectorDialog.__new__(MemoryInspectorDialog)
    target = MemoryInspectorDialog.archive_report_file(dialog, note)
    assert not note.exists()
    assert target.exists() and target.parent.name == "_archive"
    assert target.read_text(encoding="utf-8") == "# Not\n"


def test_ui_has_no_report_unlink_call():
    from pathlib import Path

    from entropy.ui.widgets import memory_inspector_dialog as mid

    source = Path(mid.__file__).read_text(encoding="utf-8")
    assert ".unlink(" not in source


# --------------------------------------------------------------- 3) dar pencere

def test_detail_panel_shrinks_before_board_overflows(qapp):
    board = tbw.TaskBoardWidget()
    board.resize(1200, 700)
    board.show()
    qapp.processEvents()
    if board.view_mode() != "kanban":
        pytest.skip("1200 px'te liste kipi seçildi; taşma sorusu doğmuyor")
    splitter = board.board_splitter
    splitter.setSizes([758, 442])              # kullanıcının bildirdiği durum
    qapp.processEvents()
    board.fit_detail_panel(board.width())
    detail = splitter.sizes()[1]
    allowed = board.detail_max_width(board.width())
    assert detail <= allowed
    assert sum(splitter.sizes()) - detail >= board.board_area_min_width() - 2 * tbw.BOARD_MARGIN
    assert detail >= tbw.DETAIL_MIN_WIDTH      # asgarinin ALTINA da inmez
    board.deleteLater()


def test_detail_panel_untouched_when_there_is_room(qapp):
    board = tbw.TaskBoardWidget()
    board.resize(1920, 900)
    board.apply_view_mode(1920)
    splitter = board.board_splitter
    splitter.setSizes([1500, 400])
    board.fit_detail_panel(1920)
    assert splitter.sizes()[1] == 400          # geniş ekranda tercih korunur
    board.deleteLater()


def test_preview_is_elided_with_ellipsis(qapp):
    long_text = " ".join(f"sozcuk{i:02d}" for i in range(80))
    label = tbw.ElidedPreviewLabel(long_text, "#ffffff")
    label.resize(240, 60)
    qapp.processEvents()
    shown = label.elided_text()
    assert shown.endswith("…")
    assert len(shown) < len(long_text)
    assert label.toolTip() == long_text        # tam metin kaybolmaz
    label.deleteLater()


def test_short_preview_is_not_elided(qapp):
    label = tbw.ElidedPreviewLabel("kısa özet", "#ffffff")
    label.resize(400, 60)
    qapp.processEvents()
    assert label.elided_text() == "kısa özet"
    label.deleteLater()


# --------------------------------------------------------------- 4) kırpık başlık

def test_truncated_frontmatter_title_loses_to_h1():
    front = "Entropy Agent Desk Uygulamasının Tekrar A"
    body = "# Entropy Agent Desk Uygulamasının Tekrar Analizi\n\nGövde.\n"
    assert rc.title_looks_truncated(front, "Entropy Agent Desk Uygulamasının Tekrar Analizi")
    assert rc.derive_report_title(front, body, "rapor.md") == \
        "Entropy Agent Desk Uygulamasının Tekrar Analizi"


def test_long_h1_is_cut_at_a_natural_boundary():
    front = "2026 İleri Otonom Ajan Mimarileri: Erlang/OTP Supervision Trees,"
    h1 = (front + " Bi-Temporal Graphiti Memory, SEP-1865 MCP Apps ve Token "
          "Fiziği (Faz 93)")
    title = rc.derive_report_title(front, f"# {h1}\n\nGövde.\n", "rapor.md")
    assert not title.endswith(",")
    assert len(title) <= rc.TITLE_MAX_CHARS
    assert title.startswith("2026 İleri Otonom Ajan Mimarileri")
    # Yarım sözcük üretilmez: her sözcük H1'de aynen geçmeli.
    assert all(word in h1 for word in title.split())


def test_plausible_short_title_is_kept():
    front = "Kısa ve doğru başlık"
    body = "# Kısa ve doğru başlık genişletilmiş sürüm\n"
    assert rc.title_looks_truncated(front, "Kısa ve doğru başlık genişletilmiş") is False
    assert rc.derive_report_title(front, body, "x.md") == front


def test_truncation_rule_needs_an_h1():
    front = "Entropy Agent Desk Uygulamasının Tekrar A"
    assert rc.title_looks_truncated(front, "") is False
    assert rc.derive_report_title(front, "Gövde, başlık yok.\n", "x.md") == front


# --------------------------------------------------------------- 5) yıkım sırası

def test_graph_job_skips_deleted_objects(qapp):
    """Silinmiş widget/olay yolu ile iş parçacığı sessizce çıkar (traceback yok)."""
    from entropy.ui.widgets import knowledge_graph as kg

    class Dead:
        pass

    assert kg._qt_alive(None) in (False, True)  # koruma çağrılabilir olmalı

    from PySide6.QtWidgets import QLabel

    victim = QLabel()
    import shiboken6

    shiboken6.delete(victim)
    assert kg._qt_alive(victim) is False


def test_apply_async_graph_on_deleted_widget_is_silent(qapp):
    from entropy.ui.widgets import knowledge_graph as kg

    calls: list = []

    class Fake:
        _graph_job_running = True

        def _apply_async_graph(self, data):
            return kg.KnowledgeGraphWidget._apply_async_graph(self, data)

    monkey = Fake()
    # `_qt_alive` False dediğinde hiçbir alan okunmaz/yazılmaz.
    original = kg._qt_alive
    kg._qt_alive = lambda obj: False
    try:
        assert monkey._apply_async_graph({"nodes": []}) is None
        assert monkey._graph_job_running is True   # dokunulmadı
        assert calls == []
    finally:
        kg._qt_alive = original


# --------------------------------------------------------------- 6) Desk denetimi

def test_ui_audit_exposes_desk_gates():
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "ui_audit_p13c", root / "scripts" / "ui_audit.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.FINAL_GATES_13C_DESK) == {
        "desk_empty_interactive_count", "desk_unnamed_icon_buttons",
        "desk_ghost_button_contrast", "desk_button_contrast",
        "desk_min_width_declaration_failures",
    }
    assert all(limit == 0 for limit in module.FINAL_GATES_13C_DESK.values())
    assert callable(module.desk_live_metrics)


def test_desk_scroll_hosts_declare_their_computed_minimum(qapp):
    """G13-4: kaydırma kabuğu artık `0` beyan etmiyor (beyan >= hesaplanan)."""
    from PySide6.QtWidgets import QLabel

    from entropy.desk.window import scroll_host

    inner = QLabel("x" * 200)
    host = scroll_host(inner)
    assert host.minimumWidth() >= host.minimumSizeHint().width()
    host.deleteLater()


def test_desk_button_token_pair_is_single_source():
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "ui_audit_p13c_2", root / "scripts" / "ui_audit.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    btn = QPushButton("x")
    btn.setProperty("variant", "primary")
    fg, bg = module.button_token_pair(btn)
    assert fg and bg and fg != bg
    btn.deleteLater()
    assert issubclass(QPushButton, QAbstractButton)
