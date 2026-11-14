"""Lunar Alien Reaction Test — attention assessment against a personal baseline.

Assessment rules:
  * 30 rounds, six lunar craters
  * evil (purple) aliens are targets, friendly (green) aliens must be avoided
  * each alien stays visible ~1800 ms
  * responses are classified FAST / NORMAL / SLOW relative to the player's
    own baseline (±10% tolerance); before a baseline exists, responses are
    simply recorded
  * missed aliens and incorrect friendly hits are tracked

The evil/friendly reference images are loaded from assets/images when
present; otherwise a procedural sprite is drawn and a notice is shown.
"""

import math
import os
import random

import pygame

from config import (
    WIDTH, WHITE, MUTED, CYAN, GOLD, GREEN, RED, PURPLE,
    PANEL_DARK, BORDER_SOFT, DIM, IMAGE_DIR,
)
from core.neuro import CLASSIFY_TOLERANCE
from games.base_game import BaseGame, INTRO_PANEL
from ui import theme
from animations.easing import clamp, ease_out_back, ease_out_cubic

ROUNDS = 30
VISIBLE_MS = 1800
COLS, ROWS = 3, 2
CRATER_W, CRATER_H = 280, 180
GAP_X, GAP_Y = 40, 30
GRID_LEFT = (WIDTH - (COLS * CRATER_W + (COLS - 1) * GAP_X)) // 2
GRID_TOP = 168

PURPLE_ALIEN = (176, 96, 255)
GREEN_ALIEN = (86, 240, 160)
ALIEN_BOX = 144          # logical px, same for every screen and state
LEGEND_BOX = 30

_IMAGES = None
_SCALED = {}
_SHADOW = None


def alien_images():
    """Load evil/friendly reference images once (any common raster format)."""
    global _IMAGES
    if _IMAGES is not None:
        return _IMAGES
    found = {}
    names = {"target": "evil_alien", "friendly": "friendly_alien"}
    for kind, stem in names.items():
        for ext in (".png", ".jpg", ".jpeg", ".webp", ".png"):
            path = os.path.join(IMAGE_DIR, stem + ext)
            if not os.path.exists(path):
                continue
            try:
                found[kind] = pygame.image.load(path).convert_alpha()
                break
            except pygame.error:
                continue
    _IMAGES = found
    return found


def fit_image(image, box):
    """Scale preserving aspect ratio into a square box (cached)."""
    key = (id(image), box)
    cached = _SCALED.get(key)
    if cached is not None:
        return cached
    w, h = image.get_size()
    scale = box / max(1, max(w, h))
    scaled = pygame.transform.smoothscale(
        image, (max(1, int(w * scale)), max(1, int(h * scale))))
    _SCALED[key] = scaled
    return scaled


def _contact_shadow():
    """Small soft ellipse that seats the sprite on the crater rim."""
    global _SHADOW
    if _SHADOW is None:
        surf = pygame.Surface((72, 22), pygame.SRCALPHA)
        for i in range(5, 0, -1):
            alpha = int(16 * (6 - i))
            pygame.draw.ellipse(surf, (0, 0, 0, alpha),
                                (36 - i * 7, 11 - i * 2, i * 14, i * 4))
        _SHADOW = surf
    return _SHADOW


def draw_alien_image(surface, image, center_x, bottom, box=ALIEN_BOX,
                     shadow=True):
    """Draw a cleaned alien sprite with a shared baseline and no halo."""
    scaled = fit_image(image, box)
    w, h = scaled.get_size()
    if shadow and box >= 60:
        sh = _contact_shadow()
        surface.blit(sh, (center_x - sh.get_width() // 2,
                          bottom - sh.get_height() // 2 - 2))
    rect = scaled.get_rect(midbottom=(int(center_x), int(bottom)))
    surface.blit(scaled, rect)
    return rect


class LunarAlienReaction(BaseGame):
    game_id = "lunar_alien_reaction"
    game_number = 1
    title = "Lunar Alien Reaction"
    subtitle = "Target recognition assessment"
    description = ("Evil aliens surface from lunar craters: tap them the "
                   "instant they appear. Friendly aliens must be left alone. "
                   "Thirty rounds measure how quickly and accurately you "
                   "recognise the right target — compared with your own "
                   "personal baseline, never a fixed norm.")
    instructions = [
        "TAP evil aliens as fast as you can.",
        "DO NOT tap friendly aliens.",
        "Each alien stays up for about 1.8 seconds.",
        "Responses are FAST / NORMAL / SLOW versus your personal baseline "
        "(±10%).",
        "The first three valid sessions establish your baseline; alerts "
        "only start after calibration.",
    ]
    accent = PURPLE
    icon = "alien"
    summary_notes = ("30 rounds • 1,800 ms window • classification against "
                     "your personal baseline")
    supports_difficulty = False

    def reset(self):
        super().reset()
        self.round_index = 0
        self.phase = "gap"
        self.phase_t = 0.0
        self.gap_duration = 0.7
        self.alien = None
        self.last_crater = -1
        self.reaction_times = []
        self.fast_count = 0
        self.normal_count = 0
        self.slow_count = 0
        self.missed = 0
        self.incorrect = 0
        self.last_result = None
        self.feedback = None
        self.feedback_t = 0.0
        self.rings = []
        self.baseline_value = None
        self.images = alien_images()

    @property
    def has_images(self):
        return "target" in self.images and "friendly" in self.images

    # ------------------------------------------------------------ logic
    def on_start(self):
        self.phase = "gap"
        self.gap_duration = 0.9
        self.phase_t = 0.0
        self.images = alien_images()
        baseline = None
        neuro = getattr(self.app, "neuro", None)
        if neuro is not None:
            baseline = neuro.reaction_baseline("lunar_alien_reaction")
        self.baseline_value = (baseline["baseline_value"]
                               if baseline else None)

    def classify(self, rt_ms):
        if not self.baseline_value:
            return "BASELINE", CYAN
        neuro = getattr(self.app, "neuro", None)
        if neuro is not None:
            label = neuro.classify_reaction(rt_ms, self.baseline_value)
        else:
            ratio = rt_ms / self.baseline_value
            label = ("fast" if ratio < 1 - CLASSIFY_TOLERANCE else
                     "slow" if ratio > 1 + CLASSIFY_TOLERANCE else "normal")
        return {"fast": ("FAST", GREEN), "normal": ("NORMAL", CYAN),
                "slow": ("SLOW", GOLD)}[label]

    def begin_round(self):
        if self.round_index >= ROUNDS:
            self.end_game()
            return
        choices = [i for i in range(COLS * ROWS) if i != self.last_crater]
        crater = random.choice(choices)
        self.last_crater = crater
        kind = "target" if random.random() < 0.72 else "friendly"
        self.alien = {"crater": crater, "kind": kind, "shown_at": self.time}
        self.round_index += 1
        self.phase = "show"
        self.phase_t = 0.0
        self.app.audio.play("pop", 0.4)

    def crater_rect(self, index):
        row, col = divmod(index, COLS)
        return pygame.Rect(
            GRID_LEFT + col * (CRATER_W + GAP_X),
            GRID_TOP + row * (CRATER_H + GAP_Y),
            CRATER_W, CRATER_H,
        )

    def update_game(self, dt):
        self.phase_t += dt
        for ring in self.rings:
            ring["t"] += dt
        self.rings = [r for r in self.rings if r["t"] < 0.6]
        if self.feedback_t > 0:
            self.feedback_t = max(0.0, self.feedback_t - dt)

        if self.phase == "gap":
            if self.phase_t >= self.gap_duration:
                self.begin_round()
        elif self.phase == "show":
            elapsed_ms = (self.time - self.alien["shown_at"]) * 1000
            if elapsed_ms >= VISIBLE_MS:
                if self.alien["kind"] == "target":
                    self.missed += 1
                    self.mistakes += 1
                    self.set_feedback("MISSED", RED)
                    self.app.audio.play("miss")
                    rect = self.crater_rect(self.alien["crater"])
                    self.add_floater("MISSED", (rect.centerx, rect.y - 30),
                                     RED, 22)
                self.phase = "feedback"
                self.phase_t = 0.0
                self.alien = None
        elif self.phase == "feedback":
            if self.phase_t >= 0.55:
                if self.round_index >= ROUNDS:
                    self.end_game()
                else:
                    self.phase = "gap"
                    self.phase_t = 0.0
                    self.gap_duration = 0.55

        avg = (sum(self.reaction_times) / len(self.reaction_times)
               if self.reaction_times else 0)
        self.set_hud([
            ("Round", f"{self.round_index}/{ROUNDS}", WHITE),
            ("Hits", f"{self.hits}", GREEN),
            ("Missed", f"{self.missed}", RED),
            ("Friendly hits", f"{self.incorrect}", RED),
            ("Avg RT", f"{avg:.0f} ms" if avg else "—", CYAN),
        ], progress=self.round_index / ROUNDS, progress_color=PURPLE)

    def set_feedback(self, text, color):
        self.last_result = (text, color)
        self.feedback = (text, color)
        self.feedback_t = 0.55

    def on_play_click(self, p):
        if self.phase != "show" or self.alien is None:
            return
        rect = self.crater_rect(self.alien["crater"])
        target_zone = rect.inflate(10, 90)
        if not target_zone.collidepoint(p.pos):
            for i in range(COLS * ROWS):
                if i != self.alien["crater"] and self.crater_rect(i).collidepoint(p.pos):
                    other = self.crater_rect(i)
                    self.particles.burst(other.centerx, other.centery, DIM,
                                         count=5, speed=90, life=(0.2, 0.35))
                    break
            return
        elapsed_ms = (self.time - self.alien["shown_at"]) * 1000
        if self.alien["kind"] == "target":
            rt = max(1.0, elapsed_ms)
            self.reaction_times.append(rt)
            self.hits += 1
            label, color = self.classify(rt)
            if label == "FAST":
                self.fast_count += 1
            elif label == "NORMAL":
                self.normal_count += 1
            elif label == "SLOW":
                self.slow_count += 1
            gained = 100 + (50 if label in ("FAST", "NORMAL") else 0)
            gained += int(max(0.0, VISIBLE_MS - rt) / VISIBLE_MS * 50)
            self.score += gained
            self.set_feedback(f"{label}  {rt:.0f} ms", color)
            self.add_floater(f"+{gained}  {label} {rt:.0f} ms",
                             (rect.centerx, rect.y - 34), color, 22)
            self.app.audio.play("hit" if label != "SLOW" else "click")
            self.flash(color, 0.35)
        else:
            self.incorrect += 1
            self.mistakes += 1
            self.score = max(0, self.score - 50)
            self.set_feedback("FRIENDLY!", RED)
            self.add_floater("-50  FRIENDLY", (rect.centerx, rect.y - 34),
                             RED, 22)
            self.app.audio.play("error")
            self.flash(RED, 0.6)
        self.rings.append({"x": rect.centerx, "y": rect.y + 40,
                           "color": GREEN if self.feedback[1] == GREEN else RED,
                           "t": 0.0})
        self.particles.burst(rect.centerx, rect.y + 10, self.feedback[1],
                             count=16, speed=260, life=(0.3, 0.6))
        self.phase = "feedback"
        self.phase_t = 0.0
        self.alien = None

    def end_game(self):
        if self.state != "playing":
            return
        self.alien = None
        avg = (sum(self.reaction_times) / len(self.reaction_times)
               if self.reaction_times else 0.0)
        accuracy = self.hits / ROUNDS * 100
        self.app.audio.play("gameover")
        self.finish({
            "score": self.score,
            "accuracy": accuracy,
            "mistakes": self.missed + self.incorrect,
            "hits": self.hits,
            "avg_reaction_ms": avg if self.reaction_times else None,
            "duration": self.time,
            "stats": [
                ("Successful hits", f"{self.hits} / {ROUNDS}"),
                ("Missed aliens", f"{self.missed}"),
                ("Friendly-alien hits", f"{self.incorrect}"),
                ("Median reaction",
                 f"{sorted(self.reaction_times)[len(self.reaction_times) // 2]:.0f} ms"
                 if self.reaction_times else "—"),
                ("Fast / Normal / Slow",
                 f"{self.fast_count} / {self.normal_count} / {self.slow_count}"),
                ("Baseline used",
                 f"{self.baseline_value:.0f} ms" if self.baseline_value else
                 "None (calibration)"),
            ],
            "extra": {
                "fast_count": self.fast_count,
                "normal_count": self.normal_count,
                "slow_count": self.slow_count,
                "missed": self.missed,
                "incorrect_friendly": self.incorrect,
                "reaction_times": [round(t, 1) for t in self.reaction_times],
                "baseline_at_time": round(self.baseline_value, 1)
                if self.baseline_value else None,
                "classify_tolerance": CLASSIFY_TOLERANCE,
                "difficulty": "normal",
            },
        })

    # ------------------------------------------------------------- draw
    def draw_world(self, surface):
        field = pygame.Rect(110, 108, WIDTH - 220, 570)
        theme.alpha_rect(surface, field, PANEL_DARK, 150, radius=26)
        pygame.draw.rect(surface, BORDER_SOFT, field, width=1, border_radius=26)

        for index in range(COLS * ROWS):
            rect = self.crater_rect(index)
            pygame.draw.ellipse(surface, (30, 49, 105), rect.inflate(14, 12))
            pygame.draw.ellipse(surface, (72, 88, 152), rect)
            inner = rect.inflate(-28, -24)
            pygame.draw.ellipse(surface, (7, 9, 26), inner)
            pygame.draw.ellipse(surface, (24, 30, 62), inner.inflate(-20, -16))
            pygame.draw.arc(surface, (55, 225, 255, 140), rect.inflate(-16, -12),
                            math.pi * 0.05, math.pi * 0.95, 2)
            theme.text(surface, f"{index + 1}", 12, (60, 70, 110),
                       (rect.x + 26, rect.y + 20))

        if self.alien is not None:
            self.draw_alien(surface, self.alien)

        for ring in self.rings:
            p = ring["t"] / 0.6
            radius = int(30 + 90 * ease_out_cubic(p))
            alpha = int(200 * (1 - p))
            s = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*ring["color"], alpha),
                               (radius + 2, radius + 2), radius, 3)
            surface.blit(s, (ring["x"] - radius - 2, ring["y"] - radius - 2))

        if self.feedback and self.feedback_t > 0:
            alpha = clamp(self.feedback_t / 0.55)
            theme.text_alpha(surface, self.feedback[0], 30, self.feedback[1],
                             (WIDTH // 2, 640), alpha=255 * alpha)

        if self.state not in ("playing", "countdown", "paused"):
            return
        # Legend uses the same artwork as the craters, at a smaller size.
        evil = self.images.get("target")
        friendly = self.images.get("friendly")
        if evil is not None and friendly is not None:
            draw_alien_image(surface, evil, WIDTH // 2 - 256, 730, LEGEND_BOX)
            theme.text(surface, "TAP EVIL", 13, WHITE, (WIDTH // 2 - 236, 712),
                       anchor="midleft")
            draw_alien_image(surface, friendly, WIDTH // 2 - 48, 730,
                             LEGEND_BOX)
            theme.text(surface, "AVOID FRIENDLY", 13, WHITE,
                       (WIDTH // 2 - 28, 712), anchor="midleft")
        else:
            pygame.draw.circle(surface, PURPLE_ALIEN,
                               (WIDTH // 2 - 240, 712), 9)
            theme.text(surface, "TAP EVIL", 13, WHITE,
                       (WIDTH // 2 - 224, 712), anchor="midleft")
            pygame.draw.circle(surface, GREEN_ALIEN,
                               (WIDTH // 2 - 40, 712), 9)
            theme.text(surface, "AVOID FRIENDLY", 13, WHITE,
                       (WIDTH // 2 - 24, 712), anchor="midleft")
        baseline = (f"BASELINE {self.baseline_value:.0f} ms"
                    if self.baseline_value else "BASELINE: CALIBRATING")
        theme.text(surface, baseline, 12, DIM,
                   (WIDTH // 2 + 200, 712), anchor="midleft")

    def draw_alien(self, surface, alien):
        rect = self.crater_rect(alien["crater"])
        elapsed = self.time - alien["shown_at"]
        appear = clamp(elapsed / 0.16)
        remaining = VISIBLE_MS / 1000 - elapsed
        leave = clamp(remaining / 0.16) if remaining < 0.16 else 1.0
        rise = ease_out_back(appear) * leave
        cx = rect.centerx
        cy = int(rect.y + 94 - 80 * rise)
        if rise <= 0.02:
            return
        is_target = alien["kind"] == "target"
        image = self.images.get("target" if is_target else "friendly")
        if image is not None:
            # Shared mid-bottom anchor keeps both characters aligned as they
            # rise from the crater and removes the old translucent halo.
            draw_alien_image(surface, image, cx, cy + int(ALIEN_BOX * 0.68),
                             ALIEN_BOX)
            return

        # Procedural fallback sprite.
        color = PURPLE_ALIEN if is_target else GREEN_ALIEN
        r = 46
        pygame.draw.line(surface, color, (cx - 20, cy - r + 8),
                         (cx - 32, cy - r - 20), 3)
        pygame.draw.line(surface, color, (cx + 20, cy - r + 8),
                         (cx + 32, cy - r - 20), 3)
        pygame.draw.circle(surface, color, (cx - 33, cy - r - 21), 6)
        pygame.draw.circle(surface, color, (cx + 33, cy - r - 21), 6)

        pygame.draw.circle(surface, color, (cx, cy), r)
        pygame.draw.circle(surface, tuple(max(0, c - 70) for c in color),
                           (cx, cy), r, 3)
        eye = (10, 15, 35)
        if is_target:
            pygame.draw.polygon(surface, eye, [
                (cx - 30, cy - 16), (cx - 8, cy - 6), (cx - 30, cy + 4)])
            pygame.draw.polygon(surface, eye, [
                (cx + 30, cy - 16), (cx + 8, cy - 6), (cx + 30, cy + 4)])
            pygame.draw.circle(surface, RED, (cx - 20, cy - 6), 3)
            pygame.draw.circle(surface, RED, (cx + 20, cy - 6), 3)
            pygame.draw.line(surface, eye, (cx - 13, cy + 20),
                             (cx + 13, cy + 20), 3)
            for tx in (-7, 0, 7):
                pygame.draw.line(surface, eye, (cx + tx, cy + 20),
                                 (cx + tx, cy + 26), 2)
        else:
            pygame.draw.circle(surface, eye, (cx - 17, cy - 6), 11)
            pygame.draw.circle(surface, eye, (cx + 17, cy - 6), 11)
            pygame.draw.circle(surface, WHITE, (cx - 13, cy - 9), 4)
            pygame.draw.circle(surface, WHITE, (cx + 21, cy - 9), 4)
            pygame.draw.arc(surface, eye, (cx - 15, cy + 8, 30, 20), 0, math.pi, 3)

    def draw_intro(self, surface):
        super().draw_intro(surface)
        if not self.has_images:
            theme.text(surface, "Reference artwork missing — add "
                                "evil_alien.png and friendly_alien.png to "
                                "assets/images.",
                       11, GOLD, (INTRO_PANEL.centerx, INTRO_PANEL.bottom - 196),
                       bold=False)
            return
        # A deliberate, aligned recognition key above the difficulty row.
        y = INTRO_PANEL.bottom - 224
        evil = self.images["target"]
        friendly = self.images["friendly"]
        draw_alien_image(surface, evil, INTRO_PANEL.x + 116, y + 44, 40)
        theme.text(surface, "EVIL — TAP", 13, WHITE,
                   (INTRO_PANEL.x + 154, y + 28), anchor="midleft")
        theme.text(surface, "Target. Tap the instant it appears.", 11, MUTED,
                   (INTRO_PANEL.x + 154, y + 46), anchor="midleft", bold=False)
        draw_alien_image(surface, friendly, INTRO_PANEL.x + 486, y + 44, 40)
        theme.text(surface, "FRIENDLY — AVOID", 13, WHITE,
                   (INTRO_PANEL.x + 524, y + 28), anchor="midleft")
        theme.text(surface, "Distractor. Leave it alone.", 11, MUTED,
                   (INTRO_PANEL.x + 524, y + 46), anchor="midleft", bold=False)
