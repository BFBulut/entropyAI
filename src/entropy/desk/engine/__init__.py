"""
Piksel ofis motoru: tile/sprite yükleme, otomatik döşeme, mobilya ve yol bulma.

Tasarım pixel-agents (MIT) uygulamasından uyarlandı; bkz. THIRD_PARTY.md.
Motor Qt'ye yalnızca QPixmap/QImage seviyesinde bağlıdır: çizim `desk/scene.py`
içindeki QPainter tarafından yapılır, mantık burada test edilebilir kalır.
"""

from entropy.desk.engine.assets import (
    TILE_SIZE,
    AssetLibrary,
    assets_root,
    library,
)
from entropy.desk.engine.furniture import FurnitureLibrary, ResolvedFurniture
from entropy.desk.engine.layout import (
    TILE_EMPTY,
    TILE_WALL,
    Layout,
    Seat,
    load_layout,
    office_layout_path,
)
from entropy.desk.engine.pathing import find_path, walkable_grid
from entropy.desk.engine.sprites import (
    ANIM_IDLE,
    ANIM_READ,
    ANIM_TYPE,
    ANIM_WALK,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    CharacterSheet,
    character_index_for,
    frame_sequence,
)
from entropy.desk.engine.tilemap import TileMap, carpet_case, wall_bitmask

__all__ = [
    "TILE_SIZE",
    "AssetLibrary",
    "assets_root",
    "library",
    "FurnitureLibrary",
    "ResolvedFurniture",
    "Layout",
    "Seat",
    "TILE_EMPTY",
    "TILE_WALL",
    "load_layout",
    "office_layout_path",
    "find_path",
    "walkable_grid",
    "CharacterSheet",
    "character_index_for",
    "frame_sequence",
    "ANIM_IDLE",
    "ANIM_WALK",
    "ANIM_TYPE",
    "ANIM_READ",
    "DIR_DOWN",
    "DIR_UP",
    "DIR_LEFT",
    "DIR_RIGHT",
    "TileMap",
    "wall_bitmask",
    "carpet_case",
]
