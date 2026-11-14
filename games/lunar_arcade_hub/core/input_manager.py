"""Unified pointer input for mouse, touchscreen and compatible stylus devices.

pygame does not expose a dedicated pen/stylus event stream on all platforms.
Where the OS/driver reports touch (or pen) contacts as FINGER events we map
them to the same pointer events used by the mouse, including pressure when the
backend provides it. See README for the documented hardware limitation.
"""

from dataclasses import dataclass

import pygame

from config import WIDTH, HEIGHT


@dataclass
class PointerEvent:
    kind: str          # "move" | "down" | "up"
    pos: tuple
    button: int = 1
    pressure: float = 1.0
    source: str = "mouse"   # "mouse" | "touch" | "stylus"


class InputManager:
    def __init__(self, mapper=None):
        self.pos = (WIDTH // 2, HEIGHT // 2)
        self.down = False
        self.source = "mouse"
        self.pressure = 0.0
        # Converts window pixel coordinates to the logical 1200x800 grid.
        self.mapper = mapper
        self._finger_positions = {}

    def _map(self, pos):
        return self.mapper(pos) if self.mapper is not None else pos

    def process(self, events):
        out = []
        for e in events:
            if e.type == pygame.MOUSEMOTION:
                self.pos = self._map(e.pos)
                self.source = "mouse"
                out.append(PointerEvent("move", self.pos))
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.down = True
                self.pos = self._map(e.pos)
                self.source = "mouse"
                self.pressure = 1.0
                out.append(PointerEvent("down", self.pos, e.button))
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self.down = False
                self.pos = self._map(e.pos)
                out.append(PointerEvent("up", self.pos, e.button))
            elif e.type == pygame.FINGERDOWN:
                pos = (int(e.x * WIDTH), int(e.y * HEIGHT))
                pressure = float(getattr(e, "pressure", 1.0) or 1.0)
                source = "stylus" if pressure < 0.85 else "touch"
                self.down = True
                self.pos = pos
                self.source = source
                self.pressure = pressure
                self._finger_positions[e.finger_id] = pos
                out.append(PointerEvent("down", pos, 1, pressure, source))
            elif e.type == pygame.FINGERMOTION:
                pos = (int(e.x * WIDTH), int(e.y * HEIGHT))
                pressure = float(getattr(e, "pressure", 1.0) or 1.0)
                self.pos = pos
                self.pressure = pressure
                self._finger_positions[e.finger_id] = pos
                out.append(PointerEvent("move", pos, 1, pressure, self.source))
            elif e.type == pygame.FINGERUP:
                pos = self._finger_positions.pop(
                    e.finger_id, (int(e.x * WIDTH), int(e.y * HEIGHT)))
                self.down = False
                self.pos = pos
                out.append(PointerEvent("up", pos, 1,
                                        float(getattr(e, "pressure", 0.0) or 0.0),
                                        self.source))
        return out
