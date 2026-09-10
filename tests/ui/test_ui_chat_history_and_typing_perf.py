"""Sohbet geçmişinin kalıcılığı, giriş kutusu gecikmesi ve okuma yüzeyi testleri.

Kapsam:
  1. Sohbet geçmişi tek kaynaktan okunur; mod değişimi / yeniden kurulum /
     ayrı pencere sohbeti silmez. Yalnızca "+ Yeni Sohbet" temizler ve eski
     sohbeti .entropy/chat_archive/<zaman>.json altına taşır.
  2. Tuş başına ana iş parçacığı işi: komut keşfi her tuşta çalışmaz (önbellek
     + 150 ms gecikme).
  3. Markdown yüzeyi: sohbet balonlarına tam HTML belgesi gömülmez (siyah
     arka plan kaynağı) ve tablolar siyah dolgu kullanmaz.
"""

import json
import sys
import time

import pytest

from PySide6.QtWidgets import QApplication

import entropy.core.config  # noqa: F401
config_module = sys.modules["entropy.core.config"]

from entropy.core.slash_commands import (
    SlashCommandRegistry,
    invalidate_command_cache,
)
from entropy.ui.widgets.markdown_renderer import (
    build_chat_bubble_html,
    render_markdown_fragment,
    render_markdown_to_html,
)


@pytest.fixture
def app():
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    return QApplication.instance() or QApplication([])


# --------------------------------------------------------------- 1. geçmiş

def test_chat_history_roundtrip_and_archive():
    """Geçmiş diske yazılır, okunur; arşivleme siler değil taşır."""
    history = [
        {"role": "user", "content": "birinci soru"},
        {"role": "assistant", "content": "birinci yanıt"},
    ]
    config_module.save_chat_history(history)
    assert config_module.load_chat_history() == history

    archived = config_module.archive_chat_history()
    assert archived is not None and archived.exists()
    assert json.loads(archived.read_text(encoding="utf-8")) == history
    # Arşivden sonra aktif sohbet boş
    assert config_module.load_chat_history() == []
    # Arşiv, geçmiş dosyasının yanındaki chat_archive klasöründe
    assert archived.parent == config_module.chat_archive_dir()


def test_chat_history_seed_prompts_filtered():
    config_module.save_chat_history([
        {"role": "user", "content": "Hello"},
        {"role": "user", "content": "gerçek mesaj"},
    ])
    loaded = config_module.load_chat_history()
    assert [m["content"] for m in loaded] == ["gerçek mesaj"]


def test_bridge_save_turn_persists_and_survives_restart(monkeypatch):
    """Köprü turu diske yazar; yeni köprü örneği (yeniden başlatma) geri yükler."""
    from entropy.core.agy_bridge import AgyProcessBridge

    monkeypatch.setattr(AgyProcessBridge, "fetch_available_models", lambda self: [])
    b1 = AgyProcessBridge()
    b1._save_chat_turn("soru", "yanıt")

    b2 = AgyProcessBridge()
    assert [m["content"] for m in b2.conversation_history] == ["soru", "yanıt"]


def test_bridge_reset_archives_instead_of_deleting(monkeypatch):
    from entropy.core.agy_bridge import AgyProcessBridge

    monkeypatch.setattr(AgyProcessBridge, "fetch_available_models", lambda self: [])
    b = AgyProcessBridge()
    b._save_chat_turn("soru", "yanıt")
    b.reset_conversation()

    assert b.conversation_history == []
    assert config_module.load_chat_history() == []
    archives = list(config_module.chat_archive_dir().glob("*.json"))
    assert len(archives) == 1
    assert "soru" in archives[0].read_text(encoding="utf-8")


def test_both_modes_show_same_history_after_mode_switch(app, monkeypatch):
    """
    Zen'de yazılan tur, Chat moduna geçince görünür (ve tersi).

    Kök neden testi: modlar geçmişi yalnızca kuruluşta okuyordu; diğer modda
    yazılan turlar görünmüyor, kullanıcıya "sohbet silinmiş" gibi geliyordu.
    """
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.ui.modes.chat_mode import ChatModeWindow

    monkeypatch.setattr(AgyProcessBridge, "fetch_available_models", lambda self: [])
    bridge = AgyProcessBridge()
    config_module.save_chat_history([
        {"role": "user", "content": "ilk mesaj"},
        {"role": "assistant", "content": "ilk yanıt"},
    ])

    win = ChatModeWindow(bridge=bridge)
    win.show()
    app.processEvents()
    assert "ilk mesaj" in win.chat_browser.toPlainText()

    # Mod değişimi: pencere gizlenir, arada başka bir modda tur eklenir.
    win.hide()
    app.processEvents()
    time.sleep(0.01)  # imza (mtime) farkı garantiye alınır
    config_module.save_chat_history([
        {"role": "user", "content": "ilk mesaj"},
        {"role": "assistant", "content": "ilk yanıt"},
        {"role": "user", "content": "zen mesajı"},
        {"role": "assistant", "content": "zen yanıtı"},
    ])

    win.show()
    app.processEvents()
    text = win.chat_browser.toPlainText()
    assert "ilk mesaj" in text and "zen mesajı" in text
    win.close()


def test_standalone_reconstruction_keeps_history(app, monkeypatch):
    """Sohbet görünümü yeniden kurulduğunda (ayrı pencere) içerik aynı kalır."""
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.ui.modes.chat_mode import ChatModeWindow

    monkeypatch.setattr(AgyProcessBridge, "fetch_available_models", lambda self: [])
    bridge = AgyProcessBridge()
    config_module.save_chat_history([
        {"role": "user", "content": "kalıcı mesaj"},
        {"role": "assistant", "content": "kalıcı yanıt"},
    ])

    w1 = ChatModeWindow(bridge=bridge)
    w2 = ChatModeWindow(bridge=bridge)
    for w in (w1, w2):
        assert "kalıcı mesaj" in w.chat_browser.toPlainText()
        assert "kalıcı yanıt" in w.chat_browser.toPlainText()
    w1.close()
    w2.close()


def test_new_chat_clears_all_open_windows(app, monkeypatch):
    """'+ Yeni Sohbet' açık tüm pencereleri temizler (bus.chat_history_cleared)."""
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.ui.modes.chat_mode import ChatModeWindow

    monkeypatch.setattr(AgyProcessBridge, "fetch_available_models", lambda self: [])
    bridge = AgyProcessBridge()
    config_module.save_chat_history([{"role": "user", "content": "silinecek mesaj"}])

    w1 = ChatModeWindow(bridge=bridge)
    w2 = ChatModeWindow(bridge=bridge)
    assert "silinecek mesaj" in w1.chat_browser.toPlainText()

    w1._on_new_chat()
    app.processEvents()

    for w in (w1, w2):
        assert "silinecek mesaj" not in w.chat_browser.toPlainText()
    assert list(config_module.chat_archive_dir().glob("*.json"))
    w1.close()
    w2.close()


# --------------------------------------------------------- 2. yazma gecikmesi

def test_command_catalog_is_cached(tmp_path):
    """Katalog keşfi tekrar tekrar diski taramaz; geçersiz kılınınca yeniden tarar."""
    reg = SlashCommandRegistry()
    invalidate_command_cache()

    calls = {"n": 0}
    original = SlashCommandRegistry._discover_all_commands

    def counting(self, project_dir=None):
        calls["n"] += 1
        return original(self, project_dir)

    SlashCommandRegistry._discover_all_commands = counting
    try:
        for _ in range(5):
            reg.get_all_commands(tmp_path)
        assert calls["n"] == 1, "önbellek çalışmıyor: her çağrı diski tarıyor"

        invalidate_command_cache()
        reg.get_all_commands(tmp_path)
        assert calls["n"] == 2, "geçersiz kılma sonrası yeniden tarama yok"
    finally:
        SlashCommandRegistry._discover_all_commands = original
        invalidate_command_cache()


def test_keystroke_does_not_trigger_command_discovery(app, tmp_path):
    """Tuş başına komut keşfi çalışmaz; öneri 150 ms gecikmeye alınır."""
    from entropy.ui.modes.chat_mode import ChatInputField

    class FakeBridge:
        active_project_dir = tmp_path

    class FakeParent:
        bridge = FakeBridge()

    field = ChatInputField(FakeParent())
    calls = {"n": 0}
    field.registry.filter_commands = lambda *a, **k: calls.__setitem__("n", calls["n"] + 1) or []

    acc = ""
    durations = []
    for ch in "/boost":
        acc += ch
        t0 = time.perf_counter()
        field.setText(acc)
        field.setCursorPosition(len(acc))
        durations.append((time.perf_counter() - t0) * 1000)

    assert calls["n"] == 0, "komut keşfi hâlâ her tuşta çalışıyor"
    assert field._suggest_timer.isActive()
    # Tuş başına ana iş parçacığı bütçesi: 5 ms
    assert max(durations) < 5.0, f"tuş başına {max(durations):.1f} ms (bütçe 5 ms)"

    # Gecikme dolunca öneri bir kez hesaplanır.
    field._update_suggestions()
    assert calls["n"] == 1
    field.close()


def test_input_field_project_dir_without_bridge(app):
    """Köprüsüz ebeveynde getattr(obj, None) TypeError'ı yeniden oluşmamalı."""
    from entropy.ui.modes.chat_mode import ChatInputField

    class ParentWithoutBridge:
        bridge = None

    field = ChatInputField(ParentWithoutBridge())
    assert field._get_active_project_dir() is None
    field.close()


# ------------------------------------------------------------- 3. okuma yüzeyi

MD_SAMPLE = """## Başlık

| Varlık | Ağırlık |
|---|---|
| Tahvil | 32.5 |
| Hisse | 47.0 |

```python
x = 1
```
"""


def test_chat_bubble_has_no_embedded_html_document():
    """Balonun içine tam HTML belgesi gömülmez (siyah arka planın kök nedeni)."""
    bubble = build_chat_bubble_html("Entropy AI", MD_SAMPLE)
    lowered = bubble.lower()
    assert "<html" not in lowered
    assert "<body" not in lowered
    assert "<!doctype" not in lowered
    assert "<table" in lowered


def test_reading_surfaces_avoid_black_fills():
    """Tablo ve kod bloğu saf siyah dolgu kullanmaz."""
    frag = render_markdown_fragment(MD_SAMPLE)
    for black in ("#000000", "#05070A", "#080B10"):
        assert black.lower() not in frag.lower(), f"siyah dolgu kaldı: {black}"


def test_table_numeric_columns_right_aligned():
    frag = render_markdown_fragment(MD_SAMPLE)
    assert "text-align:right" in frag.replace(" ", "")


def test_report_document_uses_shared_reading_css():
    from entropy.ui.themes.cyber_theme import READING_TOKENS

    doc = render_markdown_to_html(MD_SAMPLE)
    assert doc.startswith("<!DOCTYPE html>")
    assert READING_TOKENS["surface_base"] in doc
    assert READING_TOKENS["font_body"] in doc


def test_code_block_has_language_pill_and_accent_stripe():
    frag = render_markdown_fragment(MD_SAMPLE)
    assert "PYTHON" in frag
    assert "border-left:3px solid" in frag
