"""
Karakter sayfası dilimleme ve animasyon kare seçimi.

Sayfa düzeni (pixel-agents `spriteData.ts` ile aynı):
- kare 16x32, satır başına 7 kare, 3 satır -> 112x96 PNG.
- satırlar: 0=down, 1=up, 2=right. Sol yön yoktur; sağın yatay aynasıdır.
- sütunlar: 0 duruş/yürüyüş-0, 1-2 yürüyüş, 3-4 yazma, 5-6 okuma.

Animasyon dizileri:
- IDLE : [0]            (statik duruş)
- WALK : [0, 1, 0, 2]   (4 adım)
- TYPE : [3, 4]
- READ : [5, 6]
"""

from __future__ import annotations

import hashlib
from typing import Dict, List, Optional, Tuple

from PySide6.QtGui import QPixmap, QTransform

from entropy.desk.engine.assets import AssetLibrary, library

FRAME_W = 16
FRAME_H = 32
FRAMES_PER_ROW = 7

DIR_DOWN = "down"
DIR_UP = "up"
DIR_RIGHT = "right"
DIR_LEFT = "left"
DIRECTIONS = (DIR_DOWN, DIR_UP, DIR_RIGHT, DIR_LEFT)
_ROW_INDEX = {DIR_DOWN: 0, DIR_UP: 1, DIR_RIGHT: 2}

ANIM_IDLE = "idle"
ANIM_WALK = "walk"
ANIM_TYPE = "type"
ANIM_READ = "read"

# Animasyon adı -> sayfa sütun dizisi.
SEQUENCES: Dict[str, Tuple[int, ...]] = {
    ANIM_IDLE: (0,),
    ANIM_WALK: (0, 1, 0, 2),
    ANIM_TYPE: (3, 4),
    ANIM_READ: (5, 6),
}


def frame_sequence(anim: str) -> Tuple[int, ...]:
    return SEQUENCES.get(anim, SEQUENCES[ANIM_IDLE])


def character_index_for(name: str, count: int) -> int:
    """
    Ajan adı -> karakter indeksi (kararlı eşleme).

    Python'un `hash()` süreçler arası değiştiği için (PYTHONHASHSEED) md5
    kullanılır: aynı ajan her açılışta aynı karakteri alır.
    """
    if count <= 0:
        return 0
    digest = hashlib.md5(name.encode("utf-8")).digest()
    return digest[0] % count


class CharacterSheet:
    """Tek bir char_N.png sayfasının dilimlenmiş, önbellekli kareleri."""

    def __init__(self, rel: str, lib: Optional[AssetLibrary] = None) -> None:
        self.lib = lib or library()
        self.rel = rel
        self._rows: Optional[List[List[QPixmap]]] = None
        self._mirror: Dict[int, QPixmap] = {}
        self._scaled: Dict[Tuple[str, int, int], QPixmap] = {}

    # ------------------------------------------------------------ dilimleme

    def rows(self) -> List[List[QPixmap]]:
        if self._rows is None:
            sheet = self.lib.pixmap(self.rel)
            rows: List[List[QPixmap]] = []
            if not sheet.isNull():
                row_count = max(1, sheet.height() // FRAME_H)
                cols = max(1, sheet.width() // FRAME_W)
                for r in range(row_count):
                    rows.append([
                        sheet.copy(c * FRAME_W, r * FRAME_H, FRAME_W, FRAME_H)
                        for c in range(cols)
                    ])
            self._rows = rows
        return self._rows

    def frame_count(self) -> int:
        rows = self.rows()
        return len(rows[0]) if rows else 0

    def frame(self, direction: str, column: int) -> Optional[QPixmap]:
        """Yön + sütun -> kare. Sol yön sağın aynasıdır."""
        rows = self.rows()
        if not rows:
            return None
        mirror = direction == DIR_LEFT
        row_index = _ROW_INDEX.get(DIR_RIGHT if mirror else direction, 0)
        if row_index >= len(rows):
            row_index = 0
        row = rows[row_index]
        if not row:
            return None
        pix = row[column % len(row)]
        if not mirror:
            return pix
        key = column % len(row)
        cached = self._mirror.get(key)
        if cached is None:
            cached = pix.transformed(QTransform().scale(-1, 1))
            self._mirror[key] = cached
        return cached

    def animation_frame(self, direction: str, anim: str, step: int) -> Optional[QPixmap]:
        seq = frame_sequence(anim)
        return self.frame(direction, seq[step % len(seq)])

    # ------------------------------------------------------------ ölçek

    def scaled_frame(self, direction: str, anim: str, step: int, zoom: int) -> Optional[QPixmap]:
        seq = frame_sequence(anim)
        column = seq[step % len(seq)]
        key = (direction, column, zoom)
        hit = self._scaled.get(key)
        if hit is not None:
            return hit
        base = self.frame(direction, column)
        if base is None or base.isNull():
            return None
        out = AssetLibrary.scaled(base, zoom)
        self._scaled[key] = out
        return out

    def clear_scaled(self) -> None:
        self._scaled.clear()


class CharacterLibrary:
    """char_0..N sayfalarını tembel yükleyen kap."""

    def __init__(self, lib: Optional[AssetLibrary] = None) -> None:
        self.lib = lib or library()
        self._files = self.lib.character_files()
        self._sheets: Dict[int, CharacterSheet] = {}

    def count(self) -> int:
        return len(self._files)

    def sheet(self, index: int) -> Optional[CharacterSheet]:
        if not self._files:
            return None
        idx = index % len(self._files)
        cached = self._sheets.get(idx)
        if cached is None:
            cached = CharacterSheet(self._files[idx], self.lib)
            self._sheets[idx] = cached
        return cached

    def sheet_for_agent(self, name: str) -> Optional[CharacterSheet]:
        return self.sheet(character_index_for(name, max(1, self.count())))

    def clear_scaled(self) -> None:
        for sheet in self._sheets.values():
            sheet.clear_scaled()
