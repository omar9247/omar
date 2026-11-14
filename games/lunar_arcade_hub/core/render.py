"""Native-resolution rendering canvas.

The UI is authored on a fixed 1200x800 logical grid, but it is no longer
rasterised at that size and stretched by SDL (which made text soft at
non-integer window scales).  :class:`Canvas` maps logical coordinates onto the
real window surface and rasterises every piece of text at the native pixel
size, so typography stays crisp from 1280x720 up to 4K.

All drawing helpers in the project talk to ``pygame.draw`` and ``Surface.blit``
with logical coordinates.  :func:`install` wraps the ``pygame.draw`` functions
once at start-up: when they receive a Canvas the geometry is converted, while
calls that target ordinary surfaces (cached gradients, particle layers, ...)
pass straight through unchanged.
"""

import pygame

from config import WIDTH, HEIGHT

_ORIGINAL_DRAW = {}
_INSTALLED = False

_DRAW_FUNCS = ("rect", "circle", "line", "lines", "polygon", "ellipse", "arc")


def _scale_len(value, scale, minimum=0):
    if value is None or value < 0:
        return value
    return max(minimum, int(round(value * scale)))


def _scale_points(points, scale, ox=0, oy=0):
    """Map logical points to native pixels, including letterbox offsets."""
    return [(int(round(ox + x * scale)), int(round(oy + y * scale)))
            for x, y in points]


class Canvas:
    """A logical 1200x800 drawing target backed by a native window surface."""

    is_canvas = True

    def __init__(self, surface, logical=(WIDTH, HEIGHT)):
        self.logical = logical
        self.raw = surface
        self._scaled = {}          # id(source) -> (source, (w, h), scaled)
        self._seen = {}            # id(source) -> source (promotes reuse)
        self._text_cache = {}
        self._blend_cache = {}
        self._bg_cache = {}
        self._fx = None
        self.attach(surface)

    # ------------------------------------------------------------ geometry
    def attach(self, surface):
        """Point the canvas at a (possibly resized) display surface."""
        self.raw = surface
        win_w, win_h = surface.get_size()
        lw, lh = self.logical
        self.win_w, self.win_h = win_w, win_h
        if win_w <= 0 or win_h <= 0:
            self.scale = 1.0
            self.vw, self.vh = lw, lh
        else:
            self.scale = min(win_w / lw, win_h / lh)
            self.vw = max(1, min(win_w, int(round(lw * self.scale))))
            self.vh = max(1, min(win_h, int(round(lh * self.scale))))
        self.ox = max(0, (win_w - self.vw) // 2)
        self.oy = max(0, (win_h - self.vh) // 2)
        self._scaled.clear()
        self._seen.clear()
        self._text_cache.clear()
        self._blend_cache.clear()
        self._bg_cache.clear()
        self._fx = None

    def sync(self):
        """Re-attach if the display surface was resized or recreated."""
        surface = pygame.display.get_surface()
        if surface is None:
            return
        if surface is not self.raw or surface.get_size() != (self.win_w,
                                                             self.win_h):
            self.attach(surface)

    def to_physical(self, pos):
        return (self.ox + pos[0] * self.scale, self.oy + pos[1] * self.scale)

    def to_logical(self, pos):
        if self.scale <= 0:
            return tuple(pos)
        return ((pos[0] - self.ox) / self.scale,
                (pos[1] - self.oy) / self.scale)

    def map_rect(self, rect):
        rect = pygame.Rect(rect)
        x = self.ox + rect.x * self.scale
        y = self.oy + rect.y * self.scale
        w = max(0, int(round(rect.w * self.scale)))
        h = max(0, int(round(rect.h * self.scale)))
        if rect.w > 0:
            w = max(1, w)
        if rect.h > 0:
            h = max(1, h)
        return pygame.Rect(int(round(x)), int(round(y)), w, h)

    def map_point(self, point):
        return (int(round(self.ox + point[0] * self.scale)),
                int(round(self.oy + point[1] * self.scale)))

    # ------------------------------------------------------------- blitting
    def _scaled_surface(self, source, area=None):
        if area is not None:
            source = source.subsurface(area)
        if abs(self.scale - 1.0) < 1e-6:
            return source
        key = id(source)
        entry = self._scaled.get(key)
        if entry is not None and entry[0] is source and \
                entry[1] == source.get_size():
            return entry[2]
        w = max(1, int(round(source.get_width() * self.scale)))
        h = max(1, int(round(source.get_height() * self.scale)))
        scaled = pygame.transform.smoothscale(source, (w, h))
        # Only cache sources that are drawn repeatedly (gradients, glows,
        # art).  One-off effect surfaces are scaled and dropped so they do
        # not accumulate in memory.
        if self._seen.get(key) is source:
            self._scaled[key] = (source, source.get_size(), scaled)
            if len(self._scaled) > 160:
                self._scaled.pop(next(iter(self._scaled)))
        else:
            self._seen[key] = source
            if len(self._seen) > 96:
                self._seen.pop(next(iter(self._seen)))
        return scaled

    def blit(self, source, dest, area=None, special_flags=0):
        if isinstance(dest, pygame.Rect):
            x, y = dest.x, dest.y
        else:
            x, y = dest[0], dest[1]
        img = self._scaled_surface(source, area)
        px = int(round(self.ox + x * self.scale))
        py = int(round(self.oy + y * self.scale))
        return self.raw.blit(img, (px, py), special_flags=special_flags)

    def fill(self, color, rect=None, special_flags=0):
        if rect is None:
            self.raw.fill(color)
        else:
            self.raw.fill(color, self.map_rect(rect))

    def fill_alpha(self, color, alpha):
        """Blend a translucent colour over the whole window (flash/fade)."""
        alpha = max(0, min(255, int(alpha)))
        if self._fx is None or self._fx.get_size() != (self.win_w, self.win_h):
            self._fx = pygame.Surface((self.win_w, self.win_h),
                                      pygame.SRCALPHA)
        self._fx.fill((*color[:3], alpha))
        self.raw.blit(self._fx, (0, 0))

    def fill_gradient(self, top, bottom):
        """Fill letterbox areas with the same vertical gradient as the UI."""
        if self.ox == 0 and self.oy == 0:
            return
        key = (self.win_w, self.win_h, tuple(top[:3]), tuple(bottom[:3]))
        surf = self._bg_cache.get(key)
        if surf is None:
            from animations.easing import lerp_color
            surf = pygame.Surface((self.win_w, self.win_h))
            for y in range(self.win_h):
                t = y / max(1, self.win_h - 1)
                pygame.draw.line(surf, lerp_color(top, bottom, t),
                                 (0, y), (self.win_w, y))
            self._bg_cache.clear()
            self._bg_cache[key] = surf
        self.raw.blit(surf, (0, 0))

    def blend_rect(self, rect, color, alpha=255, radius=0):
        """Draw a translucent rounded rectangle without rescaling per frame."""
        rect = self.map_rect(rect)
        alpha = max(0, min(255, int(alpha)))
        radius = max(0, int(round(radius * self.scale)))
        key = (rect.w, rect.h, tuple(color[:3]), alpha, radius)
        surf = self._blend_cache.get(key)
        if surf is None:
            surf = pygame.Surface((max(1, rect.w), max(1, rect.h)),
                                  pygame.SRCALPHA)
            pygame.draw.rect(surf, (*color[:3], alpha), surf.get_rect(),
                             border_radius=radius)
            if len(self._blend_cache) > 192:
                self._blend_cache.pop(next(iter(self._blend_cache)))
            self._blend_cache[key] = surf
        self.raw.blit(surf, rect.topleft)

    # --------------------------------------------------------------- text
    def text_width(self, content, size, bold=True):
        from ui import theme
        px_size = max(9, int(round(size * self.scale)))
        return theme.get_font(px_size, bold).size(str(content))[0] / \
            self.scale

    def text(self, content, size, color, pos, anchor="center", bold=True,
             alpha=255):
        from ui import theme
        px_size = max(9, int(round(size * self.scale)))
        alpha = max(0, min(255, int(alpha)))
        key = (str(content), px_size, tuple(color[:3]), bold, alpha)
        img = self._text_cache.get(key)
        if img is None:
            img = theme.get_font(px_size, bold).render(str(content), True,
                                                       tuple(color[:3]))
            if alpha < 255:
                img = img.copy()
                img.set_alpha(alpha)
            if len(self._text_cache) > 700:
                self._text_cache.clear()
            self._text_cache[key] = img
        px, py = self.map_point(pos)
        rect = img.get_rect(**{anchor: (px, py)})
        self.raw.blit(img, rect)
        return pygame.Rect(
            int(round((rect.x - self.ox) / self.scale)),
            int(round((rect.y - self.oy) / self.scale)),
            max(1, int(round(rect.w / self.scale))),
            max(1, int(round(rect.h / self.scale))),
        )

    # ------------------------------------------------------------ drawing
    def _radius(self, radius):
        if radius is None or radius < 0:
            return radius
        return int(round(radius * self.scale))

    def _width(self, width):
        if width is None or width <= 0:
            return 0
        return max(1, int(round(width * self.scale)))

    def draw_rect(self, color, rect, width=0, **kw):
        for key in ("border_radius", "border_top_left_radius",
                    "border_top_right_radius", "border_bottom_left_radius",
                    "border_bottom_right_radius"):
            if key in kw:
                kw[key] = self._radius(kw[key])
        return _ORIGINAL_DRAW["rect"](self.raw, color, self.map_rect(rect),
                                      self._width(width), **kw)

    def draw_circle(self, color, center, radius, width=0, **kw):
        return _ORIGINAL_DRAW["circle"](
            self.raw, color, self.map_point(center),
            max(1, int(round(radius * self.scale))), self._width(width), **kw)

    def draw_line(self, color, start_pos, end_pos, width=1):
        return _ORIGINAL_DRAW["line"](
            self.raw, color, self.map_point(start_pos),
            self.map_point(end_pos), max(1, int(round(width * self.scale))))

    def draw_lines(self, color, closed, points, width=1):
        return _ORIGINAL_DRAW["lines"](
            self.raw, color, closed,
            _scale_points(points, self.scale, self.ox, self.oy),
            max(1, int(round(width * self.scale))))

    def draw_polygon(self, color, points, width=0):
        return _ORIGINAL_DRAW["polygon"](
            self.raw, color,
            _scale_points(points, self.scale, self.ox, self.oy),
            self._width(width))

    def draw_ellipse(self, color, rect, width=0):
        return _ORIGINAL_DRAW["ellipse"](
            self.raw, color, self.map_rect(rect), self._width(width))

    def draw_arc(self, color, rect, start_angle, stop_angle, width=1):
        return _ORIGINAL_DRAW["arc"](
            self.raw, color, self.map_rect(rect), start_angle, stop_angle,
            max(1, int(round(width * self.scale))))

    # ------------------------------------------------------------- helpers
    def get_size(self):
        return self.logical

    def get_width(self):
        return self.logical[0]

    def get_height(self):
        return self.logical[1]

    def get_rect(self, **kw):
        rect = pygame.Rect(0, 0, self.logical[0], self.logical[1])
        for key, value in kw.items():
            setattr(rect, key, value)
        return rect

    def save(self, path):
        pygame.image.save(self.raw, path)


# --------------------------------------------------------------- patching
def _wrap_rect(surface, color, rect, width=0, **kw):
    if isinstance(surface, Canvas):
        return surface.draw_rect(color, rect, width, **kw)
    return _ORIGINAL_DRAW["rect"](surface, color, rect, width, **kw)


def _wrap_circle(surface, color, center, radius, width=0, **kw):
    if isinstance(surface, Canvas):
        return surface.draw_circle(color, center, radius, width, **kw)
    return _ORIGINAL_DRAW["circle"](surface, color, center, radius, width, **kw)


def _wrap_line(surface, color, start_pos, end_pos, width=1):
    if isinstance(surface, Canvas):
        return surface.draw_line(color, start_pos, end_pos, width)
    return _ORIGINAL_DRAW["line"](surface, color, start_pos, end_pos, width)


def _wrap_lines(surface, color, closed, points, width=1):
    if isinstance(surface, Canvas):
        return surface.draw_lines(color, closed, points, width)
    return _ORIGINAL_DRAW["lines"](surface, color, closed, points, width)


def _wrap_polygon(surface, color, points, width=0):
    if isinstance(surface, Canvas):
        return surface.draw_polygon(color, points, width)
    return _ORIGINAL_DRAW["polygon"](surface, color, points, width)


def _wrap_ellipse(surface, color, rect, width=0):
    if isinstance(surface, Canvas):
        return surface.draw_ellipse(color, rect, width)
    return _ORIGINAL_DRAW["ellipse"](surface, color, rect, width)


def _wrap_arc(surface, color, rect, start_angle, stop_angle, width=1):
    if isinstance(surface, Canvas):
        return surface.draw_arc(color, rect, start_angle, stop_angle, width)
    return _ORIGINAL_DRAW["arc"](surface, color, rect, start_angle,
                                 stop_angle, width)


_WRAPPERS = {
    "rect": _wrap_rect,
    "circle": _wrap_circle,
    "line": _wrap_line,
    "lines": _wrap_lines,
    "polygon": _wrap_polygon,
    "ellipse": _wrap_ellipse,
    "arc": _wrap_arc,
}


def install():
    """Route pygame.draw calls that target a Canvas through its mapper."""
    global _INSTALLED
    if _INSTALLED:
        return
    for name in _DRAW_FUNCS:
        _ORIGINAL_DRAW[name] = getattr(pygame.draw, name)
        setattr(pygame.draw, name, _WRAPPERS[name])
    _INSTALLED = True
