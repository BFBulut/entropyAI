"""Pencere boyutlama yardımcıları (Faz 6).

Sorun: Zen ve Agent Desk pencereleri sabit/ekran boyu geometriyle açılıyor,
1366x768 gibi küçük ekranlarda paneller ekran dışına taşıyor, iki pencere yan
yana bir ekrandan fazla yer kaplıyordu. Buradaki tek kural her yerde uygulanır:

    pencere <= kullanılabilir alanın (görev çubuğu hariç) belli bir oranı,
    ve o alanın içinde ortalanır.

`available_geometry()` görev çubuğunu dışarıda bırakan alanı verir; tam ekran
geometrisi yerine bu kullanılır, yoksa pencere görev çubuğunun altına kaçar.
"""

from typing import Optional, Tuple

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QScreen


def available_geometry(screen: Optional[QScreen] = None) -> QRect:
    """Hedef ekranın (yoksa birincil ekranın) kullanılabilir alanı."""
    target = screen or QGuiApplication.primaryScreen()
    if target is None:
        # Başsız/ekransız ortam: makul bir varsayılan; çağıranlar çökmesin.
        return QRect(0, 0, 1366, 768)
    return target.availableGeometry()


def fitted_geometry(
    area: QRect,
    ratio: float = 0.92,
    min_size: Tuple[int, int] = (960, 600),
    preferred: Optional[Tuple[int, int]] = None,
) -> QRect:
    """Alanın `ratio` kadarını kaplayan, ortalanmış dikdörtgeni hesaplar.

    `preferred` verilirse istenen boyut üst sınırı aşmadığı sürece korunur.
    `min_size` alanın kendisinden büyükse alana kırpılır: küçük ekranda taşan
    bir pencere, minimumunu korumaktan daha kötüdür.
    """
    max_w = max(1, int(area.width() * ratio))
    max_h = max(1, int(area.height() * ratio))

    want_w, want_h = preferred if preferred else (max_w, max_h)
    width = min(max(want_w, min(min_size[0], area.width())), max_w)
    height = min(max(want_h, min(min_size[1], area.height())), max_h)

    x = area.x() + (area.width() - width) // 2
    y = area.y() + (area.height() - height) // 2
    return QRect(x, y, width, height)


def fit_window_to_screen(
    window,
    ratio: float = 0.92,
    min_size: Tuple[int, int] = (960, 600),
    screen: Optional[QScreen] = None,
    keep_preferred: bool = False,
) -> QRect:
    """Pencereyi kullanılabilir alana sığdırıp ortalar; uygulanan geometriyi döndürür."""
    area = available_geometry(screen or (window.screen() if hasattr(window, "screen") else None))
    preferred = (window.width(), window.height()) if keep_preferred else None
    geom = fitted_geometry(area, ratio=ratio, min_size=min_size, preferred=preferred)
    # Asgari boyut ekrandan büyükse pencere setGeometry ile küçültülemez;
    # minimumu da alana kırparız, yoksa küçük ekranda taşar.
    if hasattr(window, "setMinimumSize"):
        window.setMinimumSize(
            min(min_size[0], geom.width()),
            min(min_size[1], geom.height()),
        )
    if screen is not None and hasattr(window, "setScreen"):
        try:
            window.setScreen(screen)
        except Exception:
            pass
    window.setGeometry(geom)
    return geom
