"""Common game framework: intro, countdown, HUD, pause, summary, effects."""

import math

import pygame

from config import (
    WIDTH, HEIGHT, PANEL, PANEL_LIGHT, PANEL_DARK, BORDER, BORDER_SOFT,
    WHITE, MUTED, DIM, CYAN, GOLD, GREEN, RED, PURPLE, BG_TOP,
    DIFFICULTY_COLORS,
)
from ui import theme
from ui.widgets import Button
from ui.window_controls import WindowControls
from animations.easing import clamp, ease_out_cubic, ease_out_back, pulse
from animations.particles import ParticleSystem


INTRO_PANEL = pygame.Rect(WIDTH // 2 - 430, 78, 860, 644)
SUMMARY_PANEL = pygame.Rect(WIDTH // 2 - 380, 78, 760, 644)
PAUSE_PANEL = pygame.Rect(WIDTH // 2 - 230, 200, 460, 400)
MENU_RECT = pygame.Rect(38, 29, 106, 34)


class BaseGame:
    game_id = "base"
    game_number = 0
    title = "Game"
    subtitle = ""
    description = ""
    instructions = []
    accent = CYAN
    icon = "dot"
    supports_difficulty = False
    difficulty_labels = ["EASY", "NORMAL", "HARD"]
    difficulty_multipliers = [0.8, 1.0, 1.25]
    summary_notes = ""

    def __init__(self, app):
        self.app = app
        self.particles = ParticleSystem()
        self.floaters = []
        self.state = "intro"
        self.time = 0.0
        self.countdown = 0.0
        self._last_count = None
        self.flash_t = 0.0
        self.flash_max = 0.35
        self.flash_color = WHITE
        self.saved = False
        self.result = None
        self.new_best = False
        self.first_play = False
        self.exit_requested = False
        self.paused_from = "playing"
        self.difficulty_level = 1
        self.hud = []
        self.progress = None
        self.progress_color = CYAN
        self.summary_t = 0.0
        self.intro_t = 0.0
        self._summary_panel = SUMMARY_PANEL
        self.assessment = None
        self.feedback = None
        self.neuro_feedback = None
        self.window_controls = WindowControls(app, WIDTH - 190, 30, 30, 5)
        self.reset()
        self._build_buttons()

    # ------------------------------------------------------------- config
    @property
    def difficulty_name(self):
        return self.difficulty_labels[self.difficulty_level]

    @property
    def difficulty_scale(self):
        return self.difficulty_multipliers[self.difficulty_level]

    # -------------------------------------------------------------- state
    def reset(self):
        self.score = 0
        self.hits = 0
        self.misses = 0
        self.mistakes = 0
        self.time = 0.0
        self.hud = []
        self.progress = None
        self.particles.clear()
        self.floaters.clear()
        self.flash_t = 0.0
        self.result = None
        self.saved = False
        self.new_best = False
        self.first_play = False
        self.assessment = None
        self.feedback = None
        self.neuro_feedback = None

    def _build_buttons(self):
        self.start_button = Button(
            (WIDTH // 2 - 140, INTRO_PANEL.bottom - 96, 280, 56),
            "START MISSION", "primary", self.accent, 20, icon="play",
        )
        self.diff_buttons = []
        if self.supports_difficulty:
            total = 3 * 150 + 2 * 14
            x0 = WIDTH // 2 - total // 2
            y0 = INTRO_PANEL.bottom - 158
            for i, label in enumerate(self.difficulty_labels):
                self.diff_buttons.append(
                    Button((x0 + i * 164, y0, 150, 42), label, "ghost",
                           self.accent, 15)
                )
        self.resume_button = Button(
            (PAUSE_PANEL.centerx - 160, PAUSE_PANEL.y + 128, 320, 50),
            "RESUME", "primary", self.accent, 18, icon="play",
        )
        self.pause_restart_button = Button(
            (PAUSE_PANEL.centerx - 160, PAUSE_PANEL.y + 192, 320, 46),
            "RESTART", "ghost", self.accent, 17,
        )
        self.pause_exit_button = Button(
            (PAUSE_PANEL.centerx - 160, PAUSE_PANEL.y + 250, 320, 46),
            "DASHBOARD", "ghost", self.accent, 17,
        )
        self.again_button = Button(
            (SUMMARY_PANEL.centerx - 260, SUMMARY_PANEL.bottom - 92, 240, 54),
            "PLAY AGAIN", "primary", self.accent, 18, icon="play",
        )
        self.summary_exit_button = Button(
            (SUMMARY_PANEL.centerx + 20, SUMMARY_PANEL.bottom - 92, 240, 54),
            "DASHBOARD", "ghost", self.accent, 18,
        )

    def begin(self):
        self.app.audio.play("click")
        self.state = "countdown"
        self.countdown = 3.0
        self._last_count = None
        self.particles.clear()
        self.floaters.clear()

    def restart(self):
        self.reset()
        self.begin()

    def set_paused(self, paused):
        if paused and self.state in ("playing", "countdown"):
            self.paused_from = self.state
            self.state = "paused"
            self.app.audio.play("click")
        elif not paused and self.state == "paused":
            self.state = self.paused_from
            self.app.audio.play("click")

    def start_play(self):
        self.state = "playing"
        self.time = 0.0
        self.app.audio.play("go")
        self.on_start()

    def finish(self, result):
        result.setdefault("score", self.score)
        result.setdefault("accuracy", 0.0)
        result.setdefault("mistakes", self.mistakes)
        result.setdefault("hits", self.hits)
        result.setdefault("avg_reaction_ms", None)
        result.setdefault("duration", self.time)
        result.setdefault("stats", [])
        result.setdefault("extra", {})
        self.result = result
        self.state = "summary"
        self.summary_t = 0.0
        self.saved = False
        self.progress = None
        self.app.audio.play("success")
        panel = pygame.Rect(0, 0, 880, 700)
        panel.center = (WIDTH // 2, HEIGHT // 2)
        self._summary_panel = panel
        self.again_button.rect.topleft = (panel.centerx - 260,
                                          panel.bottom - 92)
        self.summary_exit_button.rect.topleft = (panel.centerx + 20,
                                                 panel.bottom - 92)
        for _ in range(3):
            self.particles.confetti(
                WIDTH // 2 + (-260 if _ == 0 else 260 if _ == 2 else 0),
                panel.y + 60,
                [self.accent, GOLD, PURPLE, GREEN], 26,
            )

    # ------------------------------------------------------------- events
    def handle_event(self, event, pointers):
        if event.type == pygame.KEYDOWN:
            self.on_key(event.key)
        for p in pointers:
            if p.kind == "down":
                self.on_pointer(p)
            elif p.kind == "up":
                self.on_pointer_up(p)

    def on_key(self, key):
        if key == pygame.K_m:
            self.app.audio.toggle_mute()
        elif key == pygame.K_ESCAPE:
            if self.state in ("playing", "countdown"):
                self.set_paused(True)
            elif self.state == "paused":
                self.set_paused(False)
            else:
                self.exit_requested = True
        elif key == pygame.K_SPACE:
            if self.state == "intro":
                self.begin()
            elif self.state == "summary":
                self.restart()
        elif key == pygame.K_r:
            if self.state in ("summary", "paused"):
                self.restart()
        elif pygame.K_1 <= key <= pygame.K_3 and self.state == "intro" \
                and self.supports_difficulty:
            self.difficulty_level = key - pygame.K_1
            self.app.audio.play("click")

    def on_pointer(self, p):
        pos = p.pos
        if self.window_controls.handle_click(pos):
            return
        if self.state in ("playing", "countdown"):
            if MENU_RECT.collidepoint(pos):
                self.set_paused(True)
                return
            mute = getattr(self, "_mute_rect", None)
            if mute is not None and mute.collidepoint(pos):
                self.app.audio.toggle_mute()
                return
        if self.state == "intro":
            if self.start_button.hit(pos):
                self.begin()
                return
            for i, b in enumerate(self.diff_buttons):
                if b.hit(pos):
                    self.difficulty_level = i
                    self.app.audio.play("click")
                    return
        elif self.state == "paused":
            if self.resume_button.hit(pos):
                self.set_paused(False)
            elif self.pause_restart_button.hit(pos):
                self.restart()
            elif self.pause_exit_button.hit(pos):
                self.exit_requested = True
            return
        elif self.state == "summary":
            if self.again_button.hit(pos):
                self.restart()
            elif self.summary_exit_button.hit(pos):
                self.exit_requested = True
            return
        elif self.state == "playing":
            self.on_play_click(p)

    def on_play_click(self, p):
        pass

    def on_pointer_up(self, p):
        pass

    # ------------------------------------------------------------ helpers
    def add_floater(self, text, pos, color=WHITE, size=24, life=0.9, rise=55):
        self.floaters.append({
            "text": str(text), "x": float(pos[0]), "y": float(pos[1]),
            "color": color, "size": size, "life": life,
            "max_life": life, "rise": rise,
        })

    def flash(self, color=WHITE, strength=1.0):
        self.flash_color = color
        self.flash_t = 0.28
        self.flash_max = 0.28
        self._flash_strength = strength

    def set_hud(self, items, progress=None, progress_color=CYAN):
        self.hud = items
        self.progress = progress
        self.progress_color = progress_color

    # ------------------------------------------------------------ update
    def update(self, dt):
        self.intro_t += dt
        mouse = self.app.input.pos
        down = self.app.input.down
        for b in self._active_buttons():
            b.update(dt, mouse, down)
        self.window_controls.update(dt)
        self.particles.update(dt)
        for f in self.floaters:
            f["life"] -= dt
            f["y"] -= f["rise"] * dt
        self.floaters = [f for f in self.floaters if f["life"] > 0]
        if self.flash_t > 0:
            self.flash_t = max(0.0, self.flash_t - dt)
        if self.state == "countdown":
            self.countdown -= dt
            count = max(1, math.ceil(self.countdown))
            if self.countdown > 0.35 and count != self._last_count:
                self._last_count = count
                self.app.audio.play("countdown")
            if self.countdown <= 0:
                self.start_play()
        elif self.state == "playing":
            self.time += dt
            self.update_game(dt)
        elif self.state == "summary":
            self.summary_t += dt

    def update_game(self, dt):
        pass

    def _active_buttons(self):
        if self.state == "intro":
            return [self.start_button] + list(self.diff_buttons)
        if self.state == "paused":
            return [self.resume_button, self.pause_restart_button,
                    self.pause_exit_button]
        if self.state == "summary":
            return [self.again_button, self.summary_exit_button]
        return []

    def on_start(self):
        pass

    # -------------------------------------------------------------- draw
    def draw(self, surface):
        self.draw_world(surface)
        self.particles.draw(surface)
        self.draw_floaters(surface)
        if self.state in ("playing", "countdown", "paused"):
            self.draw_hud(surface)
        if self.state == "intro":
            self.draw_intro(surface)
        elif self.state == "countdown":
            self.draw_countdown(surface)
        elif self.state == "paused":
            self.draw_pause(surface)
        elif self.state == "summary":
            self.draw_summary(surface)
        if self.state not in ("playing", "countdown"):
            self.window_controls.draw(surface)
        if self.flash_t > 0:
            alpha = int(150 * (self.flash_t / self.flash_max)
                        * getattr(self, "_flash_strength", 1.0))
            theme.alpha_rect(surface, (0, 0, WIDTH, HEIGHT),
                             self.flash_color, alpha)

    def draw_world(self, surface):
        pass

    def draw_floaters(self, surface):
        for f in self.floaters:
            a = clamp(f["life"] / f["max_life"])
            theme.text_alpha(surface, f["text"], f["size"], f["color"],
                             (int(f["x"]), int(f["y"])), alpha=255 * a)

    # ---------------------------------------------------------------- HUD
    def draw_hud(self, surface):
        theme.alpha_rect(surface, (24, 18, WIDTH - 48, 56), PANEL, 220,
                         radius=14)
        pygame.draw.rect(surface, BORDER_SOFT, (24, 18, WIDTH - 48, 56),
                         width=1, border_radius=14)

        # Menu button
        menu = pygame.Rect(38, 29, 106, 34)
        hovered = menu.collidepoint(self.app.input.pos)
        pygame.draw.rect(surface, PANEL_LIGHT if hovered else PANEL_DARK,
                         menu, border_radius=8)
        pygame.draw.rect(surface, BORDER, menu, width=1, border_radius=8)
        theme.draw_keycap(surface, "ESC", (46, 35, 38, 22), MUTED)
        theme.text(surface, "MENU", 14, WHITE if hovered else MUTED,
                   (92, 46), anchor="midleft")

        n = max(1, len(self.hud))
        span = (WIDTH - 360) // n
        start = 170
        for i, (label, value, color) in enumerate(self.hud):
            cx = start + span * i
            pygame.draw.circle(surface, color, (cx, 38), 3)
            theme.text(surface, label.upper(), 11, MUTED,
                       (cx + 12, 37), anchor="midleft", bold=False)
            theme.text(surface, value, 23, color,
                       (cx + 12, 57), anchor="midleft")

        # Mute indicator
        mute_rect = pygame.Rect(WIDTH - 76, 28, 40, 36)
        self._mute_rect = mute_rect
        self._draw_speaker(surface, mute_rect.center,
                           RED if self.app.audio.muted else MUTED)

        self.window_controls.draw(surface)

        if self.progress is not None:
            theme.progress_bar(
                surface, (24, 82, WIDTH - 48, 6), self.progress,
                self.progress_color,
            )

    def _draw_speaker(self, surface, c, color):
        pygame.draw.polygon(surface, color, [
            (c[0] - 9, c[1] - 4), (c[0] - 4, c[1] - 4), (c[0] + 2, c[1] - 9),
            (c[0] + 2, c[1] + 9), (c[0] - 4, c[1] + 4), (c[0] - 9, c[1] + 4),
        ])
        if self.app.audio.muted:
            pygame.draw.line(surface, color, (c[0] + 6, c[1] - 5),
                             (c[0] + 12, c[1] + 5), 2)
            pygame.draw.line(surface, color, (c[0] + 12, c[1] - 5),
                             (c[0] + 6, c[1] + 5), 2)
        else:
            pygame.draw.arc(surface, color, (c[0] - 2, c[1] - 8, 14, 16),
                            -1.0, 1.0, 2)

    # ------------------------------------------------------------- intro
    def draw_intro(self, surface):
        theme.alpha_rect(surface, (0, 0, WIDTH, HEIGHT), (3, 5, 16), 170)
        panel = INTRO_PANEL
        theme.panel(surface, panel, color=PANEL, border=BORDER, radius=24)
        pygame.draw.rect(surface, self.accent, (panel.x, panel.y, panel.w, 5),
                         border_top_left_radius=24, border_top_right_radius=24)
        theme.glow(surface, (panel.centerx, panel.y + 6), 180, self.accent,
                   layers=4, strength=0.05)

        x = panel.x + 50
        y = panel.y + 42
        label = (f"GAME {self.game_number:02d}" if self.game_number
                 else "ARCADE MISSION")
        theme.text(surface, label, 13, self.accent, (x, y), anchor="midleft")
        theme.text(surface, self.title, 38, WHITE, (x, y + 40),
                   anchor="midleft")
        theme.text(surface, self.subtitle, 16, MUTED, (x, y + 80),
                   anchor="midleft", bold=False)

        y += 124
        pygame.draw.line(surface, BORDER_SOFT, (x, y), (panel.right - 50, y), 1)

        desc_lines = theme.wrap_lines(self.description, 16, panel.w - 100,
                                      bold=False)
        for line in desc_lines:
            theme.text(surface, line, 16, (196, 205, 230), (x, y + 26),
                       anchor="midleft", bold=False)
            y += 24
        y += 32

        theme.text(surface, "HOW TO PLAY", 12, MUTED, (x, y),
                   anchor="midleft")
        y += 26
        for bullet in self.instructions:
            pygame.draw.circle(surface, self.accent, (x + 5, y - 1), 3)
            lines = theme.wrap_lines(bullet, 15, panel.w - 130, bold=False)
            for j, line in enumerate(lines):
                theme.text(surface, line, 15, WHITE,
                           (x + 20, y), anchor="midleft", bold=False)
                y += 21
            y += 4

        if self.supports_difficulty:
            theme.text(surface, "DIFFICULTY", 12, MUTED,
                       (self.diff_buttons[0].rect.x - 12,
                        self.diff_buttons[0].rect.centery),
                       anchor="midright")
            for i, b in enumerate(self.diff_buttons):
                active = i == self.difficulty_level
                if active:
                    theme.glow(surface, b.rect.center, b.rect.w // 2,
                               self.accent, layers=3, strength=0.10)
                    pygame.draw.rect(surface, self.accent, b.rect.inflate(6, 6),
                                     width=2, border_radius=14)
                b.draw(surface)

        self.start_button.draw(surface)
        theme.text(surface, "SPACE to start   •   ESC returns to the hub",
                   13, DIM, (panel.centerx, panel.bottom - 24))

    # --------------------------------------------------------- countdown
    def draw_countdown(self, surface):
        theme.alpha_rect(surface, (0, 0, WIDTH, HEIGHT), (3, 5, 16), 110)
        number = max(1, math.ceil(self.countdown))
        frac = self.countdown % 1.0
        scale = 1.0 + 0.35 * (1 - ease_out_cubic(min(1.0, (1 - frac) * 4)))
        if self.countdown > 0.35:
            label = str(number)
        else:
            label = "GO!"
        size = int(120 * scale)
        alpha = 255 if self.countdown > 0.35 else 255
        theme.glow(surface, (WIDTH // 2, HEIGHT // 2), 120, self.accent,
                   layers=5, strength=0.12)
        theme.text_alpha(surface, label, size, WHITE,
                         (WIDTH // 2, HEIGHT // 2 - 10), alpha=alpha)
        theme.text(surface, "GET READY", 16, self.accent,
                   (WIDTH // 2, HEIGHT // 2 + 90))

    # -------------------------------------------------------------- pause
    def draw_pause(self, surface):
        theme.alpha_rect(surface, (0, 0, WIDTH, HEIGHT), (3, 5, 16), 190)
        theme.panel(surface, PAUSE_PANEL, color=PANEL, border=BORDER,
                    radius=22)
        theme.text(surface, "PAUSED", 36, WHITE,
                   (PAUSE_PANEL.centerx, PAUSE_PANEL.y + 58))
        theme.text(surface, self.title, 15, self.accent,
                   (PAUSE_PANEL.centerx, PAUSE_PANEL.y + 92), bold=False)
        self.resume_button.draw(surface)
        self.pause_restart_button.draw(surface)
        self.pause_exit_button.draw(surface)
        theme.text(surface, "ESC resumes  •  M toggles sound", 12, DIM,
                   (PAUSE_PANEL.centerx, PAUSE_PANEL.bottom - 22))

    # ------------------------------------------------------------ summary
    def draw_summary(self, surface):
        from core.neuro import LEVEL_COLORS
        theme.alpha_rect(surface, (0, 0, WIDTH, HEIGHT), (3, 5, 16), 215)
        panel = self._summary_panel
        theme.panel(surface, panel, color=PANEL, border=BORDER, radius=24)
        pygame.draw.rect(surface, self.accent, (panel.x, panel.y, panel.w, 5),
                         border_top_left_radius=24, border_top_right_radius=24)
        theme.text(surface, "SESSION COMPLETE", 14, self.accent,
                   (panel.centerx, panel.y + 30))
        theme.text(surface, self.title, 28, WHITE,
                   (panel.centerx, panel.y + 62))

        result = self.result or {}
        score = int(result.get("score", 0))
        shown = int(score * ease_out_cubic(min(1.0, self.summary_t / 0.8)))
        theme.text(surface, f"{shown:,}", 52, GOLD,
                   (panel.centerx, panel.y + 112))
        theme.text(surface, "POINTS", 11, MUTED,
                   (panel.centerx, panel.y + 146))

        badge = None
        badge_color = GOLD
        if self.new_best:
            badge = "NEW PERSONAL BEST"
        elif self.first_play:
            badge = "FIRST FLIGHT"
            badge_color = CYAN
        if badge:
            bw = theme.text_width(surface, badge, 12) + 32
            brect = pygame.Rect(0, 0, bw, 24)
            brect.center = (panel.centerx, panel.y + 170)
            pygame.draw.rect(surface, badge_color, brect, border_radius=12)
            theme.text(surface, badge, 12, BG_TOP, brect.center)

        rows = result.get("stats", [])[:8]
        col_x = [panel.x + 46, panel.centerx + 20]
        top = panel.y + 200
        for i, (label, value) in enumerate(rows):
            col = i % 2
            row = i // 2
            x = col_x[col]
            y = top + row * 36
            theme.text(surface, label, 14, MUTED, (x, y), anchor="midleft",
                       bold=False)
            theme.text(surface, value, 17, WHITE,
                       (x + 340, y), anchor="midright")
            pygame.draw.line(surface, BORDER_SOFT, (x, y + 14),
                             (x + 340, y + 14), 1)

        # Neurobehavioral feedback block (separate from transient game text).
        fb = self.neuro_feedback
        box = pygame.Rect(panel.x + 30, panel.y + 350, panel.w - 60, 244)
        theme.alpha_rect(surface, box, PANEL_LIGHT, 150, radius=16)
        pygame.draw.rect(surface, BORDER_SOFT, box, width=1, border_radius=16)
        if not fb:
            theme.text(surface, "ASSESSING PERFORMANCE AGAINST BASELINE…",
                       13, MUTED, box.center)
        else:
            color = LEVEL_COLORS.get(fb.get("level"), MUTED)
            theme.text(surface, fb.get("headline", ""), 16, color,
                       (box.x + 20, box.y + 22), anchor="midleft")
            if fb.get("multisystem"):
                tag = "MULTISYSTEM"
                tw = theme.text_width(surface, tag, 10) + 20
                trect = pygame.Rect(box.right - 20 - tw, box.y + 10, tw, 20)
                pygame.draw.rect(surface, GOLD, trect, border_radius=10)
                theme.text(surface, tag, 10, BG_TOP, trect.center)
            y = box.y + 46
            lines = theme.wrap_lines(fb.get("message", ""), 12,
                                     box.w - 40, bold=False)
            for line in lines[:6]:
                theme.text(surface, line, 12, (208, 216, 238), (box.x + 20, y),
                           anchor="midleft", bold=False)
                y += 17
            actions = fb.get("actions", [])[:2]
            if actions and y < box.bottom - 40:
                y += 8
                theme.text(surface, "RECOMMENDED ACTIONS", 10, MUTED,
                           (box.x + 20, y), anchor="midleft")
                y += 18
                for action in actions:
                    pygame.draw.circle(surface, color, (box.x + 26, y - 1), 3)
                    for line in theme.wrap_lines(action, 11, box.w - 70,
                                                 bold=False)[:2]:
                        theme.text(surface, line, 11, WHITE, (box.x + 38, y),
                                   anchor="midleft", bold=False)
                        y += 15
                    y += 2

        self.again_button.draw(surface)
        self.summary_exit_button.draw(surface)
        theme.text(surface, "R replays   •   ESC returns to the hub", 12, DIM,
                   (panel.centerx, panel.bottom - 18))
