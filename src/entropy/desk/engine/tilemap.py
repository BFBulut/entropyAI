"""
Zemin / duvar / halı döşeme.

- Zemin: 16x16 tek karo, tile değeri (>=1) doğrudan `floor_{v-1}.png` seçer.
- Duvar: 16x32 sprite sayfası, 4 sütun x 4 satır = 16 parça. Parça indeksi
  dört komşunun bitmask'ı: N=1, E=2, S=4, W=8 (pixel-agents `wallTiles.ts`
  ile birebir aynı; sınır dışı = duvar değil). Sprite hücrenin ALT kenarına
  hizalanır, yukarı taşar.
- Halı: 16x16 marching squares. Vaka, kavşağı çevreleyen dört hücreden
  kurulur: NW=1, NE=2, SE=4, SW=8. Vaka 0 çizilmez.

Tüm dilimler QPixmap olarak önbelleklenir; zoom değişince ölçekli önbellek
ayrıca tutulur (her karede yeniden ölçeklemek 30 fps'te CPU yakardı).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from PySide6.QtGui import QPixmap

from entropy.desk.engine.assets import TILE_SIZE, AssetLibrary, library

WALL_SHEET_COLS = 4
WALL_TILE_H = 32
CARPET_SHEET_COLS = 4


def wall_bitmask(col: int, row: int, tiles: Sequence[Sequence[int]], wall_value: int = 0) -> int:
    """Dört ana yön komşusuna göre duvar parça indeksi (0-15)."""
    rows = len(tiles)
    cols = len(tiles[0]) if rows else 0
    mask = 0
    if row > 0 and tiles[row - 1][col] == wall_value:
        mask |= 1  # N
    if col < cols - 1 and tiles[row][col + 1] == wall_value:
        mask |= 2  # E
    if row < rows - 1 and tiles[row + 1][col] == wall_value:
        mask |= 4  # S
    if col > 0 and tiles[row][col - 1] == wall_value:
        mask |= 8  # W
    return mask


def carpet_case(jx: int, jy: int, carpet: Sequence[Sequence[bool]]) -> int:
    """Kavşak (jx, jy) için marching squares vakası (0-15)."""
    rows = len(carpet)
    cols = len(carpet[0]) if rows else 0

    def has(c: int, r: int) -> bool:
        return 0 <= c < cols and 0 <= r < rows and bool(carpet[r][c])

    case = 0
    if has(jx - 1, jy - 1):
        case |= 1  # NW
    if has(jx, jy - 1):
        case |= 2  # NE
    if has(jx, jy):
        case |= 4  # SE
    if has(jx - 1, jy):
        case |= 8  # SW
    return case


def _slice_sheet(sheet: QPixmap, tile_w: int, tile_h: int, cols: int) -> List[QPixmap]:
    """Sayfayı satır-önce sırayla parçalara böler."""
    if sheet.isNull():
        return []
    rows = max(1, sheet.height() // tile_h)
    out: List[QPixmap] = []
    for r in range(rows):
        for c in range(cols):
            out.append(sheet.copy(c * tile_w, r * tile_h, tile_w, tile_h))
    return out


class TileMap:
    """Döşeme parçalarını yükleyen ve zoom'a göre ölçekleyen önbellek."""

    def __init__(self, lib: Optional[AssetLibrary] = None) -> None:
        self.lib = lib or library()
        self._floors: Optional[List[QPixmap]] = None
        self._walls: Dict[int, List[QPixmap]] = {}
        self._carpets: Dict[int, List[QPixmap]] = {}
        # (tür, set, indeks, zoom) -> ölçekli parça
        self._scaled: Dict[Tuple[str, int, int, int], QPixmap] = {}

    # ------------------------------------------------------------- yükleme

    def floors(self) -> List[QPixmap]:
        if self._floors is None:
            self._floors = [self.lib.pixmap(rel) for rel in self.lib.floor_files()]
        return self._floors

    def wall_set(self, set_index: int = 0) -> List[QPixmap]:
        cached = self._walls.get(set_index)
        if cached is None:
            files = self.lib.wall_files()
            if not files:
                cached = []
            else:
                sheet = self.lib.pixmap(files[min(set_index, len(files) - 1)])
                cached = _slice_sheet(sheet, TILE_SIZE, WALL_TILE_H, WALL_SHEET_COLS)
            self._walls[set_index] = cached
        return cached

    def carpet_set(self, set_index: int = 0) -> List[QPixmap]:
        cached = self._carpets.get(set_index)
        if cached is None:
            files = self.lib.carpet_files()
            if not files:
                cached = []
            else:
                sheet = self.lib.pixmap(files[min(set_index, len(files) - 1)])
                cached = _slice_sheet(sheet, TILE_SIZE, TILE_SIZE, CARPET_SHEET_COLS)
            self._carpets[set_index] = cached
        return cached

    # ------------------------------------------------------------- seçiciler

    def floor_tile(self, value: int) -> Optional[QPixmap]:
        """Düzen tile değeri (>=1) -> zemin karosu."""
        floors = self.floors()
        if not floors or value < 1:
            return None
        return floors[(value - 1) % len(floors)]

    def wall_tile(self, mask: int, set_index: int = 0) -> Optional[QPixmap]:
        pieces = self.wall_set(set_index)
        if not pieces:
            return None
        return pieces[mask % len(pieces)]

    def carpet_tile(self, case: int, set_index: int = 0) -> Optional[QPixmap]:
        if case <= 0:
            return None
        pieces = self.carpet_set(set_index)
        if not pieces:
            return None
        return pieces[case % len(pieces)]

    # ------------------------------------------------------------- ölçek

    def scaled(self, kind: str, set_index: int, index: int, zoom: int) -> Optional[QPixmap]:
        """Önbellekli, nearest-neighbour ölçekli parça."""
        key = (kind, set_index, index, zoom)
        hit = self._scaled.get(key)
        if hit is not None:
            return hit
        if kind == "floor":
            base = self.floor_tile(index)
        elif kind == "wall":
            base = self.wall_tile(index, set_index)
        elif kind == "carpet":
            base = self.carpet_tile(index, set_index)
        else:
            base = None
        if base is None or base.isNull():
            return None
        out = AssetLibrary.scaled(base, zoom)
        self._scaled[key] = out
        return out

    def clear_scaled(self) -> None:
        self._scaled.clear()
