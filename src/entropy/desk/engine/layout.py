"""
Ofis düzeni: JSON okuma, karo ızgarası, mobilya yerleşimi ve masa yerleri.

Düzen şeması (pixel-agents `default-layout-1.json` ile aynı):
    {version, cols, rows, layoutRevision, tiles[], tileColors[], furniture[]}
`tiles` satır-önce düzleştirilmiş; 255 = boşluk, 0 = duvar, >=1 = zemin indeksi.

Ofis başına düzen `<kasa>/Entropy/Desk/Offices/<ofis>/layout.json` altında
tutulur; yoksa ilk açılışta varsayılan düzen oraya kopyalanır. Böylece
kullanıcı düzeni elle değiştirebilir ve güncelleme onu ezmez.

Masa yerleri (Seat) mobilyadan türetilir:
- DESK_* : ajan masanın arkasında/yanında oturur, masaya bakar.
- *_CHAIR_* : sandalye hücresi doğrudan oturma yeridir.
Yetmezse boş zemin hücrelerinden yedek yer üretilir (ajan sayısı masa
sayısından fazla olabilir; kimse görünmez kalmasın).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from entropy.desk.engine.assets import AssetLibrary, library
from entropy.desk.engine.furniture import FurnitureLibrary, PlacedFurniture, sort_by_depth
from entropy.desk.engine.sprites import DIR_DOWN, DIR_LEFT, DIR_RIGHT, DIR_UP

TILE_WALL = 0
TILE_EMPTY = 255

Cell = Tuple[int, int]


def _cheb(a: Cell, b: Cell) -> int:
    """Chebyshev uzaklığı: 1 ise iki hücre (çapraz dahil) komşudur."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


@dataclass
class Seat:
    """Bir ajanın oturacağı hücre ve baktığı yön."""

    col: int
    row: int
    facing: str = DIR_DOWN
    source: str = "floor"   # desk | chair | floor

    @property
    def cell(self) -> Cell:
        return (self.col, self.row)


@dataclass
class Layout:
    """Çözülmüş ofis düzeni."""

    cols: int = 0
    rows: int = 0
    tiles: List[List[int]] = field(default_factory=list)
    tile_colors: List[Optional[dict]] = field(default_factory=list)
    furniture: List[PlacedFurniture] = field(default_factory=list)
    revision: int = 1
    source: str = ""

    # --------------------------------------------------------------- karo

    def tile(self, col: int, row: int) -> int:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.tiles[row][col]
        return TILE_EMPTY

    def is_wall(self, col: int, row: int) -> bool:
        return self.tile(col, row) == TILE_WALL

    def is_floor(self, col: int, row: int) -> bool:
        value = self.tile(col, row)
        return value != TILE_WALL and value != TILE_EMPTY

    def floor_cells(self) -> List[Cell]:
        return [
            (c, r)
            for r in range(self.rows)
            for c in range(self.cols)
            if self.is_floor(c, r)
        ]

    def bounds(self) -> Tuple[int, int, int, int]:
        """Dolu (duvar+zemin) alanın (min_c, min_r, max_c, max_r) sınırı."""
        cells = [
            (c, r)
            for r in range(self.rows)
            for c in range(self.cols)
            if self.tile(c, r) != TILE_EMPTY
        ]
        if not cells:
            return (0, 0, max(self.cols - 1, 0), max(self.rows - 1, 0))
        cs = [c for c, _ in cells]
        rs = [r for _, r in cells]
        return (min(cs), min(rs), max(cs), max(rs))

    def center_cell(self) -> Cell:
        min_c, min_r, max_c, max_r = self.bounds()
        return ((min_c + max_c) // 2, (min_r + max_r) // 2)

    # ---------------------------------------------------------- doluluk

    def occupied_cells(self) -> Set[Cell]:
        """Mobilyanın kapladığı hücreler (yol bulmada engel)."""
        out: Set[Cell] = set()
        for placed in self.furniture:
            if placed.variant.category == "wall":
                continue
            out.update(placed.cells())
        return out

    def sorted_furniture(self) -> List[PlacedFurniture]:
        return sort_by_depth(self.furniture)

    # ------------------------------------------------------------- masalar

    def seats(self) -> List[Seat]:
        """
        Masa/sandalye kaynaklı oturma yerleri; merkeze yakınlığa göre sıralı.

        Sıralama önemli: ilk sıradaki yer orkestratöre verilir, böylece
        orkestratör masası ofis merkezine en yakın olur.
        """
        seats: List[Seat] = []
        taken: Set[Cell] = set()
        occupied = self.occupied_cells()

        for placed in self.furniture:
            for seat in self._seats_for(placed, occupied):
                if seat.cell in taken:
                    continue
                taken.add(seat.cell)
                seats.append(seat)

        center = self.center_cell()
        # Önce gerçek masalar (bilgisayarlı çalışma yeri), sonra sandalyeler;
        # her grup içinde ofis merkezine yakınlık. Orkestratör ilk sırayı alır,
        # yani daima bir masaya oturur.
        priority = {"desk": 0, "chair": 1, "floor": 2}
        seats.sort(key=lambda s: (
            priority.get(s.source, 3),
            abs(s.col - center[0]) + abs(s.row - center[1]),
            s.row, s.col,
        ))
        return seats

    def _seat_for(self, placed: PlacedFurniture, occupied: Set[Cell]) -> Optional[Seat]:
        """Geriye dönük tek yer: mobilyanın ilk (birincil) oturma yeri."""
        seats = self._seats_for(placed, occupied)
        return seats[0] if seats else None

    def _seats_for(self, placed: PlacedFurniture, occupied: Set[Cell]) -> List[Seat]:
        """
        Bir mobilyanın ürettiği TÜM oturma yerleri.

        Faz 7: eskiden yalnızca DESK_* ve sandalyeler yer üretiyordu; 10 ajanlı
        ofiste herkes birkaç masanın çevresine yığılıyordu. Artık:
        - TABLE_* : masanın dört yanı (sol/sağ/üst/alt) ayrı birer yer,
        - SOFA_*  : koltuğun kapladığı her hücre bir yer.
        """
        variant = placed.variant
        vid = variant.variant_id
        w, h = variant.footprint_w, variant.footprint_h

        side_facing = {
            "front": DIR_DOWN,
            "back": DIR_UP,
            "side": DIR_LEFT if placed.mirrored else DIR_RIGHT,
        }.get(variant.orientation, DIR_DOWN)

        if "CHAIR" in vid or "BENCH" in vid:
            # Sandalyenin kendi hücresi oturma yeri; yön sandalyenin yönü.
            return [Seat(placed.col, placed.row, side_facing, source="chair")]

        if "SOFA" in vid:
            # Koltuk çok hücreli olabilir; her hücresine bir ajan oturabilir.
            return [
                Seat(c, r, side_facing, source="chair")
                for (c, r) in placed.cells()
                if self.tile(c, r) != TILE_EMPTY
            ]

        if "TABLE" in vid:
            # Toplantı/kahve masası: dört yanı da oturulur.
            out: List[Seat] = []
            for cell, facing in (
                ((placed.col - 1, placed.row + h // 2), DIR_RIGHT),
                ((placed.col + w, placed.row + h // 2), DIR_LEFT),
                ((placed.col + w // 2, placed.row - 1), DIR_DOWN),
                ((placed.col + w // 2, placed.row + h), DIR_UP),
            ):
                if self.is_floor(*cell) and cell not in occupied:
                    out.append(Seat(cell[0], cell[1], facing, source="desk"))
            return out

        if not vid.startswith("DESK"):
            return []

        # Masa: ajan masaya BAKAN komşu hücrede oturur.
        if variant.orientation == "side":
            if placed.mirrored:
                cell = (placed.col + w, placed.row + h // 2)
                facing = DIR_LEFT
            else:
                cell = (placed.col - 1, placed.row + h // 2)
                facing = DIR_RIGHT
        elif variant.orientation == "back":
            cell = (placed.col + w // 2, placed.row + h)
            facing = DIR_UP
        else:  # front
            cell = (placed.col + w // 2, placed.row - 1)
            facing = DIR_DOWN

        if not self.is_floor(*cell) or cell in occupied:
            return []
        return [Seat(cell[0], cell[1], facing, source="desk")]

    def seats_for(self, count: int) -> List[Seat]:
        """
        `count` adet oturma yeri; ajanlar ofise YAYILARAK yerleştirilir.

        Kural (Faz 7):
        1. İlk yer orkestratörün: merkeze en yakın masa (`seats()[0]`).
        2. Sonrakiler "en uzak boş yer önce" ile seçilir (farthest-point
           sampling, Chebyshev): iki karakter komşu hücrelere düşmez.
        3. Mobilya yerleri biterse boş zeminden en az 2 hücre aralıklı
           yedekler eklenir; ancak o da yetmezse aralık gevşetilir (kimse
           görünmez kalmasın).
        """
        if count <= 0:
            return []
        pool = self.seats()
        chosen: List[Seat] = []
        if pool:
            chosen.append(pool[0])
            remaining = pool[1:]
            while remaining and len(chosen) < count:
                best = max(
                    remaining,
                    key=lambda s: (
                        min(_cheb(s.cell, c.cell) for c in chosen),
                        -(abs(s.col - self.center_cell()[0]) + abs(s.row - self.center_cell()[1])),
                    ),
                )
                remaining.remove(best)
                chosen.append(best)
        if len(chosen) >= count:
            return chosen[:count]

        # Zemin yedekleri: önce 2 hücre aralık şartıyla, sonra gevşeterek.
        occupied = self.occupied_cells() | {s.cell for s in chosen}
        center = self.center_cell()
        spare = sorted(
            (cell for cell in self.floor_cells() if cell not in occupied),
            key=lambda cell: (abs(cell[0] - center[0]) + abs(cell[1] - center[1]), cell[1], cell[0]),
        )
        for spacing in (2, 1):
            for cell in list(spare):
                if len(chosen) >= count:
                    break
                if chosen and min(_cheb(cell, s.cell) for s in chosen) < spacing:
                    continue
                spare.remove(cell)
                chosen.append(Seat(cell[0], cell[1], DIR_DOWN, source="floor"))
            if len(chosen) >= count:
                break
        return chosen[:count]


# --------------------------------------------------------------- yükleme


def parse_layout(data: dict, furniture_lib: Optional[FurnitureLibrary] = None,
                 source: str = "") -> Layout:
    """Ham JSON sözlüğünü Layout'a çevirir."""
    lib = furniture_lib or FurnitureLibrary()
    cols = int(data.get("cols", 0))
    rows = int(data.get("rows", 0))
    flat = list(data.get("tiles") or [])
    tiles: List[List[int]] = []
    for r in range(rows):
        chunk = flat[r * cols:(r + 1) * cols]
        if len(chunk) < cols:
            chunk = list(chunk) + [TILE_EMPTY] * (cols - len(chunk))
        tiles.append([int(v) for v in chunk])

    placed: List[PlacedFurniture] = []
    for entry in data.get("furniture") or []:
        variant, mirrored = lib.resolve(str(entry.get("type", "")))
        if variant is None:
            continue
        placed.append(PlacedFurniture(
            uid=str(entry.get("uid", "")),
            variant=variant,
            col=int(entry.get("col", 0)),
            row=int(entry.get("row", 0)),
            mirrored=mirrored,
        ))

    return Layout(
        cols=cols,
        rows=rows,
        tiles=tiles,
        tile_colors=list(data.get("tileColors") or []),
        furniture=placed,
        revision=int(data.get("layoutRevision", 1)),
        source=source,
    )


def office_layout_path(office: str) -> Optional[Path]:
    """`<kasa>/Entropy/Desk/Offices/<ofis>/layout.json` (kasa yoksa None)."""
    if not office:
        return None
    try:
        from entropy.memory.office_graph import desk_office_dir  # type: ignore

        return Path(desk_office_dir(office)) / "layout.json"
    except Exception:
        return None


def load_layout(office: str = "", furniture_lib: Optional[FurnitureLibrary] = None,
                asset_lib: Optional[AssetLibrary] = None) -> Layout:
    """
    Ofisin düzenini yükler; KAYITLI ofisin klasörüne varsayılanı kopyalar.

    "Hayalet ofis" kuralı: bu işlev ofis klasörü AÇMAZ. Eskiden `mkdir(parents)`
    ile her ada klasör açıyordu; kayıt defterinden silinen ya da arşive taşınan
    bir ofis sahnede seçili kaldığında `<kasa>/Entropy/Desk/Offices/<ad>/`
    yalnızca `layout.json` ile yeniden beliriyordu (künyesiz ofis; kasa
    hijyeni her turda aynı klasörleri arşivliyordu). Artık künye (`OFFICE.md`)
    yoksa diske hiç dokunulmaz, sahne bellekteki varsayılan düzenle çizilir.

    Kopyalama başarısız olursa (kasa yolu yok, yazma izni yok) sessizce
    varsayılan düzenle devam edilir: sahne her koşulda çizilmelidir.
    """
    alib = asset_lib or library()
    path = office_layout_path(office)
    if path is not None:
        try:
            if path.is_file():
                with open(path, "r", encoding="utf-8") as fh:
                    return parse_layout(json.load(fh), furniture_lib, source=str(path))
            # Yalnızca künyesi olan (kayıtlı) ofise düzen yazılır.
            if (path.parent / "OFFICE.md").is_file():
                default_path = alib.path("default-layout-1.json")
                shutil.copyfile(default_path, path)
                with open(path, "r", encoding="utf-8") as fh:
                    return parse_layout(json.load(fh), furniture_lib, source=str(path))
        except Exception:
            pass
    return parse_layout(alib.default_layout(), furniture_lib, source="default")


def carpet_mask(layout: Layout, cells: Sequence[Cell]) -> List[List[bool]]:
    """Verilen hücreler için halı doğruluk ızgarası (marching squares girdisi)."""
    grid = [[False] * layout.cols for _ in range(layout.rows)]
    for c, r in cells:
        if 0 <= r < layout.rows and 0 <= c < layout.cols:
            grid[r][c] = True
    return grid
