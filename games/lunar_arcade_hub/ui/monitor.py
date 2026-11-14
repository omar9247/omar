"""Neuro-monitor: physiology entry, personal baselines and alert history."""

import datetime

import pygame

from config import (
    WIDTH, PANEL, PANEL_LIGHT, PANEL_DARK, BORDER, BORDER_SOFT, WHITE,
    MUTED, CYAN, GOLD, GREEN, RED, PURPLE, DIM,
)
from core.neuro import ASSESSMENTS, LEVEL_COLORS, format_value
from games import GAME_CLASSES
from ui import theme
from ui.navbar import NavBar
from ui.widgets import Button
from ui.wellbeing import WellbeingView
from animations.easing import clamp

FIELDS = [
    # key, label, unit, minimum, maximum, step, decimals, default
    ("sleep_hours", "Sleep duration", "h", 0.0, 14.0, 0.5, 1, 7.5),
    ("co2_mmhg", "Cabin CO2", "mmHg", 0.0, 10.0, 0.1, 1, 2.0),
    ("hrv_ms", "Heart-rate variability", "ms", 0.0, 250.0, 1.0, 0, 55),
    ("sleep_efficiency", "Sleep efficiency", "%", 0.0, 100.0, 1.0, 0, 90),
    ("mood", "Daily mood", "/10", 1.0, 10.0, 1.0, 0, 7),
    ("hydration", "Hydration", "%", 0.0, 100.0, 1.0, 0, 92),
    ("stress", "Stress index", "/10", 0.0, 10.0, 1.0, 0, 4),
]


def format_ago(iso_string):
    try:
        then = datetime.datetime.fromisoformat(iso_string)
    except (ValueError, TypeError):
        return ""
    now = datetime.datetime.now()
    if then.date() == now.date():
        return then.strftime("TODAY %H:%M")
    return then.strftime("%d %b %H:%M").upper()


class MonitorScreen:
    def __init__(self, app):
        self.app = app
        self.nav = NavBar(app, "monitor")
        self.mode = "physiology"
        self.wellbeing = WellbeingView(app, self)
        self.wellbeing_button = Button((930, 94, 230, 36),
                                       "WELLBEING CHECK-IN", "primary",
                                       PURPLE, 11)
        self.values = {}
        self.buttons = []
        self.flags = {}
        self.baselines = {}
        self.alerts = []
        self._build_buttons()

    def _build_buttons(self):
        self.buttons = []
        y0 = 216
        for i, field in enumerate(FIELDS):
            y = y0 + i * 56
            self.buttons.append((field[0], -1, Button(
                (392, y + 10, 30, 30), "−", "ghost", CYAN, 16)))
            self.buttons.append((field[0], +1, Button(
                (430, y + 10, 30, 30), "+", "ghost", CYAN, 16)))

    def enter(self):
        rec = self.app.db.get_physiology() or {}
        self.values = {f[0]: rec.get(f[0]) for f in FIELDS}
        self.refresh()
        if self.mode == "wellbeing":
            self.wellbeing.enter()

    def show_wellbeing(self):
        self.mode = "wellbeing"
        self.wellbeing.enter()
        self.app.audio.play("click", 0.4)

    def show_physiology(self):
        self.mode = "physiology"
        self.refresh()
        self.app.audio.play("click", 0.3)

    def refresh(self):
        self.flags = {f["key"]: f for f in self.app.neuro.physiology_flags()}
        self.baselines = self.app.db.all_baselines()
        self.alerts = self.app.db.recent_alerts(3)

    def handle_event(self, event, pointers):
        if self.mode == "wellbeing":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                self.app.audio.toggle_mute()
                return
            for p in pointers:
                if p.kind == "down" and self.nav.handle_click(p.pos):
                    return
            self.wellbeing.handle_event(event, pointers)
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.go_to("dashboard")
            elif event.key == pygame.K_m:
                self.app.audio.toggle_mute()
        for p in pointers:
            if p.kind == "down":
                if self.nav.handle_click(p.pos):
                    return
                if self.wellbeing_button.hit(p.pos):
                    self.show_wellbeing()
                    return
                for key, direction, button in self.buttons:
                    if button.hit(p.pos):
                        self.adjust(key, direction)
                        return

    def adjust(self, key, direction):
        field = next(f for f in FIELDS if f[0] == key)
        _, _, _, lo, hi, step, decimals, default = field
        current = self.values.get(key)
        if current is None:
            current = default
        current = round(current + direction * step, decimals)
        self.values[key] = max(lo, min(hi, current))
        self.app.db.save_physiology(self.values)
        self.app.audio.play("click", 0.4)
        self.refresh()

    def update(self, dt):
        self.nav.update(dt)
        if self.mode == "wellbeing":
            self.wellbeing.update(dt)
            return
        mouse = self.app.input.pos
        down = self.app.input.down
        self.wellbeing_button.update(dt, mouse, down)
        for _, _, button in self.buttons:
            button.update(dt, mouse, down)

    def draw(self, surface):
        self.nav.draw(surface)
        if self.mode == "wellbeing":
            self.wellbeing.draw(surface)
            return
        theme.text(surface, "NEURO-MONITOR", 28, WHITE, (52, 104),
                   anchor="midleft")
        theme.text(surface, "Physiology, personal baselines and alert "
                            "history. All values feed the multisystem rule.",
                   12, MUTED, (54, 130), anchor="midleft", bold=False)

        self._draw_physiology(surface)
        self._draw_baselines(surface)
        self._draw_alerts(surface)
        self.wellbeing_button.draw(surface)

    # ------------------------------------------------------- physiology
    def _draw_physiology(self, surface):
        panel = pygame.Rect(40, 152, 420, 632)
        theme.panel(surface, panel, color=PANEL, border=BORDER_SOFT, radius=18,
                    width=1, shadow=False)
        theme.text(surface, "PHYSIOLOGY & ENVIRONMENT", 12, CYAN,
                   (panel.x + 20, panel.y + 24), anchor="midleft")
        theme.text(surface, "Today's entries — saved automatically", 10, DIM,
                   (panel.x + 20, panel.y + 44), anchor="midleft", bold=False)

        for i, (key, label, unit, lo, hi, step, decimals, default) in enumerate(FIELDS):
            y = 216 + i * 56
            theme.text(surface, label.upper(), 10, MUTED, (60, y + 10),
                       anchor="midleft")
            value = self.values.get(key)
            flag = self.flags.get(key)
            color = (RED if flag and flag["level"] == "red" else
                     GOLD if flag and flag["level"] == "amber" else WHITE)
            text = ("—" if value is None else
                    f"{value:.{decimals}f} {unit}")
            theme.text(surface, text, 16, color, (60, y + 28),
                       anchor="midleft")
            if flag:
                theme.text(surface, flag["detail"], 9, color,
                           (60, y + 44), anchor="midleft", bold=False)
            else:
                theme.text(surface, f"target {self._target_text(key)}", 9,
                           DIM, (60, y + 44), anchor="midleft", bold=False)
            pygame.draw.line(surface, BORDER_SOFT, (60, y + 50),
                             (440, y + 50), 1)
        for _, _, button in self.buttons:
            button.draw(surface)
        note = ("Multisystem rule: a cognitive alert (Amber >20%, Red >40% "
                "deterioration) combined with any flagged physiology "
                "indicator escalates the recommendations. Indicators are "
                "not diagnoses.")
        y = panel.bottom - 58
        for line in theme.wrap_lines(note, 9, panel.w - 40, bold=False):
            theme.text(surface, line, 9, DIM, (panel.x + 20, y),
                       anchor="midleft", bold=False)
            y += 12

    @staticmethod
    def _target_text(key):
        return {
            "sleep_hours": "≥ 7 h (red < 5 h)",
            "co2_mmhg": "≤ 2.5 mmHg",
            "hrv_ms": "≥ 20% below personal baseline",
            "sleep_efficiency": "≥ 85% (red < 75%)",
            "mood": "≥ 6/10",
            "hydration": "≥ 90%",
            "stress": "≤ 5/10",
        }.get(key, "")

    # --------------------------------------------------------- baselines
    def _draw_baselines(self, surface):
        panel = pygame.Rect(476, 152, 684, 296)
        theme.panel(surface, panel, color=PANEL, border=BORDER_SOFT, radius=18,
                    width=1, shadow=False)
        theme.text(surface, "PERSONAL BASELINES", 12, CYAN,
                   (panel.x + 20, panel.y + 24), anchor="midleft")
        theme.text(surface, "Never compared across difficulties", 10, DIM,
                   (panel.right - 20, panel.y + 24), anchor="midright",
                   bold=False)

        header_y = panel.y + 54
        cols = [("ASSESSMENT", panel.x + 20), ("METRIC", panel.x + 190),
                ("BASELINE", panel.x + 400), ("SAMPLES", panel.x + 500),
                ("STATUS", panel.right - 16)]
        cols[4] = ("STATUS", panel.right - 16)
        for label, x in cols:
            theme.text(surface, label, 9, MUTED, (x, header_y),
                       anchor="midright" if label == "STATUS" else "midleft")
        pygame.draw.line(surface, BORDER_SOFT, (panel.x + 20, header_y + 12),
                         (panel.right - 20, header_y + 12), 1)

        y = header_y + 32
        for cls in GAME_CLASSES:
            cfg = ASSESSMENTS.get(cls.game_id)
            row = self.baselines.get((cls.game_id, "normal"))
            if row is None:
                row = self.baselines.get((cls.game_id, "easy"))
            if row is None:
                row = self.baselines.get((cls.game_id, "hard"))
            theme.text(surface, cls.title, 12, WHITE, (cols[0][1], y),
                       anchor="midleft")
            theme.text(surface, cfg["label"] if cfg else "—", 9, MUTED,
                       (cols[1][1], y), anchor="midleft", bold=False)
            value = (format_value(row["baseline_value"], cfg)
                     if row and row.get("baseline_value") is not None else "—")
            theme.text(surface, value, 12, CYAN, (cols[2][1], y),
                       anchor="midleft")
            samples = f"{row['samples']}/{cfg['min_sessions']}" if row else "0/3"
            theme.text(surface, samples, 11, MUTED, (cols[3][1], y),
                       anchor="midleft")
            if row is None:
                status, color = "BASELINE REQUIRED", LEVEL_COLORS["baseline"]
            elif row["samples"] < cfg["min_sessions"]:
                status, color = "CALIBRATING", LEVEL_COLORS["baseline"]
            else:
                status, color = "ESTABLISHED", LEVEL_COLORS["normal"]
            theme.text(surface, status, 9, color, (cols[4][1], y),
                       anchor="midright")
            pygame.draw.line(surface, BORDER_SOFT, (panel.x + 20, y + 14),
                             (panel.right - 20, y + 14), 1)
            y += 36

    # ------------------------------------------------------------ alerts
    def _draw_alerts(self, surface):
        panel = pygame.Rect(476, 464, 684, 320)
        theme.panel(surface, panel, color=PANEL, border=BORDER_SOFT, radius=18,
                    width=1, shadow=False)
        theme.text(surface, "ALERTS & RECOMMENDATIONS", 12, CYAN,
                   (panel.x + 20, panel.y + 24), anchor="midleft")
        if not self.alerts:
            text = ("No alerts recorded. Alerts only appear after calibration "
                    "(3 valid sessions) and a confirmed deterioration beyond "
                    "your personal baseline.")
            y = panel.y + 80
            for line in theme.wrap_lines(text, 11, panel.w - 60, bold=False):
                theme.text(surface, line, 11, DIM, (panel.x + 30, y),
                           anchor="midleft", bold=False)
                y += 18
            return
        y = panel.y + 50
        for alert in self.alerts:
            color = LEVEL_COLORS.get(alert["level"], MUTED)
            tag = alert["level"].upper()
            if alert.get("multisystem"):
                tag += " • MULTISYSTEM"
            title = next((c.title for c in GAME_CLASSES
                          if c.game_id == alert["game_id"]), alert["game_id"])
            theme.text(surface, tag, 9, color, (panel.x + 20, y),
                       anchor="midleft")
            theme.text(surface, title, 12, WHITE, (panel.x + 150, y),
                       anchor="midleft")
            det = alert.get("deterioration")
            det_text = (f"{det:+.0f}%" if det is not None else "—")
            theme.text(surface, det_text, 11, color,
                       (panel.right - 20, y), anchor="midright")
            msg = alert.get("message") or ""
            lines = theme.wrap_lines(msg, 10, panel.w - 40, bold=False)[:2]
            yy = y + 16
            for line in lines:
                theme.text(surface, line, 10, MUTED, (panel.x + 20, yy),
                           anchor="midleft", bold=False)
                yy += 13
            theme.text(surface, format_ago(alert.get("created_at", "")), 9,
                       DIM, (panel.right - 20, y + 16), anchor="topright",
                       bold=False)
            y += 80
