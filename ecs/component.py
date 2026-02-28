import pygame

class Position:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Renderable:
    def __init__(self, surface, scaled_x, scaled_y):
        self.surface = pygame.transform.smoothscale(surface, (scaled_x, scaled_y))
        self.scaled_x = scaled_x
        self.scaled_y = scaled_y
        self.rect = surface.get_rect()
