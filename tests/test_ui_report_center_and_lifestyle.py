"""
Faz 5.5 / 5.6 arayüz testleri.

Kapsam:
  * Rapor Merkezi — kümeleme, digest kartı, önem × aciliyet, güven eşiği,
    okundu/pin/arşiv/prune, rozet canlılığı, "Orkestratöre sor" akışı
  * Yaşam tarzı arayüz — komut paleti (bulanık arama), odak modu, zaman
    çizelgesi, bildirim merkezi, sağlayıcı rozeti
  * Graf (5.6) — kontrol şeridi dizgeleri, JS sözdizimi, Node ile zaman/tür/
    önem filtresi ve topluluk açılma mantığı

Hepsi sahte veriyle ve `QT_QPA_PLATFORM=offscreen` altında koşar; ağ, model
çağrısı ve harness başlatma yoktur.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
GRAPH_PY = SRC_ROOT / "entropy" / "ui" / "widgets" / "knowledge_graph.py"


# --------------------------------------------------------------- yardımcılar

def write_report(directory: Path, name: str, title: str, body: str = "",
                 mtime: float | None = None) -> Path:
    path = directory / f"{name}.md"
    path.write_text(
        f"---\ntitle: {title}\n---\n\n{body or 'Bu bir sahte rapor gövdesidir.'}\n",
        encoding="utf-8",
    )
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def meta(path: Path, **extra):
    from entropy.ui.widgets.reports_viewer import read_report_meta

    data = read_report_meta(path)
    data.update(extra)
    return data


# ------------------------------------------------------------ kümeleme

def test_titles_cluster_by_topic():
    """Aynı konudaki başlıklar tek kümede, ilgisiz başlık ayrı kümede toplanır."""
    from entropy.ui.widgets.report_center import cluster_entries

    entries = [
        {"title": "Q3 Finansal Denetim Bölüm 1", "path": "a"},
        {"title": "Q3 Finansal Denetim Bölüm 2", "path": "b"},
        {"title": "Q3 Finansal Denetim Bölüm 3", "path": "c"},
        {"title": "Kedi Maması Pazarlama Kampanyası", "path": "d"},
    ]
    clusters = cluster_entries(entries)
    sizes = sorted(len(c) for c in clusters)
    assert sizes == [1, 3], f"beklenen 3+1 kümeleme, gelen {sizes}"


def test_same_office_card_always_clusters_together():
    """Aynı kartın raporları başlıkları farklı olsa da tek kümede kalır."""
    from entropy.ui.widgets.report_center import cluster_entries

    entries = [
        {"title": "Alfa bulguları", "path": "a", "office": "Finans", "card": "card-1"},
        {"title": "Tamamen başka bir konu", "path": "b", "office": "Finans", "card": "card-1"},
    ]
    clusters = cluster_entries(entries)
    assert len(clusters) == 1


def test_fuzzy_and_cosine_helpers_are_sane():
    from entropy.ui.widgets.report_center import cosine, tfidf_vectors

    vecs = tfidf_vectors(["Finansal Denetim Raporu", "Finansal Denetim Notu", "Kedi Maması"])
    assert cosine(vecs[0], vecs[1]) > cosine(vecs[0], vecs[2])


# ------------------------------------------------------------ digest

def test_digest_card_has_three_findings_and_one_decision(tmp_path):
    """Digest kartı: başlık, sayı, 3 bulgu satırı, 1 karar önerisi."""
    from entropy.ui.widgets.report_center import build_digest, enrich_entry

    members = []
    for i in range(4):
        path = write_report(
            tmp_path, f"rep{i}", f"Denetim Raporu {i}",
            body=f"Bulgu {i}: nakit akışı zayıf. İkinci cümle.\n\n## Öneri\nKarar {i}: bütçeyi kıs.",
        )
        members.append(enrich_entry(meta(path)))
    card = build_digest(members)
    assert card["count"] == 4
    assert len(card["findings"]) == 3, card["findings"]
    assert card["decision"].startswith("Karar"), card["decision"]
    assert "+3" in card["title"]


def test_decision_absent_is_not_invented(tmp_path):
    """Raporda öneri/sonuç başlığı yoksa karar satırı uydurulmaz."""
    from entropy.ui.widgets.report_center import build_digest, enrich_entry

    path = write_report(tmp_path, "plain", "Düz Rapor", body="Sadece bir gözlem cümlesi.")
    card = build_digest([enrich_entry(meta(path))])
    assert card["decision"] == ""


# ---------------------------------------------------- önem × aciliyet

def test_importance_falls_back_to_source_kind():
    """Bellek `importance` alanı yoksa sıra: ofis raporu > query > rapor."""
    from entropy.ui.widgets.report_center import entry_importance

    office = entry_importance({"path": str(Path("V") / "Offices" / "Finans" / "r.md")})
    query = entry_importance({"path": "x.md", "source": "query"})
    report = entry_importance({"path": "y.md", "source": "report"})
    assert office > query > report


def test_importance_prefers_memory_field():
    from entropy.ui.widgets.report_center import entry_importance

    assert entry_importance({"path": "a", "source": "report", "importance": 0.93}) == pytest.approx(0.93)


def test_urgency_reacts_to_blockers_deadline_and_failed_status():
    from entropy.ui.widgets.report_center import entry_urgency

    calm = entry_urgency({"title": "Rutin haftalık özet", "summary": ""})
    blocked = entry_urgency({"title": "Blokaj: veri kaynağı erişilemiyor", "summary": "kritik"})
    failed = entry_urgency({"title": "Rutin", "summary": "", "status": "failed"})
    overdue = entry_urgency({"title": "Rutin", "summary": "", "due": time.time() - 10})
    assert blocked > calm and failed > calm and overdue > calm


def test_urgency_and_importance_labels():
    from entropy.ui.widgets.report_center import importance_label, urgency_label

    assert importance_label(0.9) == "yüksek"
    assert importance_label(0.6) == "orta"
    assert importance_label(0.2) == "düşük"
    assert urgency_label(0.8) == "acil"
    assert urgency_label(0.4) == "yakın"
    assert urgency_label(0.0) == "sakin"


# ------------------------------------------------------------ güven eşiği

def test_low_confidence_cards_come_first_and_routine_goes_quiet(tmp_path):
    """Kusurlu raporlar öne, yüksek güvenli rutin raporlar sessiz bölüme."""
    from entropy.ui.widgets.report_center import build_report_center

    good = write_report(
        tmp_path, "iyi", "Rutin Haftalık Ölçüm",
        body="Her şey normal seyrediyor.\n\n## Sonuç\nDeğişiklik gerekmiyor.",
    )
    bad = write_report(
        tmp_path, "kotu", "Blokaj Raporu",
        body="Görev failed durumunda kaldı; grade: 0.3 ile kapandı.",
    )
    result = build_report_center([meta(good), meta(bad)], quiet_threshold=0.75)
    loud_titles = " ".join(c["title"] for c in result["cards"])
    quiet_titles = " ".join(c["title"] for c in result["quiet"])
    assert "Blokaj" in loud_titles
    assert "Rutin" in quiet_titles
    assert result["total"] == 2


def test_confidence_penalizes_failed_and_low_grade():
    from entropy.ui.widgets.report_center import entry_confidence

    full = entry_confidence({"summary": "var", "decision": "var"})
    failed = entry_confidence({"summary": "var", "decision": "var", "status": "failed"})
    low_grade = entry_confidence({"summary": "var", "decision": "var", "grade": 0.4})
    missing = entry_confidence({"summary": "", "decision": ""})
    assert full == 1.0
    assert failed < full and low_grade < full and missing < full


def test_quiet_threshold_setting_roundtrip(tmp_path):
    """`report_center_quiet_threshold` ayarı diske yazılır ve okunur."""
    from entropy.ui.widgets.report_center import load_quiet_threshold, save_quiet_threshold

    path = tmp_path / "report_center.json"
    assert save_quiet_threshold(0.42, path=path)
    assert load_quiet_threshold(path=path) == pytest.approx(0.42)
    # Bozuk dosyada varsayılana düşülür, çökme olmaz.
    path.write_text("{bozuk", encoding="utf-8")
    assert load_quiet_threshold(path=path) == pytest.approx(0.75)


# ------------------------------------------------------------ widget akışı

@pytest.fixture
def center(qapp, tmp_path, monkeypatch):
    from entropy.ui.widgets import report_center as rc_mod
    from entropy.ui.widgets.report_center import ReportCenterWidget
    from entropy.ui.widgets.report_inbox import ReportInboxStore

    # Yalıtım: widget kurulduğunda `mailbox_entries()` KULLANICININ kasasındaki
    # Entropy posta kutusunu okuyor; okunmamış bir `report` mesajı varsa
    # sayımlar (unread_count) ve kart sırası kayıyordu. Testler kullanıcı
    # durumuna bağlı olmamalı: posta kutusu kaynağı boşa alınır.
    monkeypatch.setattr(rc_mod, "mailbox_entries", lambda *a, **k: [])

    store = ReportInboxStore(path=tmp_path / "inbox.json")
    widget = ReportCenterWidget(store=store)
    yield widget
    widget.close()
    widget.deleteLater()


def test_report_center_read_pin_archive_and_prune(center, tmp_path):
    """Okundu / pin / arşiv / prune uçtan uca çalışır ve depoya yazılır."""
    a = write_report(tmp_path, "a", "Kedi Maması Kampanyası")
    b = write_report(tmp_path, "b", "Nakit Akış Denetimi")
    center.set_entries([meta(a), meta(b)])
    assert center.unread_count() == 2

    # Iki rapor iki ayri kumeye duser; hangisinin once siralandigi mtime
    # esitliginde degisebildigi icin kart secmek yerine ikisi de kullanilir.
    all_cards = center.cards() + center.quiet_cards()
    paths = [m["path"] for c in all_cards for m in c["members"]]
    assert str(a) in paths and str(b) in paths
    center.mark_paths_read(paths)
    assert all(center.store.is_read(p) for p in paths)

    assert center.toggle_pin_paths(paths) is True
    assert all(center.store.is_pinned(p) for p in paths)

    center.archive_paths(paths)
    assert all(center.store.is_archived(p) for p in paths)
    # Arşivlenen küme listeden düşer.
    assert center.cards() == [] and center.quiet_cards() == []

    # prune: dosya silinince durum kaydı da temizlenir.
    a.unlink()
    center.set_entries([meta(b)])
    removed = center.prune_missing()
    assert removed >= 1


def test_report_center_mark_all_and_unread_signal(center, tmp_path):
    """`unread_changed` rozeti besler; 'tümünü okundu' sayacı sıfırlar."""
    received = []
    center.unread_changed.connect(received.append)
    paths = [write_report(tmp_path, f"r{i}", f"Rapor {i}") for i in range(3)]
    center.set_entries([meta(p) for p in paths])
    assert received and received[-1] == 3
    center.mark_all_read()
    assert received[-1] == 0


def test_report_center_open_marks_read_and_emits(center, tmp_path):
    opened = []
    center.report_opened.connect(opened.append)
    path = write_report(tmp_path, "tek", "Tek Rapor")
    center.set_entries([meta(path)])
    card = (center.cards() + center.quiet_cards())[0]
    center.open_card(card)
    assert opened == [str(path)]
    assert center.store.is_read(str(path))


def test_report_center_quiet_section_toggles(center, tmp_path):
    """Sessiz bölüm katlıdır; açılınca kartları listeye katılır."""
    good = write_report(
        tmp_path, "rutin", "Rutin Ölçüm",
        body="Normal.\n\n## Sonuç\nDeğişiklik yok.",
    )
    center.set_entries([meta(good)])
    assert center.quiet_cards(), "yüksek güvenli rapor sessiz bölüme düşmeliydi"
    before = len(center.card_widgets)
    assert center.toggle_quiet() is True
    assert len(center.card_widgets) > before


def test_ask_orchestrator_uses_local_ask_command(center, tmp_path):
    """Kart eylemi `/ask <ofis> ...` tetikler ve yanıtı sinyalle yayar."""
    calls = []
    answers = []

    def fake_handler(office, question):
        calls.append((office, question))
        return f"<b>{office}</b> revizyonu planladı."

    center.ask_handler = fake_handler
    center.orchestrator_answer.connect(lambda o, b: answers.append((o, b)))
    card = {"title": "Nakit Akışı", "office": "Finans", "members": []}
    body = center.ask_about_card(card)
    assert calls and calls[0][0] == "Finans"
    assert "Nakit Akışı" in calls[0][1]
    assert "Finans" in body
    assert answers and answers[0][0] == "Finans"


def test_ask_orchestrator_builds_ask_command_string(monkeypatch):
    """Varsayılan işleyici gerçekten `/ask <ofis> ...` yerel komutunu çağırır."""
    import entropy.core.slash_commands as sc
    from entropy.ui.widgets import report_center

    seen = {}

    def fake_local(prompt, bridge, distiller=None):
        seen["prompt"] = prompt
        return "<b>ofis yanıtı</b>"

    monkeypatch.setattr(sc, "try_handle_local_command", fake_local)
    out = report_center.ask_orchestrator("Finans", "raporu gözden geçir")
    assert seen["prompt"].startswith("/ask Finans ")
    assert "ofis yanıtı" in out


def test_report_center_live_on_reports_updated(center, tmp_path, monkeypatch):
    """`bus.reports_updated` gelince Rapor Merkezi kasadan yeniden okur."""
    from entropy.core.event_bus import bus
    from entropy.ui.widgets import report_center as rc

    path = write_report(tmp_path, "canli", "Canlı Rapor")
    monkeypatch.setattr(rc, "collect_recent_entries", lambda limit=60: [meta(path)], raising=False)
    monkeypatch.setattr(
        "entropy.ui.widgets.report_inbox.collect_recent_entries",
        lambda limit=60: [meta(path)],
    )
    bus.reports_updated.emit("")
    titles = [c["title"] for c in center.cards() + center.quiet_cards()]
    assert any("Canlı" in t for t in titles), titles


def test_mailbox_report_messages_become_entries():
    """Posta kutusu `report` mesajı Rapor Merkezi künyesine çevrilir."""
    from entropy.ui.widgets.report_center import message_to_entry

    class FakeMessage:
        id = "m1"
        task_id = "card-9"
        from_ = "office/Finans"
        to = "entropy"
        role = "agent"
        kind = "report"
        status = "completed"
        created_at = "2026-09-09T10:00:00"
        terminal = True
        parts = [{"type": "text", "content": "Nakit Akış Bulgusu\nAyrıntılar burada."}]

    entry = message_to_entry(FakeMessage())
    assert entry["title"] == "Nakit Akış Bulgusu"
    assert entry["office"] == "Finans"
    assert entry["card"] == "card-9"
    assert entry["source"] == "mailbox"
    assert entry["mtime"] > 0


def test_report_center_readable_with_200_reports(qapp, tmp_path):
    """200 sahte raporda kümeleme okunabilir kalmalı ve hızlı olmalı."""
    from entropy.ui.widgets.report_center import build_report_center

    entries = []
    topics = ["Finansal Denetim", "Pazarlama Kampanyası", "Altyapı İzleme", "Ofis Devri"]
    for i in range(200):
        topic = topics[i % len(topics)]
        path = write_report(
            tmp_path, f"m{i}", f"{topic} Raporu {i}",
            body=f"{topic} için bulgu {i}.\n\n## Öneri\nAdım {i} atılmalı.",
        )
        entries.append(meta(path))
    started = time.perf_counter()
    result = build_report_center(entries, quiet_threshold=0.75)
    elapsed = time.perf_counter() - started
    total_cards = len(result["cards"]) + len(result["quiet"])
    assert result["total"] == 200
    # Okunabilirlik ölçütü: 200 rapor 200 karta dönüşmemeli.
    assert total_cards < 60, f"kümeleme yetersiz: {total_cards} kart"
    assert elapsed < 10.0, f"triyaj çok yavaş: {elapsed:.2f} sn"


# ------------------------------------------------------------ komut paleti

def test_fuzzy_score_ranks_prefix_and_subsequence():
    from entropy.ui.widgets.command_palette import fuzzy_score

    assert fuzzy_score("rap", "Rapor Merkezi") > fuzzy_score("rap", "Bir rapor daha sonra")
    assert fuzzy_score("zzz", "Rapor") < 0
    assert fuzzy_score("", "herhangi") == 0.0


def test_command_palette_filters_all_five_sources(qapp):
    """Palet komut/yetenek/ajan/ofis/rapor girdilerini bulanık arar."""
    from entropy.ui.widgets.command_palette import CommandPalette

    items = [
        {"kind": "command", "label": "/handoff", "subtitle": "aktarım sayfası", "payload": "/handoff"},
        {"kind": "skill", "label": "financial-auditor", "subtitle": "denetim", "payload": "/financial-auditor"},
        {"kind": "agent", "label": "Researcher", "subtitle": "araştırma", "payload": "/agent Researcher"},
        {"kind": "office", "label": "Finans", "subtitle": "mali işler", "payload": "/ask Finans "},
        {"kind": "report", "label": "Nakit Akışı", "subtitle": "rapor", "payload": "C:/r.md"},
    ]
    palette = CommandPalette(items=items)
    try:
        assert len(palette.apply_filter("")) == 5
        assert [i["kind"] for i in palette.apply_filter("finans")] == ["office"]
        assert palette.apply_filter("handof")[0]["label"] == "/handoff"
        assert palette.apply_filter("nakit")[0]["kind"] == "report"
        assert palette.apply_filter("zzzz") == []
    finally:
        palette.deleteLater()


def test_command_palette_activation_emits_selection(qapp):
    from entropy.ui.widgets.command_palette import CommandPalette

    got = []
    items = [{"kind": "report", "label": "Rapor A", "subtitle": "", "payload": "C:/a.md"}]
    palette = CommandPalette(items=items)
    palette.item_activated.connect(lambda k, p, l: got.append((k, p, l)))
    try:
        palette.apply_filter("")
        palette.activate_current()
        assert got == [("report", "C:/a.md", "Rapor A")]
    finally:
        palette.deleteLater()


def test_collect_palette_items_is_guarded():
    """Kaynaklar patlasa bile palet listesi liste döner (açılış reddedilmez)."""
    from entropy.ui.widgets.command_palette import collect_palette_items

    items = collect_palette_items(sources=["command"])
    assert isinstance(items, list)


# ------------------------------------------------------------ odak modu

def test_focus_mode_hides_and_restores_side_panels(qapp):
    from PySide6.QtWidgets import QWidget

    from entropy.ui.widgets.focus_mode import install_focus_mode

    window = QWidget()
    primary = QWidget(window)
    side_a = QWidget(window)
    side_b = QWidget(window)
    window.show()
    try:
        controller = install_focus_mode(window, primary=primary, secondary=[side_a, side_b])
        side_b.setVisible(False)  # kullanıcı bunu zaten kapatmıştı
        assert controller.toggle() is True
        assert not side_a.isVisible() and not side_b.isVisible()
        assert primary.isVisible()
        assert controller.toggle() is False
        # Kullanıcının kapalı bıraktığı panel kapalı kalır.
        assert side_a.isVisible()
        assert not side_b.isVisible()
    finally:
        window.close()
        window.deleteLater()


def test_focus_mode_shortcut_is_ctrl_shift_f():
    from entropy.ui.widgets.focus_mode import FOCUS_SHORTCUT

    assert FOCUS_SHORTCUT == "Ctrl+Shift+F"


# ------------------------------------------------------------ zaman çizelgesi

def test_timeline_keeps_only_today_and_sorts_newest_first():
    from entropy.ui.widgets.timeline_panel import collect_timeline, day_bounds

    now = time.time()
    start, _ = day_bounds(now)
    events = [
        {"kind": "task", "ts": start + 3600, "title": "Sabah görevi"},
        {"kind": "report", "ts": start + 7200, "title": "Öğlen raporu"},
        {"kind": "office", "ts": start - 86400, "title": "Dünkü ofis olayı"},
    ]
    timeline = collect_timeline(now=now, events=events)
    assert [e["title"] for e in timeline] == ["Öğlen raporu", "Sabah görevi"]


def test_timeline_panel_renders_four_event_kinds(qapp):
    from entropy.ui.widgets.timeline_panel import TimelinePanel, day_bounds

    now = time.time()
    start, _ = day_bounds(now)
    events = [
        {"kind": "task", "ts": start + 10, "title": "Görev", "detail": "success", "target": "t1"},
        {"kind": "report", "ts": start + 20, "title": "Rapor", "detail": "", "target": "C:/r.md"},
        {"kind": "handoff", "ts": start + 30, "title": "Handoff 1", "detail": "", "target": "C:/h.md"},
        {"kind": "office", "ts": start + 40, "title": "Ofis mesajı", "detail": "", "target": "m1"},
    ]
    panel = TimelinePanel(events=events, now=now)
    try:
        assert len(panel.events()) == 4
        assert panel.list_widget.count() == 4
        text = " ".join(panel.list_widget.item(i).text() for i in range(4))
        for icon in ("⏰", "📄", "🪢", "🏢"):
            assert icon in text
    finally:
        panel.close()
        panel.deleteLater()


def test_timeline_activation_signals_target(qapp):
    from entropy.ui.widgets.timeline_panel import TimelinePanel, day_bounds

    now = time.time()
    start, _ = day_bounds(now)
    panel = TimelinePanel(
        events=[{"kind": "report", "ts": start + 5, "title": "R", "target": "C:/r.md"}],
        now=now,
    )
    got = []
    panel.event_activated.connect(lambda k, t: got.append((k, t)))
    try:
        panel._on_item_clicked(panel.list_widget.item(0))
        assert got == [("report", "C:/r.md")]
    finally:
        panel.close()
        panel.deleteLater()


# ------------------------------------------------------- bildirim merkezi

def test_notification_log_keeps_last_fifty():
    from entropy.ui.widgets.notification_center import NotificationLog

    log = NotificationLog(limit=50)
    for i in range(60):
        log.add("report", f"R{i}", f"p{i}")
    assert len(log) == 50
    # En yeni başta.
    assert log.items()[0]["title"] == "R59"
    assert all(item["title"] != "R0" for item in log.items())


def test_notification_center_records_bus_events(qapp):
    from entropy.core.event_bus import bus
    from entropy.ui.widgets.notification_center import NotificationCenter

    center = NotificationCenter()
    try:
        bus.report_created.emit(str(Path("C:/vault/Yeni_Rapor.md")))
        bus.task_completed.emit("task-7", False)
        bus.playbook_updated.emit("financial-auditor")
        kinds = [i["kind"] for i in center.log.items()]
        assert "report" in kinds and "task_failed" in kinds and "playbook" in kinds
        assert center.unseen() >= 3
        center.mark_seen()
        assert center.unseen() == 0
    finally:
        center.close()
        center.deleteLater()


def test_notification_click_maps_to_target_kind(qapp):
    from entropy.ui.widgets.notification_center import NotificationCenter

    center = NotificationCenter()
    got = []
    center.notification_activated.connect(lambda k, t: got.append((k, t)))
    try:
        center.add("report", "Rapor A", "C:/a.md")
        center._on_item_clicked(center.list_widget.item(0))
        assert got == [("report", "C:/a.md")]
    finally:
        center.close()
        center.deleteLater()


# ------------------------------------------------------- sağlayıcı rozeti

def test_provider_badge_colors_and_login_hint(qapp):
    from entropy.ui.widgets.provider_badge import (
        COLOR_BAD, COLOR_OK, ProviderStatusBadge, status_color, status_tooltip,
    )

    badge = ProviderStatusBadge()
    try:
        badge.set_status("agy", {"logged_in": True, "plan": "Pro", "session_window": "3 sa",
                                 "quota_hint": "%40"})
        badge.set_status("claude", {"logged_in": False, "last_error": "oturum yok"})
        agy_html = badge.labels["agy"].text()
        claude_html = badge.labels["claude"].text()
        assert "Pro" in agy_html and "3 sa" in agy_html
        assert COLOR_OK in agy_html
        assert COLOR_BAD in claude_html
        assert "giriş yok" in claude_html
        # Düşünce (ipucu) kullanıcıya ne yapacağını söyler.
        assert "/login claude" in badge.labels["claude"].toolTip()
        assert status_color(None) not in (COLOR_OK,)
        assert "/login agy" in status_tooltip("agy", {"logged_in": False})
    finally:
        badge.close()
        badge.deleteLater()


def test_provider_badge_listens_to_bus_signal(qapp):
    from entropy.core.event_bus import bus
    from entropy.ui.widgets.provider_badge import ProviderStatusBadge

    if not hasattr(bus, "provider_status_updated"):
        pytest.skip("provider_status_updated sözleşmesi henüz yok")
    badge = ProviderStatusBadge()
    try:
        bus.provider_status_updated.emit("agy", {"logged_in": True, "plan": "Ultra"})
        assert badge.statuses["agy"]["plan"] == "Ultra"
        assert "Ultra" in badge.labels["agy"].text()
    finally:
        badge.close()
        badge.deleteLater()


# --------------------------------------------------- Zen / Chat bağlanımı

def test_zen_and_chat_expose_lifestyle_surfaces():
    """İki kip de aynı yaşam tarzı yüzeylerini kurar (parite)."""
    from entropy.ui.modes.chat_mode import ChatModeWindow
    from entropy.ui.modes.zen_mode import ZenModeWindow

    for cls in (ZenModeWindow, ChatModeWindow):
        for slot in ("_on_palette_activated", "_on_timeline_activated",
                     "_on_notification_activated", "_on_provider_login_requested"):
            assert callable(getattr(cls, slot, None)), f"{cls.__name__}.{slot} yok"


def test_reports_viewer_hosts_report_center_above_reader(qapp):
    """Rapor Merkezi, Raporlar sekmesinin üst yarısında ve okuyucudan önce."""
    from entropy.ui.widgets.report_center import ReportCenterWidget
    from entropy.ui.widgets.reports_viewer import ReportsViewerWidget

    widget = ReportsViewerWidget()
    try:
        assert isinstance(widget.report_center, ReportCenterWidget)
        idx_center = widget.layout.indexOf(widget.report_center)
        idx_splitter = widget.layout.indexOf(widget.splitter)
        assert 0 <= idx_center < idx_splitter
    finally:
        widget.close()
        widget.deleteLater()


def test_zen_report_toolbar_buttons_are_icon_only_with_tooltips(qapp):
    """1280 px'te kırpılan etiketler ikon + ipucuna indirildi."""
    from entropy.ui.widgets.reports_viewer import ReportsViewerWidget

    widget = ReportsViewerWidget()
    try:
        for btn in (widget.btn_open_obsidian, widget.btn_open_folder):
            assert len(btn.text()) <= 2, f"etiket hâlâ uzun: {btn.text()!r}"
            assert btn.toolTip(), "ikon düğmesinin ipucu zorunlu"
            assert btn.width() <= 30
    finally:
        widget.close()
        widget.deleteLater()


# ------------------------------------------------------------ graf (5.6)

def test_graph_control_strip_strings_present():
    """Kontrol şeridi: zaman kaydırıcısı, tür/önem filtresi, yalnızca geçerli."""
    src = GRAPH_PY.read_text(encoding="utf-8")
    for needle in (
        'id="graphControls"', 'id="timeSlider"', 'id="typeFilter"',
        'id="importanceSlider"', 'id="onlyValid"',
        "onTimeSlider(", "onTypeFilter(", "onImportanceSlider(", "onOnlyValid(",
        "collapseAllCommunities()", "toggleCommunity(",
        "yalnızca geçerli", "Zaman", "Önem",
    ):
        assert needle in src, f"kontrol şeridinde eksik: {needle}"
    # Topluluk düğümü efsanede ve renk/ikon tablolarında.
    # Faz 8: efsane LEGEND_DEFS + buildLegend ile JS'ten kuruluyor.
    assert "['community', " in src
    assert "'community': '#FFD166'" in src


def test_graph_script_still_valid_javascript():
    node = shutil.which("node")
    if not node:
        pytest.skip("node bulunamadı")
    src = GRAPH_PY.read_text(encoding="utf-8")
    blocks = re.findall(r"<script>(.*?)</script>", src, re.DOTALL)
    assert blocks
    import tempfile

    for block in blocks:
        js = block.replace("{{", "{").replace("}}", "}")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(js)
            temp = fh.name
        try:
            result = subprocess.run([node, "--check", temp], capture_output=True, timeout=60)
            assert result.returncode == 0, result.stderr.decode("utf-8", "ignore")
        finally:
            os.unlink(temp)


GRAPH_JS_HARNESS = r"""
// Minimal DOM/Canvas taklidi: mevcut Node düzeneğiyle aynı desen.
const elements = {};
function makeEl(id) {
    return {
        id: id,
        style: {},
        classList: { toggle: function (c, v) { this[c] = v; }, },
        disabled: false,
        textContent: '',
        className: '',
        offsetHeight: 30,
        children: [],
        attrs: {},
        // Faz 8: buildLegend efsaneyi JS ile kurarken data-cat yaziyor.
        setAttribute: function (k, v) { this.attrs[k] = v; },
        getAttribute: function (k) { return this.attrs[k]; },
        appendChild: function (c) { this.children.push(c); },
        addEventListener: function () {},
        getBoundingClientRect: function () { return { left: 0, top: 0 }; },
        getContext: function () { return CTX; }
    };
}
const CTX = new Proxy({}, {
    get: function (t, k) {
        if (k === 'measureText') return function () { return { width: 40 }; };
        if (k === 'createLinearGradient' || k === 'createRadialGradient')
            return function () { return { addColorStop: function () {} }; };
        if (k === 'canvas') return elements['canvas'];
        return function () {};
    },
    set: function () { return true; }
});
const document = {
    getElementById: function (id) {
        if (!elements[id]) elements[id] = makeEl(id);
        return elements[id];
    },
    createElement: function (tag) { return makeEl(tag); },
    documentElement: { clientWidth: 1000, clientHeight: 800 },
    querySelectorAll: function () { return []; },
    addEventListener: function () {}
};
const window = {
    innerWidth: 1000, innerHeight: 800,
    addEventListener: function () {},
    location: { href: '' }
};
const requestAnimationFrame = function (cb) {};
const setTimeout = function (cb) {};
const clearTimeout = function () {};

__GRAPH_JS__

// ---- iddialar ----
const out = [];
function check(name, cond) { out.push((cond ? 'OK   ' : 'FAIL ') + name); }

const community = nodeMap.get('com-1');
const member = nodeMap.get('fact-old');

check('topluluk düğümü var', !!community);
check('topluluk boyutu member_count ile büyüdü', community.val > 12);
check('açılışta üyeler gizli', isNodeVisible(member) === false);
toggleCommunity('com-1');
check('tıklayınca üyeler görünür', isNodeVisible(member) === true);
collapseAllCommunities();
check('kapatınca üyeler yeniden gizli', isNodeVisible(member) === false);
toggleCommunity('com-1');

// Zaman kaydırıcısı: geçmişe çekilince yeni düğüm solar.
onTimeSlider(0);
check('geçmişte yeni düğüm soluk', nodeAlphaFactor(nodeMap.get('fact-new')) < 0.5);
onTimeSlider(100);
check('şimdide yeni düğüm net', nodeAlphaFactor(nodeMap.get('fact-new')) === 1.0);

// "Yalnızca geçerli": t_valid_to dolu düğüm silik.
check('geçersizleştirilmiş düğüm silik', nodeAlphaFactor(nodeMap.get('fact-old')) <= 0.10);
onOnlyValid(false);
check('kapatınca daha görünür', nodeAlphaFactor(nodeMap.get('fact-old')) > 0.10);
onOnlyValid(true);

// Tür filtresi
onTypeFilter('entity');
check('tür filtresi entity dışını eler', isNodeVisible(nodeMap.get('fact-new')) === false);
check('tür filtresi entity bırakır', isNodeVisible(nodeMap.get('ent-1')) === true);
onTypeFilter('');

// Önem filtresi
onImportanceSlider(90);
check('düşük önem elenir', isNodeVisible(nodeMap.get('ent-1')) === false);
onImportanceSlider(0);
check('eşik sıfırlanınca geri gelir', isNodeVisible(nodeMap.get('ent-1')) === true);

// Kareler: fizik ve çizim 30 tur boyunca stabil.
for (let i = 0; i < 30; i++) { render(); }
check('30 kare hatasız', true);

console.log(out.join('\n'));
if (out.some(function (l) { return l.indexOf('FAIL') === 0; })) process.exit(1);
"""


def _graph_js_with_fixture() -> str:
    """Grafik JS'ini sahte çift zamanlı düğüm verisiyle doldurur."""
    import json

    src = GRAPH_PY.read_text(encoding="utf-8")
    block = re.findall(r"<script>(.*?)</script>", src, re.DOTALL)[0]
    now_ms = int(time.time() * 1000)
    old_ms = now_ms - 90 * 86400 * 1000
    nodes = [
        {"id": "ego-entropy-core", "name": "Çekirdek", "group": "ego", "val": 22, "x": 0, "y": 0},
        {"id": "com-1", "name": "Finans Topluluğu", "group": "community", "val": 12,
         "member_count": 40, "x": 100, "y": 50, "t_valid_from": old_ms},
        {"id": "fact-old", "name": "Eski olgu", "group": "semantic", "type": "fact",
         "importance": 0.8, "val": 10, "x": 140, "y": 70,
         "community_id": "com-1", "t_valid_from": old_ms, "t_valid_to": old_ms + 1000},
        {"id": "fact-new", "name": "Yeni olgu", "group": "semantic", "type": "fact",
         "importance": 0.9, "val": 10, "x": 160, "y": 90,
         "community_id": "com-1", "t_valid_from": now_ms},
        {"id": "ent-1", "name": "Varlık", "group": "entity", "type": "entity",
         "importance": 0.3, "val": 10, "x": 60, "y": 30, "t_valid_from": old_ms},
    ]
    links = [
        {"source": "ego-entropy-core", "target": "com-1", "is_tree_link": True},
        {"source": "fact-old", "target": "com-1", "type": "member_of"},
        {"source": "fact-new", "target": "com-1", "type": "member_of"},
    ]
    js = (
        block.replace("__NODES__", json.dumps(nodes, ensure_ascii=False))
        .replace("__LINKS__", json.dumps(links, ensure_ascii=False))
        .replace("__INITIAL_SCOPE__", "all")
        .replace("__ACTIVE_PROJECT_SLUG__", "test")
    )
    return GRAPH_JS_HARNESS.replace("__GRAPH_JS__", js)


def test_graph_time_type_importance_and_community_logic(tmp_path):
    """Node ile: topluluk açılımı, zaman kaydırıcısı, tür/önem filtresi, geçerlilik."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node bulunamadı")
    script = tmp_path / "graph_controls.mjs"
    script.write_text(_graph_js_with_fixture(), encoding="utf-8")
    result = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "FAIL" not in result.stdout, result.stdout


def test_graph_controls_disabled_without_memory_fields(tmp_path):
    """Alanlar yoksa kontroller pasifleşir; grafik yine de kurulur."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node bulunamadı")
    import json

    src = GRAPH_PY.read_text(encoding="utf-8")
    block = re.findall(r"<script>(.*?)</script>", src, re.DOTALL)[0]
    nodes = [
        {"id": "ego-entropy-core", "name": "Çekirdek", "group": "ego", "val": 22, "x": 0, "y": 0},
        {"id": "r1", "name": "Rapor", "group": "Reports", "val": 10, "x": 40, "y": 20},
    ]
    js = (
        block.replace("__NODES__", json.dumps(nodes, ensure_ascii=False))
        .replace("__LINKS__", json.dumps([{"source": "ego-entropy-core", "target": "r1", "is_tree_link": True}]))
        .replace("__INITIAL_SCOPE__", "all")
        .replace("__ACTIVE_PROJECT_SLUG__", "test")
    )
    harness = GRAPH_JS_HARNESS.split("// ---- iddialar ----")[0].replace("__GRAPH_JS__", js) + """
const out = [];
function check(name, cond) { out.push((cond ? 'OK   ' : 'FAIL ') + name); }
check('zaman verisi yok', hasTimeData === false);
check('önem verisi yok', hasImportanceData === false);
check('geçerlilik verisi yok', hasValidityData === false);
check('topluluk verisi yok', hasCommunityData === false);
check('zaman kaydırıcısı pasif', document.getElementById('timeSlider').disabled === true);
check('önem kaydırıcısı pasif', document.getElementById('importanceSlider').disabled === true);
check('rapor düğümü görünür', isNodeVisible(nodeMap.get('r1')) === true);
check('rapor düğümü net', nodeAlphaFactor(nodeMap.get('r1')) === 1.0);
for (let i = 0; i < 10; i++) { render(); }
console.log(out.join('\\n'));
if (out.some(function (l) { return l.indexOf('FAIL') === 0; })) process.exit(1);
"""
    script = tmp_path / "graph_no_fields.mjs"
    script.write_text(harness, encoding="utf-8")
    result = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "FAIL" not in result.stdout, result.stdout


def test_graph_frame_budget_with_1000_nodes(tmp_path):
    """1000+ düğümde kare süresi 30 fps bütçesinin (33 ms) altında kalmalı."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node bulunamadı")
    import json

    src = GRAPH_PY.read_text(encoding="utf-8")
    block = re.findall(r"<script>(.*?)</script>", src, re.DOTALL)[0]
    now_ms = int(time.time() * 1000)
    nodes = [{"id": "ego-entropy-core", "name": "Çekirdek", "group": "ego", "val": 22, "x": 0, "y": 0}]
    links = []
    for i in range(1000):
        nodes.append({
            "id": f"n{i}", "name": f"Düğüm {i}", "group": "Reports", "type": "fact",
            "importance": (i % 10) / 10.0, "val": 10,
            "x": (i % 40) * 25.0, "y": (i // 40) * 25.0,
            "t_valid_from": now_ms - i * 1000,
        })
        links.append({"source": "ego-entropy-core", "target": f"n{i}", "is_tree_link": True})
    js = (
        block.replace("__NODES__", json.dumps(nodes, ensure_ascii=False))
        .replace("__LINKS__", json.dumps(links))
        .replace("__INITIAL_SCOPE__", "all")
        .replace("__ACTIVE_PROJECT_SLUG__", "test")
    )
    harness = GRAPH_JS_HARNESS.split("// ---- iddialar ----")[0].replace("__GRAPH_JS__", js) + """
const FRAMES = 60;
for (let i = 0; i < 5; i++) { render(); }   // ısınma
const t0 = Date.now();
for (let i = 0; i < FRAMES; i++) { render(); }
const perFrame = (Date.now() - t0) / FRAMES;
console.log('per_frame_ms=' + perFrame.toFixed(2));
if (perFrame > 33.0) { console.log('FAIL kare bütçesi aşıldı'); process.exit(1); }
"""
    script = tmp_path / "graph_perf.mjs"
    script.write_text(harness, encoding="utf-8")
    result = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "per_frame_ms=" in result.stdout, result.stdout


def test_both_modes_route_orchestrator_answer_to_chat():
    """"Orkestratöre sor" yanıtı iki kipte de sohbet balonuna gider."""
    from entropy.ui.modes.chat_mode import ChatModeWindow
    from entropy.ui.modes.zen_mode import ZenModeWindow

    for cls in (ZenModeWindow, ChatModeWindow):
        assert callable(getattr(cls, "_on_orchestrator_answer", None)), cls.__name__
