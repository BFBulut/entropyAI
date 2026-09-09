"""HOTFIX v0.7.1 — efor kutusu sağlayıcıya VE modele göre dolar.

Kullanıcının gördüğü hata: agy'de kutu Claude'un beş seviyesini gösteriyordu ve
`medium` seçilince CLI "--model gemini-3.8-flash-high conflicts with
--effort=medium" diyordu. agy'de efor model adının son ekidir.
"""

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QHBoxLayout, QWidget

AGY_CATALOG = [
    "gemini-3.8-flash-high", "gemini-3.8-flash-medium", "gemini-3.8-flash-low",
    "gemini-3.1-pro-high", "gemini-3.1-pro-low",
    "claude-sonnet-4-6", "claude-opus-4-6-thinking", "gpt-oss-120b-medium",
]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def agy_models(monkeypatch):
    """Canlı `agy models` listesi yerine sabit katalog (model çağrısı yok)."""
    from entropy.core.config import config

    monkeypatch.setattr(config, "available_models", list(AGY_CATALOG), raising=False)
    return AGY_CATALOG


class FakeAgyBridge:
    provider_name = "agy"
    selected_effort = "medium"

    def __init__(self, model="gemini-3.8-flash-high"):
        self.selected_model = model
        self.models_set = []

    def effort_levels(self):
        return ["low", "medium", "high"]

    def fetch_available_models(self):
        return list(AGY_CATALOG)

    def set_model(self, name):
        self.models_set.append(name)
        self.selected_model = name
        return True


class FakeClaudeBridge:
    provider_name = "claude"
    selected_model = "claude-opus-5"
    selected_effort = "medium"

    def __init__(self):
        self.efforts = []

    def effort_levels(self):
        return ["low", "medium", "high", "xhigh", "max"]

    def set_effort(self, level):
        self.efforts.append(level)
        self.selected_effort = level
        return True


# ------------------------------------------------------------------ seviyeler

def test_agy_levels_follow_model_suffixes():
    from entropy.ui.widgets.effort_selector import effort_levels_for

    assert effort_levels_for("agy", "gemini-3.8-flash-high", models=AGY_CATALOG) == \
        ["low", "medium", "high"]
    assert effort_levels_for("agy", "gemini-3.1-pro-low", models=AGY_CATALOG) == \
        ["low", "high"]
    # Son eki olmayan agy modeli: efor seçimi yok.
    assert effort_levels_for("agy", "claude-sonnet-4-6", models=AGY_CATALOG) == []


def test_claude_has_five_levels():
    from entropy.ui.widgets.effort_selector import effort_levels_for

    assert effort_levels_for("claude", "claude-opus-5") == \
        ["low", "medium", "high", "xhigh", "max"]


def test_split_and_compose_roundtrip():
    from entropy.ui.widgets.effort_selector import compose_agy_model, split_agy_model

    assert split_agy_model("gemini-3.8-flash-high") == ("gemini-3.8-flash", "high")
    assert split_agy_model("claude-sonnet-4-6") == ("claude-sonnet-4-6", None)
    assert compose_agy_model("gemini-3.8-flash", "medium") == "gemini-3.8-flash-medium"


# --------------------------------------------------------------------- widget

def _selector(bridge, model_text=""):
    host = QWidget()
    layout = QHBoxLayout(host)
    model_combo = QComboBox()
    model_combo.setEditable(True)
    model_combo.addItems(AGY_CATALOG)
    model_combo.setCurrentText(model_text or getattr(bridge, "selected_model", ""))
    from entropy.ui.widgets.effort_selector import install_effort_selector

    combo = install_effort_selector(layout, bridge, host, model_combo=model_combo)
    return host, model_combo, combo


def test_agy_box_has_three_options_and_rewrites_model(qapp):
    bridge = FakeAgyBridge("gemini-3.8-flash-high")
    host, model_combo, combo = _selector(bridge)
    assert combo is not None
    assert combo.levels() == ["low", "medium", "high"]
    assert combo.currentText() == "high"

    combo.setCurrentText("medium")
    # Efor bayrağı DEĞİL, model adı değişir.
    assert bridge.models_set == ["gemini-3.8-flash-medium"]
    assert model_combo.currentText() == "gemini-3.8-flash-medium"
    host.deleteLater()


def test_agy_pro_box_has_two_options(qapp):
    bridge = FakeAgyBridge("gemini-3.1-pro-low")
    host, _model_combo, combo = _selector(bridge)
    assert combo.levels() == ["low", "high"]
    host.deleteLater()


def test_agy_model_without_suffix_disables_box(qapp):
    bridge = FakeAgyBridge("claude-sonnet-4-6")
    host, _model_combo, combo = _selector(bridge)
    assert combo is not None
    assert combo.levels() == []
    assert not combo.isEnabled()
    assert "efor seçimi yok" in combo.toolTip().lower()
    host.deleteLater()


def test_claude_box_has_five_options_and_uses_set_effort(qapp):
    bridge = FakeClaudeBridge()
    host, _model_combo, combo = _selector(bridge)
    assert combo.levels() == ["low", "medium", "high", "xhigh", "max"]
    combo.setCurrentText("xhigh")
    assert bridge.efforts == ["xhigh"]
    host.deleteLater()


def test_provider_switch_repopulates_box(qapp):
    bridge = FakeAgyBridge("gemini-3.8-flash-high")
    host, model_combo, combo = _selector(bridge)
    assert len(combo.levels()) == 3

    # Sağlayıcı değişimi: köprü ve model kutusu yenilenir, kutu tazelenir.
    combo.bridge = FakeClaudeBridge()
    model_combo.blockSignals(True)
    model_combo.setCurrentText("claude-opus-5")
    model_combo.blockSignals(False)
    combo.refresh()
    assert combo.levels() == ["low", "medium", "high", "xhigh", "max"]
    host.deleteLater()


def test_model_change_repopulates_box(qapp):
    bridge = FakeAgyBridge("gemini-3.8-flash-high")
    host, model_combo, combo = _selector(bridge)
    model_combo.setCurrentText("gemini-3.1-pro-high")
    combo.refresh()
    assert combo.levels() == ["low", "high"]
    host.deleteLater()


# ------------------------------------------------------- formlar (Entropy/Desk)

def test_agent_form_effort_follows_provider_and_model(qapp):
    from entropy.ui.widgets.agents_widget import AgentEditDialog

    dialog = AgentEditDialog(bridge=FakeAgyBridge())
    dialog.provider_combo.setCurrentText("agy")
    dialog.model_combo.setCurrentText("gemini-3.1-pro-high")
    assert dialog.effort_choices() == ["low", "high"]

    dialog.provider_combo.setCurrentText("claude")
    dialog.model_combo.setCurrentText("claude-opus-5")
    assert dialog.effort_choices() == ["low", "medium", "high", "xhigh", "max"]
    dialog.deleteLater()


def test_assign_dialog_effort_follows_model(qapp):
    from entropy.ui.widgets.agents_widget import AssignTaskDialog

    dialog = AssignTaskDialog(agent_name="arastirmaci", provider="agy",
                              bridge=FakeAgyBridge())
    dialog.model_combo.setCurrentText("gemini-3.8-flash-low")
    assert dialog.effort_choices() == ["low", "medium", "high"]
    dialog.model_combo.setCurrentText("claude-sonnet-4-6")
    assert dialog.effort_choices() == []
    dialog.deleteLater()


def test_effort_help_text_mentions_provider_levels():
    from entropy.ui.widgets.effort_selector import effort_help_text

    agy_text = effort_help_text("agy", "gemini-3.8-flash-high")
    assert "model adının son eki" in agy_text and "medium" in agy_text
    claude_text = effort_help_text("claude", "claude-opus-5")
    assert "xhigh" in claude_text and "max" in claude_text
