"""
Ajan yönetim paneli — kayıt defterindeki alt ajanları listeler, düzenler,
siler ve onlara görev verir.

Kayıt defteri (`entropy.agents.registry.AgentRegistry`) ve görev panosu
(`entropy.agents.tasks.TaskBoard`) başka bir ajan tarafından yazılıyor; bu
yüzden içe aktarma korumalıdır: modül yoksa panel boş liste ve açıklayıcı bir
uyarı gösterir, çökmez. Testler yapıcıya sahte nesne verebilir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

from PySide6.QtGui import QColor, QPalette

from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.ui_polish import BODY_PX, BODY_STRONG_PX, LABEL_PX


def _paint_dark(widget) -> None:
    """
    Widget paletini koyu yüzeye sabitler.

    Stil sayfası (`setStyleSheet`) bazı Qt sınıflarında görünüm alanına
    (viewport) uygulanmaz; o durumda sistem paleti devreye girip beyaz bir
    şerit bırakır. Palet doğrudan yazılınca sonuç stil sayfasından bağımsızdır.
    """
    try:
        palette = widget.palette()
        color = QColor(RT["surface_base"])
        for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base):
            palette.setColor(role, color)
        widget.setPalette(palette)
    except (AttributeError, RuntimeError):
        pass

# Sağlayıcı başına önerilen model listesi. Etkin köprü o sağlayıcıya aitse
# canlı liste okunur; okunamazsa bu doğrulanmış sabit liste devreye girer.
#
# Faz 9: agy listesi UYDURULMUYOR — `agy models` çıktısındaki adlar birebir
# alındı (2026-09-09; kota harcamayan salt okunur komut). Eski listedeki
# "gemini-3-pro"/"gemini-2.5-*" adları CLI'da yok, seçilince her koşu
# geçersiz `--model` ile başlıyordu.
_AGY_LIVE_MODELS = [
    "gemini-3.8-flash-high",
    "gemini-3.8-flash-medium",
    "gemini-3.8-flash-low",
    "gemini-3.7-flash-high",
    "gemini-3.7-flash-medium",
    "gemini-3.7-flash-low",
    "gemini-3.6-flash-high",
    "gemini-3.6-flash-medium",
    "gemini-3.6-flash-low",
    "gemini-3.1-pro-high",
    "gemini-3.1-pro-low",
    "claude-sonnet-4-6",
    "claude-opus-4-6-thinking",
    "gpt-oss-120b-medium",
]


def _claude_fallback_models() -> List[str]:
    """Claude tarafı: köprünün `CLAUDE_MODELS` + takma adları (tek kaynak)."""
    try:
        from entropy.core.claude_bridge import CLAUDE_MODELS, CLAUDE_MODEL_ALIASES

        return list(CLAUDE_MODELS) + sorted(CLAUDE_MODEL_ALIASES.keys())
    except Exception:
        return ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5",
                "opus", "sonnet", "haiku"]


FALLBACK_MODELS: Dict[str, List[str]] = {
    "agy": list(_AGY_LIVE_MODELS),
    "claude": _claude_fallback_models(),
}


def model_belongs_to(provider: str, name: str) -> bool:
    """
    Ad `provider`ın CLI'sine verilebilir mi.

    Doğrulama agy-1'in köprü/config süzgeçlerine devredilir (`getattr` ile
    aranır: sürüm eskiyse UI çökmez). Bulunamazsa ön ek kuralına düşülür.
    """
    name = (name or "").strip()
    if not name:
        return True  # boş = "oturumun modelini miras al"
    provider = (provider or "").strip().lower()
    try:
        from entropy.core import config as config_module

        if provider == "claude":
            checker = getattr(config_module, "is_claude_model_name", None)
            if checker is not None:
                return bool(checker(name))
        elif provider == "agy":
            checker = getattr(config_module, "is_agy_model_name", None)
            if checker is not None:
                extra = list(getattr(config_module.config, "available_models", []) or [])
                return bool(checker(name, extra=extra))
    except Exception:
        pass
    low = name.lower()
    if provider == "claude":
        return low.startswith("claude-") or low.split("[", 1)[0] in {
            "opus", "sonnet", "haiku", "fable", "best", "default", "opusplan"
        }
    if provider == "agy":
        return low.startswith(("gemini-", "gpt-")) or low in {
            "claude-sonnet-4-6", "claude-opus-4-6-thinking"
        }
    return True


def list_cards_for(board: Any, office: str = "") -> List[Any]:
    """
    Kart listesi tek yerden okunur (Faz 9 kart kökü ayrımı).

    `TaskBoard.list(office=None)` artık YALNIZCA Entropy kartlarını döndürüyor;
    ofis kartları `Desk/Offices/<ofis>/cards/` altında. Desk panelleri
    `office=` geçmezse boş görünürdü. Eski/sahte panolar `office` argümanını
    kabul etmeyebilir; o durumda konumsuz çağrıya düşülür.
    """
    if board is None:
        return []
    office = (office or "").strip()
    try:
        if office:
            return list(board.list(office=office) or [])
        return list(board.list() or [])
    except TypeError:
        try:
            return list(board.list() or [])
        except Exception:
            return []
    except Exception:
        return []

EFFORT_LEVELS = ["low", "medium", "high"]


def populate_effort_combo(combo, provider: str, model: str = "", bridge: Any = None,
                          allow_empty: bool = False) -> List[str]:
    """
    HOTFIX v0.7.1: efor kutusunu SAĞLAYICI + MODEL'e göre doldurur.

    agy'de efor `--effort` bayrağı değil, model adının son eki
    (`gemini-3.8-flash-high`); bu yüzden son eki olmayan agy modellerinde
    seçenek yoktur ve kutu pasifleşir. claude'da beş seviye geçerlidir.
    Mevcut seçim korunur (listede yoksa eklenir), sinyaller engellenir.
    """
    from entropy.ui.widgets.effort_selector import NO_EFFORT_HINT, effort_levels_for

    if not (provider or "").strip():
        # Sağlayıcı boş = "ajanın/oturumun varsayılanı"; genel küme gösterilir.
        levels = list(EFFORT_LEVELS)
    else:
        levels = effort_levels_for(provider, model, bridge)
    current = combo.currentText().strip()
    combo.blockSignals(True)
    try:
        combo.clear()
        if allow_empty:
            combo.addItem("")
        for level in levels:
            combo.addItem(level)
        # Yeni kümede olmayan eski seçim taşınmaz; aksi halde agy'de Claude'un
        # seviyeleri listede kalıyordu (hatanın kaynağı).
        if current and combo.findText(current) >= 0:
            combo.setCurrentText(current)
        elif allow_empty:
            combo.setCurrentText("")
    finally:
        combo.blockSignals(False)
    combo.setEnabled(bool(levels))
    combo.setToolTip(
        NO_EFFORT_HINT if not levels
        else "Efor düzeyi (" + " | ".join(levels) + ")"
    )
    return levels

# Ofis rolleri (Faz 3 sözleşmesi): AgentSpec.role bu üç değerden biri olabilir;
# eski ajanlarda serbest metin ("Mimari denetçi") duruyor, o zaman rozet çıkmaz.
ROLE_LABELS = {
    "orchestrator": "orkestratör",
    "evaluator": "değerlendirici",
    "worker": "üye",
}
ROLE_COLORS = {
    "orchestrator": "#C084FC",
    "evaluator": "#3DE8A8",
    "worker": "#93A3B8",
}
TOOLS_POLICIES = ["inherit", "read-only", "full", "none"]



# ------------------------------------------------------------------ sözleşme

def load_registry() -> Optional[Any]:
    """AgentRegistry örneği; modül yoksa None (panel boş liste gösterir)."""
    try:
        from entropy.agents.registry import AgentRegistry  # type: ignore

        return AgentRegistry()
    except Exception:
        return None


def load_board() -> Optional[Any]:
    """TaskBoard örneği; modül yoksa None."""
    try:
        from entropy.agents.tasks import TaskBoard  # type: ignore

        return TaskBoard()
    except Exception:
        return None


def call_flex(fn: Callable, data: Dict[str, Any], *positional: Any) -> Any:
    """
    Sözleşme imzası netleşmeden çağrıyı esnek yapar.

    Önce `fn(*positional, **data)`, olmazsa `fn(*positional, data)` denenir.
    Böylece kayıt defteri `create(**alanlar)` de `create(sozluk)` de kabul
    ediyor olsa panel çalışır.
    """
    try:
        return fn(*positional, **data)
    except TypeError:
        return fn(*positional, data)


def build_dataclass(module_path: str, class_name: str, data: Dict[str, Any]) -> Optional[Any]:
    """
    Sözleşme veri sınıfını (AgentSpec / TaskCard) sözlükten kurar.

    Gerçek kayıt defteri `create(spec)` biçiminde veri sınıfı bekler; testlerdeki
    sahte nesneler ise anahtar sözcük alır. Bu yüzden önce veri sınıfı kurulur,
    kurulamazsa (modül yok) None dönülür ve çağrı sözlük yoluna düşer.
    """
    try:
        import importlib

        cls = getattr(importlib.import_module(module_path), class_name)
        fields = getattr(cls, "__dataclass_fields__", {})
        payload = {k: v for k, v in data.items() if k in fields}
        # Zorunlu ama formda olmayan alanlar (ör. TaskCard.id) boş geçilir;
        # kimliği pano üretir.
        for field_name, field in fields.items():
            if field_name in payload:
                continue
            import dataclasses

            has_default = (
                field.default is not dataclasses.MISSING
                or field.default_factory is not dataclasses.MISSING  # type: ignore[misc]
            )
            if not has_default:
                payload[field_name] = ""
        return cls(**payload)
    except Exception:
        return None


def call_contract(fn: Callable, data: Dict[str, Any], obj: Any = None, *positional: Any) -> Any:
    """Önce veri sınıfı imzası, olmazsa kwargs/sözlük imzası denenir."""
    if obj is not None:
        try:
            return fn(obj)
        except TypeError:
            pass
    return call_flex(fn, data, *positional)


def spec_field(spec: Any, name: str, default: Any = "") -> Any:
    """AgentSpec veya sözlük fark etmeksizin alan okur."""
    if isinstance(spec, dict):
        value = spec.get(name, default)
    else:
        value = getattr(spec, name, default)
    return default if value is None else value


def models_for_provider(provider: str, bridge: Any = None) -> List[str]:
    """
    Sağlayıcıya göre model listesi.

    Canlı liste YALNIZCA etkin köprü aynı sağlayıcıya aitse kullanılır; köprü
    başka sağlayıcıdaysa (ör. Claude oturumundayken agy ajanı tanımlanırken)
    doğrulanmış sabit liste döner. Aksi halde form, o CLI'nin kabul etmediği
    model adlarını öneriyordu.
    """
    provider = (provider or "").strip().lower()
    models: List[str] = []
    if bridge is not None and getattr(bridge, "provider_name", None) == provider:
        try:
            models = [m for m in bridge.fetch_available_models() if m]
        except Exception:
            models = []
        models = [m for m in models if model_belongs_to(provider, m)]
    if not models:
        models = list(FALLBACK_MODELS.get(provider, []))
    return models


# ------------------------------------------------------------------ diyaloglar

class AgentEditDialog(QDialog):
    """Ajan ekleme/düzenleme formu; kaydedince `get_data()` sözleşme alanlarını döner."""

    def __init__(self, parent=None, spec: Any = None, skills: Optional[List[str]] = None, bridge=None):
        super().__init__(parent)
        self.existing = spec
        self.bridge = bridge
        self.setWindowTitle("Ajanı Düzenle" if spec is not None else "Yeni Ajan")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        form = QFormLayout()
        form.setSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("kebab-case: code-architect")
        form.addRow("Ad:", self.name_input)

        self.role_input = QLineEdit()
        self.role_input.setPlaceholderText("Örn: Mimari denetçi")
        form.addRow("Rol:", self.role_input)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Bu ajan ne zaman çağrılmalı?")
        form.addRow("Açıklama:", self.description_input)

        self.provider_combo = QComboBox()
        try:
            from entropy.core.provider import PROVIDERS
        except Exception:
            PROVIDERS = ("agy", "claude")
        for p in PROVIDERS:
            self.provider_combo.addItem(p)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        form.addRow("Sağlayıcı:", self.provider_combo)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        form.addRow("Model:", self.model_combo)

        self.effort_combo = QComboBox()
        for e in EFFORT_LEVELS:
            self.effort_combo.addItem(e)
        self.effort_combo.setCurrentText("medium")
        form.addRow("Efor:", self.effort_combo)
        # HOTFIX v0.7.1: efor seçenekleri sağlayıcı + modele bağlı.
        self.model_combo.currentTextChanged.connect(self._on_model_changed)

        self.skills_list = QListWidget()
        self.skills_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.skills_list.setFixedHeight(96)
        for s in (skills if skills is not None else discover_skill_names()):
            self.skills_list.addItem(QListWidgetItem(s))
        form.addRow("Yetenekler:", self.skills_list)

        self.tools_combo = QComboBox()
        self.tools_combo.setEditable(True)
        for t in TOOLS_POLICIES:
            self.tools_combo.addItem(t)
        form.addRow("Araç politikası:", self.tools_combo)

        layout.addLayout(form)

        layout.addWidget(QLabel("Sistem yönergesi (markdown gövdesi):"))
        self.prompt_input = QPlainTextEdit()
        self.prompt_input.setPlaceholderText("Ajanın davranışını tanımlayan markdown metni…")
        self.prompt_input.setMinimumHeight(160)
        layout.addWidget(self.prompt_input)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        cancel_btn = QPushButton("İptal")
        cancel_btn.setAccessibleName("İptal")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)
        self.save_btn = QPushButton("Kaydet")
        self.save_btn.setAccessibleName("Kaydet")
        self.save_btn.clicked.connect(self._on_save)
        btn_box.addWidget(self.save_btn)
        layout.addLayout(btn_box)

        self._on_provider_changed(self.provider_combo.currentText())
        if spec is not None:
            self._prefill(spec)

    def _on_provider_changed(self, provider: str) -> None:
        current = self.model_combo.currentText()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for m in models_for_provider(provider, self.bridge):
            self.model_combo.addItem(m)
        if current and self.model_combo.findText(current) >= 0:
            self.model_combo.setCurrentText(current)
        self.model_combo.blockSignals(False)
        self._refresh_effort()

    def _on_model_changed(self, _model: str) -> None:
        self._refresh_effort()

    def _refresh_effort(self) -> None:
        combo = getattr(self, "effort_combo", None)
        if combo is None:
            return
        populate_effort_combo(
            combo,
            self.provider_combo.currentText().strip(),
            self.model_combo.currentText().strip(),
            self.bridge,
        )

    def effort_choices(self) -> List[str]:
        """Test için: efor kutusundaki seçenekler."""
        return [self.effort_combo.itemText(i) for i in range(self.effort_combo.count())
                if self.effort_combo.itemText(i)]

    def model_choices(self) -> List[str]:
        """Test için: kutudaki model adları."""
        return [self.model_combo.itemText(i) for i in range(self.model_combo.count())
                if self.model_combo.itemText(i)]

    def _prefill(self, spec: Any) -> None:
        self.name_input.setText(str(spec_field(spec, "name")))
        self.role_input.setText(str(spec_field(spec, "role")))
        self.description_input.setText(str(spec_field(spec, "description")))
        provider = str(spec_field(spec, "provider", "agy")) or "agy"
        if self.provider_combo.findText(provider) < 0:
            self.provider_combo.addItem(provider)
        self.provider_combo.setCurrentText(provider)
        model = str(spec_field(spec, "model"))
        if model:
            if self.model_combo.findText(model) < 0:
                self.model_combo.addItem(model)
            self.model_combo.setCurrentText(model)
        effort = str(spec_field(spec, "effort", "medium")) or "medium"
        if self.effort_combo.findText(effort) < 0:
            self.effort_combo.addItem(effort)
        self.effort_combo.setCurrentText(effort)
        policy = str(spec_field(spec, "tools_policy", "inherit")) or "inherit"
        if self.tools_combo.findText(policy) < 0:
            self.tools_combo.addItem(policy)
        self.tools_combo.setCurrentText(policy)
        self.prompt_input.setPlainText(str(spec_field(spec, "prompt")))
        selected = set(spec_field(spec, "skills", []) or [])
        for i in range(self.skills_list.count()):
            item = self.skills_list.item(i)
            if item.text() in selected:
                item.setSelected(True)
                selected.discard(item.text())
        for leftover in sorted(selected):
            item = QListWidgetItem(leftover)
            self.skills_list.addItem(item)
            item.setSelected(True)

    def _on_save(self) -> None:
        if not self.name_input.text().strip() or not self.role_input.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Ajan adı ve rol zorunludur.")
            return
        self.accept()

    def selected_skills(self) -> List[str]:
        return [i.text() for i in self.skills_list.selectedItems()]

    def get_data(self) -> Dict[str, Any]:
        """Sözleşmedeki AgentSpec alanlarına birebir karşılık gelen sözlük."""
        return {
            "name": self.name_input.text().strip(),
            "role": self.role_input.text().strip(),
            "description": self.description_input.text().strip(),
            "provider": self.provider_combo.currentText().strip(),
            "model": self.model_combo.currentText().strip(),
            "effort": self.effort_combo.currentText().strip(),
            "skills": self.selected_skills(),
            "tools_policy": self.tools_combo.currentText().strip(),
            "prompt": self.prompt_input.toPlainText(),
        }


class AssignTaskDialog(QDialog):
    """Bir ajana görev verme formu: başlık, hedef, kabul ölçütleri."""

    def __init__(self, parent=None, agent_name: str = "", skills: Optional[List[str]] = None,
                 provider: str = "", model: str = "", effort: str = "",
                 budget_tokens: int = 0, bridge=None):
        super().__init__(parent)
        self.agent_name = agent_name
        self.bridge = bridge
        self.setWindowTitle(f"Görev Ver — {agent_name}" if agent_name else "Görev Ver")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Kısa görev başlığı")
        form.addRow("Başlık:", self.title_input)

        self.skill_combo = QComboBox()
        self.skill_combo.addItem("")
        for s in (skills or []):
            self.skill_combo.addItem(s)
        form.addRow("Yetenek:", self.skill_combo)

        # Faz 7: görev başına sağlayıcı/model/efor/bütçe. Boş bırakılırsa ajanın
        # (ya da ofisin) varsayılanı geçerlidir; kullanıcı tek bir pahalı görev
        # için modeli değiştirmek isteyip ajan tanımını bozmak zorunda kalmasın.
        self.provider_combo = QComboBox()
        try:
            from entropy.core.provider import PROVIDERS as _PROVIDERS
        except Exception:
            _PROVIDERS = ("agy", "claude")
        self.provider_combo.addItem("")
        for p in _PROVIDERS:
            self.provider_combo.addItem(p)
        self.provider_combo.setCurrentText(provider or "")
        form.addRow("Sağlayıcı:", self.provider_combo)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setToolTip(
            "Model (boş = oturumun modelini miras al). Liste seçili sağlayıcıya göre değişir."
        )
        form.addRow("Model:", self.model_combo)
        # Faz 9: model listesi sağlayıcıya bağlı; sağlayıcı değişince tazelenir.
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self._on_provider_changed(self.provider_combo.currentText())
        self.model_combo.setCurrentText(model or "")

        self.effort_combo = QComboBox()
        self.effort_combo.addItem("")
        for e in EFFORT_LEVELS:
            self.effort_combo.addItem(e)
        self.effort_combo.setCurrentText(effort or "")
        form.addRow("Efor:", self.effort_combo)
        # HOTFIX v0.7.1: seçenekler sağlayıcı + modele bağlı.
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self._refresh_effort()

        self.budget_input = QLineEdit()
        self.budget_input.setPlaceholderText("0 = ofis bütçesi")
        self.budget_input.setText(str(int(budget_tokens or 0)))
        form.addRow("Bütçe (token):", self.budget_input)

        layout.addLayout(form)

        layout.addWidget(QLabel("Hedef:"))
        self.goal_input = QPlainTextEdit()
        self.goal_input.setMinimumHeight(90)
        layout.addWidget(self.goal_input)

        layout.addWidget(QLabel("Kabul ölçütleri (her satıra bir madde):"))
        self.criteria_input = QPlainTextEdit()
        self.criteria_input.setMinimumHeight(80)
        layout.addWidget(self.criteria_input)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)
        self.start_btn = QPushButton("Görevi Başlat")
        self.start_btn.setAccessibleName("Görevi Başlat")
        self.start_btn.clicked.connect(self._on_start)
        btn_box.addWidget(self.start_btn)
        layout.addLayout(btn_box)

    def _on_provider_changed(self, provider: str) -> None:
        """Sağlayıcıya ait model listesi; ilk giriş boş = 'oturumun modelini miras al'."""
        current = self.model_combo.currentText().strip()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem("")
        provider = (provider or "").strip()
        if provider:
            for m in models_for_provider(provider, self.bridge):
                self.model_combo.addItem(m)
        # Yeni sağlayıcıya ait olmayan bir ad seçiliyse boşa (miras) düşülür.
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
        populate_effort_combo(
            combo,
            self.provider_combo.currentText().strip(),
            self.model_combo.currentText().strip(),
            self.bridge,
            allow_empty=True,
        )

    def effort_choices(self) -> List[str]:
        """Test için: efor kutusundaki seçenekler (boş girdi hariç)."""
        return [self.effort_combo.itemText(i) for i in range(self.effort_combo.count())
                if self.effort_combo.itemText(i)]

    def model_choices(self) -> List[str]:
        """Test için: kutudaki adlar (baştaki boş girdi hariç)."""
        return [self.model_combo.itemText(i) for i in range(self.model_combo.count())
                if self.model_combo.itemText(i)]

    def _on_start(self) -> None:
        if not self.title_input.text().strip() or not self.goal_input.toPlainText().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Başlık ve hedef zorunludur.")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        criteria = [
            line.strip() for line in self.criteria_input.toPlainText().splitlines() if line.strip()
        ]
        try:
            budget = max(0, int(str(self.budget_input.text()).strip() or "0"))
        except ValueError:
            budget = 0
        data: Dict[str, Any] = {
            "title": self.title_input.text().strip(),
            "goal": self.goal_input.toPlainText().strip(),
            "criteria": criteria,
            "agent": self.agent_name,
            "skill": self.skill_combo.currentText().strip(),
            "budget_tokens": budget,
        }
        # Boş sağlayıcı/model, "ajanın varsayılanını kullan" demektir; sözlüğe
        # boş yazılırsa apply_task_assignment'taki setdefault devreye girmez.
        provider = self.provider_combo.currentText().strip()
        model = self.model_combo.currentText().strip()
        effort = self.effort_combo.currentText().strip()
        if provider:
            data["provider"] = provider
        if model:
            data["model"] = model
        if effort:
            # TaskCard'da efor alanı yok; not olarak taşınır ve köprü
            # istem başlığında görünür.
            data["effort"] = effort
            data["notes"] = f"effort: {effort}"
        return data


def discover_skill_names() -> List[str]:
    """SkillManager kataloğundaki yetenek adları; hata olursa boş liste."""
    try:
        from entropy.skills.manager import SkillManager

        return sorted({getattr(s, "name", "") for s in SkillManager().list_skills() if getattr(s, "name", "")})
    except Exception:
        return []


# ------------------------------------------------------------------ ana panel

class AgentCard(QFrame):
    """Tek ajan satırı: kimlik solda, ikon düğmeler sağda."""

    def __init__(self, spec: Any, panel: "AgentsWidget", parent=None):
        super().__init__(parent)
        self.spec = spec
        self.panel = panel
        self.agent_name = str(spec_field(spec, "name"))
        self.setObjectName("agentCard")
        self.setProperty("role", "panel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 10, 9)
        layout.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        # Okunakli tasarim sistemi: kart basligi 15 px, yardimci metin 12 px.
        title = QLabel(
            f"<span style='color:{RT['text']}; font-size:{BODY_STRONG_PX}px; font-weight:600;'>"
            f"{self.agent_name}</span>"
            f"<span style='color:{RT['text_dim']}; font-size:{LABEL_PX}px;'>  ·  "
            f"{spec_field(spec, 'role')}</span>"
        )
        title.setToolTip(f"{self.agent_name} ({spec_field(spec, 'role')})")
        text_col.addWidget(title)

        # Faz 7: orkestratörün kendi kurduğu ajanlar rozetle ayrılır; kullanıcı
        # kadroya kimin eklendiğini görsün (rozet düzenlemeyi engellemez).
        self.origin_badge: Optional[QLabel] = None
        try:
            created = panel.orchestrator_created_names()
        except Exception:
            created = set()
        if self.agent_name in created:
            self.origin_badge = QLabel(
                f"<span style='color:{RT['accent_alt']}; font-size:{LABEL_PX}px;'>"
                "orkestratör oluşturdu</span>"
            )
            self.origin_badge.setToolTip(
                "Bu ajanı ofisin orkestratörü tanımladı; düzenleyebilir ya da silebilirsiniz."
            )
            text_col.addWidget(self.origin_badge)

        provider = spec_field(spec, "provider", "agy") or "agy"
        # Model boş dizge olabilir (sağlayıcı varsayılanı kullanılıyor demektir).
        # spec_field yalnızca None/eksik alanda varsayılana düşer, bu yüzden boş
        # dizgede "agy / " gibi sarkan bir ayraç kalıyordu; burada kapatılır.
        model = spec_field(spec, "model", "") or ""
        effort = spec_field(spec, "effort", "") or ""
        meta_parts = [f"{provider} / {model}" if model else f"{provider} · varsayılan model"]
        if effort:
            meta_parts.append(f"efor {effort}")
        meta = QLabel(
            f"<span style='color:{RT['text_dim']}; font-size:{LABEL_PX}px;'>"
            f"{' · '.join(meta_parts)}</span>"
        )
        meta.setToolTip(' · '.join(meta_parts))
        text_col.addWidget(meta)

        # Ofis/rol rozeti (Faz 3): ajan bir ofise bağlıysa ve rolü varsa görünür.
        office_name = str(spec_field(spec, "office", "") or "")
        agent_role = str(spec_field(spec, "role", "") or "")
        badge_parts = []
        if office_name:
            badge_parts.append(
                f"<span style='background:{RT['accent_soft']}; color:{RT['accent']}; "
                f"font-size:11px; padding:1px 6px; border-radius:4px;'>{office_name}</span>"
            )
        if agent_role in ROLE_LABELS:
            color = ROLE_COLORS.get(agent_role, RT["text_dim"])
            badge_parts.append(
                f"<span style='background:{RT['surface_soft']}; color:{color}; "
                f"font-size:11px; padding:1px 6px; border-radius:4px;'>{ROLE_LABELS[agent_role]}</span>"
            )
        if badge_parts:
            self.office_badge = QLabel(" ".join(badge_parts))
            text_col.addWidget(self.office_badge)

        skills = list(spec_field(spec, "skills", []) or [])
        if skills:
            badges = " ".join(
                f"<span style='background:{RT['accent_soft']}; color:{RT['accent']}; "
                f"font-size:11px; padding:1px 6px; border-radius:4px;'>{s}</span>"
                for s in skills[:4]
            )
            if len(skills) > 4:
                badges += f" <span style='color:{RT['text_dim']}; font-size:11px;'>+{len(skills) - 4}</span>"
            text_col.addWidget(QLabel(badges))

        self.status_label = QLabel(self._status_html())
        text_col.addWidget(self.status_label)

        # Faz 11-C: kalıcı oturum rozeti + "Oturumu yenile".
        # Kullanıcı ajanın oturumunun sürüp sürmediğini hiçbir yerden
        # göremiyordu; imza değişince oturum sessizce sıfırlanıyordu.
        session_row = QHBoxLayout()
        session_row.setSpacing(4)
        self.session_icon = QLabel("")
        self.session_icon.setProperty("role", "badge")
        self.session_label = QLabel("")
        self.session_label.setProperty("role", "badge")
        session_row.addWidget(self.session_icon)
        session_row.addWidget(self.session_label)
        self.session_reset_btn = QPushButton("Oturumu yenile")
        self.session_reset_btn.setAccessibleName("Oturumu yenile")
        self.session_reset_btn.setProperty("variant", "ghost")
        self.session_reset_btn.setToolTip(
            "Kalıcı oturum kaydını siler; ajan bir sonraki koşuda temiz oturum açar."
        )
        self.session_reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.session_reset_btn.clicked.connect(self._reset_session)
        session_row.addWidget(self.session_reset_btn)
        session_row.addStretch()
        text_col.addLayout(session_row)
        self.refresh_session_badge()

        layout.addLayout(text_col, 1)

        buttons = [
            ("assign_btn", "▶", "Görev ver", self._assign),
            ("edit_btn", "", "Düzenle", self._edit),
            ("open_btn", "", "Tanım dosyasını aç", self._open_file),
            ("delete_btn", "", "Sil", self._delete),
        ]
        # Ofis kipinde (Agent Desk roster paneli) rol atama düğmeleri eklenir.
        if getattr(panel, "office", ""):
            buttons[1:1] = [
                ("make_orchestrator_btn", "", "Bu ofisin orkestratörü yap", self._make_orchestrator),
                ("make_evaluator_btn", "", "Bu ofisin değerlendiricisi yap", self._make_evaluator),
            ]
        # Dört düğme tek sıraya sığıyor; ofis kipinde altı düğme oluyor ve tek sıra
        # dar roster sütununda taşıp yatay kaydırma çubuğu çıkarıyordu. Altı
        # düğme 3x2 ızgaraya konur.
        if len(buttons) > 4:
            btn_host = QWidget()
            btn_grid = QGridLayout(btn_host)
            btn_grid.setContentsMargins(0, 0, 0, 0)
            btn_grid.setSpacing(4)
            layout.addWidget(btn_host)
        else:
            btn_grid = None

        for index, (attr, glyph, tip, handler) in enumerate(buttons):
            btn = QPushButton(glyph)
            btn.setProperty("role", "icon")
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(handler)
            if btn_grid is not None:
                btn_grid.addWidget(btn, index // 3, index % 3)
            else:
                layout.addWidget(btn)
            setattr(self, attr, btn)

    # ------------------------------------------------------- oturum rozeti

    def session_info(self) -> Optional[Dict[str, Any]]:
        """Ajanın kalıcı oturum kaydı (yoksa None). Test bunu ezebilir."""
        from entropy.ui.widgets.agent_session_badge import read_session

        return read_session(self.agent_name)

    def refresh_session_badge(self) -> None:
        """Rozeti diskteki tek kaynaktan tazeler; uydurma değer basmaz."""
        from entropy.ui.design import TOKENS, icon
        from entropy.ui.widgets.agent_session_badge import (
            session_badge_text, session_tooltip,
        )

        info = None
        try:
            info = self.session_info()
        except Exception:
            info = None
        text = session_badge_text(info)
        tone = "ok" if info else "warn"
        self.session_label.setText(text)
        self.session_label.setProperty("tone", tone)
        self.session_label.setToolTip(session_tooltip(info))
        color = TOKENS["color"]["ok" if info else "text.muted"]
        pixmap = icon("link" if info else "debug-disconnect", color=color).pixmap(12, 12)
        self.session_icon.setPixmap(pixmap)
        self.session_reset_btn.setEnabled(bool(info))
        # Özellik değişince QSS yeniden değerlendirilmeli (Qt kuralı).
        style = self.session_label.style()
        style.unpolish(self.session_label)
        style.polish(self.session_label)

    @Slot()
    def _reset_session(self):
        self.panel.reset_agent_session(self.agent_name)
        self.refresh_session_badge()

    def _status_html(self) -> str:
        card = self.panel.latest_card_for(self.agent_name)
        if card is None:
            return f"<span style='color:{RT['text_dim']}; font-size:11px;'>son görev yok</span>"
        status = str(spec_field(card, "status", "backlog"))
        color = STATUS_COLORS.get(status, RT["text_dim"])
        title = spec_field(card, "title", "")
        return (
            f"<span style='color:{RT['text_dim']}; font-size:11px;'>son görev: {title} · </span>"
            f"<span style='color:{color}; font-size:11px; font-weight:600;'>"
            f"{STATUS_LABELS.get(status, status)}</span>"
        )

    @Slot()
    def _assign(self):
        self.panel.assign_task(self.agent_name)

    @Slot()
    def _edit(self):
        self.panel.edit_agent(self.spec)

    @Slot()
    def _open_file(self):
        self.panel.open_agent_file(self.spec)

    @Slot()
    def _delete(self):
        self.panel.delete_agent(self.agent_name)

    @Slot()
    def _make_orchestrator(self):
        self.panel.assign_office_role(self.agent_name, "orchestrator")

    @Slot()
    def _make_evaluator(self):
        self.panel.assign_office_role(self.agent_name, "evaluator")


# Faz 11-C: pano durum makinesinin 8 durumu (`agents/board_fsm.STATUSES`).
STATUS_LABELS = {
    "backlog": "Bekliyor",
    "assigned": "Atandı",
    "taken": "Sahiplenildi",
    "running": "Çalışıyor",
    "review": "İnceleme",
    "done": "Bitti",
    "failed": "Başarısız",
    "canceled": "İptal",
}

STATUS_COLORS = {
    "backlog": RT["text_dim"],
    "assigned": RT["accent_alt"],
    "taken": RT["accent"],
    "running": RT["accent"],
    "review": RT["accent_warn"],
    "done": RT["accent_alt"],
    "failed": "#FF6B6B",
    "canceled": RT["text_dim"],
}


class AgentsWidget(QFrame):
    """Ajan kayıt defterinin okunaklı listesi ve yönetim eylemleri."""

    def __init__(
        self,
        parent=None,
        registry: Any = None,
        board: Any = None,
        bridge=None,
        compact: bool = False,
        office: str = "",
        office_registry: Any = None,
    ):
        """
        `office` verilirse panel yalnızca o ofisin ajanlarını gösterir (Agent Desk
        roster paneli) ve yeni ajanlar o ofise yazılır. Boşsa eski davranış: tüm
        kayıt defteri.
        """
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.registry = registry if registry is not None else load_registry()
        self.board = board if board is not None else load_board()
        self.bridge = bridge
        self.compact = compact
        self.office = office or ""
        self.office_registry = office_registry
        self.cards: List[AgentCard] = []
        self._card_cache: List[Any] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.title_label = QLabel(
            f"<b style='color:{RT['accent']}; font-size:13px;'>AJANLAR</b>"
            if not self.office
            else f"<b style='color:{RT['accent']}; font-size:13px;'>KADRO</b>"
            f" <span style='color:{RT['text_dim']}; font-size:11px;'>{self.office}</span>"
        )
        self.title_label.setProperty("role", "label")
        header.addWidget(self.title_label)
        header.addStretch()
        self.add_btn = QPushButton("+ Yeni Ajan")
        self.add_btn.setAccessibleName("+ Yeni Ajan")
        self.add_btn.setToolTip("Kayıt defterine yeni alt ajan ekle")
        self.add_btn.clicked.connect(self.create_agent)
        header.addWidget(self.add_btn)

        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.setAccessibleName("Yenile")
        self.refresh_btn.setToolTip("Kayıt defterini diskten yeniden oku")
        self.refresh_btn.clicked.connect(self.refresh_agents)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)

        self.empty_label = QLabel("")
        self.empty_label.setWordWrap(True)
        self.empty_label.setProperty("role", "label")
        layout.addWidget(self.empty_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Faz 2 kozmetik notu: liste kısa olduğunda altta beyaz bir şerit kalıyordu.
        # Sebebi QScrollArea'nın görünüm alanı (viewport) ve içerik widget'ının
        # kendi paletlerini kullanması; yalnızca QScrollArea'ya stil vermek
        # yetmiyor. Görünüm alanı da saydam yapılır ve otomatik dolgu kapatılır.
        scroll.viewport().setAutoFillBackground(False)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Faz 4: saydamlık tek başına yetmiyordu — kapsayıcı stil sayfası
        # değişince görünüm alanı yeniden sistem paletine (beyaz) düşüyordu.
        # Palet doğrudan koyu yüzeye sabitlenir; stil sayfasından bağımsız.
        _paint_dark(scroll.viewport())
        _paint_dark(scroll)
        # Kartlar sütun genişliğine uyar; yatay çubuk yalnızca listenin altında
        # boşluk yaratıyordu.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_container = QWidget()
        self.list_container.setAutoFillBackground(False)
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_container)
        layout.addWidget(scroll, 1)

        # Sözleşme sinyalleri başka bir ajan tarafından ekleniyor; yoksa atla.
        for signal_name in ("agents_updated", "task_cards_updated"):
            signal = getattr(bus, signal_name, None)
            if signal is not None:
                signal.connect(self._on_bus_refresh)

        self.refresh_agents()

    # ------------------------------------------------------------ veri

    def list_agents(self) -> List[Any]:
        if self.registry is None:
            return []
        try:
            agents = list(self.registry.list() or [])
        except Exception:
            return []
        if not self.office:
            # Faz 9 / B-9.5: Entropy kipinde YALNIZCA Entropy kadrosu görünür.
            # `registry` (AgentRegistry) artık Desk yollarını dışlıyor; yine de
            # `office` alanı dolu bir kayıt (elle düzenleme, eski sürüm kalıntısı
            # ya da testin verdiği birleşik defter) sızabilir. Entropy'nin ajan
            # formunda Desk ajanı görünürse kullanıcı ona görev verir, kart
            # yanlış köke yazılırdı.
            return [a for a in agents if not str(spec_field(a, "office", "")).strip()]
        # Ofis süzgeci iki kaynağı birleştirir: ajanın kendi `office` alanı ve
        # ofisin `members` listesi. Yalnızca birine bakılsaydı, dosyayı elle
        # düzenleyen kullanıcı (ya da henüz `office` yazmayan bir sürüm) ajanı
        # roster'da göremezdi.
        members = set(self.office_members())
        return [
            a for a in agents
            if str(spec_field(a, "office", "")) == self.office
            or str(spec_field(a, "name", "")) in members
        ]

    def office_members(self) -> List[str]:
        """Seçili ofisin üye listesi (ofis kaydı yoksa boş)."""
        office = self.current_office_spec()
        if office is None:
            return []
        return [str(m) for m in (spec_field(office, "members", []) or [])]

    def current_office_spec(self) -> Optional[Any]:
        if not self.office:
            return None
        registry = self.office_registry
        if registry is None:
            try:
                from entropy.agents.offices import OfficeRegistry  # type: ignore

                registry = OfficeRegistry()
                self.office_registry = registry
            except Exception:
                return None
        try:
            return registry.get(self.office)
        except Exception:
            return None

    def set_office(self, office: str) -> None:
        self.office = office or ""
        title = getattr(self, "title_label", None)
        if title is not None:
            title.setText(
                f"<b style='color:{RT['accent']}; font-size:13px;'>KADRO</b>"
                f" <span style='color:{RT['text_dim']}; font-size:11px;'>{self.office}</span>"
                if self.office
                else f"<b style='color:{RT['accent']}; font-size:13px;'>AJANLAR</b>"
            )
        self.refresh_agents()

    @staticmethod
    def _update_office(registry: Any, office: Any, changes: Dict[str, Any]) -> Any:
        """
        Ofis kaydını günceller; veri sınıfı ve sözlük sözleşmelerinin ikisini de
        karşılar. Gerçek `OfficeRegistry.update(OfficeSpec)` bekler; sahte/esnek
        uygulamalar sözlük alır.
        """
        if hasattr(office, "__dataclass_fields__"):
            from dataclasses import replace

            return registry.update(replace(office, **changes))
        payload = dict(office) if isinstance(office, dict) else {}
        payload.update(changes)
        office_obj = build_dataclass("entropy.agents.offices", "OfficeSpec", payload)
        return call_contract(registry.update, payload, office_obj)

    def ensure_office_member(self, agent_name: str) -> bool:
        """Ajanı seçili ofisin üye listesine ekler (zaten üyeyse dokunmaz)."""
        if not agent_name or not self.office:
            return False
        office = self.current_office_spec()
        registry = self.office_registry
        if office is None or registry is None:
            return False
        members = [str(m) for m in (spec_field(office, "members", []) or [])]
        if agent_name in members:
            return True
        members.append(agent_name)
        try:
            self._update_office(registry, office, {"members": members})
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Roster] Ofis üyesi eklenemedi: {exc}\n")
            return False
        signal = getattr(bus, "offices_updated", None)
        if signal is not None:
            signal.emit(self.office)
        self.refresh_agents()
        return True

    def assign_office_role(self, agent_name: str, role: str) -> bool:
        """
        Ajanı bu ofisin orkestratörü/değerlendiricisi yapar.

        İki yer güncellenir: ofis kaydı (orchestrator/evaluator alanı) ve ajanın
        kendi `role` alanı. Sahne ve harness ofis kaydını, ajan derlemesi ise
        `role`'ü okuyor; ikisi ayrışırsa sahne ile gerçek koşu birbirini tutmaz.
        """
        if role not in ("orchestrator", "evaluator") or not self.office:
            return False
        office = self.current_office_spec()
        registry = self.office_registry
        if office is None or registry is None:
            return False
        members = [str(m) for m in (spec_field(office, "members", []) or [])]
        if agent_name not in members:
            members.append(agent_name)
        try:
            self._update_office(registry, office, {role: agent_name, "members": members})
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Roster] Rol atanamadı: {exc}\n")
            return False

        # Ajanın kendi rol alanını da güncelle (sözleşme: AgentSpec.role).
        try:
            spec = None
            for candidate in (self.registry.list() or []):
                if str(spec_field(candidate, "name", "")) == agent_name:
                    spec = candidate
                    break
            if spec is not None:
                if hasattr(spec, "__dataclass_fields__"):
                    from dataclasses import replace

                    self.registry.update(replace(spec, role=role, office=self.office))
                else:
                    payload = dict(spec) if isinstance(spec, dict) else {"name": agent_name}
                    payload.update({"name": agent_name, "role": role, "office": self.office})
                    call_contract(self.registry.update, payload, None)
        except Exception:
            pass

        self.refresh_agents()
        for signal_name, payload_value in (("offices_updated", self.office), ("agents_updated", agent_name)):
            signal = getattr(bus, signal_name, None)
            if signal is not None:
                signal.emit(payload_value)
        return True

    def _reload_cards(self) -> None:
        """
        Kart önbelleği (ajan kartındaki "son görev" satırı).

        Faz 9: ofis kipindeki kadro paneli ofis köküne, Entropy kipi Entropy
        köküne bakar. Ofis geçilmezse Desk kadrosu hiçbir kart göremezdi.
        """
        self._card_cache = list_cards_for(self.board, self.office)

    def latest_card_for(self, agent_name: str) -> Optional[Any]:
        """Ajana ait en son görev kartı (created_at sırasına göre)."""
        owned = [c for c in self._card_cache if str(spec_field(c, "agent", "")) == agent_name]
        if not owned:
            return None
        return sorted(owned, key=lambda c: str(spec_field(c, "created_at", "")))[-1]

    def _on_bus_refresh(self, _payload: str = "") -> None:
        """Sinyal alıcısı QObject metodudur (lambda değil): doğrudan bağlantı güvenli."""
        self.refresh_agents()

    @Slot()
    def refresh_agents(self) -> None:
        self._reload_cards()
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.cards = []

        agents = self.list_agents()
        if not agents:
            if self.registry is None:
                message = "Ajan kayıt defteri modülü henüz yüklenemedi (entropy.agents.registry)."
            elif self.office:
                message = f"'{self.office}' ofisinde ajan yok. “+ Yeni Ajan” ile ekleyin."
            else:
                message = "Kayıtlı ajan yok. “+ Yeni Ajan” ile bir alt ajan tanımlayın."
            self.empty_label.setText(message)
            self.empty_label.setVisible(True)
            return
        self.empty_label.setVisible(False)
        for spec in agents:
            card = AgentCard(spec, self)
            self.cards.append(card)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)

    # ------------------------------------------------------------ eylemler

    @Slot()
    def create_agent(self) -> None:
        dialog = AgentEditDialog(parent=self, bridge=self.bridge)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if self.office:
            # Roster panelinden eklenen ajan doğrudan bu ofisin üyesi olur.
            data.setdefault("office", self.office)
            data["office"] = self.office
        if self.office and self._create_office_member(data):
            self.ensure_office_member(str(data.get("name", "")))
            return
        if self.apply_agent_save(data, original_name=None) and self.office:
            self.ensure_office_member(str(data.get("name", "")))

    def _create_office_member(self, data: Dict[str, Any]) -> bool:
        """
        Yeni ajanı ofisin KENDİ `agents/` klasörüne yazar (Faz 7).

        `DeskRegistry.create_member` varsa o kullanılır (dosyayı yazar ve ofis
        çalışma dizinine derler); yoksa False dönülür ve çağıran genel
        `DeskAgentsView` yoluna düşer.
        """
        name = str(data.get("name", "")).strip()
        if not name:
            return False
        try:
            from entropy.agents.desk_registry import DeskRegistry  # type: ignore

            desk = DeskRegistry()
            creator = getattr(desk, "create_member", None)
            if creator is None:
                return False
            spec = creator(
                self.office,
                name,
                role=str(data.get("role", "worker") or "worker"),
                description=str(data.get("description", "")),
                provider=str(data.get("provider", "")),
                model=str(data.get("model", "")),
                tools_policy=str(data.get("tools_policy", "read-write") or "read-write"),
                prompt=str(data.get("prompt", "")),
            )
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Roster] Ofis üyesi yazılamadı: {exc}\n")
            return False
        if spec is None:
            return False
        self.refresh_agents()
        signal = getattr(bus, "agents_updated", None)
        if signal is not None:
            signal.emit(name)
        return True

    def orchestrator_created_names(self) -> set:
        """
        Orkestratörün kendi kurduğu ajanların adları.

        Provenance alanı sözleşmede yok; çıkarım şu: ofisin `agents/` klasöründe
        DOSYASI olan ama ofisin `members` ön bilgisinde YER ALMAYAN ajanı
        kullanıcı eklemedi — arayüzden eklenen ajan `ensure_office_member` ile
        listeye yazılır, orkestratörün `new_agents` yolu yazmaz.
        """
        if not self.office:
            return set()
        members = set(self.office_members())
        office = self.current_office_spec()
        for key in ("orchestrator", "evaluator"):
            value = str(spec_field(office, key, "")) if office is not None else ""
            if value:
                members.add(value)
        out = set()
        for spec in self.list_agents():
            name = str(spec_field(spec, "name", ""))
            if name and name not in members:
                out.add(name)
        return out

    def edit_agent(self, spec: Any) -> None:
        dialog = AgentEditDialog(parent=self, spec=spec, bridge=self.bridge)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.apply_agent_save(dialog.get_data(), original_name=str(spec_field(spec, "name")))

    def apply_agent_save(self, data: Dict[str, Any], original_name: Optional[str]) -> bool:
        """Diyalogsuz kayıt yolu (test edilebilir): create veya update çağırır."""
        if self.registry is None:
            return False
        spec_obj = build_dataclass("entropy.agents.registry", "AgentSpec", data)
        try:
            if original_name:
                call_contract(self.registry.update, data, spec_obj, original_name)
                # Ad değiştiyse eski tanım dosyası artık sahipsiz kalır.
                if data.get("name") and data["name"] != original_name:
                    try:
                        self.registry.delete(original_name)
                    except Exception:
                        pass
            else:
                call_contract(self.registry.create, data, spec_obj)
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Ajanlar] Kayıt hatası: {exc}\n")
            return False
        self.refresh_agents()
        signal = getattr(bus, "agents_updated", None)
        if signal is not None:
            signal.emit(data.get("name", ""))
        return True

    def reset_agent_session(self, name: str) -> bool:
        """
        Ajanın kalıcı oturum dosyasını siler ("Oturumu yenile").

        Sözleşme dosyası `Entropy/Board/agents/<ad>/session.json`; silinince
        ajan bir sonraki koşuda yeni oturum açar. Dosya zaten yoksa False.
        """
        from entropy.ui.widgets.agent_session_badge import clear_session

        removed = clear_session(name)
        if removed:
            bus.terminal_output_received.emit(
                f"[Ajanlar] '{name}' kalıcı oturumu silindi; sonraki koşu temiz başlar.\n"
            )
        return removed

    def delete_agent(self, name: str, confirm: bool = True) -> bool:
        if self.registry is None:
            return False
        if confirm:
            answer = QMessageBox.question(
                self, "Ajanı Sil",
                f"'{name}' ajanı ve tanım dosyası silinsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        try:
            self.registry.delete(name)
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Ajanlar] Silme hatası: {exc}\n")
            return False
        self.refresh_agents()
        signal = getattr(bus, "agents_updated", None)
        if signal is not None:
            signal.emit(name)
        return True

    def assign_task(self, agent_name: str) -> None:
        spec = None
        for candidate in self.list_agents():
            if str(spec_field(candidate, "name")) == agent_name:
                spec = candidate
                break
        skills = list(spec_field(spec, "skills", []) or []) if spec is not None else []
        dialog = AssignTaskDialog(
            parent=self,
            agent_name=agent_name,
            skills=skills,
            provider=str(spec_field(spec, "provider", "")) if spec is not None else "",
            model=str(spec_field(spec, "model", "")) if spec is not None else "",
            effort=str(spec_field(spec, "effort", "")) if spec is not None else "",
            bridge=self.bridge,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.apply_task_assignment(dialog.get_data(), spec)

    def apply_task_assignment(self, data: Dict[str, Any], spec: Any = None) -> Optional[Any]:
        """Görev kartını oluşturur ve hemen çalıştırır."""
        if self.board is None:
            return None
        payload = dict(data)
        if spec is not None:
            payload.setdefault("provider", str(spec_field(spec, "provider", "")))
            payload.setdefault("model", str(spec_field(spec, "model", "")))
        card_obj = build_dataclass("entropy.agents.tasks", "TaskCard", payload)
        try:
            card = call_contract(self.board.create, payload, card_obj)
            card_id = spec_field(card, "id", "") or payload.get("title", "")
            self.board.run(card_id)
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Ajanlar] Görev başlatılamadı: {exc}\n")
            return None
        self.refresh_agents()
        signal = getattr(bus, "task_cards_updated", None)
        if signal is not None:
            signal.emit(str(spec_field(card, "id", "")))
        return card

    def open_agent_file(self, spec: Any) -> bool:
        path_str = str(spec_field(spec, "path", ""))
        if not path_str:
            return False
        path = Path(path_str)
        if not path.exists():
            bus.terminal_output_received.emit(f"[Ajanlar] Dosya bulunamadı: {path}\n")
            return False
        # Faz 9: eskiden burada `bus.report_created` yayiliyordu. O sinyal
        # "yeni arastirma raporu uretildi ve bellege islendi" anlamina gelir;
        # sohbete "Yeni Arastirma Raporu: AGENT / RAG'a islendi" sahte karti
        # basiyor, bildirim uretiyor ve bilgi grafigini bastan kuruyordu.
        # Ajan dosyasi acmak bir rapor uretimi degildir: yalnizca okuyucu acilir.
        try:
            from entropy.ui.widgets.standalone_report_window import (
                open_standalone_report_window,
            )

            open_standalone_report_window(str(path))
        except Exception:
            bus.terminal_output_received.emit(f"[Ajanlar] Dosya: {path}\n")
        return True
