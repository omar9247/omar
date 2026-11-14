"""Animated galaxy backdrop: soft nebulae, distant stars and a small planet.

The nebula is composed once with numpy at half resolution and smooth-scaled
up, which gives soft natural cloud edges instead of a stack of hard circles.
Star colours are deliberately muted so HUD text stays readable.
"""
import math
import random

import pygame

try:  # numpy ships with matplotlib, but keep a procedural fallback.
    import numpy as np
except Exception:  # pragma: no cover - defensive
    np = None


STAR_TINTS = (
    (205, 218, 255),   # blue-white
    (255, 244, 224),   # warm white
    (255, 255, 255),
    (196, 214, 238),
    (255, 224, 198),   # faint amber
)


class Starfield:
    def __init__(self, width, height, count=210, seed=7):
        self.width = width
        self.height = height
        rng = random.Random(seed)
        self._rng = rng
        self.stars = []
        for _ in range(count):
            depth = rng.choice([0.25, 0.4, 0.4, 0.7, 1.0])
            self.stars.append({
                "x": rng.uniform(0, width),
                "y": rng.uniform(0, height),
                "r": 1 if depth < 0.85 else rng.choice([1, 2]),
                "depth": depth,
                "tint": rng.choice(STAR_TINTS),
                "bright": rng.uniform(0.35, 0.95),
                "phase": rng.uniform(0, math.tau),
                "twinkle": rng.uniform(0.6, 1.7),
            })
        # A few faint dust motes drift with the closest star layer.
        self.dust = [{
            "x": rng.uniform(0, width), "y": rng.uniform(0, height),
            "r": rng.choice([1, 1, 2]), "a": rng.uniform(0.18, 0.4),
            "depth": rng.choice([0.5, 0.8, 1.0]),
        } for _ in range(46)]
        self.time = 0.0
        self.nebula = self._build_nebula()
        self._planet = None

    # ------------------------------------------------------------- nebula
    def _nebula_field(self, w, h):
        """Return (rgb, alpha) float arrays for a layered galaxy."""
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        rgb = np.zeros((h, w, 3), np.float32)
        weight = np.zeros((h, w), np.float32)

        blobs = [
            # x, y, sx, sy, rotation, colour, strength
            (0.16, 0.20, 0.30, 0.22, -0.45, (116, 78, 196), 1.00),
            (0.30, 0.34, 0.18, 0.13, -0.35, (88, 62, 172), 0.65),
            (0.84, 0.24, 0.24, 0.15, 0.35, (48, 118, 176), 0.72),
            (0.92, 0.36, 0.14, 0.10, 0.20, (40, 150, 168), 0.40),
            (0.56, 0.86, 0.34, 0.16, 0.10, (112, 58, 158), 0.66),
            (0.74, 0.78, 0.18, 0.10, -0.15, (46, 108, 170), 0.42),
            (0.46, 0.52, 0.22, 0.12, -0.28, (150, 92, 128), 0.30),
        ]
        for bx, by, sx, sy, rot, colour, strength in blobs:
            dx = (xx / w - bx) * w
            dy = (yy / h - by) * h
            cr, sr = math.cos(rot), math.sin(rot)
            rx = dx * cr - dy * sr
            ry = dx * sr + dy * cr
            g = np.exp(-0.5 * ((rx / (sx * w)) ** 2 +
                               (ry / (sy * h)) ** 2))
            g *= strength
            rgb += g[:, :, None] * np.array(colour, np.float32)
            weight += g

        # Dark dust lanes cutting across the clouds for depth.
        lanes = [
            (0.00, 0.46, 0.030),
            (0.30, 0.20, 0.022),
            (0.62, 0.62, 0.026),
        ]
        dust = np.zeros((h, w), np.float32)
        for slope, offset, soft in lanes:
            d = np.abs(yy / h - (offset + slope * xx / w))
            dust += np.exp(-0.5 * (d / soft) ** 2)
        dust = np.clip(dust, 0, 1)

        safe = np.maximum(weight, 1e-5)
        rgb = rgb / safe[:, :, None]
        alpha = np.clip(weight * 74.0, 0, 132)
        alpha *= (1.0 - 0.48 * dust)
        alpha *= 0.95
        return rgb, alpha

    def _build_nebula(self):
        w, h = max(320, self.width // 2), max(220, self.height // 2)
        if np is None:
            return self._build_nebula_fallback()
        rgb, alpha = self._nebula_field(w, h)
        arr = np.zeros((h, w, 4), np.uint8)
        arr[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
        arr[:, :, 3] = np.clip(alpha, 0, 255).astype(np.uint8)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        px = pygame.surfarray.pixels3d(surf)
        pa = pygame.surfarray.pixels_alpha(surf)
        px[:, :, :] = np.transpose(arr[:, :, :3], (1, 0, 2))
        pa[:, :] = arr[:, :, 3].T
        del px, pa
        return pygame.transform.smoothscale(surf, (self.width, self.height))

    def _build_nebula_fallback(self):
        surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        blobs = [
            ((180, 120), 320, (90, 50, 180, 20)),
            ((1040, 260), 280, (30, 120, 190, 18)),
            ((620, 760), 380, (70, 40, 150, 15)),
            ((980, 700), 220, (30, 150, 170, 12)),
        ]
        for (x, y), radius, color in blobs:
            for i in range(6, 0, -1):
                r = int(radius * i / 6)
                alpha = int(color[3] * (1 - i / 7))
                pygame.draw.circle(surf, (*color[:3], alpha), (x, y), r)
        return surf

    # -------------------------------------------------------------- update
    def update(self, dt):
        self.time += dt
        for s in self.stars:
            s["x"] -= 3.5 * s["depth"] * dt
            if s["x"] < -4:
                s["x"] = self.width + 4
                s["y"] = self._rng.uniform(0, self.height)
        for d in self.dust:
            d["x"] -= 2.0 * d["depth"] * dt
            if d["x"] < -3:
                d["x"] = self.width + 3
                d["y"] = self._rng.uniform(0, self.height)

    def draw(self, surface):
        surface.blit(self.nebula, (0, 0))
        self.draw_stars(surface)

    def draw_stars(self, surface):
        t = self.time
        for d in self.dust:
            a = d["a"] * (0.8 + 0.2 * math.sin(t * 0.6 + d["x"] * 0.01))
            c = int(120 * a)
            pygame.draw.circle(surface, (c, c, min(255, c + 14)),
                               (int(d["x"]), int(d["y"])), d["r"])
        for s in self.stars:
            tw = 0.82 + 0.18 * math.sin(t * s["twinkle"] + s["phase"])
            f = s["bright"] * tw * (0.55 + 0.45 * s["depth"])
            tint = s["tint"]
            color = (int(tint[0] * f), int(tint[1] * f), int(tint[2] * f))
            color = tuple(max(24, min(235, v)) for v in color)
            pygame.draw.circle(surface, color, (int(s["x"]), int(s["y"])),
                               s["r"])

    # -------------------------------------------------------------- planet
    def draw_moon(self, surface, center=(1168, 142), radius=24):
        """Small ringed planet tucked into the top-right margin."""
        x, y = center
        if self._planet is None:
            self._planet = self._build_planet(radius)
        surface.blit(self._planet, (x - self._planet.get_width() // 2,
                                    y - self._planet.get_height() // 2))

    def _build_planet(self, radius):
        pad = int(radius * 2.6)
        size = pad * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = (size // 2, size // 2)
        # Soft atmospheric rim, no hard dark ring.
        for i in range(6, 0, -1):
            r = int(radius + i * 3)
            pygame.draw.circle(surf, (70, 104, 170, 6), c, r)
        base = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(base, (54, 66, 104), (radius, radius), radius)
        pygame.draw.circle(base, (72, 86, 128), (radius - 4, radius - 4),
                           radius - 6)
        # Subtle cloud bands.
        for off in (-0.45, -0.12, 0.18, 0.46):
            band = pygame.Rect(0, radius + off * radius,
                               radius * 2, max(3, int(radius * 0.16)))
            pygame.draw.ellipse(base, (64, 78, 118, 120), band)
        surf.blit(base, (c[0] - radius, c[1] - radius))
        # Thin ring with low contrast.
        ring = pygame.Rect(c[0] - int(radius * 1.65), c[1] - int(radius * 0.55),
                           int(radius * 3.3), int(radius * 1.1))
        pygame.draw.ellipse(surf, (96, 112, 158, 90), ring, 2)
        pygame.draw.ellipse(surf, (72, 86, 128, 60), ring.inflate(-8, -6), 1)
        return surf
