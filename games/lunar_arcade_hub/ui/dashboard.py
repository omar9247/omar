"""Dashboard: six monitored assessments, physiology strip and alert feed."""

import pygame

from config import (
    WIDTH, PANEL, PANEL_LIGHT, PANEL_DARK, BORDER, BORDER_SOFT,
    WHITE, MUTED, CYAN, GOLD, GREEN, PURPLE, DIM, RED,
)
from ui import theme
from ui.navbar import NavBar
from ui.game_cards import GameCard
from ui.widgets import Button, Chip
from games import GAME_CLASSES
from animations.easing import clamp, ease_out_cubic

PHYSIO_FIELDS = [
    ("sleep_hours", "SLEEP", "{:.1f} h"),
    ("co2_mmhg", "CABIN CO2", "{:.1f} mmHg"),
    ("hrv_ms", "HRV", "{:.0f} ms"),
    ("sleep_efficiency", "SLEEP EFF.", "{:.0f}%"),
    ("mood", "MOOD", "{:.0f}/10"),
    ("hydration", "HYDRATION", "{:.0f}%"),
    ("stress", "STRESS", "{:.0f}/10"),
]


class Dashboard:
    def __init__(self, app):
        self.app = app
        self.nav = NavBar(app, "dashboard")
        self.enter_t = 0.0
        self.cards = []
        self.totals = {}
        self.username = "Cadet"
        self.flags = {}
        self.alert = None
        self.physiology = None
        self.monitor_button = Button((978, 738, 150, 36), "OPEN MONITOR",
                                     "ghost", CYAN, 12)
        self.physio_rect = pygame.Rect(52, 632, 1096, 84)
        self._layout()

    def _layout(self):
        self.cards = []
        x0, y0, w, h, gx, gy = 52, 212, 354, 196, 16, 14
        for i, cls in enumerate(GAME_CLASSES):
            row, col = divmod(i, 3)
            rect = (x0 + col * (w + gx), y0 + row * (h + gy), w, h)
            self.cards.append(GameCard(rect, cls, i))

    def enter(self):
        self.enter_t = 0.0
        self.username = self.app.db.get_username()
        self.totals = self.app.db.totals()
        for card in self.cards:
            card.load(self.app)
        self.flags = {f["key"]: f for f in self.app.neuro.physiology_flags()}
        self.physiology = self.app.db.get_physiology()
        alerts = self.app.db.recent_alerts(1)
        self.alert = alerts[0] if alerts else None

    def handle_event(self, event, pointers):
        if event.type == pygame.KEYDOWN:
            if pygame.K_1 <= event.key <= pygame.K_6:
                index = event.key - pygame.K_1
                if index < len(GAME_CLASSES):
                    self.app.open_game(GAME_CLASSES[index].game_id)
            elif event.key == pygame.K_ESCAPE:
                self.app.request_quit()
            elif event.key == pygame.K_m:
                self.app.audio.toggle_mute()
        for p in pointers:
            if p.kind == "down":
                if self.nav.handle_click(p.pos):
                    return
                if self.monitor_button.hit(p.pos):
                    self.app.audio.play("click")
                    self.app.go_to("monitor")
                    return
                if self.physio_rect.collidepoint(p.pos):
                    self.app.audio.play("click")
                    self.app.go_to("monitor")
                    return
                for card in self.cards:
                    if card.hit(p.pos):
                        self.app.audio.play("click")
                        self.app.open_game(card.cls.game_id)
                        return

    def update(self, dt):
        self.enter_t += dt
        self.nav.update(dt)
        mouse = self.app.input.pos
        for card in self.cards:
            card.update(dt, mouse)
        self.monitor_button.update(dt, mouse, self.app.input.down)

    def draw(self, surface):
        self.nav.draw(surface)

        # Hero.
        theme.text(surface, "WELCOME BACK,", 13, CYAN, (54, 96),
                   anchor="midleft")
        theme.text(surface, self.username.upper(), 34, WHITE, (52, 130),
                   anchor="midleft")
        theme.text(surface, "Six assessments online. Personal baselines "
                            "drive your alerts.", 13, MUTED, (54, 164),
                   anchor="midleft", bold=False)

        chips = [
            ("Assessments", f"{self.totals.get('games', 0)}", CYAN),
            ("Best score", f"{self.totals.get('best', 0):,}", GOLD),
            ("Avg accuracy", f"{self.totals.get('accuracy', 0):.0f}%", GREEN),
        ]
        for i, (label, value, color) in enumerate(chips):
            Chip.draw(surface, (560 + i * 192, 96, 180, 76), label, value, color)

        # Library header.
        theme.text(surface, "COGNITIVE ASSESSMENTS", 13, MUTED, (52, 196),
                   anchor="midleft")
        pygame.draw.line(surface, BORDER_SOFT, (240, 196), (1080, 196), 1)
        theme.text(surface, "6 MODULES ONLINE", 10, DIM, (1148, 196),
                   anchor="midright")

        for i, card in enumerate(self.cards):
            delay = i * 0.04
            p = ease_out_cubic(clamp((self.enter_t - delay) / 0.5))
            base = card.rect.copy()
            offset = int((1 - p) * 14)
            if offset:
                card.rect = base.move(0, offset)
            card.draw(surface, self.enter_t)
            card.rect = base

        self._draw_physiology(surface)
        self._draw_alert(surface)

    def _draw_physiology(self, surface):
        rect = self.physio_rect
        theme.panel(surface, rect, color=PANEL, border=BORDER_SOFT, radius=16,
                    width=1, shadow=False)
        theme.text(surface, "PHYSIOLOGY & ENVIRONMENT", 10, MUTED,
                   (rect.x + 16, rect.y + 16), anchor="midleft")
        theme.text(surface, "CLICK TO EDIT IN MONITOR", 9, DIM,
                   (rect.right - 16, rect.y + 16), anchor="midright")

        rec = self.physiology
        if not rec:
            theme.text(surface, "No physiology logged yet — open the monitor "
                                "to record sleep, cabin CO2, HRV, mood, "
                                "hydration and stress.", 12, DIM,
                       (rect.centerx, rect.y + 54), bold=False)
            return
        for i, (key, label, fmt) in enumerate(PHYSIO_FIELDS):
            x = rect.x + 16 + i * 152
            value = rec.get(key)
            flag = self.flags.get(key)
            color = (RED if flag and flag["level"] == "red" else
                     GOLD if flag and flag["level"] == "amber" else WHITE)
            theme.text(surface, label, 9, MUTED, (x, rect.y + 42),
                       anchor="midleft")
            text = fmt.format(value) if value is not None else "—"
            theme.text(surface, text, 14, color, (x, rect.y + 60),
                       anchor="midleft")
            if flag:
                pygame.draw.circle(surface, color, (x + 132, rect.y + 42), 3)

    def _draw_alert(self, surface):
        rect = pygame.Rect(52, 728, 1096, 56)
        theme.panel(surface, rect, color=PANEL, border=BORDER_SOFT, radius=14,
                    width=1, shadow=False)
        color = MUTED
        text = "No alerts on record. Complete calibration sessions to enable "
        text += "monitoring."
        label = "LATEST ALERT"
        if self.alert:
            color = (RED if self.alert["level"] == "red" else GOLD)
            level = self.alert["level"].upper()
            ms = " • MULTISYSTEM" if self.alert.get("multisystem") else ""
            label = f"{level} ALERT{ms}"
            msg = self.alert.get("message") or ""
            lines = theme.wrap_lines(msg, 11, 780, bold=False)
            text = lines[0] if lines else ""
        theme.text(surface, label, 9, color, (rect.x + 16, rect.y + 15),
                   anchor="midleft")
        theme.text(surface, text, 11, WHITE if self.alert else DIM,
                   (rect.x + 16, rect.y + 35), anchor="midleft", bold=False)
        self.monitor_button.draw(surface)
