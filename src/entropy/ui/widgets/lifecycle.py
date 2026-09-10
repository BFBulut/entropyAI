"""Widget yaşam döngüsü yardımcıları — hayalet üst düzey pencereleri önler.

**Neden var (Faz 13-A2, madde 7).** Kullanıcı gerçek ekranda bir görev
çalıştırınca Görev panosunun üstünde ~20 tane beyaz, uygulama ikonlu, boş
pencerenin açılıp kapandığını gördü. Kök neden Qt'nin belgelenmiş davranışıdır:

    widget.setParent(None)   # -> widget ARTIK BİR PENCEREDİR (Qt::Window)

Pano yenilemesi kartları `layout.takeAt(0)` ile alıp `setParent(None)` +
`deleteLater()` yapıyordu. `deleteLater()` ancak olay döngüsü dönünce silindiği
için, kart o ana kadar **ebeveynsiz bir üst düzey widget** olarak yaşıyor;
Windows'ta daha önce yaratılmış bir yerel pencere tutamacı varsa masaüstünde
bir kare olarak parlıyor. 20 kart = 20 parlama.

Doğru desen: widget'ı önce **gizle**, ebeveynini bırakma, silmeyi olay
döngüsüne devret. `deleteLater()` widget'ı zaten ebeveyninin çocuk
listesinden çıkarır; `setParent(None)` gereksizdir.

`tests/ui/test_phase13a2_ux.py::test_pano_yenilemesi_hayalet_pencere_uretmez`
bu dosyanın sözleşmesini canlı widget ağacında ölçer.
"""

from __future__ import annotations

from typing import Optional

__all__ = ["discard_widget", "detach_widget", "clear_layout"]


def discard_widget(widget) -> None:
    """Widget'ı görünmez yapıp silinmek üzere işaretler (üst düzeye ÇIKARMADAN).

    `setParent(None)` **çağrılmaz**: çağrılsaydı widget silinene kadar
    ebeveynsiz bir pencere olurdu.
    """
    if widget is None:
        return
    try:
        widget.hide()
    except RuntimeError:  # C++ nesnesi zaten silinmiş
        return
    try:
        widget.deleteLater()
    except RuntimeError:
        pass


def detach_widget(widget, new_parent=None) -> None:
    """Widget'ı başka bir ebeveyne taşır (silmeden).

    Silinmeyecek ama yeniden yerleştirilecek widget'lar için: taşımadan önce
    **gizler**, böylece ebeveynsiz kaldığı kısa aralıkta ekranda parlamaz.
    """
    if widget is None:
        return
    try:
        widget.hide()
        widget.setParent(new_parent)
    except RuntimeError:
        pass


def clear_layout(layout, keep_trailing: int = 0) -> int:
    """Düzendeki widget'ları güvenle boşaltır; kaç tanesinin atıldığını döner.

    `keep_trailing` sondaki kaç öğenin (genelde `addStretch()`) korunacağını
    söyler.
    """
    if layout is None:
        return 0
    removed = 0
    while layout.count() > keep_trailing:
        item = layout.takeAt(0)
        if item is None:
            break
        widget: Optional[object] = item.widget()
        if widget is not None:
            discard_widget(widget)
            removed += 1
    return removed
