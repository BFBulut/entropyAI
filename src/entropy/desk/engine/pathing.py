"""
Izgara yol bulma (4 yönlü BFS).

Neden BFS, A* değil: ofis ızgarası en fazla birkaç yüz hücre (21x22 = 462);
BFS burada tek bir karede biter ve sezgisel ayarı gerektirmez. Hedef hücre
dolu olabilir (masaya yürünüyor); bu durumda hedefe KOMŞU en yakın yürünebilir
hücreye gidilir, yoksa yol boş döner.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

Cell = Tuple[int, int]

_NEIGHBORS = ((0, -1), (1, 0), (0, 1), (-1, 0))


def walkable_grid(tiles: Sequence[Sequence[int]], blocked: Optional[Iterable[Cell]] = None,
                  wall_value: int = 0, empty_value: int = 255) -> List[List[bool]]:
    """Zemin karosu olan ve mobilya kaplamayan hücreler yürünebilir."""
    blocked_set: Set[Cell] = set(blocked or ())
    grid: List[List[bool]] = []
    for r, row in enumerate(tiles):
        line = []
        for c, value in enumerate(row):
            ok = value != wall_value and value != empty_value and (c, r) not in blocked_set
            line.append(ok)
        grid.append(line)
    return grid


def find_path(grid: Sequence[Sequence[bool]], start: Cell, goal: Cell,
              allow_adjacent_goal: bool = True) -> List[Cell]:
    """
    start -> goal arası en kısa 4 yönlü yol (başlangıç dahil).

    Yol yoksa boş liste. `allow_adjacent_goal` açıkken hedef yürünemezse
    hedefin yürünebilir komşularından birine varılır.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if not rows or not cols:
        return []
    if not _inside(start, cols, rows) or not _inside(goal, cols, rows):
        return []
    if not grid[start[1]][start[0]]:
        return []

    goals: Set[Cell] = set()
    if grid[goal[1]][goal[0]]:
        goals.add(goal)
    elif allow_adjacent_goal:
        for dc, dr in _NEIGHBORS:
            cell = (goal[0] + dc, goal[1] + dr)
            if _inside(cell, cols, rows) and grid[cell[1]][cell[0]]:
                goals.add(cell)
    if not goals:
        return []
    if start in goals:
        return [start]

    prev: Dict[Cell, Optional[Cell]] = {start: None}
    queue = deque([start])
    found: Optional[Cell] = None
    while queue:
        cur = queue.popleft()
        if cur in goals:
            found = cur
            break
        for dc, dr in _NEIGHBORS:
            nxt = (cur[0] + dc, cur[1] + dr)
            if nxt in prev or not _inside(nxt, cols, rows):
                continue
            if not grid[nxt[1]][nxt[0]]:
                continue
            prev[nxt] = cur
            queue.append(nxt)
    if found is None:
        return []

    path: List[Cell] = []
    node: Optional[Cell] = found
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    return path


def _inside(cell: Cell, cols: int, rows: int) -> bool:
    return 0 <= cell[0] < cols and 0 <= cell[1] < rows
