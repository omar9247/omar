"""Cadet profile: callsign, lifetime totals, personal bests, reset."""

import datetime

import pygame

from config import (
    WIDTH, HEIGHT, PANEL, PANEL_LIGHT, PANEL_DARK, BORDER, BORDER_SOFT,
    WHITE, MUTED, CYAN, GOLD, GREEN, RED, PURPLE, DIM, BG_TOP,
)
from ui import theme
from ui.navbar import NavBar
from ui.widgets import Button, Chip
from ui.game_cards import draw_game_icon
from games import GAME_CLASSES
from animations.easing import clamp


def format_duration(seconds):
    seconds = int(seconds)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m {sec:02d}s"


class ProfileScreen:
    def __init__(self, app):
        self.app = app
        self.nav = NavBar(app, "profile")
        self.totals = {}
        self.per_game = {}
        self.info = {}
        self.editing = False
        self.name_buffer = ""
        self.edit_button = Button((177, 362, 170, 40), "EDIT CALLSIGN",
                                  "ghost", CYAN, 13)
        self.save_button = Button((127, 362, 130, 40), "SAVE", "primary",
                                  CYAN, 13)
        self.cancel_button = Button((267, 362, 130, 40), "CANCEL", "ghost",
                                    MUTED, 13)
        self.reset_button = Button((82, 576, 360, 44), "RESET ALL PROGRESS",
                                   "danger", RED, 14)
        self.confirm_reset = 0.0
        self.toast = None
        self.toast_t = 0.0
        self.refresh()

    def enter(self):
        self.editing = False
        self.confirm_reset = 0.0
        self.refresh()

    def refresh(self):
        self.info = self.app.db.profile_info()
        self.totals = self.app.db.totals()
        self.per_game = self.app.db.per_game()

    def handle_event(self, event, pointers):
        if self.editing:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    self.save_name()
                elif event.key == pygame.K_ESCAPE:
                    self.editing = False
                    self.app.audio.play("click")
                elif event.key == pygame.K_BACKSPACE:
                    self.name_buffer = self.name_buffer[:-1]
                elif event.unicode and event.unicode.isprintable() \
                        and len(self.name_buffer) < 16:
                    self.name_buffer += event.unicode
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
                if self.edit_button.hit(p.pos):
                    self.editing = True
                    self.name_buffer = self.info.get("username", "Cadet")
                    self.app.audio.play("click")
                    return
                if self.reset_button.hit(p.pos):
                    if self.confirm_reset > 0:
                        self.app.db.reset_progress()
                        self.refresh()
                        self.confirm_reset = 0.0
                        self.toast = "Progress cleared"
                        self.toast_t = 2.5
                        self.app.audio.play("error")
                    else:
                        self.confirm_reset = 4.0
                        self.app.audio.play("click")

    def save_name(self):
        name = self.app.db.set_username(self.name_buffer)
        self.info["username"] = name
        self.editing = False
        self.toast = "Callsign updated"
        self.toast_t = 2.0
        self.app.audio.play("success")

    def update(self, dt):
        self.nav.update(dt)
        mouse = self.app.input.pos
        down = self.app.input.down
        if self.editing:
            self.save_button.update(dt, mouse, down)
            self.cancel_button.update(dt, mouse, down)
        else:
            self.edit_button.update(dt, mouse, down)
            self.reset_button.update(dt, mouse, down)
        if self.confirm_reset > 0:
            self.confirm_reset = max(0.0, self.confirm_reset - dt)
        if self.toast_t > 0:
            self.toast_t = max(0.0, self.toast_t - dt)

    def draw(self, surface):
        self.nav.draw(surface)
        theme.text(surface, "CADET PROFILE", 30, WHITE, (52, 112),
                   anchor="midleft")
        theme.text(surface, "Local identity and lifetime mission record.",
                   13, MUTED, (54, 142), anchor="midleft", bold=False)

        self.draw_identity(surface)
        self.draw_stats(surface)
        self.draw_bests(surface)

        if self.toast_t > 0:
            w = theme.text_width(surface, self.toast, 14) + 48
            rect = pygame.Rect(0, 0, w, 40)
            rect.center = (WIDTH // 2, 760)
            pygame.draw.rect(surface, GREEN, rect, border_radius=20)
            theme.text(surface, self.toast, 14, BG_TOP, rect.center)

    def draw_identity(self, surface):
        panel = pygame.Rect(52, 160, 420, 490)
        theme.panel(surface, panel, color=PANEL, border=BORDER_SOFT,
                    radius=18, width=1, shadow=False)
        pygame.draw.rect(surface, CYAN, (panel.x, panel.y, panel.w, 4),
                         border_top_left_radius=18, border_top_right_radius=18)
        cx = panel.centerx
        avatar_c = (cx, 250)
        theme.glow(surface, avatar_c, 54, CYAN, layers=4, strength=0.08)
        pygame.draw.circle(surface, PANEL_LIGHT, avatar_c, 54)
        pygame.draw.circle(surface, CYAN, avatar_c, 54, 2)
        initials = "".join(w[0] for w in self.info.get("username", "C").split()
                           if w)[:2].upper() or "C"
        theme.text(surface, initials, 38, WHITE, avatar_c)

        if not self.editing:
            theme.text(surface, self.info.get("username", "Cadet"), 26, WHITE,
                       (cx, 316))
            created = self.info.get("created_at", "")
            try:
                joined = datetime.datetime.fromisoformat(created).strftime(
                    "JOINED %d %b %Y").upper()
            except (ValueError, TypeError):
                joined = "LOCAL CADET"
            theme.text(surface, joined, 11, MUTED, (cx, 340))
            self.edit_button.draw(surface)
        else:
            theme.text(surface, "EDIT CALLSIGN", 10, MUTED, (cx, 306))
            box = pygame.Rect(cx - 150, 320, 300, 34)
            pygame.draw.rect(surface, PANEL_DARK, box, border_radius=8)
            pygame.draw.rect(surface, CYAN, box, width=1, border_radius=8)
            theme.text(surface, self.name_buffer, 17, WHITE,
                       (box.x + 12, box.centery), anchor="midleft")
            if int(pygame.time.get_ticks() / 500) % 2 == 0:
                text_w = theme.text_width(surface, self.name_buffer, 17)
                pygame.draw.line(surface, CYAN,
                                 (box.x + 14 + text_w, box.y + 8),
                                 (box.x + 14 + text_w, box.bottom - 8), 2)
            self.save_button.draw(surface)
            self.cancel_button.draw(surface)
            theme.text(surface, "ENTER saves  •  ESC cancels", 10, DIM,
                       (cx, 418))

        pygame.draw.line(surface, BORDER_SOFT, (82, 452), (442, 452), 1)
        theme.text(surface, "MISSIONS FLOWN", 10, MUTED, (82, 480),
                   anchor="midleft")
        theme.text(surface, f"{self.totals.get('games', 0)}", 26, CYAN,
                   (82, 508), anchor="midleft")
        theme.text(surface, "TOTAL PLAY TIME", 10, MUTED, (272, 480),
                   anchor="midleft")
        theme.text(surface, format_duration(self.totals.get("seconds", 0)), 26,
                   PURPLE, (272, 508), anchor="midleft")

        label = ("CLICK AGAIN TO CONFIRM" if self.confirm_reset > 0
                 else "RESET ALL PROGRESS")
        self.reset_button.label = label
        self.reset_button.draw(surface)
        theme.text(surface, "Deletes every saved session on this device.",
                   10, DIM, (cx, 638))

    def draw_stats(self, surface):
        values = [
            ("Avg accuracy", f"{self.totals.get('accuracy', 0):.0f}%", GREEN),
            ("Successful hits", f"{self.totals.get('hits', 0)}", CYAN),
            ("Mistakes", f"{self.totals.get('mistakes', 0)}", RED),
            ("Best score", f"{self.totals.get('best', 0):,}", GOLD),
        ]
        for i, (label, value, color) in enumerate(values):
            col, row = i % 2, i // 2
            rect = pygame.Rect(506 + col * 330, 160 + row * 92, 318, 80)
            Chip.draw(surface, rect, label, value, color)

    def draw_bests(self, surface):
        panel = pygame.Rect(506, 352, 648, 298)
        theme.panel(surface, panel, color=PANEL, border=BORDER_SOFT,
                    radius=18, width=1, shadow=False)
        theme.text(surface, "PERSONAL BESTS", 11, MUTED, (528, 374),
                   anchor="midleft")
        theme.text(surface, "PLAYS", 9, DIM, (1012, 374), anchor="midright")
        theme.text(surface, "BEST", 9, DIM, (1130, 374), anchor="midright")
        for i, cls in enumerate(GAME_CLASSES):
            y = 398 + i * 35
            row = self.per_game.get(cls.game_id)
            best = int(row["best"]) if row else 0
            plays = int(row["plays"]) if row else 0
            draw_game_icon(surface, cls.icon, (530, y), 10,
                           cls.accent if best else DIM)
            theme.text(surface, cls.title, 13, WHITE if best else (170, 180, 210),
                       (548, y), anchor="midleft")
            theme.text(surface, f"{plays}", 12, MUTED, (1012, y),
                       anchor="midright")
            theme.text(surface, f"{best:,}" if best else "—", 15,
                       cls.accent if best else DIM, (1130, y),
                       anchor="midright")
            pygame.draw.line(surface, BORDER_SOFT, (528, y + 17),
                             (1130, y + 17), 1)

        theme.text(surface, "Stored locally in data/lunar_arcade.db",
                   10, DIM, (528, 676), anchor="midleft")
