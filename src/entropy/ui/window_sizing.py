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
    """Hedef ekranın (yoksa birincil ekranın) kullanılabilir alanı.

    Faz 12-D.1: `availableGeometry()` çok monitörlü + karışık DPI'lı
    kurulumlarda ekranın kendi `geometry()`'sinden taşan (ya da başka bir
    ekranın kökenini taşıyan) bir dikdörtgen döndürebiliyor; pencere o zaman
    fiziksel panelin dışına açılıyordu. İki dikdörtgeni kesiştirerek sonucun
    her zaman ekranın İÇİNDE kalmasını garanti ediyoruz.
    """
    target = screen or QGuiApplication.primaryScreen()
    if target is None:
        # Başsız/ekransız ortam: makul bir varsayılan; çağıranlar çökmesin.
        return QRect(0, 0, 1366, 768)
    area = target.availableGeometry()
    full = target.geometry()
    if full.isValid():
        clipped = area.intersected(full)
        if clipped.isValid() and clipped.width() > 0 and clipped.height() > 0:
            area = clipped
    return area


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


def half_screen_geometry(
    area: QRect,
    width_ratio: float = 0.5,
    height_ratio: float = 0.9,
    side: str = "right",
    min_size: Tuple[int, int] = (900, 560),
) -> QRect:
    """Alanın bir yarısını kaplayan, dikey ortalanmış dikdörtgen (Faz 7).

    Tek monitörlü kurulumda Agent Desk ekranın sağ yarısında, Zen solda
    durabilsin diye: genişlik alanın `width_ratio` katı, yükseklik
    `height_ratio` katı. `min_size` alanı aşmayacak biçimde kırpılır.
    """
    width = max(1, int(area.width() * width_ratio))
    height = max(1, int(area.height() * height_ratio))
    width = max(width, min(min_size[0], area.width()))
    height = max(height, min(min_size[1], area.height()))
    width = min(width, area.width())
    height = min(height, area.height())

    if str(side).lower() == "left":
        x = area.x()
    else:
        x = area.x() + area.width() - width
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


def maximize_window_to_screen(
    window,
    min_size: Tuple[int, int] = (960, 600),
    screen: Optional[QScreen] = None,
) -> QRect:
    """Pencereyi hedef ekranın **tüm kullanılabilir alanına** yayar (Faz 8).

    Neden `showMaximized()` değil de geometri: Zen çerçevesiz
    (`FramelessWindowHint`) bir pencere; Windows'ta çerçevesiz pencereyi
    maksimize etmek onu görev çubuğunun altına da yayar. Kullanılabilir alanı
    doğrudan geometri olarak vermek görev çubuğunu erişilebilir bırakır ve
    kullanıcı raporundaki "Zen tam ekrandan çıkmış" (1766x949) durumunu
    kaldırır — pencere artık alanın tamamını kaplar.

    Pencere zaten maksimize/tam ekransa dokunulmaz.
    """
    if hasattr(window, "isMaximized") and (
        window.isMaximized() or getattr(window, "isFullScreen", lambda: False)()
    ):
        return window.geometry()

    area = available_geometry(screen or (window.screen() if hasattr(window, "screen") else None))
    if hasattr(window, "setMinimumSize"):
        window.setMinimumSize(
            min(min_size[0], area.width()),
            min(min_size[1], area.height()),
        )
    if screen is not None and hasattr(window, "setScreen"):
        try:
            window.setScreen(screen)
        except Exception:
            pass
    window.setGeometry(area)
    return area


def clamp_window_into_screen(window, screen: Optional[QScreen] = None) -> QRect:
    """Pencereyi kullanılabilir alanın içine çeker (Faz 8).

    Mod geçişlerinden sonra çağrılır: kullanıcı pencereyi ekran dışına
    sürüklediyse ya da önceki mod daha büyük bir ekranda açıldıysa pencere
    görünmez kalabiliyordu. Boyut alandan büyükse kırpılır, konum alana
    kaydırılır. Maksimize/tam ekran pencereye dokunulmaz.
    """
    if hasattr(window, "isMaximized") and (
        window.isMaximized() or getattr(window, "isFullScreen", lambda: False)()
    ):
        return window.geometry()

    area = available_geometry(screen or (window.screen() if hasattr(window, "screen") else None))
    geom = QRect(window.geometry())
    width = min(geom.width(), area.width())
    height = min(geom.height(), area.height())
    x = min(max(geom.x(), area.x()), area.x() + area.width() - width)
    y = min(max(geom.y(), area.y()), area.y() + area.height() - height)
    target = QRect(x, y, width, height)
    if target != geom:
        if hasattr(window, "setMinimumSize"):
            window.setMinimumSize(
                min(window.minimumWidth(), width),
                min(window.minimumHeight(), height),
            )
        window.setGeometry(target)
    return target
