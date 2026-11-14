"""Dashboard assessment cards with status, baseline and trend data."""

import pygame

from config import (
    PANEL, PANEL_LIGHT, PANEL_DARK, BORDER, BORDER_SOFT, WHITE, MUTED,
    CYAN, GOLD, GREEN, RED, PURPLE, BG_TOP, DIFFICULTY_COLORS,
)
from core.neuro import LEVEL_COLORS, format_value
from ui import theme
from animations.easing import approach, clamp, ease_out_cubic, lerp_color

SHORT_TITLES = {
    "lunar_alien_reaction": "Alien Reaction",
    "coloring_shapes": "Coloring Shapes",
    "memory_test": "Memory Test",
    "reaction_test": "Reaction Test",
    "speed_click": "Speed Click",
    "number_hunt": "Number Hunt",
}

DIFFICULTY = {
    "lunar_alien_reaction": 3,
    "coloring_shapes": 3,
    "memory_test": 4,
    "reaction_test": 1,
    "speed_click": 3,
    "number_hunt": 4,
}


def draw_game_icon(surface, icon, center, size, color):
    cx, cy = center
    s = size
    if icon == "alien":
        pygame.draw.circle(surface, color, (cx, cy), s * 0.62, 2)
        pygame.draw.ellipse(surface, color, (cx - s * 0.42, cy - s * 0.25,
                                             s * 0.3, s * 0.46))
        pygame.draw.ellipse(surface, color, (cx + s * 0.12, cy - s * 0.25,
                                             s * 0.3, s * 0.46))
        pygame.draw.line(surface, color, (cx - s * 0.25, cy - s * 0.55),
                         (cx - s * 0.4, cy - s * 0.85), 2)
        pygame.draw.line(surface, color, (cx + s * 0.25, cy - s * 0.55),
                         (cx + s * 0.4, cy - s * 0.85), 2)
        pygame.draw.circle(surface, color, (cx - s * 0.4, cy - s * 0.87), 2)
        pygame.draw.circle(surface, color, (cx + s * 0.4, cy - s * 0.87), 2)
    elif icon == "shapes":
        pygame.draw.polygon(surface, color, [
            (cx - s * 0.15, cy - s * 0.85), (cx + s * 0.45, cy + s * 0.15),
            (cx - s * 0.75, cy + s * 0.15)], 2)
        pygame.draw.circle(surface, color, (cx + s * 0.4, cy - s * 0.35),
                           s * 0.4, 2)
        pygame.draw.rect(surface, color, (cx - s * 0.25, cy + s * 0.3,
                                          s * 0.7, s * 0.55), 2)
    elif icon == "memory":
        for dx in (-1, 1):
            for dy in (-1, 1):
                pygame.draw.rect(surface, color,
                                 (cx + dx * s * 0.5 - s * 0.32,
                                  cy + dy * s * 0.5 - s * 0.32,
                                  s * 0.6, s * 0.6), 2, border_radius=3)
        pygame.draw.circle(surface, color, (cx - s * 0.32, cy - s * 0.32), 2)
    elif icon == "reaction":
        pygame.draw.polygon(surface, color, [
            (cx + s * 0.15, cy - s * 0.95), (cx - s * 0.5, cy + s * 0.1),
            (cx - s * 0.05, cy + s * 0.1), (cx - s * 0.25, cy + s * 0.95),
            (cx + s * 0.55, cy - s * 0.15), (cx + s * 0.08, cy - s * 0.15),
        ], 2)
    elif icon == "target":
        pygame.draw.circle(surface, color, (cx, cy), s * 0.9, 2)
        pygame.draw.circle(surface, color, (cx, cy), s * 0.55, 2)
        pygame.draw.circle(surface, color, (cx, cy), s * 0.2)
    elif icon == "numbers":
        theme.text(surface, "1", s, color, (cx - s * 0.55, cy - s * 0.3))
        theme.text(surface, "2", s, color, (cx, cy + s * 0.25))
        theme.text(surface, "3", s, color, (cx + s * 0.55, cy - s * 0.15))
    else:  # plus
        pygame.draw.line(surface, color, (cx - s * 0.6, cy),
                         (cx + s * 0.6, cy), 3)
        pygame.draw.line(surface, color, (cx, cy - s * 0.6),
                         (cx, cy + s * 0.6), 3)


def draw_sparkline(surface, rect, values, color):
    if len(values) < 2:
        theme.text(surface, "TREND —", 9, MUTED, rect.center)
        return
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    points = []
    for i, v in enumerate(values):
        x = rect.x + i * rect.w / (len(values) - 1)
        y = rect.bottom - (v - lo) / span * (rect.h - 6) - 3
        points.append((x, y))
    pygame.draw.lines(surface, color, False, points, 2)
    pygame.draw.circle(surface, WHITE, (int(points[-1][0]), int(points[-1][1])), 3)


class GameCard:
    def __init__(self, rect, cls, index):
        self.rect = pygame.Rect(rect)
        self.cls = cls
        self.index = index
        self.hover = 0.0
        self.best = 0
        self.plays = 0
        self.latest = None
        self.baseline = None
        self.status = "BASELINE REQUIRED"
        self.level = "none"
        self.delta = None
        self.history = []
        self.action = "Complete a session to begin monitoring."
        self.metric_value = None
        self.alert_level = None

    def update(self, dt, mouse_pos):
        target = 1.0 if self.rect.collidepoint(mouse_pos) else 0.0
        self.hover = approach(self.hover, target, 10.0, dt)

    def hit(self, pos):
        return self.rect.collidepoint(pos)

    def load(self, app):
        db = app.db
        stats = db.per_game().get(self.cls.game_id)
        self.best = int(stats["best"]) if stats else 0
        self.plays = int(stats["plays"]) if stats else 0
        self.latest = db.latest_session(self.cls.game_id)
        self.baseline = app.neuro.get_baseline(self.cls.game_id)
        self.status, self.level = app.neuro.status_for(self.cls.game_id)
        self.history = [r["metric_value"] for r in
                        db.metric_history(self.cls.game_id, None, 12)]
        latest = self.latest or {}
        self.delta = latest.get("deterioration")
        self.metric_value = latest.get("metric_value")
        self.alert_level = latest.get("alert_level")
        action = ""
        if latest.get("feedback"):
            import json
            try:
                fb = json.loads(latest["feedback"])
                action = (fb.get("actions") or [""])[0]
            except (ValueError, TypeError):
                action = ""
        self.action = action or "Complete a session to begin monitoring."

    def draw(self, surface, time):
        h = ease_out_cubic(self.hover)
        rect = self.rect.move(0, -int(4 * h))
        accent = self.cls.accent
        level_color = LEVEL_COLORS.get(self.level, MUTED)

        if h > 0.02:
            theme.glow(surface, (rect.centerx, rect.bottom - 20),
                       rect.width // 2, accent, layers=4, strength=0.06 * h)
        surface.blit(theme.card_shadow(rect.width, rect.height, 18, 80, 12),
                     (rect.x - 12, rect.y - 12))

        fill = lerp_color(PANEL, PANEL_LIGHT, 0.35 * h)
        pygame.draw.rect(surface, fill, rect, border_radius=18)
        pygame.draw.rect(surface, lerp_color(BORDER, accent, h), rect,
                         width=2, border_radius=18)
        pygame.draw.rect(surface, accent, (rect.x + 16, rect.y,
                                           rect.width - 32, 3),
                         border_top_left_radius=2, border_top_right_radius=2)

        # Header: icon, title, subtitle, status pill.
        badge = pygame.Rect(rect.x + 16, rect.y + 14, 42, 42)
        pygame.draw.rect(surface, (14, 19, 44), badge, border_radius=11)
        pygame.draw.rect(surface, accent, badge, width=1, border_radius=11)
        draw_game_icon(surface, self.cls.icon, badge.center, 13, accent)

        theme.text(surface, SHORT_TITLES.get(self.cls.game_id, self.cls.title),
                   14, WHITE, (rect.x + 68, rect.y + 24), anchor="midleft")
        theme.text(surface, self.cls.subtitle, 9, MUTED,
                   (rect.x + 68, rect.y + 42), anchor="midleft", bold=False)

        pill_text = self.status
        pw = theme.text_width(surface, pill_text, 8) + 14
        pill = pygame.Rect(rect.right - 14 - pw, rect.y + 15, pw, 17)
        pygame.draw.rect(surface, level_color, pill, border_radius=8)
        theme.text(surface, pill_text, 8, BG_TOP, pill.center)

        pygame.draw.line(surface, BORDER_SOFT, (rect.x + 16, rect.y + 66),
                         (rect.right - 16, rect.y + 66), 1)

        cfg = self.cls.neuro_cfg if hasattr(self.cls, "neuro_cfg") else None
        # Three compact figures: best, latest metric, baseline.
        cols = [("BEST", f"{self.best:,}" if self.best else "—", GOLD),
                ("LATEST", self._latest_text(), WHITE),
                ("BASELINE", self._baseline_text(), CYAN)]
        for i, (label, value, color) in enumerate(cols):
            x = rect.x + 18 + i * 112
            theme.text(surface, label, 8, MUTED, (x, rect.y + 76),
                       anchor="midleft")
            theme.text(surface, value, 14, color, (x, rect.y + 92),
                       anchor="midleft")

        # Delta + sparkline.
        from core.neuro import ASSESSMENTS
        cfg = ASSESSMENTS.get(self.cls.game_id) or {}
        if self.delta is None:
            delta_text, delta_color = "—", MUTED
        else:
            if cfg.get("absolute"):
                delta_text = f"{self.delta:+.1f} pts"
            else:
                delta_text = f"{self.delta:+.0f}%"
            amber = cfg.get("amber_abs", 20.0)
            red = cfg.get("red_abs", 40.0)
            delta_color = (LEVEL_COLORS["red"] if self.delta > red else
                           LEVEL_COLORS["amber"] if self.delta > amber else
                           LEVEL_COLORS["normal"])
        theme.text(surface, "Δ VS BASELINE", 8, MUTED,
                   (rect.x + 18, rect.y + 112), anchor="midleft")
        theme.text(surface, delta_text, 15, delta_color,
                   (rect.x + 18, rect.y + 130), anchor="midleft")
        spark = pygame.Rect(rect.x + 190, rect.y + 112, rect.width - 210, 30)
        draw_sparkline(surface, spark, self.history, accent)

        # Recommended action (two lines max).
        y = rect.y + 154
        for line in theme.wrap_lines(self.action, 10, rect.width - 60,
                                     bold=False)[:2]:
            theme.text(surface, line, 10, MUTED, (rect.x + 18, y),
                       anchor="midleft", bold=False)
            y += 13

        cx = rect.right - 26
        cy = rect.bottom - 24
        radius = int(13 + 2 * h)
        pygame.draw.circle(surface, accent, (cx, cy), radius)
        pygame.draw.polygon(surface, BG_TOP, [
            (cx - 3, cy - 6), (cx - 3, cy + 6), (cx + 6, cy)])

    def _latest_text(self):
        if not self.latest:
            return "—"
        if self.metric_value is not None:
            from core.neuro import ASSESSMENTS
            cfg = ASSESSMENTS.get(self.cls.game_id)
            if cfg:
                return format_value(self.metric_value, cfg)
        return f"{int(self.latest.get('score', 0)):,} pts"

    def _baseline_text(self):
        if not self.baseline or self.baseline.get("baseline_value") is None:
            return "—"
        from core.neuro import ASSESSMENTS
        cfg = ASSESSMENTS.get(self.cls.game_id)
        return format_value(self.baseline["baseline_value"], cfg)
