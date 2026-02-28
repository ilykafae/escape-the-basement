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
        self.screen.fill((255, 255, 255))

        for entity, components in em.get_entities(Position, Renderable):
            pos = components[Position]
            ren = components[Renderable]

            scaled_surface = pygame.transform.smoothscale(ren.surface, (ren.scaled_x, ren.scaled_y))

            self.screen.blit(scaled_surface, (pos.x, pos.y))

        pygame.display.flip()