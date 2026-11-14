"""Simple Reaction Test — tap as soon as the signal appears."""

import math
import random

import pygame

from config import (
    WIDTH, HEIGHT, WHITE, MUTED, CYAN, GOLD, GREEN, RED, PURPLE,
    PANEL, PANEL_DARK, BORDER_SOFT, DIM, BG_TOP,
)
from games.base_game import BaseGame
from ui import theme
from animations.easing import clamp, ease_out_cubic

TRIALS = 10
FIELD = pygame.Rect(60, 108, 1080, 582)


class ReactionTest(BaseGame):
    game_id = "reaction_test"
    game_number = 4
    title = "Reaction Test"
    subtitle = "Pure reflex measurement"
    description = ("The screen waits in the dark, then flashes a target. "
                   "Tap the instant it appears. Ten trials measure your "
                   "average reaction, your fastest and slowest responses, "
                   "your consistency and any premature clicks.")
    instructions = [
        "Wait for the dark screen to turn green.",
        "Tap (or press SPACE) the moment the target appears.",
        "Tapping too early is a premature click and costs points.",
        "Ten trials; the report shows average, fastest, slowest and "
        "consistency.",
    ]
    accent = GREEN
    icon = "reaction"
    supports_difficulty = False

    def reset(self):
        super().reset()
        self.trial = 0
        self.reaction_times = []
        self.premature = 0
        self.phase = "wait"
        self.phase_t = 0.0
        self.wait_time = random.uniform(1.4, 3.0)
        self.target_at = 0.0
        self.last_rt = 0.0
        self.feedback = None
        self.feedback_t = 0.0
        self.trial_pts = 0

    def on_start(self):
        self.start_wait()

    def start_wait(self):
        self.phase = "wait"
        self.phase_t = 0.0
        self.wait_time = random.uniform(1.2, 3.2)
        self.feedback = None

    def show_target(self):
        self.phase = "target"
        self.phase_t = 0.0
        self.target_at = self.time
        self.app.audio.play("go", 0.7)

    def update_game(self, dt):
        self.phase_t += dt
        if self.feedback_t > 0:
            self.feedback_t = max(0.0, self.feedback_t - dt)
        if self.phase == "wait":
            if self.phase_t >= self.wait_time:
                self.show_target()
        elif self.phase == "target":
            if self.phase_t > 2.5:
                # No response: recorded as a missed trial, excluded from
                # the reaction-time average.
                self.mistakes += 1
                self.feedback = ("NO RESPONSE", RED)
                self.feedback_t = 0.9
                self.app.audio.play("miss")
                self.trial += 1
                self.phase = "feedback"
                self.phase_t = 0.0
        elif self.phase == "feedback":
            if self.phase_t >= 1.0:
                if self.trial >= TRIALS:
                    self.end_game()
                else:
                    self.start_wait()

        self.set_hud([
            ("Trial", f"{min(self.trial + 1, TRIALS)}/{TRIALS}", WHITE),
            ("Last", f"{self.last_rt:.0f} ms" if self.last_rt else "—", GREEN),
            ("Best", f"{min(self.reaction_times):.0f} ms"
             if self.reaction_times else "—", CYAN),
            ("Premature", f"{self.premature}", RED),
            ("Score", f"{self.score}", GOLD),
        ], progress=min(1.0, self.trial / TRIALS), progress_color=GREEN)

    def handle_click(self, pos):
        if self.phase == "wait":
            self.start_wait()
            self.premature += 1
            self.mistakes += 1
            self.score = max(0, self.score - 50)
            self.feedback = ("TOO SOON!", RED)
            self.feedback_t = 0.9
            self.flash(RED, 0.6)
            self.app.audio.play("error")
        elif self.phase == "target":
            rt = (self.time - self.target_at) * 1000
            self.reaction_times.append(rt)
            self.last_rt = rt
            self.hits += 1
            self.trial_pts = max(0, int(650 - rt))
            self.score += self.trial_pts
            self.app.audio.play("hit")
            self.feedback = (f"{rt:.0f} ms", GREEN)
            self.feedback_t = 0.9
            self.flash(GREEN, 0.3)
            self.particles.burst(WIDTH // 2, HEIGHT // 2, GREEN, count=24,
                                 speed=380, life=(0.3, 0.7), spark=True)
            self.trial += 1
            self.phase = "feedback"
            self.phase_t = 0.0

    def on_play_click(self, p):
        self.handle_click(p.pos)

    def on_key(self, key):
        if self.state == "playing" and key == pygame.K_SPACE:
            self.handle_click(self.app.input.pos)
            return
        super().on_key(key)

    def end_game(self):
        self.phase = "done"
        times = self.reaction_times
        avg = sum(times) / len(times) if times else 0.0
        fastest = min(times) if times else 0.0
        slowest = max(times) if times else 0.0
        if len(times) > 1:
            mean = avg
            std = math.sqrt(sum((t - mean) ** 2 for t in times) / len(times))
        else:
            std = 0.0
        accuracy = (TRIALS / (TRIALS + self.premature) * 100
                    if TRIALS + self.premature else 0.0)
        self.app.audio.play("gameover")
        self.finish({
            "score": self.score,
            "accuracy": accuracy,
            "mistakes": self.premature,
            "hits": len(times),
            "avg_reaction_ms": avg,
            "duration": self.time,
            "stats": [
                ("Average reaction", f"{avg:.0f} ms"),
                ("Fastest reaction", f"{fastest:.0f} ms"),
                ("Slowest reaction", f"{slowest:.0f} ms"),
                ("Consistency (±)", f"{std:.0f} ms"),
                ("Premature clicks", f"{self.premature}"),
                ("Accuracy", f"{accuracy:.0f}%"),
            ],
            "extra": {"fastest_ms": round(fastest, 1),
                      "slowest_ms": round(slowest, 1),
                      "std_dev_ms": round(std, 1),
                      "premature": self.premature,
                      "trials_total": TRIALS,
                      "trials": [round(t, 1) for t in times],
                      "difficulty": "normal"},
        })

    # ------------------------------------------------------------- draw
    def draw_world(self, surface):
        field = FIELD
        if self.phase == "target":
            pygame.draw.rect(surface, (26, 190, 130), field, border_radius=26)
            p = clamp(self.phase_t / 0.25)
            theme.glow(surface, field.center, 200, (120, 255, 200),
                       layers=5, strength=0.12)
            scale = 1.0 + 0.3 * (1 - ease_out_cubic(p))
            pygame.draw.circle(surface, (16, 90, 70), field.center,
                               int(170 * scale), 4)
            pygame.draw.circle(surface, (16, 90, 70), field.center,
                               int(230 * scale), 2)
            theme.text(surface, "TAP!", 96, WHITE, field.center)
            theme.text(surface, "NOW", 22, (16, 90, 70),
                       (field.centerx, field.centery + 86))
        else:
            theme.alpha_rect(surface, field, (8, 11, 30), 200, radius=26)
            pygame.draw.rect(surface, BORDER_SOFT, field, width=1,
                             border_radius=26)
            pulse = 0.5 + 0.5 * math.sin(self.time * 2.4)
            ring_c = (field.centerx, field.centery - 34)
            radius = int(50 + 8 * pulse)
            pygame.draw.circle(surface, (60, 72, 120), ring_c, radius + 20, 2)
            pygame.draw.circle(surface, (30, 38, 80), ring_c, radius)
            pygame.draw.circle(surface, (90, 105, 160), ring_c, radius, 2)
            theme.text(surface, "WAIT FOR THE SIGNAL", 30, WHITE,
                       (field.centerx, field.centery + 62))
            theme.text(surface, "The screen will turn green — tap instantly",
                       15, MUTED, (field.centerx, field.centery + 100),
                       bold=False)
            if self.feedback and self.feedback_t > 0 and self.phase != "target":
                theme.text(surface, self.feedback[0], 42, self.feedback[1],
                           (field.centerx, field.centery + 200))
                if self.feedback[0].endswith("ms"):
                    theme.text(surface, f"+{self.trial_pts} pts", 20, GOLD,
                               (field.centerx, field.centery + 246))

        # Trial dots.
        n = TRIALS
        x0 = WIDTH // 2 - (n * 22) // 2
        for i in range(n):
            if i < self.trial:
                color = GREEN
            elif i == self.trial and self.phase != "feedback":
                color = CYAN
            else:
                color = (50, 60, 100)
            pygame.draw.circle(surface, color, (x0 + i * 22 + 11, 712), 6)

        if self.premature:
            theme.text(surface, f"Premature clicks: {self.premature}", 12, RED,
                       (WIDTH - 60, 712), anchor="midright")
