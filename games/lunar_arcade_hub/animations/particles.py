"""Lightweight particle effects shared by every game."""

import math
import random

import pygame

from animations.easing import clamp


class Particle:
    __slots__ = (
        "x", "y", "vx", "vy", "life", "max_life", "color",
        "radius", "gravity", "drag", "spark",
    )

    def __init__(self, x, y, vx, vy, life, color, radius,
                 gravity=380.0, drag=0.0, spark=False):
        self.x = float(x)
        self.y = float(y)
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color
        self.radius = radius
        self.gravity = gravity
        self.drag = drag
        self.spark = spark

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        if self.drag:
            damp = max(0.0, 1.0 - self.drag * dt)
            self.vx *= damp
            self.vy *= damp
        self.life -= dt


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def clear(self):
        self.particles.clear()

    def burst(self, x, y, color, count=18, speed=260.0, gravity=380.0,
              life=(0.35, 0.8), radius=(2, 5), spark=False, spread=math.tau,
              angle=None):
        for _ in range(count):
            if angle is None:
                a = random.uniform(0, spread)
            else:
                a = angle + random.uniform(-spread / 2, spread / 2)
            v = random.uniform(speed * 0.35, speed)
            self.particles.append(
                Particle(
                    x, y,
                    math.cos(a) * v,
                    math.sin(a) * v - (60 if not spark else 0),
                    random.uniform(*life),
                    color,
                    random.randint(*radius),
                    gravity=gravity,
                    drag=0.8 if spark else 0.0,
                    spark=spark,
                )
            )

    def confetti(self, x, y, colors, count=30):
        for _ in range(count):
            color = random.choice(colors)
            a = random.uniform(-math.pi, 0)
            v = random.uniform(160, 420)
            self.particles.append(
                Particle(
                    x + random.uniform(-20, 20), y,
                    math.cos(a) * v, math.sin(a) * v,
                    random.uniform(0.7, 1.3), color,
                    random.randint(3, 6), gravity=520.0, drag=0.4,
                )
            )

    def update(self, dt):
        for p in self.particles:
            p.update(dt)
        if self.particles:
            self.particles = [p for p in self.particles if p.life > 0]

    def draw(self, surface):
        for p in self.particles:
            if p.life <= 0:
                continue
            a = clamp(p.life / p.max_life)
            r = max(1, int(p.radius * (0.4 + 0.6 * a)))
            if p.spark:
                color = tuple(int(c * a) for c in p.color)
                pygame.draw.circle(surface, color, (int(p.x), int(p.y)), r)
            else:
                glow = tuple(int(c * a * 0.35) for c in p.color)
                core = tuple(int(c * a) for c in p.color)
                pygame.draw.circle(surface, glow, (int(p.x), int(p.y)), r + 2)
                pygame.draw.circle(surface, core, (int(p.x), int(p.y)), r)
