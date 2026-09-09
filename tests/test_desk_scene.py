"""
Faz 6 piksel ofis testleri: varlıklar, motor tabloları, sahne davranışı.

Hepsi offscreen çalışır (`QT_QPA_PLATFORM=offscreen`); model çağrısı yoktur.
"""

from __future__ import annotations

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from entropy.desk.engine.assets import TILE_SIZE, library  # noqa: E402
from entropy.desk.engine.furniture import FurnitureLibrary  # noqa: E402
from entropy.desk.engine.layout import parse_layout  # noqa: E402
from entropy.desk.engine.pathing import find_path, walkable_grid  # noqa: E402
from entropy.desk.engine.sprites import (  # noqa: E402
    ANIM_IDLE,
    ANIM_READ,
    ANIM_TYPE,
    ANIM_WALK,
    DIR_LEFT,
    DIR_RIGHT,
    CharacterLibrary,
    character_index_for,
    frame_sequence,
)
from entropy.desk.engine.tilemap import TileMap, carpet_case, wall_bitmask  # noqa: E402
from entropy.desk import scene as scene_mod  # noqa: E402
from entropy.desk.scene import (  # noqa: E402
    STATE_ERROR,
    STATE_IDLE,
    STATE_READING,
    STATE_THINKING,
    STATE_WAITING,
    STATE_WORKING,
    OfficeScene,
    state_for_tool,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="session")
def assets(qapp):
    return library()


@pytest.fixture(scope="session")
def layout(assets):
    return parse_layout(assets.default_layout(), FurnitureLibrary(assets))


OFFICE = {
    "name": "arastirma",
    "orchestrator": "lider",
    "evaluator": "denetci",
    "members": ["arastirmaci", "yazar", "kodcu", "denetci"],
}


def make_scene(office=None):
    scene = OfficeScene(office=office if office is not None else OFFICE)
    scene.resize(21 * TILE_SIZE * 2, 22 * TILE_SIZE * 2)
    scene.relayout()
    return scene


# --------------------------------------------------------------- varlıklar


def test_assets_present(assets):
    """6 karakter, 9 zemin, duvar/halı sayfaları ve mobilya manifestleri."""
    assert len(assets.character_files()) == 6
    assert len(assets.floor_files()) >= 1
    assert len(assets.wall_files()) >= 1
    assert len(assets.carpet_files()) >= 1
    assert "DESK" in assets.furniture_ids()
    assert "PC" in assets.furniture_ids()


def test_default_layout_dimensions(layout):
    assert (layout.cols, layout.rows) == (21, 22)
    assert len(layout.tiles) == 22 and len(layout.tiles[0]) == 21
    assert layout.furniture, "düzende mobilya çözülmedi"


# ------------------------------------------------------------ döşeme tabloları


def test_wall_bitmask_table():
    """N=1, E=2, S=4, W=8; sınır dışı duvar sayılmaz."""
    tiles = [
        [1, 0, 1],
        [0, 0, 0],
        [1, 0, 1],
    ]
    assert wall_bitmask(1, 1, tiles) == 1 + 2 + 4 + 8   # dört komşu da duvar
    assert wall_bitmask(1, 0, tiles) == 4               # yalnız güney
    assert wall_bitmask(0, 1, tiles) == 2               # yalnız doğu
    assert wall_bitmask(1, 2, tiles) == 1               # yalnız kuzey


def test_carpet_marching_squares_table():
    """NW=1, NE=2, SE=4, SW=8; boş kavşak 0."""
    grid = [
        [True, True],
        [True, False],
    ]
    assert carpet_case(0, 0, grid) == 4                 # yalnız SE hücresi
    assert carpet_case(1, 1, grid) == 1 + 2 + 8         # SE hücresi yok
    assert carpet_case(5, 5, grid) == 0


def test_tilemap_slices(qapp, assets):
    tm = TileMap(assets)
    assert len(tm.wall_set()) == 16     # 4 sütun x 4 satır bitmask parçası
    assert len(tm.carpet_set()) == 16
    wall = tm.wall_tile(0)
    assert wall is not None and (wall.width(), wall.height()) == (16, 32)
    scaled = tm.scaled("wall", 0, 3, 2)
    assert scaled is not None and scaled.width() == 32


# ---------------------------------------------------------------- sprite


def test_character_sheet_slicing(qapp, assets):
    """112x96 sayfa -> 7 sütun x 3 satır, kare 16x32."""
    lib = CharacterLibrary(assets)
    assert lib.count() == 6
    sheet = lib.sheet(0)
    img = assets.image(sheet.rel)
    assert (img.width(), img.height()) == (112, 96)
    assert sheet.frame_count() == 7
    assert len(sheet.rows()) == 3
    frame = sheet.frame(DIR_RIGHT, 0)
    assert (frame.width(), frame.height()) == (16, 32)


def test_left_is_mirrored_right(qapp, assets):
    sheet = CharacterLibrary(assets).sheet(0)
    right = sheet.frame(DIR_RIGHT, 1).toImage()
    left = sheet.frame(DIR_LEFT, 1).toImage()
    assert right.pixelColor(2, 20) == left.pixelColor(right.width() - 3, 20)


def test_animation_sequences():
    assert frame_sequence(ANIM_IDLE) == (0,)
    assert frame_sequence(ANIM_WALK) == (0, 1, 0, 2)
    assert frame_sequence(ANIM_TYPE) == (3, 4)
    assert frame_sequence(ANIM_READ) == (5, 6)


def test_character_index_is_stable():
    first = character_index_for("arastirmaci", 6)
    assert first == character_index_for("arastirmaci", 6)
    assert 0 <= first < 6


# --------------------------------------------------------------- mobilya


def test_furniture_resolution(qapp, assets):
    lib = FurnitureLibrary(assets)
    desk, mirrored = lib.resolve("DESK_FRONT")
    assert desk is not None and not mirrored
    assert (desk.footprint_w, desk.footprint_h) == (3, 2)

    pc_on, _ = lib.resolve("PC_FRONT_ON")
    assert pc_on is not None and pc_on.frame_count == 3 and pc_on.animated

    side, mirror = lib.resolve("PC_SIDE:left")
    assert side is not None and mirror is True


def test_depth_sorting_is_row_major(layout):
    ordered = layout.sorted_furniture()
    depths = [p.depth for p in ordered]
    assert depths == sorted(depths)


# --------------------------------------------------------------- yol bulma


def test_pathing_reaches_desk(layout):
    grid = walkable_grid(layout.tiles, layout.occupied_cells())
    seats = layout.seats()
    assert seats
    start = None
    for cell in layout.floor_cells():
        if grid[cell[1]][cell[0]] and cell != seats[0].cell:
            start = cell
            break
    path = find_path(grid, start, seats[0].cell)
    assert path and path[0] == start
    # Her adım tek hücre, dört yön.
    for a, b in zip(path, path[1:]):
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


def test_pathing_blocked_returns_empty():
    grid = [[True, False], [False, True]]
    assert find_path(grid, (0, 0), (1, 1), allow_adjacent_goal=False) == []


# ------------------------------------------------------------- masa ataması


def test_seat_assignment_prefers_desks(qapp):
    scene = make_scene()
    seats = {s.agent: s.seat for s in scene.slots}
    assert len(seats) == 5
    # Orkestratör masaya oturur ve tekil hücre alır.
    assert seats["lider"].source == "desk"
    cells = [ (s.col, s.row) for s in seats.values() ]
    assert len(set(cells)) == len(cells)
    scene.deleteLater()


def test_orchestrator_is_closest_desk_to_center(qapp):
    scene = make_scene()
    center = scene.layout.center_cell()
    orch = scene.slot_for("lider").seat
    desks = [s for s in scene.layout.seats() if s.source == "desk"]
    best = min(desks, key=lambda s: abs(s.col - center[0]) + abs(s.row - center[1]))
    assert (orch.col, orch.row) == (best.col, best.row)
    scene.deleteLater()


# ---------------------------------------------------------- durum/animasyon


def test_state_to_animation_mapping(qapp):
    scene = make_scene()
    slot = scene.slot_for("arastirmaci")
    for state, anim in (
        (STATE_IDLE, ANIM_IDLE),
        (STATE_WORKING, ANIM_TYPE),
        (STATE_READING, ANIM_READ),
        (STATE_THINKING, ANIM_IDLE),
        (STATE_WAITING, ANIM_IDLE),
        (STATE_ERROR, ANIM_IDLE),
    ):
        slot.state = state
        slot.walking = False
        assert scene._anim_step(slot)[0] == anim
    slot.walking = True
    assert scene._anim_step(slot)[0] == ANIM_WALK
    scene.deleteLater()


def test_read_tools_map_to_reading_state():
    assert state_for_tool("Read") == STATE_READING
    assert state_for_tool("dosya_oku") == STATE_READING
    assert state_for_tool("Bash") == STATE_WORKING


def test_bubbles_for_thinking_waiting_error():
    assert scene_mod.STATE_BUBBLE[STATE_THINKING] == "…"
    assert scene_mod.STATE_BUBBLE[STATE_WAITING] == "⏳"
    assert scene_mod.STATE_BUBBLE[STATE_ERROR] == "!"


def test_agent_walks_to_desk_on_task(qapp):
    """Masasından uzaktaki ajan görev gelince yürüyerek masasına döner."""
    scene = make_scene()
    slot = scene.slot_for("arastirmaci")
    seat = slot.seat
    # Ajanı yürünebilir başka bir hücreye taşı.
    away = next(
        cell for cell in scene.layout.floor_cells()
        if scene._walkable[cell[1]][cell[0]] and cell != (seat.col, seat.row)
    )
    slot.x, slot.y = away[0] * TILE_SIZE, away[1] * TILE_SIZE
    assert scene.set_state("arastirmaci", STATE_WORKING)
    assert slot.walking and len(slot.path) >= 2
    # Yeterli süre ilerletince masaya varır ve oturuş yönüne döner.
    for _ in range(400):
        scene._advance_walk(slot, 33)
        if not slot.walking:
            break
    assert slot.cell == (seat.col, seat.row)
    assert slot.facing == seat.facing
    scene.deleteLater()


# --------------------------------------------------------------- görüntü


def test_zoom_and_fit(qapp):
    scene = make_scene()
    scene.set_zoom(3)
    assert scene.zoom == 3 and not scene.fit_mode
    assert scene._view_transform()[0] == 3.0
    scene.set_zoom(99)
    assert scene.zoom == scene_mod.MAX_ZOOM

    scene.fit_to_view()
    scene.resize(21 * TILE_SIZE, 22 * TILE_SIZE)
    scale, _, _ = scene._view_transform()
    assert 0 < scale <= scene_mod.MAX_ZOOM
    # Dar pencerede tüm düzen sığar (widget'ın asgari boyutu 520x330).
    scene.setMinimumSize(1, 1)
    scene.resize(200, 140)
    scale, dx, dy = scene._view_transform()
    logical_w, logical_h = scene._logical_size
    assert logical_w * scale <= scene.width() + 1
    assert logical_h * scale <= scene.height() + 1
    assert scale < 1.0
    scene.deleteLater()


def test_frame_rate_and_hidden_stop(qapp):
    scene = make_scene()
    scene.show()
    assert scene._timer.interval() == scene_mod.IDLE_INTERVAL_MS
    assert 1000 / scene._timer.interval() <= 11
    scene.set_state("arastirmaci", STATE_WORKING)
    assert scene._timer.interval() == scene_mod.ACTIVE_INTERVAL_MS
    assert 1000 / scene._timer.interval() <= 31
    scene.hide()
    assert not scene._timer.isActive()
    scene.deleteLater()


def test_click_selects_agent(qapp):
    scene = make_scene()
    scene.show()
    received = []
    scene.agent_clicked.connect(received.append)
    slot = scene.slot_for("lider")
    scale, dx, dy = scene._view_transform()
    center = slot.rect.center()
    point = QPoint(int(center.x() * scale + dx), int(center.y() * scale + dy))
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress, point, Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    scene.mousePressEvent(event)
    assert scene.selected_agent == "lider"
    assert received == ["lider"]
    scene.deleteLater()


def test_hover_tooltip_mentions_role_and_state(qapp):
    scene = make_scene()
    scene.show()
    scene.set_state("lider", STATE_WORKING, note="kart-1")
    slot = scene.slot_for("lider")
    scale, dx, dy = scene._view_transform()
    center = slot.rect.center()
    from PySide6.QtGui import QMouseEvent as _E

    event = _E(
        _E.Type.MouseMove,
        QPoint(int(center.x() * scale + dx), int(center.y() * scale + dy)),
        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
    )
    scene.mouseMoveEvent(event)
    tip = scene.toolTip()
    assert "lider" in tip and "orkestratör" in tip and "çalışıyor" in tip
    scene.deleteLater()


def test_paint_renders_pixels(qapp):
    """Sahne gerçekten piksel varlık çiziyor: kare tek renk kalmamalı."""
    scene = make_scene()
    scene.show()
    qapp.processEvents()
    image = scene.grab().toImage()
    colors = {image.pixel(x, y) for x in range(0, image.width(), 17)
              for y in range(0, image.height(), 17)}
    assert len(colors) > 12
    scene.deleteLater()
