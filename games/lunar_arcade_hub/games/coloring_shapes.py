"""Coloring Shapes — I-Pen target detection with mouse/touch fallback.

Press-and-hold colours a shape; pen pressure (when reported by the OS/driver)
accelerates the ink fill.  Once the shape is completely filled a short release
window opens: lift off in time to lock it in, or the shape is lost.  A
distractor is registered after a short deliberate contact, while sub-50 ms
brushes are ignored.
"""

import math
import random

import pygame

from config import (
    WIDTH, HEIGHT, WHITE, MUTED, CYAN, GOLD, GREEN, RED, PURPLE, BLUE,
    ORANGE, PANEL_DARK, PANEL_LIGHT, BORDER_SOFT, DIM, BG_TOP,
)
from games.base_game import BaseGame
from ui import theme
from animations.easing import clamp, ease_out_back, ease_out_cubic

ROUNDS = 5
SHAPE_COUNTS = {
    0: [7, 9, 11, 13, 15],
    1: [9, 12, 15, 18, 21],
    2: [12, 15, 18, 22, 26],
}
TIME_LIMITS = {0: 24, 1: 21, 2: 18}

# A shape must be completely filled before the release window opens.  The
# window starts only at full ink and shrinks with difficulty; holding past it
# loses the shape immediately (penalty unchanged: -25).
FILL_THRESHOLD = 0.999
RELEASE_WINDOWS = {0: 0.90, 1: 0.60, 2: 0.38}   # Easy > Medium > Hard
RELEASE_WARN = 0.55      # remaining fraction: meter turns amber
RELEASE_DANGER = 0.25    # remaining fraction: meter turns red, "RELEASE!"
# A distractor only needs a short deliberate contact to register; waiting for
# the full hold limit made wrong answers feel unresponsive.  Contacts shorter
# than TAP_MIN are treated as accidental brushes and are ignored.
WRONG_GRACE = 0.15
TAP_MIN = 0.05

PALETTE = {
    "CYAN": (55, 225, 255),
    "PURPLE": (165, 105, 255),
    "GOLD": (255, 205, 75),
    "GREEN": (75, 245, 170),
    "RED": (255, 95, 120),
    "BLUE": (100, 150, 255),
    "ORANGE": (255, 150, 70),
}
SHAPE_NAMES = ["STAR", "CIRCLE", "TRIANGLE", "DIAMOND", "HEXAGON", "SQUARE"]
FIELD = pygame.Rect(70, 158, 1060, 500)


def shape_points(kind, cx, cy, r):
    if kind == "CIRCLE":
        return None
    if kind == "SQUARE":
        pts = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        return [(cx + x * r * 0.82, cy + y * r * 0.82) for x, y in pts]
    if kind == "TRIANGLE":
        angles = [-90, 30, 150]
    elif kind == "DIAMOND":
        angles = [-90, 0, 90, 180]
    elif kind == "HEXAGON":
        angles = [-90 + i * 60 for i in range(6)]
    else:  # STAR
        pts = []
        for i in range(10):
            radius = r if i % 2 == 0 else r * 0.45
            a = math.radians(-90 + i * 36)
            pts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
        return pts
    return [(cx + math.cos(math.radians(a)) * r,
             cy + math.sin(math.radians(a)) * r) for a in angles]


def draw_shape(surface, kind, cx, cy, r, color, width=0):
    pts = shape_points(kind, cx, cy, r)
    if pts is None:
        pygame.draw.circle(surface, color, (int(cx), int(cy)), int(r), width)
    else:
        pygame.draw.polygon(surface, color, pts, width)


def inside_shape(kind, cx, cy, r, pos):
    dx, dy = pos[0] - cx, pos[1] - cy
    if dx * dx + dy * dy > (r + 6) ** 2:
        return False
    if kind == "CIRCLE":
        return dx * dx + dy * dy <= (r + 2) ** 2
    if kind == "SQUARE":
        return abs(dx) <= r * 0.9 and abs(dy) <= r * 0.9
    return True  # polygons: bounding circle is close enough for touch


class Shape:
    __slots__ = ("kind", "color", "name", "x", "y", "r", "ink", "target",
                 "state", "wrong_t", "shake", "spawn", "seed", "hold",
                 "release_t", "window")

    def __init__(self, kind, color_name, x, y, r, target, seed):
        self.kind = kind
        self.name = color_name
        self.color = PALETTE[color_name]
        self.x, self.y, self.r = x, y, r
        self.ink = 0.0
        self.target = target
        self.state = "idle"
        self.wrong_t = 0.0
        self.shake = 0.0
        self.spawn = 0.0
        self.seed = seed
        self.hold = 0.0
        self.release_t = 0.0
        self.window = False


class ColoringShapes(BaseGame):
    game_id = "coloring_shapes"
    game_number = 2
    title = "Coloring Shapes"
    subtitle = "I-Pen target detection"
    description = ("A target shape and colour are announced. Colour every "
                   "matching shape and leave the distractors untouched. "
                   "Shapes with the same colour but the wrong form are "
                   "deliberately mixed in.")
    instructions = [
        "Read the rule card: e.g. 'colour every CYAN STAR'.",
        "Press and hold until the shape is completely filled.",
        "Release inside the short window that opens at full ink to lock it in.",
        "The window is longest on Easy and shortest on Hard; holding past it "
        "loses the shape and costs 25 points.",
        "Do not colour distractors — they cost points and count as errors.",
        "Mouse, touchscreen and stylus input are supported; pen pressure "
        "speeds up the ink when the device reports it.",
        "Five rounds, each with more shapes and less time.",
    ]
    accent = GOLD
    icon = "shapes"
    supports_difficulty = True

    def reset(self):
        super().reset()
        self.round_index = 0
        self.shapes = []
        self.phase = "announce"
        self.phase_t = 0.0
        self.rule_mode = "both"
        self.rule_shape = "STAR"
        self.rule_color = "CYAN"
        self.time_limit = 21
        self.round_start = 0.0
        self.round_time = 0.0
        self.correct = 0
        self.wrong = 0
        self.missed = 0
        self.round_times = []
        self.active = None
        self.bonus = 0
        self.time_left = 0.0
        self.targets_total = 0
        self.overholds = 0

    # ------------------------------------------------------------ rounds
    def on_start(self):
        self.setup_round()

    def pick_rule(self):
        mode = random.choices(["both", "shape", "color"], [0.7, 0.15, 0.15])[0]
        shape = random.choice(SHAPE_NAMES)
        color = random.choice(list(PALETTE.keys()))
        return mode, shape, color

    def matches(self, kind, color_name):
        if self.rule_mode == "both":
            return kind == self.rule_shape and color_name == self.rule_color
        if self.rule_mode == "shape":
            return kind == self.rule_shape
        return color_name == self.rule_color

    def rule_text(self):
        if self.rule_mode == "both":
            return f"COLOUR EVERY {self.rule_color} {self.rule_shape}"
        if self.rule_mode == "shape":
            return f"COLOUR EVERY {self.rule_shape}"
        return f"COLOUR EVERY {self.rule_color} SHAPE"

    def setup_round(self):
        self.round_index += 1
        self.phase = "announce"
        self.phase_t = 0.0
        self.active = None
        self.correct_round = 0
        self.wrong_round = 0
        self.rule_mode, self.rule_shape, self.rule_color = self.pick_rule()
        self.time_limit = TIME_LIMITS[self.difficulty_level]
        count = SHAPE_COUNTS[self.difficulty_level][self.round_index - 1]
        target_count = random.randint(3, min(5, max(3, count // 4)))
        self.targets_total += target_count
        self.build_shapes(count, target_count)
        self.app.audio.play("click")

    def build_shapes(self, count, target_count):
        self.shapes = []
        rng = random.Random()
        colors = list(PALETTE.keys())
        others = [c for c in colors if c != self.rule_color]
        shapes = []
        for i in range(target_count):
            shapes.append((self.rule_shape, self.rule_color, True))
        while len(shapes) < count:
            mode = rng.random()
            if self.rule_mode == "both":
                if mode < 0.42:
                    kind, col = self.rule_shape, rng.choice(others)
                elif mode < 0.80:
                    kind, col = rng.choice([s for s in SHAPE_NAMES
                                            if s != self.rule_shape]), self.rule_color
                else:
                    kind, col = rng.choice([s for s in SHAPE_NAMES
                                            if s != self.rule_shape]), rng.choice(others)
            elif self.rule_mode == "shape":
                # Shape-only rule: a distractor may not share the shape.
                kind, col = rng.choice([s for s in SHAPE_NAMES
                                        if s != self.rule_shape]), rng.choice(colors)
            else:
                # Colour-only rule: a distractor may not share the colour.
                kind, col = rng.choice(SHAPE_NAMES), rng.choice(others)
            shapes.append((kind, col, False))
        rng.shuffle(shapes)
        placed = []
        attempts = 0
        while shapes and attempts < 4000:
            attempts += 1
            kind, col, target = shapes[-1]
            r = rng.randint(30, 40)
            x = rng.randint(FIELD.x + r + 18, FIELD.right - r - 18)
            y = rng.randint(FIELD.y + r + 18, FIELD.bottom - r - 18)
            if all((x - p.x) ** 2 + (y - p.y) ** 2 >= (r + p.r + 14) ** 2
                   for p in placed):
                placed.append(Shape(kind, col, x, y, r, target, rng.random()))
                shapes.pop()
        self.shapes = placed

    def update_game(self, dt):
        for shape in self.shapes:
            shape.spawn = min(1.0, shape.spawn + dt * 4)
            shape.shake = max(0.0, shape.shake - dt * 2.5)
            if shape.wrong_t > 0:
                shape.wrong_t -= dt
                if shape.wrong_t <= 0 and shape.state == "wrong":
                    shape.state = "idle"
                    shape.ink = 0.0

        if self.phase == "announce":
            self.phase_t += dt
            if self.phase_t >= 1.5:
                self.phase = "play"
                self.phase_t = 0.0
                self.round_start = self.time
        elif self.phase == "play":
            self.round_time = self.time - self.round_start
            self.time_left = max(0.0, self.time_limit - self.round_time)
            self.update_ink(dt)
            targets = [s for s in self.shapes if s.target]
            if targets and all(s.state == "colored" for s in targets):
                self.end_round(success=True)
            elif self.time_left <= 0:
                self.missed += sum(1 for s in targets if s.state != "colored")
                self.end_round(success=False)
        elif self.phase == "round_end":
            self.phase_t += dt
            if self.phase_t >= 1.0:
                if self.round_index >= ROUNDS:
                    self.end_game()
                else:
                    self.setup_round()

        targets = [s for s in self.shapes if s.target]
        found = sum(1 for s in targets if s.state == "colored")
        self.set_hud([
            ("Round", f"{self.round_index}/{ROUNDS}", WHITE),
            ("Score", f"{self.score}", GOLD),
            ("Found", f"{found}/{len(targets)}", GREEN),
            ("Errors", f"{self.wrong}", RED),
            ("Time", f"{math.ceil(self.time_left)}s"
             if self.phase == "play" else "—",
             RED if 0 < self.time_left <= 5 else WHITE),
        ], progress=(self.time_left / self.time_limit
                     if self.phase == "play" else 1.0),
            progress_color=GOLD)

    def release_window(self):
        """Release window in seconds for the current difficulty."""
        return RELEASE_WINDOWS.get(self.difficulty_level,
                                   RELEASE_WINDOWS[1])

    def update_ink(self, dt):
        if self.active is None:
            return
        shape = self.active
        if not self.app.input.down:
            return
        # Once the window is open, time runs even if the pointer drifts; the
        # player is still holding the shape.
        if shape.window:
            shape.release_t += dt
            if shape.release_t >= self.release_window():
                self.overhold(shape)
            return
        hover = self.shape_at(self.app.input.pos)
        if hover is shape:
            pressure = max(0.4, min(1.0, self.app.input.pressure or 1.0))
            shape.ink = min(1.0, shape.ink + dt * (0.8 + pressure))
            shape.hold += dt
            if not self.matches(shape.kind, shape.name) and \
                    shape.hold >= WRONG_GRACE:
                # Wrong target: register at the decision point.
                self.complete_shape(shape)
                return
            if shape.ink >= FILL_THRESHOLD:
                # Full ink: the release window starts now, not before.
                shape.window = True
                shape.release_t = 0.0
                self.app.audio.play("tick", 0.3)

    def shape_at(self, pos):
        for shape in reversed(self.shapes):
            if shape.state in ("idle", "wrong") and inside_shape(
                    shape.kind, shape.x, shape.y, shape.r, pos):
                return shape
        return None

    def on_play_click(self, p):
        if self.phase != "play" or self.active is not None:
            return
        shape = self.shape_at(p.pos)
        if shape is None or shape.state != "idle" or shape.wrong_t > 0:
            return
        self.active = shape
        shape.hold = 0.0
        shape.ink = 0.0
        shape.release_t = 0.0
        shape.window = False
        self.app.audio.play("tick", 0.25)

    def on_pointer_up(self, p):
        if self.phase != "play" or self.active is None:
            return
        shape = self.active
        held = shape.hold
        window = shape.window
        released_at = shape.release_t
        self.active = None
        shape.hold = 0.0
        shape.window = False
        shape.release_t = 0.0
        if held < TAP_MIN and not window:
            # Accidental brush / click-through: no score, no error feedback.
            shape.ink = 0.0
            return
        if not self.matches(shape.kind, shape.name):
            # Deliberate tap on a distractor: register once, immediately.
            self.complete_shape(shape)
        elif window and released_at <= self.release_window():
            # Released inside the window: lock the fully filled shape in.
            self.complete_shape(shape)
        elif window:
            # Safety net; update_ink normally pops the shape at the deadline.
            self.overhold(shape)
        else:
            # Early release before the ink is complete: cancel, no penalty.
            shape.ink = 0.0

    def complete_shape(self, shape):
        if shape.state == "colored" or shape.wrong_t > 0:
            return
        self.active = None
        shape.hold = 0.0
        shape.window = False
        shape.release_t = 0.0
        if self.matches(shape.kind, shape.name):
            shape.state = "colored"
            shape.ink = 1.0
            self.correct += 1
            self.score += 50
            self.add_floater("+50", (shape.x, shape.y - shape.r - 10),
                             GREEN, 20)
            self.particles.burst(shape.x, shape.y, shape.color, count=14,
                                 speed=220, life=(0.3, 0.6))
            self.app.audio.play("hit", 0.4)
            self.flash(shape.color, 0.15)
        else:
            shape.state = "wrong"
            shape.wrong_t = 0.55
            shape.ink = 0.0
            shape.shake = 0.55
            self.wrong += 1
            self.mistakes += 1
            self.score = max(0, self.score - 25)
            self.add_floater("-25", (shape.x, shape.y - shape.r - 10),
                             RED, 20)
            self.particles.burst(shape.x, shape.y, RED, count=10, speed=160)
            self.app.audio.play("error", 0.5)
            self.flash(RED, 0.4)

    def overhold(self, shape):
        """Continuous contact exceeded the safe duration: the shape is lost."""
        self.active = None
        shape.hold = 0.0
        shape.window = False
        shape.release_t = 0.0
        shape.state = "wrong"
        shape.wrong_t = 0.7
        shape.ink = 0.0
        shape.shake = 0.7
        self.wrong += 1
        self.mistakes += 1
        self.overholds += 1
        self.score = max(0, self.score - 25)
        self.add_floater("WINDOW MISSED -25",
                         (shape.x, shape.y - shape.r - 10), RED, 20)
        self.particles.burst(shape.x, shape.y, RED, count=14, speed=220)
        self.app.audio.play("error", 0.55)
        self.flash(RED, 0.45)

    def end_round(self, success):
        self.phase = "round_end"
        self.phase_t = 0.0
        self.active = None
        if success:
            self.round_times.append(self.round_time)
            bonus = int(max(0, self.time_limit - self.round_time) * 8)
            self.bonus += bonus
            self.score += bonus
            self.add_floater(f"+{bonus} TIME BONUS",
                             (WIDTH // 2, 255), GOLD, 24, life=1.2)
            self.app.audio.play("success")
            self.particles.confetti(WIDTH // 2, 300, [self.accent, CYAN, GREEN],
                                    count=30)
        else:
            self.app.audio.play("gameover")

    def end_game(self):
        self.shapes = []
        taps = self.correct + self.wrong
        accuracy = self.correct / taps * 100 if taps else 0.0
        avg_round = (sum(self.round_times) / len(self.round_times)
                     if self.round_times else 0.0)
        errors = self.wrong + self.missed
        error_rate = (errors / self.targets_total * 100
                      if self.targets_total else 0.0)
        self.finish({
            "score": self.score,
            "accuracy": accuracy,
            "mistakes": self.wrong + self.missed,
            "hits": self.correct,
            "avg_reaction_ms": None,
            "duration": self.time,
            "stats": [
                ("Shapes coloured", f"{self.correct}"),
                ("Incorrect selections", f"{self.wrong}"),
                ("Missed targets", f"{self.missed}"),
                ("Selection error rate", f"{error_rate:.1f}%"),
                ("Accuracy", f"{accuracy:.1f}%"),
                ("Average round time", f"{avg_round:.1f}s" if avg_round else "—"),
                ("Shapes lost to overhold", f"{self.overholds}"),
                ("Time bonus", f"{self.bonus} pts"),
            ],
            "extra": {"wrong": self.wrong, "missed": self.missed,
                      "targets_total": self.targets_total,
                      "error_rate": round(error_rate, 2),
                      "overholds": self.overholds,
                      "time_bonus": self.bonus,
                      "avg_round_time": round(avg_round, 2),
                      "difficulty": self.difficulty_name.lower()},
        })

    # ------------------------------------------------------------- draw
    def draw_world(self, surface):
        field = FIELD
        theme.alpha_rect(surface, field, PANEL_DARK, 160, radius=24)
        pygame.draw.rect(surface, BORDER_SOFT, field, width=1, border_radius=24)

        if self.phase == "announce":
            self.draw_announce(surface)
            return

        for shape in self.shapes:
            self.draw_shape_token(surface, shape)

        # Rule card.
        card = pygame.Rect(WIDTH // 2 - 350, 112, 700, 40)
        theme.alpha_rect(surface, card, PANEL_LIGHT, 235, radius=12)
        pygame.draw.rect(surface, BORDER_SOFT, card, width=1, border_radius=12)
        theme.text(surface, f"ROUND {self.round_index}/{ROUNDS}", 13, MUTED,
                   (card.x + 18, card.centery), anchor="midleft")
        theme.text(surface, self.rule_text(), 17, self.accent,
                   (card.centerx, card.centery))
        target_icon_x = card.right - 34
        draw_shape(surface, self.rule_shape, target_icon_x, card.centery, 13,
                   PALETTE[self.rule_color])

        if self.phase == "round_end":
            label = "ROUND CLEAR" if self.time_left > 0 else "TIME UP"
            color = GREEN if self.time_left > 0 else RED
            theme.glow(surface, (WIDTH // 2, 400), 120, color, layers=4,
                       strength=0.10)
            theme.text(surface, label, 40, color, (WIDTH // 2, 390))
            if self.round_index < ROUNDS:
                theme.text(surface, "Next round loading…", 15, MUTED,
                           (WIDTH // 2, 436))

        theme.text(surface,
                   "PRESS & HOLD TO FILL  •  RELEASE IN THE WINDOW  •  "
                   "HOLDING PAST IT LOSES THE SHAPE",
                   11, DIM, (WIDTH // 2, 712))

    def draw_announce(self, surface):
        theme.alpha_rect(surface, FIELD, (5, 7, 22), 200, radius=24)
        theme.glow(surface, (WIDTH // 2, 350), 140, self.accent, layers=4,
                   strength=0.08)
        theme.text(surface, f"ROUND {self.round_index} OF {ROUNDS}", 14,
                   MUTED, (WIDTH // 2, 260))
        theme.text(surface, "COLOUR EVERY", 20, WHITE, (WIDTH // 2, 310))
        draw_shape(surface, self.rule_shape, WIDTH // 2 - 160, 400, 42,
                   PALETTE[self.rule_color])
        if self.rule_mode != "shape":
            theme.text(surface, self.rule_color, 34, PALETTE[self.rule_color],
                       (WIDTH // 2 + 20, 400))
        else:
            theme.text(surface, self.rule_shape, 34, PALETTE[self.rule_color],
                       (WIDTH // 2 + 20, 400))
        if self.rule_mode == "both":
            theme.text(surface, self.rule_shape, 34, WHITE,
                       (WIDTH // 2 + 200, 400))
        hint = ("Colour only shapes that match BOTH the colour and the shape"
                if self.rule_mode == "both" else
                "Colour only shapes that match the rule")
        theme.text(surface, hint, 15, MUTED, (WIDTH // 2, 470), bold=False)

    def draw_shape_token(self, surface, shape):
        pop = ease_out_back(clamp(shape.spawn))
        shake = math.sin(shape.shake * 40) * 6 * shape.shake
        cx = shape.x + shake
        cy = shape.y
        r = shape.r * pop
        if r < 4:
            return
        hovered = (self.phase == "play" and shape.state == "idle" and
                   self.shape_at(self.app.input.pos) is shape)
        if shape.state == "colored":
            draw_shape(surface, shape.kind, cx, cy, r, shape.color)
            draw_shape(surface, shape.kind, cx, cy, r, WHITE, width=2)
            return
        if hovered or shape is self.active:
            # Thin halo-free focus ring instead of a soft dark cloud.
            draw_shape(surface, shape.kind, cx, cy, r + 7, shape.color,
                       width=1)
        # Ink fill grows from the centre.
        if shape.ink > 0.02:
            draw_shape(surface, shape.kind, cx, cy, r * (0.25 + 0.75 * shape.ink),
                       tuple(int(c * 0.85) for c in shape.color))
        draw_shape(surface, shape.kind, cx, cy, r,
                   WHITE if hovered else shape.color, width=3)
        if shape is self.active and self.phase == "play":
            self.draw_hold_meter(surface, shape, cx, cy, r)
        if shape.state == "wrong":
            pygame.draw.line(surface, RED, (cx - r * 0.6, cy - r * 0.6),
                             (cx + r * 0.6, cy + r * 0.6), 4)
            pygame.draw.line(surface, RED, (cx + r * 0.6, cy - r * 0.6),
                             (cx - r * 0.6, cy + r * 0.6), 4)

    def draw_hold_meter(self, surface, shape, cx, cy, r):
        """Fill progress, then the shrinking release window at full ink."""
        pad = 13
        ring = pygame.Rect(cx - r - pad, cy - r - pad,
                           2 * (r + pad), 2 * (r + pad))
        pygame.draw.arc(surface, BORDER_SOFT, ring, 0, math.tau, 2)
        if not shape.window:
            frac = clamp(shape.ink)
            pygame.draw.arc(surface, GREEN, ring, -math.pi / 2,
                            -math.pi / 2 + max(0.02, math.tau * frac), 4)
            theme.text(surface, f"FILL  {int(frac * 100)}%", 11, GREEN,
                       (cx, cy - r - 26))
            return
        window = self.release_window()
        remaining = max(0.0, window - shape.release_t)
        frac = remaining / window if window else 0.0
        if frac > RELEASE_WARN:
            color = GREEN
        elif frac > RELEASE_DANGER:
            color = GOLD
        else:
            color = RED
        pygame.draw.arc(surface, color, ring, -math.pi / 2,
                        -math.pi / 2 + max(0.02, math.tau * frac), 4)
        if frac <= RELEASE_DANGER:
            blink = 0.55 + 0.45 * math.sin(self.time * 22)
            theme.text_alpha(surface, "RELEASE!", 13, RED,
                             (cx, cy - r - 26), alpha=255 * blink)
        else:
            theme.text(surface, f"RELEASE NOW  {remaining:.1f}s", 12, color,
                       (cx, cy - r - 26))
