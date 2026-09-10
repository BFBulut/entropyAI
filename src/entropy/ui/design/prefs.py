"""Arayüz tercihleri — tema, yoğunluk ve yerleşim kalıcılığı (`QSettings`).

Faz 12-D.2 (denetim D12-07 "bölücü konumu kalıcı değil", D12-08 "açık tema ve
rahat yoğunluk ölü özellik"). Bu değerler **çekirdek yapılandırmaya değil**
`QSettings`'e yazılır: yerleşim tercihi kullanıcının o makinedeki penceresine
aittir, ajanların/otomasyonun okuduğu `config` sözleşmesine değil.

`QSettings` kökü: `Entropy/EntropyAI` (test yalıtımı için
`QSettings.setDefaultFormat` + `setPath` değil, `_settings_factory` kancası
kullanılır; testler kendi geçici INI dosyalarını verir).
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional

__all__ = [
    "THEMES",
    "DENSITIES",
    "settings",
    "set_settings_factory",
    "ui_theme",
    "ui_density",
    "set_ui_theme",
    "set_ui_density",
    "zen_core_visible",
    "set_zen_core_visible",
    "section_expanded",
    "set_section_expanded",
    "save_splitter",
    "install_splitter_persistence",
    "restore_splitter",
    "reset_layout",
]

THEMES = ("dark", "light")
DENSITIES = ("compact", "comfortable")

ORGANIZATION = "Entropy"
APPLICATION = "EntropyAI"

_factory: Optional[Callable[[], object]] = None


def set_settings_factory(factory: Optional[Callable[[], object]]) -> None:
    """Test kancası: `QSettings` yerine geçici bir depo döndüren üretici."""
    global _factory
    _factory = factory


def settings():
    """Uygulama `QSettings` nesnesi (ana iş parçacığından çağrılır)."""
    if _factory is not None:
        return _factory()
    from PySide6.QtCore import QSettings

    return QSettings(ORGANIZATION, APPLICATION)


def _get(key: str, default: str) -> str:
    try:
        value = settings().value(key, default)
    except Exception:
        return default
    return str(value) if value not in (None, "") else default


def ui_theme() -> str:
    value = _get("ui/theme", "dark")
    return value if value in THEMES else "dark"


def ui_density() -> str:
    value = _get("ui/density", "compact")
    return value if value in DENSITIES else "compact"


def set_ui_theme(theme: str) -> str:
    if theme not in THEMES:
        raise ValueError(f"bilinmeyen tema: {theme!r}")
    settings().setValue("ui/theme", theme)
    return theme


def set_ui_density(density: str) -> str:
    if density not in DENSITIES:
        raise ValueError(f"bilinmeyen yoğunluk: {density!r}")
    settings().setValue("ui/density", density)
    return density


def zen_core_visible() -> bool:
    """Zen sohbet bölgesindeki çekirdek görselleştirici görünür mü (varsayılan: evet).

    Faz 13 (kullanıcı geri bildirimi): 11-E'de çekirdek 24 px'lik bir duruma
    noktasına indirilmişti; kullanıcı "çekirdek görseli gitmiş" dedi. Geri
    getirildi ve **gizleme** buradan ayarlanır; varsayılan görünür.
    """
    return _get("ui/zen_core_visible", "1") not in ("0", "false", "False")


def set_zen_core_visible(visible: bool) -> bool:
    settings().setValue("ui/zen_core_visible", "1" if visible else "0")
    return bool(visible)


def section_expanded(name: str, default: bool = True) -> bool:
    """Katlanabilir bir bölümün açık/kapalı durumu (ui-design §0.9).

    Faz 13-A2 madde 6: Görevler ekranı üç bölüm birden gösterdiği için
    kalabalıktı; "Arka plan görevleri" varsayılan olarak KATLI açılır ve
    kullanıcının açtığı hâl oturumlar arası korunur.
    """
    return _get(f"ui/section/{name}", "1" if default else "0") not in ("0", "false", "False")


def set_section_expanded(name: str, expanded: bool) -> bool:
    settings().setValue(f"ui/section/{name}", "1" if expanded else "0")
    return bool(expanded)


# --------------------------------------------------------------------------- #
# Bölücü konumları
# --------------------------------------------------------------------------- #
def save_splitter(name: str, splitter) -> None:
    """Bölücünün o anki boyut listesini kalıcılaştırır (hata yükseltmez)."""
    try:
        sizes = [int(v) for v in splitter.sizes()]
    except Exception:
        return
    if not sizes or sum(sizes) <= 0:
        return
    try:
        settings().setValue(f"layout/splitter/{name}", ",".join(str(v) for v in sizes))
    except Exception:
        pass


def restore_splitter(name: str, splitter) -> bool:
    """Kayıtlı konumu uygular. İlk açılışta (kayıt yoksa) varsayılan korunur."""
    try:
        raw = settings().value(f"layout/splitter/{name}", "")
    except Exception:
        return False
    if not raw:
        return False
    try:
        sizes = [int(part) for part in str(raw).split(",") if part.strip()]
    except ValueError:
        return False
    if len(sizes) != splitter.count() or sum(sizes) <= 0:
        return False
    splitter.setSizes(sizes)
    return True


def install_splitter_persistence(name: str, splitter) -> None:
    """Bölücüyü geri yükler ve `splitterMoved` ile kaydeder.

    Alıcı lambda değildir: `QSplitter`'a bağlı bir `_SplitterPersister`
    (QObject) nesnesi kullanılır, böylece bağlantı doğrudan ve nesne ömrü
    bölücüyle aynıdır.
    """
    restore_splitter(name, splitter)
    persister = _SplitterPersister(name, splitter)
    splitter.splitterMoved.connect(persister.on_moved)
    # Ömrü bölücüye bağla (aksi hâlde çöp toplayıcı alır).
    setattr(splitter, "_entropy_persister", persister)


def reset_layout(names: Iterable[str] = ()) -> None:
    """Kayıtlı bölücü konumlarını siler (varsayılan yerleşime dönüş)."""
    s = settings()
    try:
        if names:
            for name in names:
                s.remove(f"layout/splitter/{name}")
        else:
            s.remove("layout/splitter")
    except Exception:
        pass


def _persister_base():
    from PySide6.QtCore import QObject

    return QObject


try:  # PySide6 yoksa (saf ölçüm bağlamı) modül yine içe aktarılabilsin.
    from PySide6.QtCore import QObject, Slot

    class _SplitterPersister(QObject):
        """`splitterMoved` alıcısı — sinyal alıcısı lambda olmaz kuralı."""

        def __init__(self, name: str, splitter):
            super().__init__(splitter)
            self._name = name
            self._splitter = splitter

        @Slot(int, int)
        def on_moved(self, pos: int, index: int) -> None:  # noqa: ARG002
            save_splitter(self._name, self._splitter)

except Exception:  # pragma: no cover - PySide6 yok
    _SplitterPersister = None  # type: ignore[assignment]
