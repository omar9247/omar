"""Performance analytics screen with matplotlib charts."""

import io
import math

import pygame

from config import (
    WIDTH, HEIGHT, PANEL, PANEL_LIGHT, PANEL_DARK, BORDER, BORDER_SOFT,
    WHITE, MUTED, CYAN, GOLD, GREEN, RED, PURPLE, DIM,
)
from ui import theme
from ui.navbar import NavBar
from ui.game_cards import draw_game_icon
from games import GAME_CLASSES
from animations.easing import clamp, lerp_color

PANEL_HEX = "#121734"
AXIS_HEX = "#0f1430"
TEXT_HEX = "#d6dcf5"
MUTED_HEX = "#8e9ac0"
GRID_HEX = "#2a3260"

CHART_RECTS = {
    "score": pygame.Rect(430, 150, 718, 252),
    "accuracy": pygame.Rect(430, 418, 350, 228),
    "activity": pygame.Rect(796, 418, 352, 228),
}


def _hex(color):
    return "#%02x%02x%02x" % color[:3]


def _style_axes(ax):
    ax.set_facecolor(AXIS_HEX)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=MUTED_HEX, labelsize=8, length=0)
    ax.grid(True, color=GRID_HEX, alpha=0.5, linewidth=0.6)
    ax.set_axisbelow(True)


class StatisticsScreen:
    def __init__(self, app):
        self.app = app
        self.nav = NavBar(app, "statistics")
        self.selected = GAME_CLASSES[0].game_id
        self.row_rects = {}
        self.chart_cache = {}
        self.history = {}
        self.activity = []
        self.per_game = {}
        self.comp = (None, None, None)
        self.refresh()
        self._build_rows()

    def _build_rows(self):
        self.row_rects = {}
        for i, cls in enumerate(GAME_CLASSES):
            self.row_rects[cls.game_id] = pygame.Rect(
                52, 182 + i * 60, 350, 52)

    def enter(self):
        self.refresh()

    def refresh(self):
        self.history = {
            cls.game_id: self.app.db.history(cls.game_id, 30)
            for cls in GAME_CLASSES
        }
        self.activity = self.app.db.daily_activity(14)
        self.per_game = self.app.db.per_game()
        self.comp = self.app.db.comparison(self.selected)
        self.chart_cache.clear()

    def select(self, game_id):
        self.selected = game_id
        self.comp = self.app.db.comparison(game_id)
        self.app.audio.play("click")

    def handle_event(self, event, pointers):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.go_to("dashboard")
            elif event.key == pygame.K_m:
                self.app.audio.toggle_mute()
        for p in pointers:
            if p.kind == "down":
                if self.nav.handle_click(p.pos):
                    return
                for game_id, rect in self.row_rects.items():
                    if rect.collidepoint(p.pos):
                        self.select(game_id)
                        return

    def update(self, dt):
        self.nav.update(dt)

    def draw(self, surface):
        self.nav.draw(surface)
        theme.text(surface, "PERFORMANCE DECK", 30, WHITE, (52, 112),
                   anchor="midleft")
        theme.text(surface, "Session history, trend analytics and personal "
                            "comparisons.", 13, MUTED, (54, 142),
                   anchor="midleft", bold=False)

        total_sessions = sum(len(rows) for rows in self.history.values())
        theme.text(surface, f"{total_sessions} SESSIONS LOGGED", 11, DIM,
                   (1148, 122), anchor="midright")

        self.draw_game_list(surface)
        self.draw_charts(surface)
        self.draw_comparison(surface)

    def draw_game_list(self, surface):
        panel = pygame.Rect(52, 150, 350, 500)
        theme.panel(surface, panel, color=PANEL, border=BORDER_SOFT, radius=18,
                    width=1, shadow=False)
        theme.text(surface, "SELECT A MODULE", 11, MUTED, (74, 172),
                   anchor="midleft")
        for cls in GAME_CLASSES:
            rect = self.row_rects[cls.game_id]
            row = self.per_game.get(cls.game_id)
            best = int(row["best"]) if row else 0
            plays = int(row["plays"]) if row else 0
            active = cls.game_id == self.selected
            hovered = rect.collidepoint(self.app.input.pos)
            if active:
                theme.alpha_rect(surface, rect, cls.accent, 22, radius=12)
                pygame.draw.rect(surface, cls.accent, rect, width=1,
                                 border_radius=12)
            elif hovered:
                pygame.draw.rect(surface, PANEL_LIGHT, rect, border_radius=12)
            draw_game_icon(surface, cls.icon, (rect.x + 26, rect.centery), 12,
                           cls.accent if (active or hovered) else MUTED)
            theme.text(surface, cls.title, 14, WHITE if (active or hovered)
                       else (200, 208, 230), (rect.x + 50, rect.centery - 8),
                       anchor="midleft")
            theme.text(surface, f"{plays} played", 10, MUTED,
                       (rect.x + 50, rect.centery + 12), anchor="midleft",
                       bold=False)
            theme.text(surface, f"{best:,}" if best else "—", 16,
                       cls.accent if best else DIM,
                       (rect.right - 16, rect.centery), anchor="midright")

    # ----------------------------------------------------------- charts
    def _chart_key(self, kind):
        rows = self.history.get(self.selected, [])
        return (kind, self.selected, len(rows), len(self.activity))

    def _chart_image(self, kind, rect):
        key = self._chart_key(kind)
        if key in self.chart_cache:
            return self.chart_cache[key]
        try:
            image = self._render_chart(kind, rect.width, rect.height)
        except Exception:
            # Pygbag does not ship matplotlib; keep analytics useful on web.
            try:
                image = self._render_native_chart(kind, rect.width, rect.height)
            except Exception:
                image = None
        self.chart_cache[key] = image
        return image

    def _render_native_chart(self, kind, width, height):
        """Dependency-free chart used when matplotlib is unavailable."""
        surface = pygame.Surface((max(20, width), max(20, height)),
                                 pygame.SRCALPHA)
        w, h = surface.get_size()
        left, top, right, bottom = 34, 14, w - 12, h - 24
        plot_w, plot_h = max(1, right - left), max(1, bottom - top)
        for i in range(5):
            y = top + plot_h * i / 4
            pygame.draw.line(surface, (42, 50, 96), (left, y), (right, y), 1)

        if kind == "activity":
            counts = [d[1] for d in self.activity]
            peak = max(3, max(counts) if counts else 3)
            slot = plot_w / max(1, len(counts))
            for i, value in enumerate(counts):
                bh = plot_h * value / peak
                pygame.draw.rect(surface, CYAN,
                                 (left + i * slot + 2, bottom - bh,
                                  max(2, slot - 4), bh), border_radius=2)
            theme.text(surface, "14-DAY ACTIVITY", 9, MUTED, (left, 2),
                       anchor="midleft", bold=False)
            return surface

        rows = self.history.get(self.selected, [])
        if not rows:
            theme.text(surface, "NO SESSIONS YET", 10, DIM,
                       (w // 2, h // 2), bold=False)
            return surface
        values = ([r["score"] for r in rows] if kind == "score"
                  else [r["accuracy"] for r in rows])
        high = max(values) * 1.2 + 1 if kind == "score" else 105
        points = []
        for i, value in enumerate(values):
            x = left + plot_w * (i + 0.5) / max(1, len(values))
            y = bottom - plot_h * max(0, value) / max(1, high)
            points.append((int(x), int(y)))
        color = GOLD if kind == "score" else GREEN
        if len(points) > 1:
            pygame.draw.lines(surface, color, False, points, 2)
        for point in points:
            pygame.draw.circle(surface, color, point, 3)
        theme.text(surface, "SCORE" if kind == "score" else "ACCURACY %",
                   9, MUTED, (left, 2), anchor="midleft", bold=False)
        theme.text(surface, f"{int(values[-1])}", 10, WHITE, (right, 2),
                   anchor="midright")
        return surface

    def _render_chart(self, kind, width, height):
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        dpi = 100
        fig = Figure(figsize=(width / dpi, height / dpi), dpi=dpi)
        fig.patch.set_facecolor(PANEL_HEX)
        ax = fig.add_subplot(111)
        _style_axes(ax)

        rows = self.history.get(self.selected, [])
        if kind == "activity":
            days = self.activity
            labels = [d[0][5:].replace("-", "/") for d in days]
            counts = [d[1] for d in days]
            ax.bar(range(len(days)), counts, color="#37e1ff", width=0.6,
                   alpha=0.85)
            ax.set_xticks(range(0, len(days), 2))
            ax.set_xticklabels(labels[::2], rotation=0, fontsize=7)
            ax.set_ylim(0, max(3, max(counts) + 1) if counts else 3)
            ax.tick_params(axis="y", labelsize=7)
        elif not rows:
            ax.text(0.5, 0.5, "NO SESSIONS YET", ha="center", va="center",
                    color=MUTED_HEX, fontsize=10, transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.grid(False)
        else:
            xs = list(range(1, len(rows) + 1))
            ax.set_xlim(0.5, len(xs) + 0.5)
            if len(xs) <= 10:
                ax.set_xticks(xs)
            if kind == "score":
                ys = [r["score"] for r in rows]
                color = _hex(self._accent())
                ax.plot(xs, ys, color=color, linewidth=1.8, marker="o",
                        markersize=4, markerfacecolor=color,
                        markeredgecolor=PANEL_HEX, markeredgewidth=1)
                ax.fill_between(xs, ys, 0, color=color, alpha=0.12)
                ax.set_ylim(0, max(ys) * 1.25 + 1)
                ax.tick_params(axis="x", labelsize=7)
                ax.set_xlabel("session", color=MUTED_HEX, fontsize=7)
            else:
                ys = [r["accuracy"] for r in rows]
                color = "#4bf5aa"
                ax.plot(xs, ys, color=color, linewidth=1.8, marker="o",
                        markersize=3)
                ax.fill_between(xs, ys, 0, color=color, alpha=0.12)
                ax.set_ylim(0, 105)
                ax.tick_params(axis="x", labelsize=7)
                ax.set_xlabel("session", color=MUTED_HEX, fontsize=7)
        fig.tight_layout(pad=1.0)

        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        buf = io.BytesIO()
        canvas.print_png(buf)
        buf.seek(0)
        image = pygame.image.load(buf, "chart.png").convert()
        return image

    def _accent(self):
        for cls in GAME_CLASSES:
            if cls.game_id == self.selected:
                return cls.accent
        return CYAN

    def draw_charts(self, surface):
        titles = {
            "score": f"SCORE HISTORY — {self._selected_title()}",
            "accuracy": "ACCURACY TREND",
            "activity": "ACTIVITY — LAST 14 DAYS",
        }
        for kind, rect in CHART_RECTS.items():
            theme.panel(surface, rect, color=PANEL, border=BORDER_SOFT,
                        radius=18, width=1, shadow=False)
            theme.text(surface, titles[kind], 11, MUTED,
                       (rect.x + 18, rect.y + 18), anchor="midleft")
            inner = pygame.Rect(rect.x + 8, rect.y + 32, rect.w - 16,
                                rect.h - 40)
            image = self._chart_image(kind, inner)
            if image is not None:
                surface.blit(image, inner.topleft)
            else:
                theme.text(surface, "Chart unavailable — install matplotlib",
                           12, DIM, inner.center, bold=False)

    def _selected_title(self):
        for cls in GAME_CLASSES:
            if cls.game_id == self.selected:
                return cls.title.upper()
        return ""

    def draw_comparison(self, surface):
        panel = pygame.Rect(52, 676, 1096, 96)
        theme.panel(surface, panel, color=PANEL, border=BORDER_SOFT,
                    radius=16, width=1, shadow=False)
        latest, previous, best = self.comp
        theme.text(surface, "SESSION COMPARISON", 11, MUTED, (74, 696),
                   anchor="midleft")
        if latest is None:
            theme.text(surface, "Play this module to unlock session-to-session "
                                "comparisons.", 13, DIM, (74, 730),
                       anchor="midleft", bold=False)
            return

        def fmt(row):
            return (f"{row['score']:,} pts  •  {row['accuracy']:.0f}% acc  •  "
                    f"{row['played_at'][5:16].replace('T', ' ')}")

        entries = [
            ("LAST SESSION", latest, CYAN),
            ("PREVIOUS", previous, MUTED),
            ("PERSONAL BEST", best, GOLD),
        ]
        for i, (label, row, color) in enumerate(entries):
            x = 74 + i * 340
            theme.text(surface, label, 10, color, (x, 720), anchor="midleft")
            if row is None:
                theme.text(surface, "—", 15, DIM, (x, 742), anchor="midleft")
            else:
                theme.text(surface, fmt(row), 13, WHITE, (x, 742),
                           anchor="midleft")
        if previous is not None:
            delta = latest["score"] - previous["score"]
            color = GREEN if delta >= 0 else RED
            arrow = "▲" if delta >= 0 else "▼"
            theme.text(surface, f"{arrow} {abs(delta):,} vs previous", 13,
                       color, (1148, 720), anchor="midright")
            acc_delta = latest["accuracy"] - previous["accuracy"]
            theme.text(surface, f"{acc_delta:+.0f}% accuracy", 11,
                       color if acc_delta >= 0 else RED,
                       (1148, 744), anchor="midright")
