import pygame, asyncio, maze, random
from ecs.system import *

GAME_W = 765
GAME_H = 435

PLAYER_FACING_FRONT_PATH = "assets/sprite/player_front.jpg"
PLAYER_FACING_RIGHT_PATH = "assets/sprite/player_right.jpg"
PLAYER_FACING_LEFT_PATH = "assets/sprite/player_left.jpg"
GHOST_PATH = "assets/sprite/ghost.jpg"
WALL_PATH = "assets/world/wall.png"
B_WALL_PATH = "assets/world/wall_with_blood.png"
FLOOR_PATH = "assets/world/floor.png"
B_FLOOR_PATH = "assets/world/floor_with_blood.png"

WALL_OFFSET = 15

async def main():
    pygame.init()

    VIRTUAL_W, VIRTUAL_H = GAME_W, GAME_H

    screen = pygame.display.set_mode((GAME_W, GAME_H), pygame.RESIZABLE)
    virtual_surface = pygame.Surface((VIRTUAL_W, VIRTUAL_H))

    clock = pygame.time.Clock()
    em = EntityManager()

    # init systems
    velo_sys = VelocitySystem()
    ren_sys = RenderSystem(virtual_surface)

    # create entities here
    #ghost_id = em.create_entity();
    #em.add_component(ghost_id, Position(1, 1))
    #em.add_component(ghost_id, Renderable(pygame.image.load(GHOST_SPIRTE_PATH).convert_alpha(), 50, 50))

    mz = maze.generate_maze(GAME_W // WALL_OFFSET, GAME_H // WALL_OFFSET, 10, 10)

    print(mz)
    print([[1, 0], [0, 1]])

    for irow, row in enumerate(mz):
        for icol, tile in enumerate(row):
            surface = None
            ttype = random.randrange(0, 7)
            if tile == 1:
                if ttype == 0:
                    surface = pygame.image.load(B_WALL_PATH).convert_alpha()
                else:
                    surface = pygame.image.load(WALL_PATH).convert_alpha()
            elif tile == 0:
                if ttype == 0:
                    surface = pygame.image.load(B_FLOOR_PATH).convert_alpha()
                else:
                    surface = pygame.image.load(FLOOR_PATH).convert_alpha()
            else:
                surface = pygame.image.load(FLOOR_PATH).convert_alpha()
            
            x = icol * WALL_OFFSET
            y = irow * WALL_OFFSET
            tile_entity = em.create_entity()
            em.add_component(tile_entity, Position(x, y))
            em.add_component(tile_entity, Renderable(surface, WALL_OFFSET, WALL_OFFSET))


    # main loop
    while True:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event == pygame.QUIT:
                return

            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
        
        # systems here
        velo_sys.update(em, dt)
        ren_sys.render(em)

        current_window_size = screen.get_size()
        scaled_surface = pygame.transform.scale(virtual_surface, current_window_size)
        
        screen.blit(scaled_surface, (0, 0))
        pygame.display.flip()
    
        await asyncio.sleep(0)

asyncio.run(main())