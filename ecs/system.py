import pygame
from ecs.component import *
from ecs.entity import EntityManager

class RenderSystem:
    def __init__(self, surface):
        self.surface = surface
    
    def render(self, em):
        self.surface.fill((0, 0, 0))

        for entity, components in em.get_entities(Position, Renderable):
            pos = components[Position]
            ren = components[Renderable]
            self.surface.blit(ren.surface, (pos.x, pos.y))