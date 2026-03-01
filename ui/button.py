import pygame

class Button:
    def __init__(self, x, y, w, h, text, fg, hfg, bg, hfg, font):
        self.rect = pygame.Rect(x, y, w, h)

        self.fg, self.hfg = fg, hfg
        self.bg, self.hbg = bg, hbg
        
        self.txt_norm = font.render(text, True, fg)
        self.txt_hover = font.render(text, True, hfg)

        self.txt_rect = self.txt_norm.get_rect(center=self.rect.center)

    def draw(self, surface, font):
        mouse_pos = pygame.mouse.get_pos()
        is_mouse_on_button = self.rect.collidepoint(mouse_pos)

        fg_clr = self.hfg if is_mouse_on_button else self.fg
        bg_clr = self.hbg if is_mouse_on_button else self.bg

        pygame.draw.rect(surface, bg_clr, self.rect)

    def is_pressed(self, event):
        return event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos)