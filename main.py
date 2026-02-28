# pygbag: width=1280, height=720

import pygame, asyncio, maze, random
from ecs.system import *

GAME_W = 765
GAME_H = 435
V_GAME_W = 2550
V_GAME_H = 1450

USE_FOG_OF_WAR = True

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

FONT_PATH = 'assets/fonts/redcap.ttf'

WALL_OFFSET = 50

font = None

async def main():
    pygame.init()
    pygame.font.init()

    global font
    font = pygame.font.Font(FONT_PATH, 75)

    # game settings
    is_door_unlocked = True

    player_x = 0
    player_y = 0

    ghost_x = 0
    ghost_y = 0

    total_buttons = 50
    preseed_buttons = 0

    exit_x = 0
    exit_y = 0

    active_msg = ""
    msg_start_time = 0

    fog_surface = pygame.Surface((V_GAME_W, V_GAME_H), pygame.SRCALPHA)
    light_rad = 200

    light_mask = pygame.Surface((light_rad * 2, light_rad * 2), pygame.SRCALPHA)
    light_mask.fill((0, 0, 0, 255)) 
    for r in range(light_rad, 0, -1):
        alpha = int(255 * (r / light_rad))
        pygame.draw.circle(light_mask, (0, 0, 0, alpha), (light_rad, light_rad), r)

    VIRTUAL_W, VIRTUAL_H = GAME_W, GAME_H

    screen = pygame.display.set_mode((GAME_W, GAME_H), pygame.RESIZABLE)
    virtual_surface = pygame.Surface((V_GAME_W, V_GAME_H))

    clock = pygame.time.Clock()
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

    ghost = em.create_entity();
    em.add_component(ghost, Position(ghost_x, ghost_y))
    em.add_component(ghost, Renderable(pygame.image.load(GHOST_PATH).convert_alpha(), WALL_OFFSET, WALL_OFFSET))

    player = em.create_entity();
    em.add_component(player, Position(player_x, player_y))
    em.add_component(player, Renderable(pygame.image.load(PLAYER_PATH).convert_alpha(), WALL_OFFSET, WALL_OFFSET))


    # main loop
    while True:
        for event in pygame.event.get():
            if event == pygame.QUIT:
                return

            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    components = em.entities[player]

                    next_x = components[Position].x
                    next_y = components[Position].y - WALL_OFFSET

                    try:
                        if mz[next_y // WALL_OFFSET][next_x // WALL_OFFSET] != 1:
                            components[Position].y = next_y
                    except IndexError:
                        pass
                elif event.key == pygame.K_DOWN:
                    components = em.entities[player]

                    next_x = components[Position].x
                    next_y = components[Position].y + WALL_OFFSET

                    try:
                        if mz[next_y // WALL_OFFSET][next_x // WALL_OFFSET] != 1:
                            components[Position].y = next_y
                    except IndexError:
                        pass
                elif event.key == pygame.K_RIGHT:
                    components = em.entities[player]

                    next_x = components[Position].x + WALL_OFFSET
                    next_y = components[Position].y 

                    try:
                        if mz[next_y // WALL_OFFSET][next_x // WALL_OFFSET] != 1:
                            components[Position].x = next_x
                    except IndexError:
                        pass
                elif event.key == pygame.K_LEFT:
                    components = em.entities[player]

                    next_x = components[Position].x - WALL_OFFSET
                    next_y = components[Position].y

                    try:
                        if mz[next_y // WALL_OFFSET][next_x // WALL_OFFSET] != 1:
                            components[Position].x = next_x
                    except IndexError:
                        pass
                elif event.key == pygame.K_SPACE:
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
        
        fog_surface.fill((0, 0, 0, 255))
        position_component = em.entities[player][Position]
        
        mask_x = (position_component.x + (WALL_OFFSET // 2)) - light_rad
        mask_y = (position_component.y + (WALL_OFFSET // 2)) - light_rad

        fog_surface.blit(light_mask, (mask_x, mask_y), special_flags=pygame.BLEND_RGBA_MIN)

        ren_sys.render(em)

        if USE_FOG_OF_WAR:
            virtual_surface.blit(fog_surface, (0, 0))

        if active_msg:
            still_active = draw_timed_text(virtual_surface, active_msg, msg_start_time, 3000)
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