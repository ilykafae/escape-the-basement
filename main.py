import pygame, asyncio
from ecs.system import *

GAME_W = 1280
GAME_H = 720

async def main():
    pygame.init()

    screen = pygame.display.set_mode((GAME_W, GAME_H))
    clock = pygame.time.Clock()
    em = EntityManager()

    # init systems
    velo_sys = VelocitySystem()
    ren_sys = RenderSystem(screen)

    # create entities here

    # main loop
    is_running = True
    while is_running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event == pygame.QUIT:
                is_running = False
        
        # systems here
        velo_sys.update(em, dt)
        ren_sys.render(em)


if __name__ == "__main__":
    asyncio.run(main())