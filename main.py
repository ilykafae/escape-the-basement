import pygame, asyncio, maze, random
from ecs.system import *

GAME_W = 765
GAME_H = 435
V_GAME_W = 2550
V_GAME_H = 1450

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

WALL_OFFSET = 50

async def main():
    pygame.init()

    # game settings
    is_door_unlocked = True

    player_x = 0
    player_y = 0

    ghost_x = 0
    ghost_y = 0

    VIRTUAL_W, VIRTUAL_H = GAME_W, GAME_H

    screen = pygame.display.set_mode((GAME_W, GAME_H), pygame.RESIZABLE)
    virtual_surface = pygame.Surface((V_GAME_W, V_GAME_H))

    clock = pygame.time.Clock()
    em = EntityManager()

    # init systems
    ren_sys = RenderSystem(virtual_surface)

    mz = maze.generate_maze(V_GAME_W // WALL_OFFSET, V_GAME_H // WALL_OFFSET, 1, 10)

    # create entities here
    ite = 0
    for irow, row in enumerate(mz):
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
                    if ite == 25:
                        ghost_x = icol * WALL_OFFSET
                        ghost_y = irow * WALL_OFFSET
                    else:
                        ite += 1
            elif tile == -1:
                if is_door_unlocked:
                    surface = pygame.image.load(DOOR_PATH).convert_alpha()
                else:
                    surface = pygame.image.load(LOCKED_DOOR_PATH).convert_alpha()
            elif tile == 2:
                surface = pygame.image.load(FLOOR_PATH).convert_alpha()
                player_x = icol * WALL_OFFSET
                player_y = irow * WALL_OFFSET
            elif tile == 3:
                surface = pygame.image.load(BUTTON_PATH)
            else:
                surface = pygame.image.load(FLOOR_PATH).convert_alpha()
            
            x = icol * WALL_OFFSET
            y = irow * WALL_OFFSET
            tile_entity = em.create_entity()
            em.add_component(tile_entity, Position(x, y))
            em.add_component(tile_entity, Renderable(surface, WALL_OFFSET, WALL_OFFSET))

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
            # TODO: input & movement & button logic
        
        # systems here
        ren_sys.render(em)

        current_window_size = screen.get_size()
        scaled_surface = pygame.transform.scale(virtual_surface, current_window_size)

        #TODO: fog of war
        
        screen.blit(scaled_surface, (0, 0))
        pygame.display.flip()
    
        clock.tick(60)
        await asyncio.sleep(0)

asyncio.run(main())