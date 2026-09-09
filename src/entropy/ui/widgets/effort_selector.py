"""Efor (düşünme çabası) seçici — Faz 6, HOTFIX v0.7.1.

Köprü sözleşmesi:
    bridge.effort_levels() -> list[str]
    bridge.selected_effort -> str
    bridge.set_effort(level) -> bool | None   (isteğe bağlı)

HOTFIX v0.7.1: efor seviyeleri artık SAĞLAYICI ve MODEL'e bağlı.
  * claude → CLI `--effort` bayrağı: low|medium|high|xhigh|max
  * agy    → efor bayrağı DEĞİL, model adının bir parçası
    (`gemini-3.8-flash-high`). `--model …-high` ile `--effort medium`
    birlikte verilince CLI "conflicts with" hatası veriyordu. Bu yüzden
    agy'de efor kutusu model adının son ekini sürer: seçim değişince
    model adı yeniden kurulur (`compose_agy_model`) ve model kutusu
    güncellenir.

`entropy.core.provider` bu yardımcıları sağlıyorsa onlar kullanılır
(`getattr` ile), yoksa buradaki yerel yedek çalışır.

Sinyal alıcısı lambda değil, QObject metodudur.
"""

from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QComboBox, QWidget

EFFORT_COMBO_STYLE = """
    QComboBox {
        background-color: #0E1420;
        color: #FFB300;
        border: 1px solid #1F2B42;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 10px;
        font-weight: bold;
    }
    QComboBox:hover { border-color: #FFB300; }
    QComboBox:disabled { color: #5A6474; border-color: #161E2C; }
    QComboBox::drop-down { border: none; width: 16px; }
    QComboBox QAbstractItemView {
        background-color: #0E1420;
        color: #F0F6FC;
        border: 1px solid #FFB300;
        selection-background-color: #1F2B42;
        selection-color: #FFB300;
    }
"""

# Yerel yedek seviye kümeleri (core sözleşmesi yoksa).
CLAUDE_EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"]
#: agy model adlarında geçerli efor son ekleri; sıra kutuda görünen sıradır.
AGY_EFFORT_SUFFIXES = ("low", "medium", "high")

NO_EFFORT_HINT = "Bu modelde efor seçimi yok"
AGY_EFFORT_HINT = (
    "agy'de efor model adına gömülüdür; seçim model adının son ekini değiştirir."
)
CLAUDE_EFFORT_HINT = "Modelin düşünme/çaba düzeyi (--effort). Seçim kalıcıdır."


# --------------------------------------------------------------- sözleşme köprüsü

def _core_fn(name: str):
    """`entropy.core.provider` içindeki yardımcıyı (varsa) döner."""
    try:
        from entropy.core import provider as _provider
    except Exception:
        return None
    fn = getattr(_provider, name, None)
    return fn if callable(fn) else None


def split_agy_model(name: str) -> Tuple[str, Optional[str]]:
    """`gemini-3.8-flash-high` → `("gemini-3.8-flash", "high")`; son ek yoksa (ad, None)."""
    fn = _core_fn("split_agy_model")
    if fn is not None:
        try:
            base, effort = fn(name)
            return str(base or ""), (str(effort) if effort else None)
        except Exception:
            pass
    text = (name or "").strip()
    for suffix in AGY_EFFORT_SUFFIXES:
        tail = "-" + suffix
        if text.lower().endswith(tail) and len(text) > len(tail):
            return text[: -len(tail)], suffix
    return text, None


def compose_agy_model(base: str, effort: str) -> str:
    """Taban model + efor → tam agy model adı."""
    fn = _core_fn("compose_agy_model")
    if fn is not None:
        try:
            return str(fn(base, effort))
        except Exception:
            pass
    base = (base or "").strip()
    effort = (effort or "").strip()
    if not effort:
        return base
    return f"{base}-{effort}" if base else base


def known_agy_models(bridge=None) -> List[str]:
    """Canlı `agy models` listesi (kota harcamaz; yapılandırmadan okunur)."""
    models: List[str] = []
    try:
        from entropy.core.config import config

        models = [str(m) for m in (getattr(config, "available_models", []) or []) if m]
    except Exception:
        models = []
    if not models and bridge is not None and getattr(bridge, "provider_name", "") == "agy":
        try:
            models = [str(m) for m in (bridge.fetch_available_models() or []) if m]
        except Exception:
            models = []
    return models


def effort_levels_for(
    provider: str,
    model: str = "",
    bridge=None,
    models: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    Sağlayıcı + model için geçerli efor seçenekleri.

    claude → sabit beş seviye. agy → model adının son eki varsa, aynı taban
    model için canlı listede bulunan son ekler; son ek yoksa boş liste
    (kutu pasif olur). Model adı hiç bilinmiyorsa köprünün kendi
    `effort_levels()` listesine düşülür.
    """
    provider = (provider or "").strip().lower()
    model = (model or "").strip()

    # Model adı hiç bilinmiyorsa (test köprüleri, model seçilmemiş oturum)
    # sağlayıcıya özgü çıkarım yapılamaz; köprünün kendi listesi geçerlidir.
    if provider == "agy" and not model:
        return _bridge_levels(bridge)

    fn = _core_fn("effort_levels_for")
    if fn is not None:
        try:
            if models is not None:
                return [str(x) for x in (fn(provider, model, list(models)) or [])]
            return [str(x) for x in (fn(provider, model) or [])]
        except TypeError:
            try:
                return [str(x) for x in (fn(provider, model) or [])]
            except Exception:
                pass
        except Exception:
            pass

    if provider == "claude":
        return list(CLAUDE_EFFORT_LEVELS)

    if provider == "agy":
        if not model:
            return _bridge_levels(bridge)
        base, suffix = split_agy_model(model)
        if not suffix:
            return []
        catalog = list(models) if models is not None else known_agy_models(bridge)
        found = []
        for candidate in catalog:
            c_base, c_suffix = split_agy_model(str(candidate))
            if c_suffix and c_base.lower() == base.lower() and c_suffix not in found:
                found.append(c_suffix)
        ordered = [s for s in AGY_EFFORT_SUFFIXES if s in found]
        return ordered or [suffix]

    return _bridge_levels(bridge)


def _bridge_levels(bridge) -> List[str]:
    getter = getattr(bridge, "effort_levels", None)
    if not callable(getter):
        return []
    try:
        return [str(x) for x in (getter() or [])]
    except Exception:
        return []


def effort_help_text(provider: str, model: str = "", bridge=None) -> str:
    """`/effort` yardımı ve ipuçları için sağlayıcıya göre seviye cümlesi."""
    provider = (provider or "").strip().lower()
    levels = effort_levels_for(provider, model, bridge)
    if provider == "agy":
        if not levels:
            return (
                f"agy: '{model or 'bu model'}' için efor seçimi yok "
                "(efor model adına gömülüdür)."
            )
        return (
            "agy: efor model adının son ekidir — "
            + " | ".join(levels)
            + " (seçim model adını değiştirir)."
        )
    if not levels:
        return NO_EFFORT_HINT
    return "claude: /effort " + " | ".join(levels)


def bridge_supports_effort(bridge) -> bool:
    """Köprü efor sözleşmesini uyguluyor mu?"""
    return bool(_bridge_levels(bridge))


# --------------------------------------------------------------------- widget

class EffortSelector(QComboBox):
    """Model kutusunun yanındaki küçük 'Efor' kutusu (sağlayıcı+model bağlı)."""

    def __init__(self, bridge, parent: Optional[QWidget] = None,
                 model_combo: Optional[QComboBox] = None):
        super().__init__(parent)
        self.bridge = bridge
        self.model_combo = model_combo
        self._applying = False
        self.setObjectName("effortCombo")
        self.setStyleSheet(EFFORT_COMBO_STYLE)
        self.setFixedHeight(24)
        self.currentTextChanged.connect(self._on_effort_changed)
        self.refresh()

    # -- durum ------------------------------------------------------------
    def _provider(self) -> str:
        return str(getattr(self.bridge, "provider_name", "") or "")

    def _model(self) -> str:
        if self.model_combo is not None:
            text = self.model_combo.currentText().strip()
            if text:
                return text
        return str(getattr(self.bridge, "selected_model", "") or "")

    def levels(self) -> List[str]:
        """Test için: kutudaki seçenekler."""
        return [self.itemText(i) for i in range(self.count()) if self.itemText(i)]

    @Slot()
    def refresh(self) -> None:
        """Sağlayıcı/model değişince kutuyu yeniden doldurur (döngüsüz)."""
        provider = self._provider()
        model = self._model()
        levels = effort_levels_for(provider, model, self.bridge)

        current = ""
        if provider == "agy":
            _, suffix = split_agy_model(model)
            current = suffix or ""
        if not current:
            current = str(getattr(self.bridge, "selected_effort", "") or "")

        self._applying = True
        try:
            self.clear()
            self.addItems(levels)
            if current in levels:
                self.setCurrentIndex(levels.index(current))
        finally:
            self._applying = False

        self.setEnabled(bool(levels))
        if not levels:
            self.setToolTip(NO_EFFORT_HINT)
        elif provider == "agy":
            self.setToolTip(AGY_EFFORT_HINT)
        else:
            self.setToolTip(CLAUDE_EFFORT_HINT)

        from entropy.ui.widgets.flow_layout import fit_combo_to_contents

        fit_combo_to_contents(self, min_width=70)

    # -- seçim ------------------------------------------------------------
    @Slot(str)
    def _on_effort_changed(self, level: str):
        level = (level or "").strip()
        if not level or self._applying:
            return
        # agy'de efor model adının son eki; ancak model adı bilinmiyorsa
        # (son eksiz/boş) köprünün kendi efor yolu kullanılır.
        if self._provider() == "agy" and split_agy_model(self._model())[1]:
            self._apply_agy_effort(level)
            return
        self._apply_bridge_effort(level)

    def _apply_agy_effort(self, level: str) -> None:
        """agy: efor model adının son eki — model adını yeniden kurar."""
        model = self._model()
        base, suffix = split_agy_model(model)
        if not suffix or suffix == level:
            return
        new_model = compose_agy_model(base, level)
        setter = getattr(self.bridge, "set_model", None)
        if callable(setter):
            try:
                if setter(new_model) is False:
                    self.refresh()
                    return
            except Exception:
                return
        else:
            try:
                self.bridge.selected_model = new_model
            except Exception:
                return
        if self.model_combo is not None:
            self.model_combo.blockSignals(True)
            try:
                if self.model_combo.findText(new_model) < 0:
                    self.model_combo.addItem(new_model)
                self.model_combo.setCurrentText(new_model)
            finally:
                self.model_combo.blockSignals(False)

    def _apply_bridge_effort(self, level: str) -> None:
        setter = getattr(self.bridge, "set_effort", None)
        if callable(setter):
            try:
                setter(level)
                return
            except Exception:
                pass
        # Köprüde set_effort yoksa alanı doğrudan yaz ve yapılandırmayı kaydet.
        try:
            self.bridge.selected_effort = level
            from entropy.core.config import config

            provider = self._provider() or "agy"
            if isinstance(getattr(config, "provider_effort", None), dict):
                config.provider_effort[provider] = level
                config.save_settings()
        except Exception:
            pass


def install_effort_selector(layout, bridge, parent: Optional[QWidget] = None,
                            model_combo: Optional[QComboBox] = None) -> Optional[EffortSelector]:
    """
    Efor kutusunu (destekleniyorsa) verilen düzene ekler; yoksa None döner.

    "Destek" ölçütü köprünün efor sözleşmesi; agy'de model adında efor son eki
    olması da yeterlidir (kutu o zaman son eki sürer).
    """
    provider = str(getattr(bridge, "provider_name", "") or "")
    model = str(getattr(bridge, "selected_model", "") or "")
    supported = bridge_supports_effort(bridge) or bool(
        effort_levels_for(provider, model, bridge)
    )
    if not supported:
        return None
    combo = EffortSelector(bridge, parent, model_combo=model_combo)
    layout.addWidget(combo)
    return combo
