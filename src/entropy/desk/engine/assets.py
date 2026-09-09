"""
Varlık kökü ve QPixmap yükleyici.

Neden ayrı modül: PyInstaller tek dosya paketinde varlıklar `sys._MEIPASS`
altına açılır; kaynak ağacında ise `src/entropy/desk/assets`. Yol çözümü tek
yerde toplanmazsa donmuş derlemede sahne boş kalır (Faz 4'te aynı hata
`skills/` için yaşanmıştı).

QPixmap yalnızca QGuiApplication varken üretilebilir; bu yüzden yükleyici
tembeldir ve önbelleklidir. Ölçekleme her zaman nearest-neighbour
(FastTransformation): piksel sanatın kenarları bulanıklaşmasın.
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

# Mantıksal ızgara hücresi (piksel). Karakter ve duvar sprite'ları 16x32.
TILE_SIZE = 16


def assets_root() -> Path:
    """Varlık klasörünün mutlak yolu (donmuş derleme dahil)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        packed = Path(meipass) / "entropy" / "desk" / "assets"
        if packed.is_dir():
            return packed
    return Path(__file__).resolve().parent.parent / "assets"


@lru_cache(maxsize=1)
def _root() -> Path:
    return assets_root()


class AssetLibrary:
    """PNG/JSON varlıklarını yükleyip önbellekleyen tekil kütüphane."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root is not None else _root()
        self._images: Dict[str, QImage] = {}
        self._pixmaps: Dict[str, QPixmap] = {}
        self._json: Dict[str, object] = {}

    # ------------------------------------------------------------- yollar

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def exists(self, *parts: str) -> bool:
        return self.path(*parts).is_file()

    # ------------------------------------------------------------ yükleme

    def image(self, rel: str) -> QImage:
        """
        Ham QImage (QPixmap'in aksine QGuiApplication gerektirmez).

        Dilimleme ve test doğrulaması QImage üzerinden yapılır; ekran yoksa
        (saf birim testi) yine de çalışır.
        """
        cached = self._images.get(rel)
        if cached is not None:
            return cached
        img = QImage(str(self.path(*rel.split("/"))))
        self._images[rel] = img
        return img

    def pixmap(self, rel: str) -> QPixmap:
        cached = self._pixmaps.get(rel)
        if cached is not None:
            return cached
        pix = QPixmap.fromImage(self.image(rel))
        self._pixmaps[rel] = pix
        return pix

    def json(self, rel: str) -> object:
        cached = self._json.get(rel)
        if cached is not None:
            return cached
        with open(self.path(*rel.split("/")), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self._json[rel] = data
        return data

    # ------------------------------------------------------------ listeler

    def floor_files(self) -> List[str]:
        return sorted(
            (f"floors/{p.name}" for p in self.path("floors").glob("floor_*.png")),
            key=_numeric_key,
        )

    def wall_files(self) -> List[str]:
        return sorted(
            (f"walls/{p.name}" for p in self.path("walls").glob("wall_*.png")),
            key=_numeric_key,
        )

    def carpet_files(self) -> List[str]:
        return sorted(
            (f"carpets/{p.name}" for p in self.path("carpets").glob("carpet_*.png")),
            key=_numeric_key,
        )

    def character_files(self) -> List[str]:
        return sorted(
            (f"characters/{p.name}" for p in self.path("characters").glob("char_*.png")),
            key=_numeric_key,
        )

    def furniture_ids(self) -> List[str]:
        base = self.path("furniture")
        if not base.is_dir():
            return []
        return sorted(p.name for p in base.iterdir() if (p / "manifest.json").is_file())

    def furniture_manifest(self, furniture_id: str) -> dict:
        return dict(self.json(f"furniture/{furniture_id}/manifest.json"))  # type: ignore[arg-type]

    def default_layout(self) -> dict:
        return dict(self.json("default-layout-1.json"))  # type: ignore[arg-type]

    # ------------------------------------------------------------ ölçekleme

    @staticmethod
    def scaled(pix: QPixmap, zoom: int) -> QPixmap:
        """Tamsayı zoom ile nearest-neighbour büyütme."""
        if zoom <= 1 or pix.isNull():
            return pix
        return pix.scaled(
            pix.width() * zoom,
            pix.height() * zoom,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )


def _numeric_key(rel: str):
    """`floor_10.png` > `floor_2.png` olsun diye sayısal sıralama anahtarı."""
    stem = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    tail = stem.rsplit("_", 1)[-1]
    return (int(tail) if tail.isdigit() else 0, stem)


_LIBRARY: Optional[AssetLibrary] = None


def library() -> AssetLibrary:
    """Süreç genelinde tek kütüphane (önbellekler paylaşılsın)."""
    global _LIBRARY
    if _LIBRARY is None:
        _LIBRARY = AssetLibrary()
    return _LIBRARY
