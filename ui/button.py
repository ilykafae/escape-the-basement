import pygame

class Button:
    def __init__(self, x, y, w, h, text, fg, hfg, bg, hbg, font):
        self.rect = pygame.Rect(x, y, w, h)
        self.fg, self.hfg, self.bg, self.hbg = fg, hfg, bg, hbg
        self.text_norm = font.render(text, True, fg)
        self.text_hover = font.render(text, True, hfg)
        self.text_rect = self.text_norm.get_rect(center=self.rect.center)

    def draw(self, surface, v_mouse):
        is_hovered = self.rect.collidepoint(v_mouse)
        bg_clr = self.hbg if is_hovered else self.bg
        txt_surf = self.text_hover if is_hovered else self.text_norm

        pygame.draw.rect(surface, bg_clr, self.rect)
        surface.blit(txt_surf, self.text_rect)

    def is_pressed(self, event, v_mouse):
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(v_mouse)
