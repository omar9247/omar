"""Screen transition helpers."""

import pygame

from animations.easing import clamp, ease_in_out_cubic


class FadeTransition:
    """Fades to black, runs a callback at the darkest point, fades back in."""

    def __init__(self, duration=0.42):
        self.duration = duration
        self.phase = "idle"  # idle / out / in
        self.t = 0.0
        self.callback = None
        self.alpha = 0
        self._overlay = pygame.Surface((1200, 800), pygame.SRCALPHA)

    @property
    def busy(self):
        return self.phase != "idle"

    def start(self, callback):
        if self.busy:
            return
        self.callback = callback
        self.phase = "out"
        self.t = 0.0

    def update(self, dt):
        if self.phase == "idle":
            return
        self.t += dt
        if self.phase == "out":
            p = clamp(self.t / self.duration)
            self.alpha = int(255 * ease_in_out_cubic(p))
            if p >= 1.0:
                if self.callback:
                    self.callback()
                    self.callback = None
                self.phase = "in"
                self.t = 0.0
        else:
            p = clamp(self.t / self.duration)
            self.alpha = int(255 * (1.0 - ease_in_out_cubic(p)))
            if p >= 1.0:
                self.phase = "idle"
                self.alpha = 0

    def draw(self, surface):
        if self.alpha > 0:
            if getattr(surface, "is_canvas", False):
                surface.fill_alpha((3, 5, 16), self.alpha)
                return
            self._overlay.fill((3, 5, 16, self.alpha))
            surface.blit(self._overlay, (0, 0))
