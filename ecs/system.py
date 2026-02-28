import pygame
from ecs.component import *
from ecs.entity import EntityManager

class VelocitySystem:
    def update(self, em, dt):
        for entity, components in em.get_entities(Position, Velocity):
            pos = components[Position]
            vel = components[Velocity]
            pos.x = vel.dx * dt
            pos.y = vel.dy * dt

class RenderSystem:
    def __init__(self, screen):
        self.screen = screen
    
    def render(self, em):
        self.screen.fill((0, 0, 0))

        for entity, components in em.get_entities(Position, Renderable):
            pos = components[Position]
            ren = components[Renderable]
            self.screen.blit(ren.surface, (pos.x, pox.y))

        pygame.display.flip()