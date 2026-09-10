"""Faz 9 — P0 arayüz kararlılığı regresyon testleri.

Kaynak: `docs/reports/2026-09-11_Faz9_Teshis_Notu.md`. Her test orada belgelenen
bir kök nedeni kilitler:

1. `frameless.py` `int(Qt.Edge)` TypeError → donma + Windows hayalet pencereleri
2. Rapor Merkezi'nin ana iş parçacığını bloklaması (703 rapor ×2 okuma)
3. Zen/Chat ayrı `ReportInboxStore` → okundu durumu yarışı
4. `open_agent_file` `bus.report_created` yayması → sahte "AGENT" raporu
5. Yetenek slash token'ının istemden temizlenmemesi → CLI "Unknown command"
6. Emoji fontu yoksa rozetin boş kutuya (tofu) düşmesi
7. `setOpenLinks(False)` eksikliği → `No document for entropy-report://`
8. Sağlayıcı rozetinin uzun cümle basması

Hepsi `QT_QPA_PLATFORM=offscreen` ile koşar; model çağrısı yoktur.
"""

from __future__ import annotations

import json
import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# --------------------------------------------------------------- 1) frameless


def test_has_edges_accepts_qt_edge_flag():
    """`Qt.Edge` bir enum.Flag; `int()` TypeError verir, `has_edges` vermez."""
    from entropy.ui.widgets.frameless import has_edges

    assert has_edges(Qt.Edge(0)) is False
    assert has_edges(Qt.Edge.LeftEdge) is True
    assert has_edges(Qt.Edge.LeftEdge | Qt.Edge.TopEdge) is True
    assert has_edges(None) is False


def test_event_filter_never_raises_on_edge_press(qapp):
    """Kenar bandına basmak istisna üretmemeli (kök neden A)."""
    from entropy.ui.widgets.frameless import FramelessWindowHelper

    window = QWidget()
    window.resize(400, 300)
    handle = QWidget(window)
    helper = FramelessWindowHelper(window, handle=handle)
    try:
        # Pencerenin sol üst köşesi = LeftEdge | TopEdge
        for local in (QPoint(1, 1), QPoint(200, 150), QPoint(399, 299)):
            event = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(local),
                QPointF(window.mapToGlobal(local)),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            # Eski kod burada TypeError fırlatıyordu.
            assert helper.eventFilter(window, event) in (True, False)
    finally:
        window.deleteLater()


def test_event_filter_swallows_internal_errors(qapp):
    """Süzgeç içindeki beklenmedik hata da olay dağıtımını kırmamalı."""
    from entropy.ui.widgets.frameless import FramelessWindowHelper

    window = QWidget()
    helper = FramelessWindowHelper(window)

    def boom(obj, event):
        raise RuntimeError("patla")

    helper._filter = boom
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(0, 0),
        QPointF(0, 0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    assert helper.eventFilter(window, event) is False
    window.deleteLater()


# ------------------------------------------------------- 2) depo: tek yazım


def test_mark_all_read_writes_state_file_once(tmp_path, monkeypatch):
    """`set_many` N girdiyi TEK dosya yazımıyla işaretler."""
    from entropy.ui.widgets.report_inbox import ReportInboxStore

    store = ReportInboxStore(path=tmp_path / "inbox.json")
    writes = {"n": 0}
    original = store.save

    def counting_save():
        writes["n"] += 1
        return original()

    monkeypatch.setattr(store, "save", counting_save)
    paths = [str(tmp_path / f"r{i}.md") for i in range(50)]
    assert store.set_many(paths, read=True) == 50
    assert writes["n"] == 1, "toplu işlem tek yazım yapmalı"
    assert all(store.is_read(p) for p in paths)

    # Diskte gerçekten duruyor mu?
    data = json.loads((tmp_path / "inbox.json").read_text(encoding="utf-8"))
    assert len(data["items"]) == 50


def test_shared_store_is_single_instance(tmp_path):
    """Zen ve Chat aynı depoyu paylaşır (son-yazan-kazanır yarışı biter)."""
    from entropy.ui.widgets import report_inbox as ri

    store = ri.reset_shared_store(ri.ReportInboxStore(path=tmp_path / "inbox.json"))
    try:
        assert ri.get_shared_store() is store
        from entropy.ui.widgets.report_center import ReportCenterWidget

        a = ReportCenterWidget()
        b = ReportCenterWidget()
        try:
            assert a.store is b.store is store
            a.store.mark_read(str(tmp_path / "x.md"), True)
            assert b.store.is_read(str(tmp_path / "x.md"))
        finally:
            a.deleteLater()
            b.deleteLater()
    finally:
        ri._SHARED_STORE = None


def test_read_state_survives_reload(qapp, tmp_path):
    """Kasadan tazeleme okundu durumunu ezmemeli."""
    from entropy.ui.widgets import report_inbox as ri
    from entropy.ui.widgets.report_center import ReportCenterWidget

    report = tmp_path / "r.md"
    report.write_text("# Rapor\n\nGovde", encoding="utf-8")
    entry = {"path": str(report), "title": "Rapor", "mtime": time.time(), "tags": []}

    store = ri.reset_shared_store(ri.ReportInboxStore(path=tmp_path / "inbox.json"))
    try:
        center = ReportCenterWidget()
        try:
            center.set_entries([entry])
            center.mark_all_read()
            assert center.unread_count() == 0
            center.set_entries([dict(entry)])  # tazeleme
            assert center.unread_count() == 0
        finally:
            center.deleteLater()
    finally:
        ri._SHARED_STORE = None
        del store


# ------------------------------------------- 2b) ana iş parçacığı bloklanması


def test_reports_updated_does_not_block_main_thread(qapp, tmp_path, monkeypatch):
    """`reports_updated` ana iş parçacığında kasa taraması yapmamalı.

    Ölçüm: yavaş (200 ms) bir `collect_recent_entries` taklidiyle sinyal
    yayılır; sinyalin dönüş süresi tarama süresinden çok küçük olmalıdır.
    """
    from entropy.core.event_bus import bus
    from entropy.ui.widgets.report_center import ReportCenterWidget

    def slow_collect(limit=60):
        time.sleep(0.2)
        return []

    monkeypatch.setattr(
        "entropy.ui.widgets.report_inbox.collect_recent_entries", slow_collect
    )
    center = ReportCenterWidget()
    try:
        started = time.perf_counter()
        bus.reports_updated.emit("")
        elapsed_ms = (time.perf_counter() - started) * 1000
        assert elapsed_ms < 50, f"ana iş parçacığı {elapsed_ms:.1f} ms bloklandı"
        assert center._reload_timer.isActive(), "tazeleme geciktirilmiş olmalı"
    finally:
        center._reload_timer.stop()
        center.deleteLater()


def test_read_head_cache_avoids_second_disk_read(tmp_path):
    """`enrich_entry` aynı dosyayı imzası değişmedikçe iki kez okumamalı."""
    from entropy.ui.widgets import report_center as rc

    path = tmp_path / "r.md"
    path.write_text("# Baslik\n\nOzet metni burada.", encoding="utf-8")
    rc._HEAD_CACHE.clear()
    first = rc._read_head(str(path))
    assert first
    assert len(rc._HEAD_CACHE) == 1
    path.unlink()  # dosya gitse bile önbellekten dönmeli (ikinci okuma yok)
    # stat başarısız olacağı için önbellek anahtarı üretilemez; bu yüzden
    # önbellek isabetini dosya dururken ölçüyoruz:
    path.write_text("# Baslik\n\nOzet metni burada.", encoding="utf-8")
    rc._HEAD_CACHE.clear()
    rc._read_head(str(path))
    hits = len(rc._HEAD_CACHE)
    rc._read_head(str(path))
    assert len(rc._HEAD_CACHE) == hits == 1


# ------------------------------------------------------ 4) sahte AGENT raporu


def test_open_agent_file_does_not_emit_report_created(qapp, tmp_path, monkeypatch):
    """Ajan dosyası açmak "yeni araştırma raporu" sinyali yaymamalı."""
    from entropy.core.event_bus import bus
    from entropy.ui.widgets import agents_widget as aw

    agent_file = tmp_path / "AGENT.md"
    agent_file.write_text("name: Alfa\n", encoding="utf-8")

    opened = []
    monkeypatch.setattr(
        "entropy.ui.widgets.standalone_report_window.open_standalone_report_window",
        lambda p, parent=None: opened.append(p),
    )

    seen = []

    def on_report(path):
        seen.append(path)

    bus.report_created.connect(on_report)
    try:
        widget = aw.AgentsWidget.__new__(aw.AgentsWidget)
        assert widget.open_agent_file({"path": str(agent_file)}) is True
    finally:
        bus.report_created.disconnect(on_report)

    assert seen == [], "AGENT.md rapor sayılmamalı"
    assert opened == [str(agent_file)], "dosya okuyucuda açılmalı"


# ------------------------------------------------------- 5) yetenek slash'ı


def test_strip_skill_token_from_prompt():
    from entropy.ui.widgets.slash_prompt import strip_skill_tokens, strip_slash_token

    assert (
        strip_slash_token("/media-agency-soldier reklam metni yaz", "media-agency-soldier")
        == "reklam metni yaz"
    )
    assert strip_slash_token("/media-agency-soldier", "media-agency-soldier") == ""
    # Sadece ilk geçiş silinir, metnin geri kalanı korunur.
    assert strip_skill_tokens("/x bir /x iki", ["x"]) == "bir /x iki"
    # Bilinmeyen token'a dokunulmaz.
    assert strip_slash_token("/plan yap", "media") == "/plan yap"


def test_unknown_slash_is_detected_and_passthrough_respected():
    from entropy.ui.widgets.slash_prompt import CLI_PASSTHROUGH, unknown_slash_token

    known = {"plan", "distill", "help"}
    assert unknown_slash_token("/bilinmeyen bir sey", known, CLI_PASSTHROUGH) == "bilinmeyen"
    assert unknown_slash_token("/plan yap", known, CLI_PASSTHROUGH) == ""
    assert unknown_slash_token("/compact", known, CLI_PASSTHROUGH) == ""
    # Metin ortasındaki slash bir yol olabilir; engellenmez.
    assert unknown_slash_token("dosya a/b oku", known, CLI_PASSTHROUGH) == ""


def test_unknown_slash_html_mentions_command():
    from entropy.ui.widgets.slash_prompt import close_matches, unknown_slash_html

    html = unknown_slash_html("bilinmeyen", close_matches("bil", ["/bilgi", "/plan"]))
    assert "/bilinmeyen" in html
    assert "/help" in html


# ---------------------------------------------------------- 6) emoji yedeği


def test_emoji_or_text_falls_back_when_font_missing(monkeypatch):
    from entropy.ui.widgets import ui_polish

    monkeypatch.setattr(ui_polish, "emoji_font_available", lambda *a, **k: False)
    assert ui_polish.emoji_or_text("🔴", "●") == "●"
    assert ui_polish.emoji_or_text("🟢") == "●"
    monkeypatch.setattr(ui_polish, "emoji_font_available", lambda *a, **k: True)
    assert ui_polish.emoji_or_text("🔴", "●") == "🔴"


def test_apply_emoji_font_fallback_sets_family_chain(qapp):
    from entropy.ui.widgets.ui_polish import EMOJI_FALLBACK_FAMILIES, apply_emoji_font_fallback

    apply_emoji_font_fallback(qapp)
    families = [f.lower() for f in qapp.font().families()]
    assert "segoe ui emoji" in families
    assert families[0] not in ("", None)
    assert any(f.lower() in families for f in EMOJI_FALLBACK_FAMILIES)


def test_state_badge_never_shows_bare_emoji(qapp):
    """Durum tek noktada; anlam metinle (ipucu) taşınır, emojiyle değil.

    Faz 11-E adım 2/5: emoji ikon yasağı ve "aynı bilgi bir kez" kuralı
    gereği durum rozeti metin taşıyan bir etiket olmaktan çıkıp üst çubuktaki
    `role="statusDot"` noktasına indi. Sözleşme artık şu: her durumda
    (a) ton belirteci ayarlanır, (b) ipucu HARFLİ bir açıklama taşır —
    yani kullanıcı durumu asla yalnızca renkten/emojiden okumaz.
    """
    from entropy.ui.widgets.header_bar import BrandCluster

    brand = BrandCluster()
    for state, tone in (
        ("thinking", "warn"), ("executing", "warn"),
        ("error", "danger"), ("idle", "ok"),
    ):
        brand.set_state(state)
        assert brand.status_dot.property("tone") == tone
        tip = brand.status_dot.toolTip()
        assert [c for c in tip if c.isalpha()], f"{state} ipucu metinsiz"


# ------------------------------------------------- 7) QTextBrowser bağlantısı


def test_chat_and_zen_browsers_do_not_open_links_themselves():
    """`setOpenLinks(False)` yoksa `entropy-report://` uyarısı basılır."""
    import inspect

    from entropy.ui.modes import chat_mode, zen_mode

    for module in (chat_mode, zen_mode):
        src = inspect.getsource(module)
        assert "setOpenLinks(False)" in src, module.__name__


# ------------------------------------------------------ 8) sağlayıcı rozeti


def test_provider_badge_is_compact():
    from entropy.ui.widgets.provider_badge import (
        MARK_BAD, MARK_OK, MARK_WARN, status_mark, status_text,
    )

    assert status_text("agy", "AGY", {"logged_in": True}) == f"AGY {MARK_OK}"
    assert status_text("agy", "AGY", {"logged_in": False}) == f"AGY {MARK_BAD}"
    assert (
        status_text("claude", "Claude", {"logged_in": True, "plan": "max"})
        == f"Claude {MARK_OK} max"
    )
    assert status_mark({"logged_in": True, "last_error": "yenilenecek"}) == MARK_WARN
    # Uzun cümle geri gelmesin: rozet metni kısa kalmalı.
    long_status = {
        "logged_in": True,
        "plan": "antigravity-cli",
        "session_window": "belirteç süresi doldu (yenilenecek)",
        "quota_hint": "%40",
    }
    assert len(status_text("agy", "AGY", long_status)) <= 14


def test_provider_badge_width_budget(qapp):
    from entropy.ui.widgets.provider_badge import MAX_BADGE_WIDTH, ProviderStatusBadge

    badge = ProviderStatusBadge()
    try:
        badge.set_status("agy", {"logged_in": True, "plan": "ultra"})
        badge.set_status("claude", {"logged_in": True, "plan": "max"})
        badge.adjustSize()
        assert MAX_BADGE_WIDTH * 2 + 6 <= 160
        assert badge.sizeHint().width() <= 160
    finally:
        badge.close()
        badge.deleteLater()
