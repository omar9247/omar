"""Minimize / maximize / restore buttons drawn inside the UI."""

import pygame

from config import (
    PANEL, PANEL_LIGHT, BORDER, BORDER_SOFT, WHITE, MUTED, CYAN, IS_WEB,
)
from ui import theme
from animations.easing import approach, clamp, lerp_color

ACTIONS = ("minimize", "maximize", "restore")


class WindowControls:
    def __init__(self, app, x, y, size=30, gap=5):
        self.app = app
        self.size = size
        self.rects = {
            action: pygame.Rect(x + i * (size + gap), y, size, size)
            for i, action in enumerate(ACTIONS)
        }
        self.hover = {action: 0.0 for action in ACTIONS}

    @property
    def width(self):
        return self.size * 3 + 5 * 2

    def update(self, dt):
        if IS_WEB:
            return
        pos = self.app.input.pos
        for action, rect in self.rects.items():
            target = 1.0 if rect.collidepoint(pos) else 0.0
            self.hover[action] = approach(self.hover[action], target,
                                          12.0, dt)

    def handle_click(self, pos):
        if IS_WEB:
            return None
        for action, rect in self.rects.items():
            if rect.collidepoint(pos):
                self.app.audio.play("click", 0.4)
                window = self.app.window
                if action == "minimize":
                    window.minimize()
                elif action == "maximize":
                    window.maximize()
                else:
                    window.restore()
                return action
        return None

    def draw(self, surface):
        if IS_WEB:
            return
        for action, rect in self.rects.items():
            h = self.hover[action]
            pygame.draw.rect(surface, lerp_color(PANEL, PANEL_LIGHT, h), rect,
                             border_radius=8)
            pygame.draw.rect(surface, lerp_color(BORDER_SOFT, CYAN, h), rect,
                             width=1, border_radius=8)
            color = lerp_color(MUTED, WHITE, h)
            c = rect.center
            s = self.size
            if action == "minimize":
                pygame.draw.line(surface, color, (c[0] - s * 0.28, c[1] + 1),
                                 (c[0] + s * 0.28, c[1] + 1), 2)
            elif action == "maximize":
                pygame.draw.rect(surface, color,
                                 (c[0] - s * 0.24, c[1] - s * 0.24,
                                  s * 0.48, s * 0.48), 2, border_radius=2)
            else:
                pygame.draw.rect(surface, color,
                                 (c[0] - s * 0.24, c[1] - s * 0.24,
                                  s * 0.40, s * 0.40), 2, border_radius=2)
                pygame.draw.rect(surface, color,
                                 (c[0] - s * 0.10, c[1] - s * 0.10,
                                  s * 0.40, s * 0.40), 2, border_radius=2)
