"""Top navigation bar shared by dashboard, statistics and profile."""

import math

import pygame

from config import (
    WIDTH, PANEL, PANEL_LIGHT, PANEL_DARK, BORDER_SOFT, WHITE, MUTED,
    CYAN, PURPLE, RED, BG_TOP,
)
from ui import theme
from ui.window_controls import WindowControls
from animations.easing import approach, clamp, lerp_color

NAV_ITEMS = [
    ("dashboard", "DASHBOARD", 548, 110),
    ("statistics", "STATISTICS", 668, 108),
    ("monitor", "MONITOR", 786, 96),
    ("profile", "PROFILE", 892, 84),
]


class NavBar:
    def __init__(self, app, active="dashboard"):
        self.app = app
        self.active = active
        self.hover = {key: 0.0 for key, _, _, _ in NAV_ITEMS}
        self.sound_hover = 0.0
        self.rect = pygame.Rect(24, 16, WIDTH - 48, 56)
        self.sound_rect = pygame.Rect(992, 27, 42, 34)
        self.window_controls = WindowControls(app, 1046, 29, 32, 4)

    def update(self, dt):
        pos = self.app.input.pos
        for key, _, x, w in NAV_ITEMS:
            target = 1.0 if pygame.Rect(x, 28, w, 34).collidepoint(pos) else 0.0
            self.hover[key] = approach(self.hover[key], target, 12.0, dt)
        target = 1.0 if self.sound_rect.collidepoint(pos) else 0.0
        self.sound_hover = approach(self.sound_hover, target, 12.0, dt)
        self.window_controls.update(dt)

    def draw(self, surface):
        theme.alpha_rect(surface, self.rect, PANEL, 225, radius=16)
        pygame.draw.rect(surface, BORDER_SOFT, self.rect, width=1,
                         border_radius=16)

        # Logo.
        cx, cy = 58, 44
        pygame.draw.circle(surface, (40, 55, 120), (cx, cy), 15)
        pygame.draw.circle(surface, CYAN, (cx, cy), 15, 2)
        pygame.draw.ellipse(surface, PURPLE, (cx - 22, cy - 6, 44, 12), 2)
        pygame.draw.circle(surface, WHITE, (cx + 6, cy - 6), 2)
        theme.text(surface, "LUNAR ARCADE", 19, WHITE, (88, 36),
                   anchor="midleft")
        theme.text(surface, "COGNITIVE TRAINING HUB", 9, MUTED, (89, 55),
                   anchor="midleft", bold=False)

        for key, label, x, w in NAV_ITEMS:
            rect = pygame.Rect(x, 28, w, 34)
            active = key == self.active
            h = self.hover[key]
            if active:
                theme.alpha_rect(surface, rect, CYAN, 26, radius=10)
                pygame.draw.rect(surface, (*CYAN,), rect, width=1,
                                 border_radius=10)
            elif h > 0.01:
                theme.alpha_rect(surface, rect, PANEL_LIGHT, int(180 * h),
                                 radius=10)
            color = CYAN if active else lerp_color(MUTED, WHITE, h)
            theme.text(surface, label, 13, color, rect.center)

        # Sound toggle.
        h = self.sound_hover
        pygame.draw.rect(surface, lerp_color(PANEL, PANEL_LIGHT, h),
                         self.sound_rect, border_radius=9)
        pygame.draw.rect(surface, lerp_color(BORDER_SOFT, CYAN, h),
                         self.sound_rect, width=1, border_radius=9)
        c = self.sound_rect.center
        muted = self.app.audio.muted
        color = RED if muted else lerp_color(MUTED, CYAN, h)
        pygame.draw.polygon(surface, color, [
            (c[0] - 8, c[1] - 4), (c[0] - 3, c[1] - 4), (c[0] + 3, c[1] - 9),
            (c[0] + 3, c[1] + 9), (c[0] - 3, c[1] + 4), (c[0] - 8, c[1] + 4),
        ])
        if muted:
            pygame.draw.line(surface, color, (c[0] + 7, c[1] - 5),
                             (c[0] + 13, c[1] + 5), 2)
            pygame.draw.line(surface, color, (c[0] + 13, c[1] - 5),
                             (c[0] + 7, c[1] + 5), 2)
        else:
            pygame.draw.arc(surface, color, (c[0] - 2, c[1] - 8, 14, 16),
                            -1.0, 1.0, 2)

        self.window_controls.draw(surface)

    def handle_click(self, pos):
        if self.window_controls.handle_click(pos):
            return "window"
        if self.sound_rect.collidepoint(pos):
            self.app.audio.toggle_mute()
            return "mute"
        for key, _, x, w in NAV_ITEMS:
            if pygame.Rect(x, 28, w, 34).collidepoint(pos):
                if key != self.active:
                    self.app.go_to(key)
                return key
        return None
