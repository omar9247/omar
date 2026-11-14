"""Speed Click — rapid target interception with real difficulty tiers.

Each difficulty changes target size, spawn interval, target lifetime, target
density and placement precision, not just the round length. Per-target
time-to-hit is recorded so the neuro-monitor can track psychomotor speed and
fine-motor variability.
"""

import math
import random

import pygame

from config import (
    WIDTH, WHITE, MUTED, CYAN, GOLD, GREEN, RED, PURPLE, ORANGE,
    PANEL_DARK, BORDER_SOFT, DIM,
)
from games.base_game import BaseGame
from ui import theme
from animations.easing import clamp, ease_out_back, lerp


def _median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return (ordered[middle] if len(ordered) % 2
            else (ordered[middle - 1] + ordered[middle]) / 2)


def _pstdev(values):
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))

DIFFICULTIES = {
    0: {"name": "easy", "duration": 30.0, "interval": (0.95, 0.62),
        "radius": (42, 52), "lifetime": (1.95, 1.40), "max_targets": 4,
        "margin": 72, "spacing": 2.4},
    1: {"name": "normal", "duration": 25.0, "interval": (0.74, 0.45),
        "radius": (33, 43), "lifetime": (1.60, 1.00), "max_targets": 5,
        "margin": 60, "spacing": 2.7},
    2: {"name": "hard", "duration": 20.0, "interval": (0.56, 0.30),
        "radius": (24, 32), "lifetime": (1.22, 0.72), "max_targets": 6,
        "margin": 46, "spacing": 3.0},
}
FIELD = pygame.Rect(50, 104, 1100, 592)
TARGET_COLORS = [CYAN, PURPLE, GREEN, GOLD, ORANGE]


class Target:
    __slots__ = ("x", "y", "r", "age", "lifetime", "color", "hit", "hit_t",
                 "phase")

    def __init__(self, x, y, r, lifetime, color):
        self.x, self.y, self.r = x, y, r
        self.age = 0.0
        self.lifetime = lifetime
        self.color = color
        self.hit = False
        self.hit_t = 0.0
        self.phase = random.uniform(0, math.tau)

    @property
    def alive(self):
        return not self.hit and self.age < self.lifetime


class SpeedClick(BaseGame):
    game_id = "speed_click"
    game_number = 5
    title = "Speed Click"
    subtitle = "Psychomotor speed & precision"
    description = ("Targets blink into existence across the lunar field and "
                   "vanish fast. Hit as many as you can before the clock runs "
                   "out — every hit records your time-to-target for the "
                   "motor-speed monitor.")
    instructions = [
        "Tap targets before they fade away.",
        "Five consecutive hits raise your multiplier (up to x5).",
        "A missed or expired target resets the combo.",
        "Clicking empty space counts as a miss.",
        "EASY / NORMAL / HARD change target size, spawn rate, density and "
        "placement precision — each tier keeps its own personal baseline.",
    ]
    accent = ORANGE
    icon = "target"
    supports_difficulty = True

    def reset(self):
        super().reset()
        self.apply_difficulty()
        self.targets = []
        self.spawn_timer = 0.0
        self.combo = 0
        self.best_combo = 0
        self.missed_targets = 0
        self.empty_clicks = 0
        self.hit_times = []
        self.remaining = self.duration

    def apply_difficulty(self):
        self.params = DIFFICULTIES[self.difficulty_level]
        self.duration = self.params["duration"]
        self.remaining = self.duration

    @property
    def multiplier(self):
        return min(5, 1 + self.combo // 5)

    def on_start(self):
        # The intro screen may have changed the difficulty after reset().
        self.apply_difficulty()
        self.targets = []
        self.spawn_timer = 0.0
        self.combo = 0
        self.best_combo = 0
        self.missed_targets = 0
        self.empty_clicks = 0
        self.hit_times = []
        self.remaining = self.duration
        self.spawn_target()
        self.spawn_target()

    def progress_frac(self):
        return 1.0 - self.time / self.duration

    def _free_spot(self, radius, spacing):
        margin = self.params["margin"]
        best = None
        for _ in range(18):
            x = random.randint(FIELD.x + margin, FIELD.right - margin)
            y = random.randint(FIELD.y + margin, FIELD.bottom - margin)
            if all((x - t.x) ** 2 + (y - t.y) ** 2 >=
                   ((radius + t.r) * spacing) ** 2 for t in self.targets):
                return x, y
            best = (x, y)
        return best or (FIELD.centerx, FIELD.centery)

    def spawn_target(self):
        if len(self.targets) >= self.params["max_targets"]:
            return
        progress = clamp(self.time / max(0.1, self.duration))
        r = random.randint(*self.params["radius"])
        x, y = self._free_spot(r, self.params["spacing"])
        life_start, life_end = self.params["lifetime"]
        lifetime = lerp(life_start, life_end, progress)
        self.targets.append(Target(x, y, r, lifetime,
                                   random.choice(TARGET_COLORS)))

    def update_game(self, dt):
        self.remaining = max(0.0, self.duration - self.time)
        self.spawn_timer += dt
        start, end = self.params["interval"]
        interval = lerp(start, end, clamp(self.time / max(0.1, self.duration)))
        if self.spawn_timer >= interval:
            self.spawn_timer = 0.0
            self.spawn_target()

        for target in list(self.targets):
            target.age += dt
            if target.hit:
                target.hit_t += dt
                if target.hit_t > 0.25:
                    self.targets.remove(target)
            elif not target.alive:
                self.targets.remove(target)
                self.missed_targets += 1
                self.combo = 0
                self.particles.burst(target.x, target.y, (90, 100, 140),
                                     count=6, speed=120, life=(0.2, 0.4))

        hits = self.hits
        total = hits + self.missed_targets + self.empty_clicks
        accuracy = hits / total * 100 if total else 0.0
        self.set_hud([
            ("Score", f"{self.score}", ORANGE),
            ("Combo", f"x{self.multiplier}", GOLD),
            ("Hits", f"{self.hits}", GREEN),
            ("Accuracy", f"{accuracy:.0f}%", CYAN),
            ("Time", f"{math.ceil(self.remaining)}s",
             RED if self.remaining <= 5 else WHITE),
        ], progress=self.progress_frac(),
            progress_color=RED if self.remaining <= 5 else ORANGE)

        if self.remaining <= 0:
            self.end_game()

    def on_play_click(self, p):
        for target in reversed(self.targets):
            if target.hit:
                continue
            dx = p.pos[0] - target.x
            dy = p.pos[1] - target.y
            if dx * dx + dy * dy <= (target.r + 8) ** 2:
                self.hit_target(target)
                return
        # Clicking the fading ghost of an already hit target is ignored:
        # it is neither a duplicate hit nor an empty miss.
        for target in self.targets:
            if target.hit:
                dx = p.pos[0] - target.x
                dy = p.pos[1] - target.y
                if dx * dx + dy * dy <= (target.r + 8) ** 2:
                    return
        if FIELD.collidepoint(p.pos):
            self.empty_clicks += 1
            self.combo = 0
            self.app.audio.play("miss", 0.4)
            self.add_floater("MISS", (p.pos[0], p.pos[1] - 16), RED, 18,
                             life=0.5)
            self.particles.burst(p.pos[0], p.pos[1], RED, count=5, speed=110,
                                 life=(0.2, 0.35), radius=(1, 3))

    def hit_target(self, target):
        target.hit = True
        target.hit_t = 0.0
        self.hit_times.append(target.age * 1000.0)
        self.hits += 1
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        gained = 10 * self.multiplier
        self.score += gained
        self.app.audio.play("hit" if self.combo < 5 else "combo")
        self.particles.burst(target.x, target.y, target.color, count=16,
                             speed=280, life=(0.3, 0.6))
        self.add_floater(f"+{gained}", (target.x, target.y - target.r - 8),
                         target.color, 20)
        if self.multiplier > 1:
            self.add_floater(f"x{self.multiplier}",
                             (target.x + 44, target.y - target.r - 30),
                             GOLD, 16, life=0.6)

    def end_game(self):
        if self.state != "playing":
            return
        self.targets.clear()
        times = self.hit_times
        avg_hit = sum(times) / len(times) if times else None
        med_hit = _median(times) if times else None
        std_hit = _pstdev(times) if len(times) > 1 else 0.0
        total = self.hits + self.missed_targets + self.empty_clicks
        accuracy = self.hits / total * 100 if total else 0.0
        self.app.audio.play("gameover")
        self.finish({
            "score": self.score,
            "accuracy": accuracy,
            "mistakes": self.missed_targets + self.empty_clicks,
            "hits": self.hits,
            "avg_reaction_ms": avg_hit,
            "duration": self.time,
            "stats": [
                ("Targets hit", f"{self.hits}"),
                ("Expired targets", f"{self.missed_targets}"),
                ("Empty clicks", f"{self.empty_clicks}"),
                ("Median time-to-hit",
                 f"{med_hit:.0f} ms" if med_hit else "—"),
                ("Hit-time variability (±)",
                 f"{std_hit:.0f} ms" if times else "—"),
                ("Accuracy", f"{accuracy:.1f}%"),
                ("Best combo", f"x{self.best_combo}"),
                ("Difficulty", self.params["name"].upper()),
            ],
            "extra": {"best_combo": self.best_combo,
                      "expired": self.missed_targets,
                      "empty_clicks": self.empty_clicks,
                      "hit_times": [round(t, 1) for t in times],
                      "avg_hit_ms": round(avg_hit, 1) if avg_hit else None,
                      "median_hit_ms": round(med_hit, 1) if med_hit else None,
                      "std_hit_ms": round(std_hit, 1),
                      "difficulty": self.params["name"],
                      "duration_s": self.duration,
                      "target_radius": list(self.params["radius"]),
                      "max_targets": self.params["max_targets"]},
        })

    # ------------------------------------------------------------- draw
    def draw_world(self, surface):
        field = FIELD
        theme.alpha_rect(surface, field, PANEL_DARK, 150, radius=26)
        pygame.draw.rect(surface, BORDER_SOFT, field, width=1, border_radius=26)
        for i in range(3):
            pygame.draw.circle(surface, (22, 28, 58),
                               (field.centerx, field.centery),
                               120 + i * 90, 1)

        for target in self.targets:
            self.draw_target(surface, target)

        label = (f"{self.params['name'].upper()}  •  {self.duration:.0f}s  •  "
                 f"{self.params['max_targets']} MAX TARGETS")
        theme.text(surface, "HIT THE GLOWING TARGETS BEFORE THEY FADE",
                   12, DIM, (WIDTH // 2, 700))
        theme.text(surface, label, 11, MUTED, (WIDTH // 2, 718))

    def draw_target(self, surface, target):
        if target.hit:
            p = target.hit_t / 0.25
            radius = int(target.r * (1 + p * 1.4))
            alpha = int(200 * (1 - p))
            s = pygame.Surface((radius * 2 + 4, radius * 2 + 4),
                               pygame.SRCALPHA)
            pygame.draw.circle(s, (*target.color, alpha),
                               (radius + 2, radius + 2), radius, 3)
            surface.blit(s, (target.x - radius - 2, target.y - radius - 2))
            return
        appear = clamp(target.age / 0.16)
        pop = ease_out_back(appear)
        r = max(2, int(target.r * pop))
        pulse = 0.5 + 0.5 * math.sin(self.time * 6 + target.phase)
        life_left = clamp(1.0 - target.age / target.lifetime)
        theme.glow(surface, (target.x, target.y), r + 6, target.color,
                   layers=4, strength=0.14)
        pygame.draw.circle(surface, (14, 18, 40), (target.x, target.y), r)
        pygame.draw.circle(surface, target.color, (target.x, target.y), r, 4)
        pygame.draw.circle(surface, target.color, (target.x, target.y),
                           max(3, int(r * 0.32 * (0.8 + 0.2 * pulse))))
        pygame.draw.arc(surface, target.color,
                        (target.x - r - 7, target.y - r - 7,
                         (r + 7) * 2, (r + 7) * 2),
                        -math.pi / 2, -math.pi / 2 + math.tau * life_left, 3)
