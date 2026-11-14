"""Number Hunt — find numbers in ascending order amid distractors."""

import math
import random

import pygame

from config import (
    WIDTH, HEIGHT, WHITE, MUTED, CYAN, GOLD, GREEN, RED, PURPLE, BLUE,
    PANEL_DARK, PANEL_LIGHT, BORDER_SOFT, DIM,
)
from games.base_game import BaseGame
from ui import theme
from animations.easing import clamp, ease_out_back, ease_out_cubic

CONFIG = {
    0: {"numbers": 10, "distractors": 12, "time": 60.0},
    1: {"numbers": 15, "distractors": 25, "time": 55.0},
    2: {"numbers": 20, "distractors": 40, "time": 50.0},
}
FIELD = pygame.Rect(50, 104, 1100, 592)


class Token:
    __slots__ = ("value", "x", "y", "r", "sequence", "state", "t", "shake",
                 "seed")

    def __init__(self, value, x, y, r, sequence, seed):
        self.value = value
        self.x, self.y, self.r = x, y, r
        self.sequence = sequence
        self.state = "idle"
        self.t = 0.0
        self.shake = 0.0
        self.seed = seed


class NumberHunt(BaseGame):
    game_id = "number_hunt"
    game_number = 6
    title = "Number Hunt"
    subtitle = "Visual search & attention"
    description = ("The lunar field is littered with numbers. Find them in "
                   "ascending order — 1, 2, 3 and so on — while ignoring the "
                   "distractor tokens scattered between them.")
    instructions = [
        "Find and tap the numbers in ascending order.",
        "Distractor numbers are mixed in and cost points if tapped.",
        "The timer keeps running until you finish or run out of time.",
        "EASY and NORMAL highlight the next number; HARD mode removes all "
        "hints, so the search is entirely on you.",
    ]
    accent = BLUE
    icon = "numbers"
    supports_difficulty = True

    @property
    def show_hints(self):
        return self.difficulty_level < 2

    def reset(self):
        super().reset()
        self.apply_difficulty()

    def apply_difficulty(self):
        self.cfg = CONFIG[self.difficulty_level]
        self.tokens = []
        self.next_number = 1
        self.found = 0
        self.wrong_clicks = 0
        self.total_clicks = 0
        self.remaining = self.cfg["time"]
        self.completion_time = 0.0
        self.completed = False
        self.build_field()

    def build_field(self):
        rng = random.Random()
        n = self.cfg["numbers"]
        entries = [(i, True) for i in range(1, n + 1)]
        used = set(range(1, n + 1))
        while len(entries) < n + self.cfg["distractors"]:
            value = rng.randint(n + 1, 99)
            if value in used:
                continue
            used.add(value)
            entries.append((value, False))
        rng.shuffle(entries)
        placed = []
        attempts = 0
        while entries and attempts < 8000:
            attempts += 1
            value, seq = entries[-1]
            r = 30 if len(entries) > 20 else 33
            x = rng.randint(FIELD.x + r + 16, FIELD.right - r - 16)
            y = rng.randint(FIELD.y + r + 16, FIELD.bottom - r - 16)
            if all((x - t.x) ** 2 + (y - t.y) ** 2 >= (r + t.r + 12) ** 2
                   for t in placed):
                placed.append(Token(value, x, y, r, seq, rng.random()))
                entries.pop()
        self.tokens = placed
        self.next_number = 1

    def on_start(self):
        # Apply the difficulty selected on the intro screen (the field was
        # generated at construction time).
        self.apply_difficulty()
        self.score = 0
        self.app.audio.play("go")

    def update_game(self, dt):
        self.remaining = max(0.0, self.cfg["time"] - self.time)
        for token in self.tokens:
            token.t += dt
            token.shake = max(0.0, token.shake - dt * 3)
        hud = []
        if self.show_hints:
            hud.append(("Find",
                        f"{self.next_number if not self.completed else '✓'}",
                        GOLD))
        hud += [
            ("Found", f"{self.found}/{self.cfg['numbers']}", GREEN),
            ("Mistakes", f"{self.wrong_clicks}", RED),
            ("Time", f"{math.ceil(self.remaining)}s",
             RED if self.remaining <= 8 else WHITE),
            ("Score", f"{self.score}", CYAN),
        ]
        self.set_hud(hud, progress=self.remaining / self.cfg["time"],
            progress_color=RED if self.remaining <= 8 else BLUE)

        if self.remaining <= 0 and not self.completed:
            self.end_game(False)

    def on_play_click(self, p):
        if self.completed:
            return
        for token in self.tokens:
            if token.state != "idle":
                continue
            dx, dy = p.pos[0] - token.x, p.pos[1] - token.y
            if dx * dx + dy * dy <= (token.r + 8) ** 2:
                self.total_clicks += 1
                if token.sequence and token.value == self.next_number:
                    self.found_number(token)
                else:
                    self.wrong_number(token)
                return

    def found_number(self, token):
        token.state = "found"
        token.t = 0.0
        self.found += 1
        self.score += 100
        self.app.audio.play("hit", 0.5)
        self.particles.burst(token.x, token.y, CYAN, count=14, speed=230,
                             life=(0.3, 0.6))
        self.add_floater("+100", (token.x, token.y - token.r - 8), CYAN, 20)
        self.next_number += 1
        if self.next_number > self.cfg["numbers"]:
            self.completed = True
            self.completion_time = self.time
            self.app.audio.play("success")
            self.end_game(True)

    def wrong_number(self, token):
        token.shake = 0.5
        self.wrong_clicks += 1
        self.mistakes += 1
        self.score = max(0, self.score - 25)
        self.app.audio.play("error", 0.5)
        self.add_floater("-25", (token.x, token.y - token.r - 8), RED, 18,
                         life=0.6)
        self.flash(RED, 0.3)

    def end_game(self, completed):
        taps = self.total_clicks
        accuracy = (self.found / taps * 100) if taps else 0.0
        bonus = int(max(0.0, self.remaining) * 10) if completed else 0
        if completed:
            self.score += bonus
        self.finish({
            "score": self.score,
            "accuracy": accuracy,
            "mistakes": self.wrong_clicks,
            "hits": self.found,
            "avg_reaction_ms": None,
            "duration": min(self.time, self.cfg["time"]),
            "stats": [
                ("Numbers found", f"{self.found}/{self.cfg['numbers']}"),
                ("Completion time",
                 f"{self.completion_time:.1f}s" if completed else "—"),
                ("Mistakes", f"{self.wrong_clicks}"),
                ("Tap accuracy", f"{accuracy:.1f}%"),
                ("Time bonus", f"{bonus} pts" if completed else "—"),
                ("Status", "CLEARED" if completed else "TIME OUT"),
            ],
            "extra": {"completed": completed,
                      "completion_time": round(self.completion_time, 2),
                      "wrong_clicks": self.wrong_clicks,
                      "targets": self.cfg["numbers"],
                      "distractors": self.cfg["distractors"],
                      "show_hints": self.show_hints,
                      "difficulty": self.difficulty_name.lower()},
        })

    # ------------------------------------------------------------- draw
    def draw_world(self, surface):
        field = FIELD
        theme.alpha_rect(surface, field, PANEL_DARK, 150, radius=26)
        pygame.draw.rect(surface, BORDER_SOFT, field, width=1, border_radius=26)

        for token in self.tokens:
            self.draw_token(surface, token)

        # Progress strip.
        n = self.cfg["numbers"]
        found = self.found
        x0 = WIDTH // 2 - min(n, 20) * 11
        for i in range(n):
            color = GREEN if i < found else (52, 62, 104)
            pygame.draw.circle(surface, color, (x0 + i * 22, 150), 5)

        theme.text(surface, "TAP THE NUMBERS IN ASCENDING ORDER  •  IGNORE DISTRACTORS",
                   12, DIM, (WIDTH // 2, 712))

    def draw_token(self, surface, token):
        if token.state == "found":
            p = clamp(token.t / 0.4)
            if p >= 1:
                return
            radius = int(token.r * (1 + p * 0.8))
            alpha = int(220 * (1 - p))
            s = pygame.Surface((radius * 2 + 4, radius * 2 + 4),
                               pygame.SRCALPHA)
            pygame.draw.circle(s, (*CYAN, alpha), (radius + 2, radius + 2),
                               radius, 3)
            surface.blit(s, (token.x - radius - 2, token.y - radius - 2))
            return
        shake = math.sin(token.shake * 50) * 5 * token.shake
        cx, cy = token.x + shake, token.y
        appear = clamp(token.t / 0.25)
        r = max(2, int(token.r * ease_out_back(appear)))
        # HARD mode never highlights the next number.
        next_up = (self.show_hints and token.sequence
                   and token.value == self.next_number)
        if next_up:
            pulse = 0.5 + 0.5 * math.sin(self.time * 5)
            theme.glow(surface, (cx, cy), r + 4, CYAN, layers=3,
                       strength=0.05 + 0.05 * pulse)
        pygame.draw.circle(surface, (25, 31, 66), (cx, cy), r)
        pygame.draw.circle(surface, RED if token.shake > 0.2 else
                           (CYAN if next_up else (74, 90, 150)),
                           (cx, cy), r, 2)
        theme.text(surface, str(token.value), 24,
                   WHITE if next_up else (176, 186, 214), (cx, cy))
