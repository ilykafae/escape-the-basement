"""maze.py

Random maze generator for the "beneath the surface" basement.

Outputs a 2D array (list[list[int]]) where:
  -1 = exit
   0 = floor (walkable)
   1 = wall  (solid)
   2 = entrance (player spawn)
   3 = button (collectible)

Public API:
  The main function is `generate_maze(length, width, difficulty, button_count)`
  which returns (tiles, player_spawn, exit_spawn).

The maze is regenerated each run (always random).

This uses a DFS / recursive-backtracker (stack) algorithm, which produces a
"perfect maze" (connected, no isolated regions), so the exit is always reachable.
"""

from __future__ import annotations

import random
from collections import deque
from typing import List, Tuple

# =============================
# User-tweakable parameters
# =============================

# Maze size in TILES (the returned 2D array size), not pixels.
# Note: The generator internally uses maze "cells"; for best results use odd numbers
# (e.g. 31x31). Even sizes work too; extra border tiles may remain walls.

MAZE_CELLS_W = 20
MAZE_CELLS_H = 14


# Optional: how many steps away from the player we try to place the exit (soft goal).
# If the maze is small, we still pick the farthest reachable tile.
MIN_EXIT_DISTANCE = 30

# Maze complexity coefficient in [1, 100].
# 1 = easiest (almost a perfect maze, very few loops)
# 100 = hardest (many extra loops/connections)
DEFAULT_DIFFICULTY = 15


# Bit flags for carved passages per cell
N, E, S, W = 1, 2, 4, 8
DIRS = [
    (0, -1, N, S),
    (1, 0, E, W),
    (0, 1, S, N),
    (-1, 0, W, E),
]


def _generate_cells(w: int, h: int, rng: random.Random) -> List[List[int]]:
    """Generate a w x h grid of cells with carved passages encoded as bit flags."""
    grid = [[0 for _ in range(w)] for _ in range(h)]
    visited = [[False for _ in range(w)] for _ in range(h)]

    sx, sy = rng.randrange(w), rng.randrange(h)
    stack = [(sx, sy)]
    visited[sy][sx] = True

    while stack:
        x, y = stack[-1]

        neighbors = []
        for dx, dy, bit, opp in DIRS:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                neighbors.append((nx, ny, bit, opp))

        if not neighbors:
            stack.pop()
            continue

        nx, ny, bit, opp = rng.choice(neighbors)
        grid[y][x] |= bit
        grid[ny][nx] |= opp
        visited[ny][nx] = True
        stack.append((nx, ny))

    return grid


def _cells_to_tiles(cells: List[List[int]]) -> List[List[int]]:
    """Convert cell-passages representation into a tile grid (0 floor, 1 wall)."""
    h, w = len(cells), len(cells[0])

    tile_h = h * 2 + 1
    tile_w = w * 2 + 1
    tiles = [[1 for _ in range(tile_w)] for _ in range(tile_h)]

    for cy in range(h):
        for cx in range(w):
            tx, ty = 2 * cx + 1, 2 * cy + 1
            tiles[ty][tx] = 0
            v = cells[cy][cx]
            if v & N:
                tiles[ty - 1][tx] = 0
            if v & S:
                tiles[ty + 1][tx] = 0
            if v & E:
                tiles[ty][tx + 1] = 0
            if v & W:
                tiles[ty][tx - 1] = 0

    return tiles


def _cells_to_tiles_exact(cells: List[List[int]], out_w: int, out_h: int) -> List[List[int]]:
    """Convert cells to a tile grid, then fit it into an exact out_w x out_h array.

    The classic conversion produces (2*h+1) x (2*w+1). Here we embed that result
    into an exact-sized array filled with walls. If the requested size is larger,
    the extra area remains walls. If smaller, we generate fewer cells so it fits.
    """
    base = _cells_to_tiles(cells)
    base_h, base_w = len(base), len(base[0])

    tiles = [[1 for _ in range(out_w)] for _ in range(out_h)]

    copy_h = min(out_h, base_h)
    copy_w = min(out_w, base_w)

    for y in range(copy_h):
        tiles[y][:copy_w] = base[y][:copy_w]

    return tiles


# --- Helper to add loops/complexity to the maze ---
def _add_loops(tiles: List[List[int]], rng: random.Random, complexity: float | int) -> None:
    """Carve extra connections in the maze to increase complexity.

    The base DFS maze is a "perfect maze" (a tree). By removing additional walls
    between existing corridors we introduce cycles/loops.

    complexity coefficient:
      1   -> easiest (almost no extra carving)
      100 -> hardest (lots of extra carving)

    This mutates `tiles` in-place.
    """
    # Accept either old-style [0.0, 1.0] floats or the new [1, 100] coefficient.
    # New scale: 1 easiest -> ~0.0, 100 hardest -> 1.0
    c = float(complexity)

    # If it's in the 1..100 range, treat it as the coefficient.
    if 1.0 <= c <= 100.0:
        c = (c - 1.0) / 99.0

    # Clamp to [0, 1]
    c = max(0.0, min(1.0, c))

    if c <= 0.0:
        return

    H, W_ = len(tiles), len(tiles[0])
    # Candidate walls are interior tiles (not the outer border) that separate two floor tiles.
    candidates: List[Tuple[int, int]] = []

    for y in range(1, H - 1):
        for x in range(1, W_ - 1):
            if tiles[y][x] != 1:
                continue

            # Vertical wall between left/right corridors
            if tiles[y][x - 1] != 1 and tiles[y][x + 1] != 1:
                candidates.append((x, y))
                continue

            # Horizontal wall between up/down corridors
            if tiles[y - 1][x] != 1 and tiles[y + 1][x] != 1:
                candidates.append((x, y))

    if not candidates:
        return

    # Heuristic: carve a fraction of candidates proportional to complexity.
    # The divisor keeps the maze from turning into an open field at modest values.
    carve_count = int(len(candidates) * (c / 3.0))
    carve_count = max(0, min(carve_count, len(candidates)))

    rng.shuffle(candidates)
    for i in range(carve_count):
        x, y = candidates[i]
        tiles[y][x] = 0


def _random_floor_tile(tiles: List[List[int]], rng: random.Random) -> Tuple[int, int]:
    """Pick a random walkable tile (x, y)."""
    floors = [(x, y) for y, row in enumerate(tiles) for x, t in enumerate(row) if t != 1]
    if not floors:
        raise ValueError("Maze has no floor tiles (this should never happen).")
    return rng.choice(floors)


def _place_buttons(tiles: List[List[int]], rng: random.Random, button_count: int) -> None:
    """Place `button_count` buttons (value 3) on random floor tiles (value 0).

    Does NOT place on walls (1), entrance (2), or exit (-1).
    Mutates `tiles` in-place.
    """
    if button_count <= 0:
        return

    floors = [(x, y) for y, row in enumerate(tiles) for x, t in enumerate(row) if t == 0]
    if not floors:
        return

    rng.shuffle(floors)
    n = min(int(button_count), len(floors))
    for i in range(n):
        x, y = floors[i]
        tiles[y][x] = 3


def _bfs_dist(tiles: List[List[int]], start: Tuple[int, int]) -> List[List[int]]:
    """BFS distances on the tile grid (4-neighbor). Unreachable = large number."""
    H, W_ = len(tiles), len(tiles[0])
    INF = 10**9
    dist = [[INF for _ in range(W_)] for _ in range(H)]
    sx, sy = start

    q = deque([(sx, sy)])
    dist[sy][sx] = 0

    while q:
        x, y = q.popleft()
        nd = dist[y][x] + 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W_ and 0 <= ny < H and tiles[ny][nx] != 1 and dist[ny][nx] > nd:
                dist[ny][nx] = nd
                q.append((nx, ny))

    return dist


def _farthest_floor_tile(
    tiles: List[List[int]],
    from_pos: Tuple[int, int],
    min_distance: int = 0,
) -> Tuple[int, int]:
    """Pick a floor tile far from from_pos. If min_distance can't be met, pick the farthest."""
    dist = _bfs_dist(tiles, from_pos)

    best = from_pos
    bestd = -1

    for y, row in enumerate(dist):
        for x, d in enumerate(row):
            if tiles[y][x] == 1 or d >= 10**9:
                continue
            # Prefer tiles that meet the min distance, otherwise just maximize distance.
            if d >= min_distance and d > bestd:
                bestd = d
                best = (x, y)

    if bestd >= 0:
        return best

    # Fallback: no tiles meet min_distance (tiny maze). Return absolute farthest.
    for y, row in enumerate(dist):
        for x, d in enumerate(row):
            if tiles[y][x] != 1 and d < 10**9 and d > bestd:
                bestd = d
                best = (x, y)

    return best


def generate_maze_tiles(
    length: int = MAZE_CELLS_W,
    width: int = MAZE_CELLS_H,
    complexity: int = DEFAULT_DIFFICULTY,
) -> List[List[int]]:
    """Public API: returns a 2D array of EXACT size width x length.

    Args:
      length: output tile width (number of columns)
      width:  output tile height (number of rows)

    Returns a 2D array where 1=wall, 0=floor.
    """
    out_w = max(3, int(length))
    out_h = max(3, int(width))

    # Convert desired tile size into an internal cell size that will fit.
    cells_w = max(1, (out_w - 1) // 2)
    cells_h = max(1, (out_h - 1) // 2)

    rng = random.Random()
    cells = _generate_cells(cells_w, cells_h, rng)
    tiles = _cells_to_tiles_exact(cells, out_w=out_w, out_h=out_h)
    _add_loops(tiles, rng, complexity)
    return tiles


def generate_maze_with_spawns(
    length: int = MAZE_CELLS_W,
    width: int = MAZE_CELLS_H,
    complexity: int = DEFAULT_DIFFICULTY,
    button_count: int = 0,
    min_exit_distance: int = MIN_EXIT_DISTANCE,
) -> Tuple[List[List[int]], Tuple[int, int], Tuple[int, int]]:
    """Convenience helper.

    Returns:
      tiles: 2D array (1 wall, 0 floor, 2 entrance, -1 exit, 3 button)
      player_spawn: (x, y) entrance tile
      exit_spawn: (x, y) exit tile
    """
    rng = random.Random()

    out_w = max(3, int(length))
    out_h = max(3, int(width))

    # Convert desired tile size into an internal cell size that will fit.
    cells_w = max(1, (out_w - 1) // 2)
    cells_h = max(1, (out_h - 1) // 2)

    cells = _generate_cells(cells_w, cells_h, rng)
    tiles = _cells_to_tiles_exact(cells, out_w=out_w, out_h=out_h)

    # Increase complexity by carving extra loops, if requested.
    _add_loops(tiles, rng, complexity)

    # Choose an entrance opening on the TOP border.
    # In this maze representation, walkable corridor tiles are typically at odd x and odd y.
    # The tile just inside the top border is y=1; the border itself is y=0.
    candidates_top = [x for x in range(1, out_w - 1) if tiles[1][x] == 0]
    if not candidates_top:
        # Extremely unlikely, but keep it robust.
        player_spawn = _random_floor_tile(tiles, rng)
    else:
        x = rng.choice(candidates_top)
        tiles[0][x] = 0  # carve opening to outside
        player_spawn = (x, 0)

    # Place the exit as an opening on the BOTTOM border, far from the entrance.
    # First compute a distance map from the entrance.
    dist = _bfs_dist(tiles, player_spawn)
    bottom_y = out_h - 1
    inner_bottom_y = out_h - 2

    candidates_bottom = [x for x in range(1, out_w - 1) if tiles[inner_bottom_y][x] == 0]
    if not candidates_bottom:
        exit_spawn = _farthest_floor_tile(tiles, player_spawn, min_distance=min_exit_distance)
    else:
        # Prefer the bottom opening whose *inside tile* is farthest from the entrance.
        bestx = candidates_bottom[0]
        bestd = -1
        for x in candidates_bottom:
            d = dist[inner_bottom_y][x]
            if d < 10**9 and d > bestd:
                bestd = d
                bestx = x
        tiles[bottom_y][bestx] = 0  # carve opening to outside
        exit_spawn = (bestx, bottom_y)

    # Mark entrance/exit in the tile map for convenience.
    px, py = player_spawn
    ex, ey = exit_spawn
    tiles[py][px] = 2
    tiles[ey][ex] = -1

    # Place buttons on random floor tiles.
    _place_buttons(tiles, rng, button_count)

    return tiles, player_spawn, exit_spawn


def generate_maze(
    length: int,
    width: int,
    difficulty: int = DEFAULT_DIFFICULTY,
    button_count: int = 0,
):
    """Generate a maze.

    Args:
      length: output tile width (number of columns)
      width:  output tile height (number of rows)
      difficulty: 1..100 (1 easiest, 100 hardest). Internally controls how many extra loops get carved.
      button_count: number of buttons (value 3) to place on floor tiles

    Returns:
      (tiles, player_spawn, exit_spawn)

    tiles is a 2D array where:
      1 = wall, 0 = floor, 2 = entrance, -1 = exit
    """
    # We map difficulty directly onto the loop-carving "complexity" parameter.
    return generate_maze_with_spawns(length=length, width=width, complexity=difficulty, button_count=button_count)


# Backwards/typo-friendly alias: some code may call the singular name.
# Same behavior: x, y are the output tile width/height (2D array size).

def generate_maze_with_spawn(
    x: int = MAZE_CELLS_W,
    y: int = MAZE_CELLS_H,
    complexity: int = DEFAULT_DIFFICULTY,
    button_count: int = 0,
    min_exit_distance: int = MIN_EXIT_DISTANCE,
) -> Tuple[List[List[int]], Tuple[int, int], Tuple[int, int]]:
    return generate_maze_with_spawns(
        length=x,
        width=y,
        complexity=complexity,
        button_count=button_count,
        min_exit_distance=min_exit_distance,
    )
