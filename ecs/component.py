class Position:
    def __init__(self):
        self.x: float
        self.y: float

class Velocity:
    def __init__(self):
        self.dx: float
        self.dy: float

class Renderable:
    def __init__(self):
        self.surface: pygame.surface
