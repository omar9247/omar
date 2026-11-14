"""Sequence Memory Test — repeat the flashing pattern."""

import math
import random

import pygame

from config import (
    WIDTH, HEIGHT, WHITE, MUTED, CYAN, GOLD, GREEN, RED, PURPLE, BLUE,
    PANEL, PANEL_DARK, PANEL_LIGHT, BORDER, BORDER_SOFT, DIM,
)
from games.base_game import BaseGame
from ui import theme
from animations.easing import clamp, ease_out_cubic

TILE_W, TILE_H = 250, 170
GAP = 24
GRID_LEFT = (WIDTH - (3 * TILE_W + 2 * GAP)) // 2
GRID_TOP = 196

TILES = [
    ("CYAN", (55, 225, 255), "CIRCLE"),
    ("VIOLET", (170, 110, 255), "SQUARE"),
    ("AMBER", (255, 200, 80), "TRIANGLE"),
    ("MINT", (75, 245, 170), "STAR"),
    ("CORAL", (255, 100, 125), "DIAMOND"),
    ("AZURE", (95, 150, 255), "HEXAGON"),
]

FLASH_DURATION = {0: 0.65, 1: 0.55, 2: 0.45}
START_LENGTH = {0: 3, 1: 3, 2: 4}
MAX_LENGTH = 16


def tile_rect(index):
    row, col = divmod(index, 3)
    return pygame.Rect(GRID_LEFT + col * (TILE_W + GAP),
                       GRID_TOP + row * (TILE_H + GAP), TILE_W, TILE_H)


def draw_symbol(surface, kind, center, size, color, width=0):
    cx, cy = center
    if kind == "CIRCLE":
        pygame.draw.circle(surface, color, (int(cx), int(cy)), int(size), width)
    elif kind == "SQUARE":
        pygame.draw.rect(surface, color,
                         (cx - size * 0.82, cy - size * 0.82,
                          size * 1.64, size * 1.64), width)
    elif kind == "TRIANGLE":
        pygame.draw.polygon(surface, color, [
            (cx, cy - size), (cx + size * 0.95, cy + size * 0.75),
            (cx - size * 0.95, cy + size * 0.75)], width)
    elif kind == "DIAMOND":
        pygame.draw.polygon(surface, color, [
            (cx, cy - size), (cx + size, cy), (cx, cy + size),
            (cx - size, cy)], width)
    elif kind == "HEXAGON":
        pts = [(cx + math.cos(math.radians(-90 + i * 60)) * size,
                cy + math.sin(math.radians(-90 + i * 60)) * size)
               for i in range(6)]
        pygame.draw.polygon(surface, color, pts, width)
    else:
        pts = []
        for i in range(10):
            r = size if i % 2 == 0 else size * 0.45
            a = math.radians(-90 + i * 36)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        pygame.draw.polygon(surface, color, pts, width)


class MemoryTest(BaseGame):
    game_id = "memory_test"
    game_number = 3
    title = "Memory Test"
    subtitle = "Sequence recall assessment"
    description = ("Watch the tiles light up in order, then repeat the exact "
                   "sequence. Every cleared round adds one more step. Three "
                   "lives, and a shrinking time window keep the pressure on.")
    instructions = [
        "Watch the flashing sequence carefully.",
        "Repeat it by tapping the tiles in the same order.",
        "Each successful round adds one step and earns points.",
        "A wrong tap or running out of time costs a life.",
        "Three lives — how long a sequence can you hold?",
    ]
    accent = PURPLE
    icon = "memory"
    supports_difficulty = True

    def reset(self):
        super().reset()
        self.length = START_LENGTH[self.difficulty_level]
        self.lives = 3
        self.sequence = []
        self.phase = "show"
        self.phase_t = 0.0
        self.show_index = 0
        self.show_timer = 0.0
        self.lit = None
        self.input_index = 0
        self.input_timer = 0.0
        self.input_limit = 0.0
        self.max_length = 0
        self.rounds_cleared = 0
        self.correct_clicks = 0
        self.total_clicks = 0
        self.response_times = []
        self.last_step_at = 0.0
        self.press_light = {}
        self.feedback = None
        self.feedback_t = 0.0
        self.flash_len = FLASH_DURATION[self.difficulty_level]
        self.last_lit = -1

    # ------------------------------------------------------------ rounds
    def on_start(self):
        # Difficulty is chosen on the intro screen, after reset() ran.
        self.length = START_LENGTH[self.difficulty_level]
        self.flash_len = FLASH_DURATION[self.difficulty_level]
        self.lives = 3
        self.max_length = 0
        self.rounds_cleared = 0
        self.start_round()

    def start_round(self):
        self.sequence = [random.randrange(6) for _ in range(self.length)]
        self.phase = "show"
        self.phase_t = 0.0
        self.show_index = 0
        self.lit = None
        self.show_timer = 0.8
        self.last_lit = -1
        self.input_index = 0

    def update_game(self, dt):
        for k in list(self.press_light):
            self.press_light[k] = max(0.0, self.press_light[k] - dt * 2.5)
        if self.feedback_t > 0:
            self.feedback_t = max(0.0, self.feedback_t - dt)

        if self.phase == "show":
            self.show_timer -= dt
            if self.lit is None and self.show_timer <= 0:
                self.lit = self.sequence[self.show_index]
                self.last_lit = self.lit
                self.show_timer = self.flash_len
                self.app.audio.play("tick", 0.5)
            elif self.lit is not None and self.show_timer <= 0:
                self.lit = None
                self.show_index += 1
                if self.show_index >= len(self.sequence):
                    self.phase = "input"
                    self.input_index = 0
                    self.input_limit = len(self.sequence) * 1.1 + 2.0
                    self.input_timer = self.input_limit
                    self.last_step_at = self.time
                else:
                    self.show_timer = 0.22
        elif self.phase == "input":
            self.input_timer -= dt
            if self.input_timer <= 0:
                self.fail_round("TOO SLOW")
        elif self.phase == "feedback":
            self.phase_t += dt
            if self.phase_t >= 1.0:
                if self.lives <= 0 or self.length > MAX_LENGTH:
                    self.end_game()
                else:
                    self.start_round()

        self.set_hud([
            ("Level", f"{self.length}", PURPLE),
            ("Lives", "● " * self.lives + "○ " * (3 - self.lives), RED),
            ("Score", f"{self.score}", GOLD),
            ("Best", f"{self.max_length}", GREEN),
            ("Time", f"{self.input_timer:.1f}s" if self.phase == "input"
             else "—", WHITE),
        ], progress=(self.input_timer / self.input_limit
                     if self.phase == "input" else 1.0),
            progress_color=RED if self.phase == "input"
            and self.input_timer < 3 else PURPLE)

    def on_play_click(self, p):
        if self.phase != "input":
            return
        index = self.tile_at(p.pos)
        if index is None:
            return
        self.total_clicks += 1
        self.press_light[index] = 1.0
        expected = self.sequence[self.input_index]
        if index == expected:
            self.correct_clicks += 1
            self.response_times.append((self.time - self.last_step_at) * 1000)
            self.last_step_at = self.time
            self.app.audio.play("tick", 0.7)
            self.input_index += 1
            if self.input_index >= len(self.sequence):
                self.clear_round()
        else:
            self.fail_round("WRONG TILE")

    def tile_at(self, pos):
        for i in range(6):
            if tile_rect(i).collidepoint(pos):
                return i
        return None

    def clear_round(self):
        self.max_length = max(self.max_length, self.length)
        self.rounds_cleared += 1
        bonus = int(max(0.0, self.input_limit - (self.input_limit - self.input_timer)) * 25)
        gained = self.length * 100 + bonus
        self.score += gained
        self.add_floater(f"+{gained}", (WIDTH // 2, 150), GOLD, 26)
        self.app.audio.play("success")
        self.particles.confetti(WIDTH // 2, 170, [PURPLE, CYAN, GOLD], 24)
        self.feedback = ("SEQUENCE CLEARED", GREEN)
        self.feedback_t = 1.0
        self.length += 1
        self.phase = "feedback"
        self.phase_t = 0.0

    def fail_round(self, reason):
        self.lives -= 1
        self.mistakes += 1
        self.app.audio.play("error")
        self.feedback = (reason, RED)
        self.feedback_t = 1.0
        self.flash(RED, 0.5)
        self.phase = "feedback"
        self.phase_t = 0.0

    def end_game(self):
        self.phase = "done"
        avg_rt = (sum(self.response_times) / len(self.response_times)
                  if self.response_times else 0.0)
        accuracy = (self.correct_clicks / self.total_clicks * 100
                    if self.total_clicks else 0.0)
        self.finish({
            "score": self.score,
            "accuracy": accuracy,
            "mistakes": self.mistakes,
            "hits": self.rounds_cleared,
            "avg_reaction_ms": avg_rt if self.response_times else None,
            "duration": self.time,
            "stats": [
                ("Longest sequence", f"{self.max_length} steps"),
                ("Rounds cleared", f"{self.rounds_cleared}"),
                ("Mistakes", f"{self.mistakes}"),
                ("Tap accuracy", f"{accuracy:.1f}%"),
                ("Average tap time", f"{avg_rt:.0f} ms" if avg_rt else "—"),
                ("Level reached", f"{self.length}"),
            ],
            "extra": {"longest_sequence": self.max_length,
                      "rounds_cleared": self.rounds_cleared,
                      "lives_left": max(0, self.lives),
                      "response_times_ms": [round(t) for t in self.response_times],
                      "difficulty": self.difficulty_name.lower()},
        })

    # ------------------------------------------------------------- draw
    def draw_world(self, surface):
        for i, (name, color, symbol) in enumerate(TILES):
            rect = tile_rect(i)
            lit = (self.lit == i or self.press_light.get(i, 0) > 0.05)
            press = self.press_light.get(i, 0)
            if lit:
                theme.glow(surface, rect.center, rect.w // 2, color,
                           layers=5, strength=0.16)
                fill = color
                border = WHITE
                symbol_color = (10, 15, 35)
            else:
                fill = (24, 29, 62)
                border = tuple(int(c * 0.55) for c in color)
                symbol_color = tuple(int(c * 0.55) for c in color)
            if press > 0:
                fill = tuple(min(255, int(c + press * 60)) for c in fill)
            pygame.draw.rect(surface, fill, rect, border_radius=18)
            pygame.draw.rect(surface, border, rect, width=3, border_radius=18)
            draw_symbol(surface, symbol, rect.center, 46, symbol_color, 4)

        # Status banner.
        banner = pygame.Rect(WIDTH // 2 - 260, 120, 520, 46)
        if self.phase == "show":
            label, color = "WATCH THE SEQUENCE", PURPLE
        elif self.phase == "input":
            label, color = "YOUR TURN — REPEAT IT", CYAN
        else:
            label, color = (self.feedback[0] if self.feedback else ""), \
                (self.feedback[1] if self.feedback else WHITE)
        theme.alpha_rect(surface, banner, PANEL, 230, radius=12)
        pygame.draw.rect(surface, BORDER_SOFT, banner, width=1, border_radius=12)
        if self.phase in ("show", "input"):
            pulse = 0.75 + 0.25 * math.sin(self.time * 4)
            theme.glow(surface, (banner.centerx, banner.centery), 120, color,
                       layers=3, strength=0.05 * pulse)
        theme.text(surface, label, 16, color, banner.center)

        # Sequence progress dots during input.
        if self.phase == "input" and self.sequence:
            n = len(self.sequence)
            total_w = n * 18
            x0 = WIDTH // 2 - total_w // 2
            for i in range(n):
                done = i < self.input_index
                color = GREEN if done else (60, 70, 110)
                pygame.draw.circle(surface, color,
                                   (x0 + i * 18 + 9, 178), 5)

        # Lives under the grid.
        for i in range(3):
            color = RED if i < self.lives else (60, 70, 110)
            pygame.draw.circle(surface, color, (WIDTH // 2 - 30 + i * 30, 610), 7)

        theme.text(surface, "REPEAT THE FLASHING ORDER  •  THREE LIVES",
                   12, DIM, (WIDTH // 2, 712))
