"""Reusable animated widgets (buttons, chips, meters)."""

import pygame

from config import (
    PANEL, PANEL_LIGHT, PANEL_DARK, BORDER, BORDER_SOFT, WHITE, MUTED,
    CYAN, RED, GREEN, BG_TOP, BLACK,
)
from ui import theme
from animations.easing import approach, clamp, ease_out_cubic, lerp_color


class Button:
    """Animated button with hover glow and press feedback."""

    def __init__(self, rect, label, style="primary", accent=CYAN, size=19,
                 icon=None, enabled=True, bold=True):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.style = style
        self.accent = accent
        self.size = size
        self.icon = icon
        self.enabled = enabled
        self.bold = bold
        self.hover = 0.0
        self.press = 0.0
        self._hovering = False
        self._pressed = False

    def update(self, dt, mouse_pos, mouse_down=False):
        hovered = self.enabled and self.rect.collidepoint(mouse_pos)
        if hovered != self._hovering:
            self._hovering = hovered
        target = 1.0 if hovered else 0.0
        self.hover = approach(self.hover, target, 10.0, dt)
        pressed_now = hovered and mouse_down
        self._pressed = pressed_now
        self.press = 1.0 if pressed_now else max(0.0, self.press - dt * 6)

    def hit(self, pos):
        return self.enabled and self.rect.collidepoint(pos)

    def draw(self, surface, mouse_pos=None):
        if mouse_pos is not None and mouse_pos != getattr(self, "_last_pos", None):
            self._last_pos = mouse_pos
        h = ease_out_cubic(self.hover)
        rect = self.rect.move(0, int(2 * self.press))
        radius = min(14, rect.height // 2)

        if self.style == "primary":
            if self.enabled:
                base = self.accent
            else:
                base = (60, 68, 100)
            fill = lerp_color(base, WHITE, 0.18 * h)
            if h > 0.02 and self.enabled:
                theme.glow(surface, rect.center, rect.width // 2, base,
                           layers=4, strength=0.10 * h)
            pygame.draw.rect(surface, fill, rect, border_radius=radius)
            pygame.draw.rect(surface, lerp_color(fill, WHITE, 0.35),
                             (rect.x, rect.y, rect.width, rect.height // 2),
                             border_top_left_radius=radius,
                             border_top_right_radius=radius)
            pygame.draw.rect(surface, fill, rect, border_radius=radius)
            pygame.draw.rect(surface, lerp_color(fill, WHITE, 0.45), rect,
                             width=1, border_radius=radius)
            label_color = BG_TOP
        elif self.style == "danger":
            fill = lerp_color(PANEL, (60, 20, 34), h)
            pygame.draw.rect(surface, fill, rect, border_radius=radius)
            border = lerp_color((110, 46, 64), RED, h)
            pygame.draw.rect(surface, border, rect, width=2, border_radius=radius)
            label_color = RED
        else:  # ghost
            fill = lerp_color(PANEL, PANEL_LIGHT, h)
            pygame.draw.rect(surface, fill, rect, border_radius=radius)
            border = lerp_color(BORDER, self.accent, h)
            pygame.draw.rect(surface, border, rect, width=2, border_radius=radius)
            label_color = WHITE if self.enabled else MUTED

        if self.icon == "play":
            cx = rect.x + 22
            cy = rect.centery
            color = label_color
            pygame.draw.polygon(surface, color, [
                (cx - 4, cy - 8), (cx - 4, cy + 8), (cx + 9, cy)
            ])
            theme.text(surface, self.label, self.size, label_color,
                       (rect.centerx + 8, rect.centery), bold=self.bold)
        else:
            theme.text(surface, self.label, self.size, label_color,
                       rect.center, bold=self.bold)
        return rect


class IconButton:
    def __init__(self, rect, icon, accent=CYAN):
        self.rect = pygame.Rect(rect)
        self.icon = icon
        self.accent = accent
        self.hover = 0.0

    def update(self, dt, mouse_pos):
        target = 1.0 if self.rect.collidepoint(mouse_pos) else 0.0
        self.hover = approach(self.hover, target, 10.0, dt)

    def hit(self, pos):
        return self.rect.collidepoint(pos)

    def draw(self, surface):
        h = self.hover
        fill = lerp_color(PANEL, PANEL_LIGHT, h)
        pygame.draw.rect(surface, fill, self.rect, border_radius=10)
        pygame.draw.rect(surface, lerp_color(BORDER, self.accent, h),
                         self.rect, width=1, border_radius=10)
        c = self.rect.center
        color = lerp_color(MUTED, self.accent, h)
        if self.icon == "mute":
            pygame.draw.polygon(surface, color, [
                (c[0] - 9, c[1] - 4), (c[0] - 4, c[1] - 4), (c[0] + 2, c[1] - 9),
                (c[0] + 2, c[1] + 9), (c[0] - 4, c[1] + 4), (c[0] - 9, c[1] + 4),
            ])
            pygame.draw.line(surface, color, (c[0] + 6, c[1] - 5),
                             (c[0] + 12, c[1] + 5), 2)
            pygame.draw.line(surface, color, (c[0] + 12, c[1] - 5),
                             (c[0] + 6, c[1] + 5), 2)
        else:  # sound
            pygame.draw.polygon(surface, color, [
                (c[0] - 10, c[1] - 4), (c[0] - 5, c[1] - 4), (c[0] + 1, c[1] - 9),
                (c[0] + 1, c[1] + 9), (c[0] - 5, c[1] + 4), (c[0] - 10, c[1] + 4),
            ])
            pygame.draw.arc(surface, color, (c[0] - 2, c[1] - 8, 14, 16),
                            -1.0, 1.0, 2)
            pygame.draw.arc(surface, color, (c[0] - 5, c[1] - 12, 22, 24),
                            -1.0, 1.0, 2)


class Chip:
    @staticmethod
    def draw(surface, rect, label, value, color=CYAN, icon=None):
        rect = pygame.Rect(rect)
        theme.panel(surface, rect, color=PANEL, border=BORDER_SOFT,
                    radius=12, width=1, shadow=False)
        theme.text(surface, label.upper(), 12, MUTED,
                   (rect.x + 16, rect.y + 15), anchor="midleft")
        theme.text(surface, value, 22, color, (rect.x + 16, rect.y + 39),
                   anchor="midleft")
        pygame.draw.circle(surface, color, (rect.right - 16, rect.y + 16), 3)
        return rect


def stat_row(surface, label, value, x, y, width, color=WHITE):
    theme.text(surface, label, 15, MUTED, (x, y), anchor="midleft", bold=False)
    theme.text(surface, value, 18, color, (x + width, y), anchor="midright")
    pygame.draw.line(surface, BORDER_SOFT, (x, y + 15), (x + width, y + 15), 1)
