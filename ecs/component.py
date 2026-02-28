class Position:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Velocity:
    def __init__(self):
        self.dx = 0
        self.dy = 0

class Renderable:
    def __init__(self, surface, scaled_x, scaled_y):
        self.surface = surface
        self.scaled_x = scaled_x
        self.scaled_y = scaled_y
        self.rect = surface.get_rect()
