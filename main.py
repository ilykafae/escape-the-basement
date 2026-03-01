# pygbag: width=1280, height=720

import pygame, asyncio, maze, random, math
from collections import deque
from pathlib import Path
from ecs.system import *

GAME_W = 765
GAME_H = 435
V_GAME_W = 2550
V_GAME_H = 1450

# Make asset paths robust (works no matter where you run `python main.py` from)
BASE_DIR = Path(__file__).resolve().parent

def asset_path(rel: str) -> str:
    return str(BASE_DIR / rel)


USE_FOG_OF_WAR = True

# =========================
# TUNABLE SETTINGS (edit here)
# =========================

# Tile size in pixels
TILE_SIZE = 50

# Player: hold-to-move (arrow keys)
MOVE_INITIAL_DELAY_MS = 200
MOVE_REPEAT_MS = 90

# Buttons
TOTAL_BUTTONS = 25

# Fog-of-war: when enabled, player vision radius = LOCK_RADIUS * TILE_SIZE
FOG_RADIUS_MATCH_LOCK = True

# Ghost movement timing (ms per tile step)
GHOST_STEP_NORMAL_MS = 250
GHOST_STEP_RAGE_MS = 210

# Lock (acquire) radius in tiles
LOCK_RADIUS = 5

# Unlock (de-target) radius in tiles (hysteresis)
UNLOCK_RADIUS = 9

# Jumpscare visuals
JUMPSCARE_VISUAL_MS = 1000
JUMPSCARE_COOLDOWN_MS = 6000

# Timed UI message duration
MSG_DURATION_MS = 3000

# Font
FONT_SIZE = 75

# Audio volumes
BGM_VOLUME = 0.5
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

BGM_PATH = asset_path("assets/audio/bgm.mp3")
HEARTBEAT_PATH = asset_path("assets/audio/heartbeat.mp3")
JUMPSCARE_AUDIO_PATH = asset_path("assets/audio/jumpscare_scream.mp3")

# Your repo has had multiple spellings/cases for this file. We'll try a few.
JUMPSCARE_IMG_CANDIDATES = [
    asset_path("assets/sprite/jumpscar.JPG"),
    asset_path("assets/sprite/jumpscar.jpg"),
    asset_path("assets/sprite/jumpscare.JPG"),
    asset_path("assets/sprite/jumpscare.jpg"),
    asset_path("assets/sprite/jumpscar.JPEG"),
    asset_path("assets/sprite/jumpscare.JPEG"),
]

FONT_PATH = 'assets/fonts/redcap.ttf'

WALL_OFFSET = TILE_SIZE

font = None

async def main():
    # =========================
    # Hold-to-move (arrow keys)
    # =========================
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
    pygame.init()
    pygame.font.init()
    pygame.mixer.init()

    global font
    font = pygame.font.Font(FONT_PATH, FONT_SIZE)

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

    active_msg = ""
    msg_start_time = 0

    fog_surface = pygame.Surface((V_GAME_W, V_GAME_H), pygame.SRCALPHA)

    # 先給一個預設值；之後會在 Ghost AI 參數出現後（TARGET_RADIUS_NORMAL）重建一次
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

    # --- audio setup ---
    try:
        pygame.mixer.music.load(BGM_PATH)
        pygame.mixer.music.set_volume(BGM_VOLUME)
        pygame.mixer.music.play(-1)
    except Exception:
        # If audio fails on some machines, keep game running.
        pass

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

    # Reserve channels so SFX don't fight
    heartbeat_channel = pygame.mixer.Channel(1)
    jumpscare_channel = pygame.mixer.Channel(2)

    # --- jumpscare visuals ---
    jumpscare_img = None
    for p in JUMPSCARE_IMG_CANDIDATES:
        try:
            if Path(p).exists():
                # JPG has no alpha channel; convert() is fine, but convert_alpha() also works.
                jumpscare_img = pygame.image.load(p).convert_alpha()
                break
        except Exception:
            jumpscare_img = None

    jumpscare_active = False
    jumpscare_start_ms = 0

    # Jumpscare visual timing
    # 需求：圖片只保留 1.0 秒（不做淡出），之後直接消失。
    # 音效照常播放，不受這裡影響。
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
        avoid = {(player_x // WALL_OFFSET, player_y // WALL_OFFSET), (exit_x, exit_y)}
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

    g1_tx = ghost_x // WALL_OFFSET
    g1_ty = ghost_y // WALL_OFFSET
    g2_tx, g2_ty = find_farthest_walkable_from(g1_tx, g1_ty)

    ghost2_x = g2_tx * WALL_OFFSET
    ghost2_y = g2_ty * WALL_OFFSET

    ghost2 = em.create_entity()
    em.add_component(ghost2, Position(ghost2_x, ghost2_y))
    em.add_component(ghost2, Renderable(pygame.image.load(GHOST_PATH).convert_alpha(), WALL_OFFSET, WALL_OFFSET))

    player = em.create_entity()
    em.add_component(player, Position(player_x, player_y))
    em.add_component(player, Renderable(pygame.image.load(PLAYER_PATH).convert_alpha(), WALL_OFFSET, WALL_OFFSET))


    # =========================
    # Ghost AI (normal / rage)
    # =========================

    rage_mode = False
    rage_target_tile = None  # (tx, ty) snapshot at rage start

    # Use tunables from the top of the script
    TARGET_RADIUS_NORMAL = LOCK_RADIUS
    TARGET_RADIUS_RAGE = LOCK_RADIUS

    # =========================
    # Fog-of-war: 視野半徑跟鎖定距離一致
    # =========================
    # 需求：關燈模式下，玩家視野（像素） = 鎖定距離（tile） * WALL_OFFSET
    if USE_FOG_OF_WAR and FOG_RADIUS_MATCH_LOCK:
        light_rad = LOCK_RADIUS * TILE_SIZE
        light_mask = build_light_mask(light_rad)

    ghost_next_step_ms = 0
    ghost2_next_step_ms = 0

    ghost_targeting = False

    def tile_of_entity(eid: int) -> tuple[int, int]:
        p = em.entities[eid][Position]
        return (p.x // WALL_OFFSET, p.y // WALL_OFFSET)  # (tx, ty)

    def set_entity_tile(eid: int, tx: int, ty: int) -> None:
        em.entities[eid][Position].x = tx * WALL_OFFSET
        em.entities[eid][Position].y = ty * WALL_OFFSET

    def is_walkable_tile(tx: int, ty: int) -> bool:
        if ty < 0 or tx < 0 or ty >= len(mz) or tx >= len(mz[0]):
            return False
        return mz[ty][tx] != 1

    # Precompute walkable tiles for roaming targets (so roaming can pick a far goal)
    walkable_tiles = [(x, y) for y, row in enumerate(mz) for x, v in enumerate(row) if v != 1]

    def manhattan(a: tuple[int,int], b: tuple[int,int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    # Last known player tile when a lock starts (used when LOS is broken)
    last_known_player_tile = None  # (tx, ty)

    def has_los(a: tuple[int,int], b: tuple[int,int]) -> bool:
        """Very simple LOS: only same row or same column with no walls between.
        Turning a corner breaks LOS, which matches your design.
        """
        ax, ay = a
        bx, by = b

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

    # =========================
    # Pac-Man style roaming (scatter)
    # =========================
    # 參考 Pac-Man 鬼的行為：
    # - 每隻鬼有一個「角落目標點」（scatter target）
    # - 每一步在路口選擇會讓自己更接近目標的方向
    # - 盡量不走回頭路（除非被迫）
    # - tie 隨機打破，避免像機器人

    W_TILES = len(mz[0])
    H_TILES = len(mz)

    # 四個角落（保守一點避開邊界，避免卡牆）
    corners = [
        (1, 1),
        (W_TILES - 2, 1),
        (1, H_TILES - 2),
        (W_TILES - 2, H_TILES - 2),
    ]

    # 每隻鬼的 scatter 角落不同（像 Pac-Man）
    scatter_index = {ghost: 1, ghost2: 2}

    # 記住上一個移動方向（避免來回抖）
    roam_dir = {ghost: (0, 0), ghost2: (0, 0)}  # eid -> (dx, dy)

    def next_scatter_goal(eid: int) -> tuple[int, int]:
        idx = scatter_index.get(eid, 0)
        # 找到下一個可走角落（如果角落剛好是牆，就往內縮）
        gx, gy = corners[idx % 4]
        if not is_walkable_tile(gx, gy):
            # 往內縮一格試試
            gx = max(1, min(W_TILES - 2, gx))
            gy = max(1, min(H_TILES - 2, gy))
        return (gx, gy)

    def advance_scatter_goal(eid: int) -> None:
        scatter_index[eid] = (scatter_index.get(eid, 0) + 1) % 4

    def pacman_roam_step(eid: int, start: tuple[int, int]) -> tuple[int, int] | None:
        """Pac-Man 式漫遊：朝角落目標走，路口選最接近目標的方向，盡量不回頭。"""
        x, y = start

        goal = next_scatter_goal(eid)
        if start == goal:
            advance_scatter_goal(eid)
            goal = next_scatter_goal(eid)

        last_dx, last_dy = roam_dir.get(eid, (0, 0))
        reverse = (-last_dx, -last_dy)

        # 收集合法鄰居
        moves = []  # (nx, ny, dx, dy)
        for dx, dy in ((0, -1), (-1, 0), (0, 1), (1, 0)):
            nx, ny = x + dx, y + dy
            if is_walkable_tile(nx, ny):
                moves.append((nx, ny, dx, dy))

        if not moves:
            return None

        # Pac-Man 規則：如果有其他選擇，就避免回頭
        filtered = moves
        if reverse != (0, 0) and len(moves) > 1:
            filtered = [m for m in moves if (m[2], m[3]) != reverse]
            if not filtered:
                filtered = moves

        # 選擇讓自己更接近目標的方向（Manhattan 距離最小）
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

        # Audio behavior:
        # - When targeting: pause BGM and play ONLY heartbeat loop.
        # - When not targeting: stop heartbeat and resume BGM.
        try:
            if on:
                pygame.mixer.music.pause()
            else:
                pygame.mixer.music.unpause()
        except Exception:
            # If music wasn't loaded, ignore.
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

    # main loop
    while True:
        for event in pygame.event.get():
            if event == pygame.QUIT:
                return

            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    held_dir = (0, -1)
                    move_player_by_tiles(0, -1)
                    now = pygame.time.get_ticks()
                    next_move_time = now + MOVE_INITIAL_DELAY_MS
                elif event.key == pygame.K_DOWN:
                    held_dir = (0, 1)
                    move_player_by_tiles(0, 1)
                    now = pygame.time.get_ticks()
                    next_move_time = now + MOVE_INITIAL_DELAY_MS
                elif event.key == pygame.K_RIGHT:
                    held_dir = (1, 0)
                    move_player_by_tiles(1, 0)
                    now = pygame.time.get_ticks()
                    next_move_time = now + MOVE_INITIAL_DELAY_MS
                elif event.key == pygame.K_LEFT:
                    held_dir = (-1, 0)
                    move_player_by_tiles(-1, 0)
                    now = pygame.time.get_ticks()
                    next_move_time = now + MOVE_INITIAL_DELAY_MS
                elif event.key == pygame.K_h:
                    x = components[Position].x // WALL_OFFSET
                    y = components[Position].y // WALL_OFFSET

                    if mz[y][x] == 3:
                        mz[y][x] = 4

                        components = em.entities[mz_entities[y][x]]
                        components[Renderable].surface = pygame.image.load(BUTTON_PRESSED_PATH).convert_alpha()
                        preseed_buttons += 1

                        if preseed_buttons == total_buttons:
                            components = em.entities[mz_entities[exit_y][exit_x]]
                            components[Renderable].surface = pygame.image.load(DOOR_PATH).convert_alpha()

                            is_door_unlocked = False

                            active_msg = "The door has been unlocked"
                            msg_start_time = pygame.time.get_ticks()
                        else:
                            active_msg = f"{preseed_buttons}/{total_buttons} button(s) pressed"
                            msg_start_time = pygame.time.get_ticks()

                    # Rage mode triggers exactly when all buttons are pressed
                    if preseed_buttons == total_buttons and not rage_mode:
                        rage_mode = True
                        # snapshot player location at rage start
                        px_t = em.entities[player][Position].x // WALL_OFFSET
                        py_t = em.entities[player][Position].y // WALL_OFFSET
                        rage_target_tile = (px_t, py_t)
                        trigger_jumpscare()
            elif event.type == pygame.KEYUP:
                # Release stops the continuous movement immediately
                dx, dy = held_dir
                if dy == -1 and event.key == pygame.K_UP:
                    held_dir = (0, 0)
                elif dy == 1 and event.key == pygame.K_DOWN:
                    held_dir = (0, 0)
                elif dx == 1 and event.key == pygame.K_RIGHT:
                    held_dir = (0, 0)
                elif dx == -1 and event.key == pygame.K_LEFT:
                    held_dir = (0, 0)
        
        # Continuous movement while holding an arrow key
        if held_dir != (0, 0):
            now = pygame.time.get_ticks()
            if now >= next_move_time:
                dx, dy = held_dir
                move_player_by_tiles(dx, dy)
                next_move_time = now + MOVE_REPEAT_MS

        # =========================
        # Ghost update (movement + targeting + catch)
        # =========================
        now_ms = pygame.time.get_ticks()

        # Determine current player target
        player_tile = (em.entities[player][Position].x // WALL_OFFSET, em.entities[player][Position].y // WALL_OFFSET)

        # Choose target radius and step speed based on mode
        if rage_mode:
            step_ms = GHOST_STEP_RAGE_MS
            radius = TARGET_RADIUS_RAGE
            # Rage uses snapshot target first; if reached, continue chasing live player
            target_tile = rage_target_tile if rage_target_tile is not None else player_tile
        else:
            step_ms = GHOST_STEP_NORMAL_MS
            radius = TARGET_RADIUS_NORMAL
            target_tile = player_tile

        # Targeting rule (lock): within radius can lock THROUGH walls.
        # But real-time tracking (updating last-known) only happens when LOS exists.
        g1_tile = tile_of_entity(ghost)
        g2_tile = tile_of_entity(ghost2)

        g1_can_see = has_los(g1_tile, player_tile)
        g2_can_see = has_los(g2_tile, player_tile)

        d1 = manhattan(g1_tile, player_tile)
        d2 = manhattan(g2_tile, player_tile)

        # Hysteresis:
        # - Acquire lock when within `radius` (5)
        # - Keep lock until BOTH ghosts are farther than UNLOCK_RADIUS (8)
        if ghost_targeting:
            targeting_now = not (d1 > UNLOCK_RADIUS and d2 > UNLOCK_RADIUS)
        else:
            targeting_now = (d1 <= radius) or (d2 <= radius)

        # If targeting just started: jumpscare + heartbeat + snapshot last known player tile (ONE-TIME info)
        if targeting_now and not ghost_targeting:
            last_known_player_tile = player_tile
            trigger_jumpscare()

        # If still targeting: ONLY update last-known when at least one ghost has LOS (real-time info)
        if targeting_now and (g1_can_see or g2_can_see):
            last_known_player_tile = player_tile

        # If lock is lost (out of radius), drop last-known so ghosts resume roaming
        if not targeting_now:
            last_known_player_tile = None

        set_targeting(targeting_now)

        # Move ghost1
        if now_ms >= ghost_next_step_ms:
            ghost_next_step_ms = now_ms + step_ms
            start = g1_tile

            nxt = None

            # While targeting (within radius), allow BFS even through walls.
            # BUT we BFS toward last-known player tile, not guaranteed live position.
            if targeting_now and last_known_player_tile is not None:
                nxt = bfs_next_step(start, last_known_player_tile)

            # If BFS fails, fall back to a greedy step toward last-known
            if nxt is None and last_known_player_tile is not None:
                nxt = greedy_step_towards(start, last_known_player_tile)

            # Otherwise roam
            if nxt is None:
                nxt = pacman_roam_step(ghost, start)

            if nxt is not None:
                set_entity_tile(ghost, nxt[0], nxt[1])

        # Move ghost2 (slightly desync so they don't stack)
        if now_ms >= ghost2_next_step_ms:
            ghost2_next_step_ms = now_ms + step_ms + 35
            start = g2_tile

            nxt = None

            # While targeting (within radius), allow BFS even through walls.
            # BFS toward last-known player tile (not necessarily live).
            if targeting_now and last_known_player_tile is not None:
                nxt = bfs_next_step(start, last_known_player_tile)

            # If BFS fails, fall back to a greedy step toward last-known
            if nxt is None and last_known_player_tile is not None:
                nxt = greedy_step_towards(start, last_known_player_tile)

            # Otherwise roam
            if nxt is None:
                nxt = pacman_roam_step(ghost2, start)

            if nxt is not None:
                set_entity_tile(ghost2, nxt[0], nxt[1])

        # If rage snapshot reached, switch to live chase
        if rage_mode and rage_target_tile is not None:
            if tile_of_entity(ghost) == rage_target_tile or tile_of_entity(ghost2) == rage_target_tile:
                rage_target_tile = None

        # If last-known reached, clear it (stop the "go to that coordinate" behavior)
        if last_known_player_tile is not None:
            if tile_of_entity(ghost) == last_known_player_tile or tile_of_entity(ghost2) == last_known_player_tile:
                last_known_player_tile = None

        # Catch condition: ghost touches player
        if tile_of_entity(ghost) == player_tile or tile_of_entity(ghost2) == player_tile:
            trigger_jumpscare()
            return

        # Jumpscare lifetime
        if jumpscare_active:
            if now_ms - jumpscare_start_ms >= jumpscare_duration_ms:
                jumpscare_active = False

        fog_surface.fill((0, 0, 0, 255))
        position_component = em.entities[player][Position]
        
        mask_x = (position_component.x + (WALL_OFFSET // 2)) - light_rad
        mask_y = (position_component.y + (WALL_OFFSET // 2)) - light_rad

        fog_surface.blit(light_mask, (mask_x, mask_y), special_flags=pygame.BLEND_RGBA_MIN)

        ren_sys.render(em)

        if USE_FOG_OF_WAR:
            virtual_surface.blit(fog_surface, (0, 0))

        # Jumpscare overlay: player can still move, but essentially can't see
        # 需求：圖片保持比例，但要「貼緊上下邊」（fit-to-height）。
        # 左右全部塗黑，且黑邊/圖片都要跟著 alpha 淡出（1.5s -> 3.0s）。
        if jumpscare_active and jumpscare_img is not None:
            now_ms = pygame.time.get_ticks()
            a = jumpscare_alpha(now_ms)
            if a > 0:
                # 先蓋一層全黑遮罩（同 alpha），確保完全看不到迷宮
                cover = pygame.Surface((V_GAME_W, V_GAME_H))
                cover.fill((0, 0, 0))
                cover.set_alpha(a)
                virtual_surface.blit(cover, (0, 0))

                iw, ih = jumpscare_img.get_size()
                if iw > 0 and ih > 0:
                    # Fit-to-height: make image height exactly V_GAME_H
                    scale = V_GAME_H / ih
                    nw, nh = int(iw * scale), V_GAME_H

                    # Scale and ensure surface supports alpha blending
                    overlay = pygame.transform.smoothscale(jumpscare_img, (nw, nh)).convert_alpha()
                    overlay.set_alpha(a)

                    # Center horizontally; crop automatically if it overflows
                    ox = (V_GAME_W - nw) // 2
                    virtual_surface.blit(overlay, (ox, 0))

        if active_msg:
            still_active = draw_timed_text(virtual_surface, active_msg, msg_start_time, MSG_DURATION_MS)
            if not still_active:
                active_msg = ""

        current_window_size = screen.get_size()
        scaled_surface = pygame.transform.scale(virtual_surface, current_window_size)

        screen.blit(scaled_surface, (0, 0))
        pygame.display.flip()
    
        clock.tick(60)
        await asyncio.sleep(0)

def draw_timed_text(surface, text, start_ticks, duration_ms):
    if pygame.time.get_ticks() - start_ticks < duration_ms:
        text_surf = font.render(text, True, (255, 0, 0)) 

        text_rect = text_surf.get_rect(center=(V_GAME_W // 2, V_GAME_H // 10))
        
        surface.blit(text_surf, text_rect)
        return True
    return False

asyncio.run(main())