import pygame, asyncio
from ecs.system import *

GAME_W = 750
GAME_H = 750

PLAYER_FACING_FRONT_PATH = "assets/sprite/player_front.jpg"
PLAYER_FACING_RIGHT_PATH = "assets/sprite/player_right.jpg"
PLAYER_FACING_LEFT_PATH = "assets/sprite/player_left.jpg"
GHOST_PATH = "assets/sprite/ghost.jpg"
WALL_PATH = "assets/world/wall.png"
B_WALL_PATH = "assets/world/wall_with_blood.png"
FLOOR_PATH = "assets/world/floor.png"
B_FLOOR_PATH = "assets/world/floor_with.png"

WALL_OFFSET = 15

async def main():
    pygame.init()

    screen = pygame.display.set_mode((GAME_W, GAME_H))
    clock = pygame.time.Clock()
    em = EntityManager()

    # init systems
    velo_sys = VelocitySystem()
    ren_sys = RenderSystem(screen)

    # create entities here
    #ghost_id = em.create_entity();
    #em.add_component(ghost_id, Position(1, 1))
    #em.add_component(ghost_id, Renderable(pygame.image.load(GHOST_SPIRTE_PATH).convert_alpha(), 50, 50))

    for irow, row in enumerate(TEST_MAZE):
        for icol, tile in enumerate(row):
            path = ""
            if tile == 1:
                path = WALL_PATH
            elif tile == 0:
                path = FLOOR_PATH
            
            x = icol * WALL_OFFSET
            y = irow * WALL_OFFSET
            tile_entity = em.create_entity()
            em.add_component(tile_entity, Position(x, y))
            em.add_component(tile_entity, Renderable(pygame.image.load(path).convert_alpha(), WALL_OFFSET, WALL_OFFSET))


    # main loop
    while True:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event == pygame.QUIT:
                return
        
        # systems here
        velo_sys.update(em, dt)
        ren_sys.render(em)
    
        await asyncio.sleep(0)

asyncio.run(main())