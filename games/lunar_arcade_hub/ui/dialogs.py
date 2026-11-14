"""Modal confirmation dialog that guards accidental application closure."""

import pygame

from config import (
    WIDTH, HEIGHT, PANEL, BORDER, WHITE, MUTED, DIM, CYAN, RED,
)
from ui import theme
from ui.widgets import Button


class QuitDialog:
    def __init__(self, app):
        self.app = app
        self.rect = pygame.Rect(0, 0, 560, 280)
        self.rect.center = (WIDTH // 2, HEIGHT // 2)
        self.stay = Button((self.rect.centerx - 240, self.rect.bottom - 92,
                            220, 50), "STAY IN HUB", "primary", CYAN, 17)
        self.quit = Button((self.rect.centerx + 20, self.rect.bottom - 92,
                            220, 50), "QUIT HUB", "danger", RED, 17)
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        mouse = self.app.input.pos
        down = self.app.input.down
        self.stay.update(dt, mouse, down)
        self.quit.update(dt, mouse, down)

    def handle_event(self, event, pointers):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_n):
                self.app.close_dialog()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_y):
                self.app.confirm_quit()
            return True
        for p in pointers:
            if p.kind == "down":
                if self.stay.hit(p.pos):
                    self.app.audio.play("click")
                    self.app.close_dialog()
                elif self.quit.hit(p.pos):
                    self.app.audio.play("click")
                    self.app.confirm_quit()
                return True
        return True

    def draw(self, surface):
        theme.alpha_rect(surface, (0, 0, WIDTH, HEIGHT), (3, 5, 16), 200)
        rect = self.rect
        theme.panel(surface, rect, color=PANEL, border=BORDER, radius=22)
        pygame.draw.rect(surface, RED, (rect.x, rect.y, rect.w, 4),
                         border_top_left_radius=22, border_top_right_radius=22)
        theme.text(surface, "LEAVE THE HUB?", 26, WHITE,
                   (rect.centerx, rect.y + 58))
        theme.text(surface, "All completed assessments are already stored in "
                            "your longitudinal record.", 14, MUTED,
                   (rect.centerx, rect.y + 94), bold=False)
        theme.text(surface, "Quit the application?", 14, MUTED,
                   (rect.centerx, rect.y + 118), bold=False)
        self.stay.draw(surface)
        self.quit.draw(surface)
        theme.text(surface, "ESC stays   •   ENTER quits", 12, DIM,
                   (rect.centerx, rect.bottom - 24))
