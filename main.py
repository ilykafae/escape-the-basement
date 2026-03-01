
import pygame, asyncio, maze, random, math
from collections import deque
from pathlib import Path
from ecs.system import *
from ui.button import Button

GAME_W = 765
GAME_H = 435
V_GAME_W = 2550
V_GAME_H = 1450

BASE_DIR = Path(__file__).resolve().parent

def asset_path(rel: str) -> str:
    return str(BASE_DIR / rel)


USE_FOG_OF_WAR = True
USE_SMOOTH_MOVEMENT = True
PLAYER_STEP_MS = 120

# Tunable settings

# Tile size in pixels
TILE_SIZE = 50

# Player: hold-to-move (arrow keys)
MOVE_INITIAL_DELAY_MS = 200
MOVE_REPEAT_MS = 90

TOTAL_BUTTONS = 2

FOG_RADIUS_MATCH_LOCK = True

GHOST_STEP_NORMAL_MS = 220
GHOST_STEP_RAGE_MS = 180

LOCK_RADIUS = 6
VISION_RADIUS = 6  # tiles (player vision radius when fog-of-war is on)


UNLOCK_RADIUS = 10

# Hide bar
HIDE_BAR_MAX = 3.0
HIDE_BAR_WIDTH_PAD = 5
HIDE_BAR_HEIGHT = 6
HIDE_BAR_Y_OFFSET = -18

JUMPSCARE_VISUAL_MS = 1000
JUMPSCARE_COOLDOWN_MS = 6000

# Timed UI message duration
MSG_DURATION_MS = 3000

# Font
FONT_SIZE = 75

HIDDEN_RECHARGE_MULTIPLIER = 3 / 20

# Audio volumes
BGM_VOLUME = 0.5
RAGE_BGM_VOLUME = 1
HEARTBEAT_VOLUME = 1.0
JUMPSCARE_VOLUME = 0.9

GHOST_PATH = "assets/sprite/ghost.jpg"
WALL_PATH = "assets/world/wall.png"
B_WALL_PATH = "assets/world/wall_with_blood.png"
FLOOR_PATH = "assets/world/floor.png"
B_FLOOR_PATH = "assets/world/floor_with_blood.png"
DOOR_PATH = "assets/doors/door.png"
LOCKED_DOOR_PATH = "assets/doors/locked_door.png"
BUTTON_PATH = "assets/world/button.png"
BUTTON_PRESSED_PATH = "assets/world/button_pressed.png"
PLAYER_PATH = "assets/sprite/char.png"
PLAYER_RIGHT_PATH = "assets/sprite/char_right.png"
PLAYER_LEFT_PATH = "assets/sprite/char_left.png"

BGM_PATH = asset_path("assets/audio/bgm.ogg")
RAGE_BGM_PATH = asset_path("assets/audio/rage_audio.ogg")
HEARTBEAT_PATH = asset_path("assets/audio/heartbeat.ogg")
JUMPSCARE_AUDIO_PATH = asset_path("assets/audio/jumpscare_scream.ogg")

# try common jumpscare filename variants
JUMPSCARE_IMG_CANDIDATES = [
    asset_path("assets/sprite/jumpscar.JPG"),
    asset_path("assets/sprite/jumpscar.jpg"),
    asset_path("assets/sprite/jumpscare.JPG"),
    asset_path("assets/sprite/jumpscare.jpg"),
    asset_path("assets/sprite/jumpscar.JPEG"),
    asset_path("assets/sprite/jumpscare.JPEG"),
]

FONT_PATH = 'assets/fonts/redcap.ttf'
MC_FONT_PATH = "assets/fonts/minecraft.ttf"

WALL_OFFSET = TILE_SIZE

MENU_SCENE_STR = "menu"
GAME_SCENE_STR = "game"
WIN_SCENE_STR = "win"
JS_SCENE_STR = 'jumpscare'

WALL_OFFSET = 50

font = None

async def main():
    # Hold-to-move (arrow keys)
    held_dir = (0, 0)            # (dx_tiles, dy_tiles)
    next_move_time = 0

    def move_player_by_tiles(dx: int, dy: int):
        """Move player by (dx,dy) tiles if not blocked. Returns True if moved."""
        components = em.entities[player]
        next_x = components[Position].x + dx * WALL_OFFSET
        next_y = components[Position].y + dy * WALL_OFFSET
        try:
            if mz[next_y // WALL_OFFSET][next_x // WALL_OFFSET] != 1:
                components[Position].x = next_x
                components[Position].y = next_y
                return True
        except IndexError:
            pass
        return False

    # Smooth movement (optional)
    player_target = None  # (x_px, y_px) or None
    player_step_ms = PLAYER_STEP_MS   # ms per tile for smooth movement

    def update_player_smooth(dt: float):
        nonlocal player_target
        p = em.entities[player][Position]

        if player_target is None:
            dx, dy = held_dir
            if dx == 0 and dy == 0:
                return

            tx = int((p.x + WALL_OFFSET / 2) // WALL_OFFSET)
            ty = int((p.y + WALL_OFFSET / 2) // WALL_OFFSET)
            ntx, nty = tx + dx, ty + dy

            if 0 <= nty < len(mz) and 0 <= ntx < len(mz[0]) and mz[nty][ntx] != 1:
                player_target = (ntx * WALL_OFFSET, nty * WALL_OFFSET)
            return

        tx, ty = player_target
        vx = tx - p.x
        vy = ty - p.y
        dist2 = vx * vx + vy * vy

        speed_px = WALL_OFFSET * 1000.0 / max(1.0, float(player_step_ms))
        step = speed_px * dt

        if dist2 <= step * step:
            p.x, p.y = tx, ty
            player_target = None
            return

        dist = math.sqrt(dist2)
        if dist > 1e-6:
            p.x += (vx / dist) * step
            p.y += (vy / dist) * step

    pygame.init()
    pygame.font.init()
    pygame.mixer.init()

    global font
    font = pygame.font.Font(FONT_PATH, 75)
    mc_font = pygame.font.Font(MC_FONT_PATH, 75)

    # game settings
    is_door_unlocked = True

    player_x = 0
    player_y = 0

    ghost_x = 0
    ghost_y = 0

    total_buttons = TOTAL_BUTTONS
    preseed_buttons = 0

    exit_x = 0
    exit_y = 0

    hide_bar_max = HIDE_BAR_MAX
    hide_bar_curent = hide_bar_max
    hiden_tick = 0
    is_hidden = False

    active_msg = ""
    msg_start_time = 0

    fog_surface = pygame.Surface((V_GAME_W, V_GAME_H), pygame.SRCALPHA)

    # Temporary default; rebuilt later after ghost/vision parameters are set
    light_rad = 200

    def build_light_mask(radius_px: int) -> pygame.Surface:
        """Create a radial alpha mask for fog-of-war."""
        m = pygame.Surface((radius_px * 2, radius_px * 2), pygame.SRCALPHA)
        m.fill((0, 0, 0, 255))
        for r in range(radius_px, 0, -1):
            alpha = int(255 * (r / radius_px))
            pygame.draw.circle(m, (0, 0, 0, alpha), (radius_px, radius_px), r)
        return m

    light_mask = build_light_mask(light_rad)

    VIRTUAL_W, VIRTUAL_H = GAME_W, GAME_H

    screen = pygame.display.set_mode((GAME_W, GAME_H), pygame.RESIZABLE)
    virtual_surface = pygame.Surface((V_GAME_W, V_GAME_H))

    clock = pygame.time.Clock()

    # Preload frequently-used UI/interaction sprites so keypresses can't crash on file load
    IMG_BUTTON_PRESSED = pygame.image.load(BUTTON_PRESSED_PATH).convert_alpha()
    IMG_DOOR = pygame.image.load(DOOR_PATH).convert_alpha()

    # --- audio setup ---
    def set_music(path: str) -> None:
        """Load + loop a music track safely. Keeps current pause state."""
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(RAGE_BGM_VOLUME if path == RAGE_BGM_PATH else BGM_VOLUME)
            pygame.mixer.music.play(-1)
            # If currently targeting, keep NON-rage music paused.
            # Rage music should always play regardless of lock state.
            if ghost_targeting and path != RAGE_BGM_PATH:
                pygame.mixer.music.pause()
        except Exception:
            pass

    # start normal BGM
    set_music(BGM_PATH)

    heartbeat_snd = None
    jumpscare_snd = None
    try:
        heartbeat_snd = pygame.mixer.Sound(HEARTBEAT_PATH)
        heartbeat_snd.set_volume(HEARTBEAT_VOLUME)
    except Exception:
        heartbeat_snd = None

    try:
        jumpscare_snd = pygame.mixer.Sound(JUMPSCARE_AUDIO_PATH)
        jumpscare_snd.set_volume(JUMPSCARE_VOLUME)
    except Exception:
        jumpscare_snd = None

    heartbeat_channel = pygame.mixer.Channel(1)
    jumpscare_channel = pygame.mixer.Channel(2)

    # jumpscare visuals (audio length unchanged)
    jumpscare_img = None
    for p in JUMPSCARE_IMG_CANDIDATES:
        try:
            if Path(p).exists():
                jumpscare_img = pygame.image.load(p).convert_alpha()
                break
        except Exception:
            jumpscare_img = None

    jumpscare_active = False
    jumpscare_start_ms = 0

    jumpscare_duration_ms = JUMPSCARE_VISUAL_MS
    jumpscare_fade_start_ms = JUMPSCARE_VISUAL_MS
    jumpscare_fade_end_ms = JUMPSCARE_VISUAL_MS

    # Cooldown to prevent spam when targeting flickers near the radius
    last_jumpscare_ms = -10**9

    def trigger_jumpscare():
        nonlocal jumpscare_active, jumpscare_start_ms, last_jumpscare_ms
        now = pygame.time.get_ticks()

        # Cooldown: ignore triggers for a few seconds after a jumpscare
        if now - last_jumpscare_ms < JUMPSCARE_COOLDOWN_MS:
            return

        last_jumpscare_ms = now
        jumpscare_active = True
        jumpscare_start_ms = now

        if jumpscare_snd is not None:
            jumpscare_channel.play(jumpscare_snd)

    def jumpscare_alpha(now_ms: int) -> int:
        # 0..fade_start => 255, then fade out until fade_end, then 0
        t = now_ms - jumpscare_start_ms
        if t < 0:
            return 0
        if t <= jumpscare_fade_start_ms:
            return 255
        if t >= jumpscare_fade_end_ms:
            return 0
        # linear fade
        span = jumpscare_fade_end_ms - jumpscare_fade_start_ms
        left = jumpscare_fade_end_ms - t
        return max(0, min(255, int(255 * (left / span))))

    em = EntityManager()

    # init systems
    ren_sys = RenderSystem(virtual_surface)

    mz = maze.generate_maze(V_GAME_W // WALL_OFFSET, V_GAME_H // WALL_OFFSET, 1, total_buttons)

    # create entities here
    mz_entities = []

    for irow, row in enumerate(mz):
        current_row_entities = []
        for icol, tile in enumerate(row):
            surface = None
            if tile == 1:
                ttype = random.randrange(0, 7)
                if ttype == 0:
                    surface = pygame.image.load(B_WALL_PATH).convert_alpha()
                else:
                    surface = pygame.image.load(WALL_PATH).convert_alpha()
            elif tile == 0:
                    surface = pygame.image.load(FLOOR_PATH).convert_alpha()
            elif tile == -1:
                surface = pygame.image.load(LOCKED_DOOR_PATH).convert_alpha()
                exit_x = icol
                exit_y = irow

                ghost_x = icol * WALL_OFFSET
                ghost_y = (irow - 1) * WALL_OFFSET
            elif tile == 2:
                surface = pygame.image.load(FLOOR_PATH).convert_alpha()
                player_x = icol * WALL_OFFSET
                player_y = irow * WALL_OFFSET
            elif tile == 3:
                surface = pygame.image.load(BUTTON_PATH).convert_alpha()
            elif tile == 4:
                surface = pygame.image.load(BUTTON_PRESSED_PATH).convert_alpha()
            else:
                surface = pygame.image.load(FLOOR_PATH).convert_alpha()
            
            x = icol * WALL_OFFSET
            y = irow * WALL_OFFSET
            tile_entity = em.create_entity()
            em.add_component(tile_entity, Position(x, y))
            em.add_component(tile_entity, Renderable(surface, WALL_OFFSET, WALL_OFFSET))

            current_row_entities.append(tile_entity)

        mz_entities.append(current_row_entities)

    ghost = em.create_entity()
    em.add_component(ghost, Position(ghost_x, ghost_y))
    em.add_component(ghost, Renderable(pygame.image.load(GHOST_PATH).convert_alpha(), WALL_OFFSET, WALL_OFFSET))

    # second ghost: spawn FAR from the first so they patrol different regions
    def find_farthest_walkable_from(start_tx: int, start_ty: int) -> tuple[int, int]:
        W = len(mz[0])
        H = len(mz)
        INF = 10**9

        dist = [[INF for _ in range(W)] for _ in range(H)]
        q = deque()

        if 0 <= start_tx < W and 0 <= start_ty < H and mz[start_ty][start_tx] != 1:
            dist[start_ty][start_tx] = 0
            q.append((start_tx, start_ty))
        else:
            # fallback: scan for any walkable tile
            for yy in range(H):
                for xx in range(W):
                    if mz[yy][xx] != 1:
                        dist[yy][xx] = 0
                        q.append((xx, yy))
                        break
                if q:
                    break

        while q:
            x, y = q.popleft()
            nd = dist[y][x] + 1
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H and mz[ny][nx] != 1 and dist[ny][nx] > nd:
                    dist[ny][nx] = nd
                    q.append((nx, ny))

        # pick farthest tile (avoid player spawn and door tile if possible)
        avoid = {
            (
                int((player_x + (WALL_OFFSET / 2)) // WALL_OFFSET),
                int((player_y + (WALL_OFFSET / 2)) // WALL_OFFSET),
            ),
            (exit_x, exit_y),
        }
        best = (start_tx, start_ty)
        bestd = -1
        for yy in range(H):
            for xx in range(W):
                if mz[yy][xx] == 1:
                    continue
                d = dist[yy][xx]
                if d >= INF:
                    continue
                if (xx, yy) in avoid:
                    continue
                if d > bestd:
                    bestd = d
                    best = (xx, yy)

        # if everything was avoided (tiny maps), just use absolute farthest
        if bestd < 0:
            for yy in range(H):
                for xx in range(W):
                    if mz[yy][xx] == 1:
                        continue
                    d = dist[yy][xx]
                    if d >= INF:
                        continue
                    if d > bestd:
                        bestd = d
                        best = (xx, yy)

        return best

    g1_tx = int((ghost_x + (WALL_OFFSET / 2)) // WALL_OFFSET)
    g1_ty = int((ghost_y + (WALL_OFFSET / 2)) // WALL_OFFSET)
    g2_tx, g2_ty = find_farthest_walkable_from(g1_tx, g1_ty)

    ghost2_x = g2_tx * WALL_OFFSET
    ghost2_y = g2_ty * WALL_OFFSET

    ghost2 = em.create_entity()
    em.add_component(ghost2, Position(ghost2_x, ghost2_y))
    em.add_component(ghost2, Renderable(pygame.image.load(GHOST_PATH).convert_alpha(), WALL_OFFSET, WALL_OFFSET))

    player = em.create_entity()
    em.add_component(player, Position(player_x, player_y))
    em.add_component(player, Renderable(pygame.image.load(PLAYER_PATH).convert_alpha(), WALL_OFFSET, WALL_OFFSET))

    # play bgm (already started in the audio setup try-block)
    try:
        if not pygame.mixer.music.get_busy():
            pygame.mixer.music.play(-1)
    except Exception:
        pass

    # Ghost AI (normal / rage)

    rage_mode = False
    rage_target_tile = None  # (tx, ty) snapshot at rage start

    # Use tunables from the top of the script
    TARGET_RADIUS_NORMAL = LOCK_RADIUS
    TARGET_RADIUS_RAGE = LOCK_RADIUS

    if USE_FOG_OF_WAR and FOG_RADIUS_MATCH_LOCK:
        light_rad = VISION_RADIUS * TILE_SIZE
        light_mask = build_light_mask(light_rad)

    ghost_next_step_ms = 0
    ghost2_next_step_ms = 0

    ghost_targeting = False

    ghost_slide = {
        ghost: {"moving": False, "target": (0.0, 0.0)},
        ghost2: {"moving": False, "target": (0.0, 0.0)},
    }

    def start_ghost_slide(eid: int, next_tile: tuple[int, int]) -> None:
        st = ghost_slide[eid]
        if st["moving"]:
            return
        ntx, nty = next_tile
        st["moving"] = True
        st["target"] = (float(ntx * WALL_OFFSET), float(nty * WALL_OFFSET))

    def update_ghost_slide(eid: int, dt: float, step_ms: int) -> None:
        st = ghost_slide[eid]
        if not st["moving"]:
            return
        p = em.entities[eid][Position]
        tx, ty = st["target"]
        vx = tx - p.x
        vy = ty - p.y
        dist2 = vx * vx + vy * vy

        speed_px = WALL_OFFSET * 1000.0 / max(1.0, float(step_ms))
        step = speed_px * dt

        if dist2 <= step * step:
            p.x = tx
            p.y = ty
            st["moving"] = False
            return

        dist = math.sqrt(dist2)
        if dist > 1e-6:
            p.x += (vx / dist) * step
            p.y += (vy / dist) * step

    def tile_of_entity(eid: int) -> tuple[int, int]:
        p = em.entities[eid][Position]
        return (
            int((p.x + (WALL_OFFSET / 2)) // WALL_OFFSET),
            int((p.y + (WALL_OFFSET / 2)) // WALL_OFFSET),
        )

    def set_entity_tile(eid: int, tx: int, ty: int) -> None:
        em.entities[eid][Position].x = tx * WALL_OFFSET
        em.entities[eid][Position].y = ty * WALL_OFFSET

    def is_walkable_tile(tx: int, ty: int) -> bool:
        if ty < 0 or tx < 0 or ty >= len(mz) or tx >= len(mz[0]):
            return False
        return mz[ty][tx] != 1

    walkable_tiles = [(x, y) for y, row in enumerate(mz) for x, v in enumerate(row) if v != 1]

    def manhattan(a: tuple[int,int], b: tuple[int,int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    # Last known player tile when a lock starts (used when LOS is broken)
    last_known_player_tile = None  # (tx, ty)

    def has_los(a: tuple[int,int], b: tuple[int,int]) -> bool:
        """LOS only for same row/col with no walls."""
        ax, ay = int(a[0]), int(a[1])
        bx, by = int(b[0]), int(b[1])

        if ax == bx:
            # same column, scan y
            step = 1 if by > ay else -1
            for y in range(ay + step, by, step):
                if not is_walkable_tile(ax, y):
                    return False
            return True

        if ay == by:
            # same row, scan x
            step = 1 if bx > ax else -1
            for x in range(ax + step, bx, step):
                if not is_walkable_tile(x, ay):
                    return False
            return True

        return False

    def greedy_step_towards(start: tuple[int,int], goal: tuple[int,int]) -> tuple[int,int] | None:
        """No BFS. Take one step that reduces Manhattan distance if possible."""
        x, y = start
        gx, gy = goal

        candidates = []
        # Try moves in an order that tends to close distance
        if gx > x:
            candidates.append((x + 1, y))
        elif gx < x:
            candidates.append((x - 1, y))
        if gy > y:
            candidates.append((x, y + 1))
        elif gy < y:
            candidates.append((x, y - 1))

        # Add sideways options as fallbacks
        candidates.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])

        seen = set()
        best = None
        bestd = 10**9
        for nx, ny in candidates:
            if (nx, ny) in seen:
                continue
            seen.add((nx, ny))
            if not is_walkable_tile(nx, ny):
                continue
            d = manhattan((nx, ny), goal)
            if d < bestd:
                bestd = d
                best = (nx, ny)

        return best

    def bfs_next_step(start: tuple[int,int], goal: tuple[int,int]) -> tuple[int,int] | None:
        """Return next tile from start towards goal using BFS (grid, walls blocked)."""
        if start == goal:
            return None

        q = deque([start])
        prev = {start: None}

        while q:
            x, y = q.popleft()
            if (x, y) == goal:
                break
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) in prev:
                    continue
                if not is_walkable_tile(nx, ny):
                    continue
                prev[(nx, ny)] = (x, y)
                q.append((nx, ny))

        if goal not in prev:
            return None

        # walk back from goal to find the step after start
        cur = goal
        while prev[cur] is not None and prev[cur] != start:
            cur = prev[cur]
        return cur if prev[cur] == start else None

    # roaming: pacman-style scatter

    W_TILES = len(mz[0])
    H_TILES = len(mz)

    # Four corner targets (kept inside the border to avoid sticking to walls)
    corners = [
        (1, 1),
        (W_TILES - 2, 1),
        (1, H_TILES - 2),
        (W_TILES - 2, H_TILES - 2),
    ]

    # Each ghost uses a different scatter corner (Pac-Man style)
    scatter_index = {ghost: 1, ghost2: 2}

    # Remember last move direction (avoids back-and-forth jitter)
    roam_dir = {ghost: (0, 0), ghost2: (0, 0)}  # eid -> (dx, dy)

    def next_scatter_goal(eid: int) -> tuple[int, int]:
        idx = scatter_index.get(eid, 0)
        # Pick the next corner goal; if it is blocked, nudge inward
        gx, gy = corners[idx % 4]
        if not is_walkable_tile(gx, gy):
            # Try nudging inward
            gx = max(1, min(W_TILES - 2, gx))
            gy = max(1, min(H_TILES - 2, gy))
        return (gx, gy)

    def advance_scatter_goal(eid: int) -> None:
        scatter_index[eid] = (scatter_index.get(eid, 0) + 1) % 4

    def pacman_roam_step(eid: int, start: tuple[int, int]) -> tuple[int, int] | None:
        """Pac-Man style roaming: head toward a corner target, pick the move that gets closer, avoid reversing."""
        x, y = start

        goal = next_scatter_goal(eid)
        if start == goal:
            advance_scatter_goal(eid)
            goal = next_scatter_goal(eid)

        last_dx, last_dy = roam_dir.get(eid, (0, 0))
        reverse = (-last_dx, -last_dy)

        # Collect legal neighbor moves
        moves = []  # (nx, ny, dx, dy)
        for dx, dy in ((0, -1), (-1, 0), (0, 1), (1, 0)):
            nx, ny = x + dx, y + dy
            if is_walkable_tile(nx, ny):
                moves.append((nx, ny, dx, dy))

        if not moves:
            return None

        # Pac-Man rule: avoid reversing unless forced
        filtered = moves
        if reverse != (0, 0) and len(moves) > 1:
            filtered = [m for m in moves if (m[2], m[3]) != reverse]
            if not filtered:
                filtered = moves

        # Choose the move that minimizes Manhattan distance to the goal
        bestd = 10**9
        best = []
        for nx, ny, dx, dy in filtered:
            d = manhattan((nx, ny), goal)
            if d < bestd:
                bestd = d
                best = [(nx, ny, dx, dy)]
            elif d == bestd:
                best.append((nx, ny, dx, dy))

        choice = random.choice(best)
        nx, ny, dx, dy = choice
        roam_dir[eid] = (dx, dy)
        return (nx, ny)

    def set_targeting(on: bool):
        nonlocal ghost_targeting
        if on == ghost_targeting:
            return
        ghost_targeting = on

        # Music policy:
        # - Normal mode: targeting pauses music, losing target resumes music.
        # - Rage mode: rage music should keep playing no matter what.
        try:
            if not rage_mode:
                if on:
                    pygame.mixer.music.pause()
                else:
                    pygame.mixer.music.unpause()
        except Exception:
            pass

        if heartbeat_snd is None:
            return

        if on:
            try:
                heartbeat_channel.play(heartbeat_snd, loops=-1)
            except Exception:
                pass
        else:
            try:
                heartbeat_channel.stop()
            except Exception:
                pass

    scene = MENU_SCENE_STR
    js_scene_start_ms = 0
    js_scene_length_ms = jumpscare_duration_ms  # reuse the visual duration

    WHITE = (255, 255, 255)
    GREY = (150, 150, 150)
    DARK_GREY = (50, 50, 50)
    HOVER_GREY = (80, 80, 80)

    start_btn = Button(V_GAME_W//2 - 300, V_GAME_H//2 - 120, 600, 100, "START GAME", WHITE, GREY, DARK_GREY, HOVER_GREY, mc_font)
    quit_btn = Button(V_GAME_W//2 - 300, V_GAME_H//2 + 20, 600, 100, "QUIT", WHITE, GREY, DARK_GREY, HOVER_GREY, mc_font)
    return_btn = Button(V_GAME_W//2 - 500, V_GAME_H//2 + 150, 1000, 100, "RETURN TO MENU", WHITE, GREY, DARK_GREY, HOVER_GREY, mc_font)

    win_text = mc_font.render("YOU ESCAPED!", True, (255, 255, 255)) # Green text
    win_rect = win_text.get_rect(center=(V_GAME_W // 2, V_GAME_H // 2 - 100))

    # main loop
    while True:
        dt = clock.tick(60) / 1000.0
        if dt > 0.05:
            dt = 0.05

        if scene == MENU_SCENE_STR:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            curr_screen_w, curr_screen_h = screen.get_size()
            v_mouse = (mouse_x * V_GAME_W / curr_screen_w, mouse_y * V_GAME_H / curr_screen_h)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

                if start_btn.is_pressed(event, v_mouse):
                    scene = GAME_SCENE_STR
                elif quit_btn.is_pressed(event, v_mouse):
                    return
            
            virtual_surface.fill((0, 0, 0))

            start_btn.draw(virtual_surface, v_mouse)
            quit_btn.draw(virtual_surface, v_mouse)

            screen.blit(pygame.transform.scale(virtual_surface, (curr_screen_w, curr_screen_h)), (0, 0))
            pygame.display.flip()
            continue

        elif scene == WIN_SCENE_STR:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            curr_screen_w, curr_screen_h = screen.get_size()
            v_mouse = (mouse_x * V_GAME_W / curr_screen_w, mouse_y * V_GAME_H / curr_screen_h)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                
                if return_btn.is_pressed(event, v_mouse):
                    scene = MENU_SCENE_STR

            virtual_surface.fill((0, 255, 0))
            
            virtual_surface.blit(win_text, win_rect)
            
            return_btn.draw(virtual_surface, v_mouse)

            screen.blit(pygame.transform.scale(virtual_surface, (curr_screen_w, curr_screen_h)), (0, 0))
            pygame.display.flip()
            continue


        elif scene == JS_SCENE_STR:
            # Show jumpscare overlay for a short time, then return to menu
            now_ms = pygame.time.get_ticks()

            # Render world (optional background)
            ren_sys.render(em)

            # Full black cover + jumpscare image
            if jumpscare_img is not None:
                cover = pygame.Surface((V_GAME_W, V_GAME_H))
                cover.fill((0, 0, 0))
                virtual_surface.blit(cover, (0, 0))

                iw, ih = jumpscare_img.get_size()
                if iw > 0 and ih > 0:
                    scale = V_GAME_H / ih
                    nw, nh = int(iw * scale), V_GAME_H
                    overlay = pygame.transform.smoothscale(jumpscare_img, (nw, nh)).convert_alpha()
                    ox = (V_GAME_W - nw) // 2
                    virtual_surface.blit(overlay, (ox, 0))

            curr_screen_w, curr_screen_h = screen.get_size()
            screen.blit(pygame.transform.scale(virtual_surface, (curr_screen_w, curr_screen_h)), (0, 0))
            pygame.display.flip()

            # After the scene length, return to menu
            if now_ms - js_scene_start_ms >= js_scene_length_ms:
                scene = MENU_SCENE_STR

            # Handle quit events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.VIDEORESIZE:
                    screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)

            continue

        elif scene == GAME_SCENE_STR:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

                if event.type == pygame.VIDEORESIZE:
                    screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)

                elif event.type == pygame.KEYDOWN:
                    # Always reference player's components (safe for any key)
                    components = em.entities[player]

                    # Arrow keys: hold-to-move direction
                    if event.key == pygame.K_w:
                        held_dir = (0, -1)
                        if not USE_SMOOTH_MOVEMENT:
                            move_player_by_tiles(0, -1)
                            now = pygame.time.get_ticks()
                            next_move_time = now + MOVE_INITIAL_DELAY_MS
                    elif event.key == pygame.K_s:
                        held_dir = (0, 1)
                        if not USE_SMOOTH_MOVEMENT:
                            move_player_by_tiles(0, 1)
                            now = pygame.time.get_ticks()
                            next_move_time = now + MOVE_INITIAL_DELAY_MS
                    elif event.key == pygame.K_d:
                        held_dir = (1, 0)
                        if not USE_SMOOTH_MOVEMENT:
                            move_player_by_tiles(1, 0)
                            now = pygame.time.get_ticks()
                            next_move_time = now + MOVE_INITIAL_DELAY_MS
                    elif event.key == pygame.K_a:
                        held_dir = (-1, 0)
                        if not USE_SMOOTH_MOVEMENT:
                            move_player_by_tiles(-1, 0)
                            now = pygame.time.get_ticks()
                            next_move_time = now + MOVE_INITIAL_DELAY_MS

                    # Button press (H) and legacy key (F) do the same thing
                    elif event.key in (pygame.K_f, pygame.K_h) and not is_hidden:
                        x = int((components[Position].x + (WALL_OFFSET / 2)) // WALL_OFFSET)
                        y = int((components[Position].y + (WALL_OFFSET / 2)) // WALL_OFFSET)

                        if 0 <= y < len(mz) and 0 <= x < len(mz[0]):
                            if mz[y][x] == 3:
                                mz[y][x] = 4

                                tile_comp = em.entities[mz_entities[y][x]]
                                tile_comp[Renderable].surface = IMG_BUTTON_PRESSED
                                preseed_buttons += 1

                                if preseed_buttons == total_buttons:
                                    door_comp = em.entities[mz_entities[exit_y][exit_x]]
                                    door_comp[Renderable].surface = IMG_DOOR

                                    is_door_unlocked = False
                                    active_msg = "The door has been unlocked"
                                    msg_start_time = pygame.time.get_ticks()
                                else:
                                    active_msg = f"{preseed_buttons}/{total_buttons} button(s) pressed"
                                    msg_start_time = pygame.time.get_ticks()

                    # Rage triggers exactly when all buttons are pressed
                    if preseed_buttons == total_buttons and not rage_mode:
                        rage_mode = True

                        # Switch BGM to rage track
                        set_music(RAGE_BGM_PATH)

                        px_t = int((em.entities[player][Position].x + (WALL_OFFSET / 2)) // WALL_OFFSET)
                        py_t = int((em.entities[player][Position].y + (WALL_OFFSET / 2)) // WALL_OFFSET)
                        rage_target_tile = (px_t, py_t)
                        trigger_jumpscare()

                    # Hide toggle (legacy feature)
                    elif event.key == pygame.K_q:
                        if hide_bar_curent > 0:
                            is_hidden = not is_hidden
                            hiden_tick = dt

                elif event.type == pygame.KEYUP:
                    dx, dy = held_dir
                    if dy == -1 and event.key == pygame.K_w:
                        held_dir = (0, 0)
                    elif dy == 1 and event.key == pygame.K_s:
                        held_dir = (0, 0)
                    elif dx == 1 and event.key == pygame.K_d:
                        held_dir = (0, 0)
                    elif dx == -1 and event.key == pygame.K_a:
                        held_dir = (0, 0)

            # Movement update
            if USE_SMOOTH_MOVEMENT:
                update_player_smooth(dt)
            else:
                if held_dir != (0, 0):
                    now = pygame.time.get_ticks()
                    if now >= next_move_time:
                        dx, dy = held_dir
                        move_player_by_tiles(dx, dy)
                        next_move_time = now + MOVE_REPEAT_MS

            # Hide bar drain/recover (legacy feature)
            if is_hidden:
                hide_bar_curent = max(hide_bar_curent - dt, 0)
                if hide_bar_curent == 0:
                    is_hidden = False
            else:
                if hide_bar_curent < hide_bar_max:
                    hide_bar_curent = min(hide_bar_curent + (dt * HIDDEN_RECHARGE_MULTIPLIER), hide_bar_max)

            # =========================
            # Ghost update (movement + targeting + catch)
            # =========================
            now_ms = pygame.time.get_ticks()

            player_tile = (
                int((em.entities[player][Position].x + (WALL_OFFSET / 2)) // WALL_OFFSET),
                int((em.entities[player][Position].y + (WALL_OFFSET / 2)) // WALL_OFFSET),
            )

            # Win condition: touching the door after it's unlocked
            if preseed_buttons == total_buttons and player_tile == (exit_x, exit_y):
                scene = WIN_SCENE_STR
                continue

            if rage_mode:
                step_ms = GHOST_STEP_RAGE_MS
                radius = TARGET_RADIUS_RAGE
                target_tile = rage_target_tile if rage_target_tile is not None else player_tile
            else:
                step_ms = GHOST_STEP_NORMAL_MS
                radius = TARGET_RADIUS_NORMAL
                target_tile = player_tile

            g1_tile = tile_of_entity(ghost)
            g2_tile = tile_of_entity(ghost2)

            g1_can_see = has_los(g1_tile, player_tile)
            g2_can_see = has_los(g2_tile, player_tile)

            d1 = manhattan(g1_tile, player_tile)
            d2 = manhattan(g2_tile, player_tile)

            if ghost_targeting:
                targeting_now = not (d1 > UNLOCK_RADIUS and d2 > UNLOCK_RADIUS)
            else:
                targeting_now = (d1 <= radius) or (d2 <= radius)

            chase_cooldown_active = (now_ms - last_jumpscare_ms) < JUMPSCARE_COOLDOWN_MS
            bfs_override_active = rage_mode

            # Acquire snapshot on lock start
            if targeting_now and not ghost_targeting:
                last_known_player_tile = player_tile
                trigger_jumpscare()

            # Update last-known only when LOS exists
            if targeting_now and (g1_can_see or g2_can_see):
                last_known_player_tile = player_tile

            # Clear last-known only when lock is off and no overrides
            if not targeting_now and not chase_cooldown_active and not bfs_override_active:
                last_known_player_tile = None

            set_targeting(targeting_now)

            # Move ghost1
            if now_ms >= ghost_next_step_ms and not ghost_slide[ghost]["moving"]:
                ghost_next_step_ms = now_ms + step_ms
                start = g1_tile

                nxt = None
                if (targeting_now or chase_cooldown_active or bfs_override_active) and last_known_player_tile is not None:
                    nxt = bfs_next_step(start, last_known_player_tile)
                if nxt is None and last_known_player_tile is not None:
                    nxt = greedy_step_towards(start, last_known_player_tile)
                if nxt is None:
                    nxt = pacman_roam_step(ghost, start)
                if nxt is not None:
                    start_ghost_slide(ghost, nxt)

            # Move ghost2
            if now_ms >= ghost2_next_step_ms and not ghost_slide[ghost2]["moving"]:
                ghost2_next_step_ms = now_ms + step_ms + 35
                start = g2_tile

                nxt = None
                if (targeting_now or chase_cooldown_active or bfs_override_active) and last_known_player_tile is not None:
                    nxt = bfs_next_step(start, last_known_player_tile)
                if nxt is None and last_known_player_tile is not None:
                    nxt = greedy_step_towards(start, last_known_player_tile)
                if nxt is None:
                    nxt = pacman_roam_step(ghost2, start)
                if nxt is not None:
                    start_ghost_slide(ghost2, nxt)

            # Smooth ghost sliding update
            update_ghost_slide(ghost, dt, step_ms)
            update_ghost_slide(ghost2, dt, step_ms)

            # Catch condition -> go to jumpscare scene
            if tile_of_entity(ghost) == player_tile or tile_of_entity(ghost2) == player_tile:
                if not is_hidden:
                    trigger_jumpscare()
                    js_scene_start_ms = pygame.time.get_ticks()
                    scene = JS_SCENE_STR
                    continue

            # Jumpscare lifetime
            if jumpscare_active and (now_ms - jumpscare_start_ms >= jumpscare_duration_ms):
                jumpscare_active = False

            # Render world
            ren_sys.render(em)

            # Fog overlay (optional)
            if USE_FOG_OF_WAR:
                fog_surface.fill((0, 0, 0, 255))
                position_component = em.entities[player][Position]
                mask_x = (position_component.x + (WALL_OFFSET // 2)) - light_rad
                mask_y = (position_component.y + (WALL_OFFSET // 2)) - light_rad
                fog_surface.blit(light_mask, (mask_x, mask_y), special_flags=pygame.BLEND_RGBA_MIN)
                virtual_surface.blit(fog_surface, (0, 0))

            # Jumpscare overlay
            if jumpscare_active and jumpscare_img is not None:
                a = jumpscare_alpha(pygame.time.get_ticks())
                if a > 0:
                    cover = pygame.Surface((V_GAME_W, V_GAME_H))
                    cover.fill((0, 0, 0))
                    cover.set_alpha(a)
                    virtual_surface.blit(cover, (0, 0))

                    iw, ih = jumpscare_img.get_size()
                    if iw > 0 and ih > 0:
                        scale = V_GAME_H / ih
                        nw, nh = int(iw * scale), V_GAME_H
                        overlay = pygame.transform.smoothscale(jumpscare_img, (nw, nh)).convert_alpha()
                        overlay.set_alpha(a)
                        ox = (V_GAME_W - nw) // 2
                        virtual_surface.blit(overlay, (ox, 0))

            # Timed message
            if active_msg:
                still_active = draw_timed_text(virtual_surface, active_msg, msg_start_time, MSG_DURATION_MS)
                if not still_active:
                    active_msg = ""

            # Hide bar UI (above player)
            p_pos = em.entities[player][Position]
            bar_w = WALL_OFFSET + HIDE_BAR_WIDTH_PAD
            bar_h = HIDE_BAR_HEIGHT
            bar_x = p_pos.x + (WALL_OFFSET / 2) - (bar_w / 2)
            bar_y = p_pos.y + HIDE_BAR_Y_OFFSET

            # background
            pygame.draw.rect(virtual_surface, (50, 50, 50), (bar_x, bar_y, bar_w, bar_h))

            # fill
            frac = 0.0 if hide_bar_max <= 0 else max(0.0, min(1.0, hide_bar_curent / hide_bar_max))
            fill_w = int(bar_w * frac)
            if fill_w > 0:
                bar_color = (255, 0, 0) if is_hidden else (0, 255, 0)
                pygame.draw.rect(virtual_surface, bar_color, (bar_x, bar_y, fill_w, bar_h))

            # Present
            curr_w, curr_h = screen.get_size()
            scaled_surface = pygame.transform.scale(virtual_surface, (curr_w, curr_h))
            screen.blit(scaled_surface, (0, 0))
            pygame.display.flip()

            continue


        await asyncio.sleep(0)

def draw_timed_text(surface, text, start_ticks, duration_ms):
    if pygame.time.get_ticks() - start_ticks < duration_ms:
        text_surf = font.render(text, True, (255, 0, 0)) 

        text_rect = text_surf.get_rect(center=(V_GAME_W // 2, V_GAME_H // 10))
        
        surface.blit(text_surf, text_rect)
        return True
    return False


# Ensure main loop is invoked when run as a script
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
