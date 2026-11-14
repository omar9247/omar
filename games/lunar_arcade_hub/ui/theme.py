"""Shared visual language: fonts, colours, panels, glows and text."""

import os

import pygame

from config import (
    WIDTH, HEIGHT, BG_TOP, BG_BOTTOM, PANEL, PANEL_LIGHT, PANEL_DARK,
    BORDER, BORDER_SOFT, WHITE, MUTED, CYAN, FONT_DIR,
)
from animations.easing import clamp, lerp_color

_font_path = None
_font_bold_path = None
_font_cache = {}
_render_cache = {}
_gradient_cache = {}
_glow_cache = {}
_shadow_cache = {}
_backdrop_cache = {}


def _locate_fonts():
    global _font_path, _font_bold_path
    if _font_path is not None:
        return
    bundled = [
        os.path.join(FONT_DIR, "SpaceGrotesk-Regular.ttf"),
        os.path.join(FONT_DIR, "SpaceGrotesk-Bold.ttf"),
    ]
    if os.path.exists(bundled[0]):
        _font_path = bundled[0]
        _font_bold_path = bundled[1] if os.path.exists(bundled[1]) else bundled[0]
        return
    candidates = [
        "Segoe UI", "Arial", "Helvetica", "DejaVu Sans",
        "Liberation Sans", "Noto Sans", "Verdana",
    ]
    for name in candidates:
        path = pygame.font.match_font(name, bold=False)
        if path:
            _font_path = path
            _font_bold_path = pygame.font.match_font(name, bold=True) or path
            return
    _font_path = ""
    _font_bold_path = ""


def get_font(size, bold=True):
    """Return a font for logical UI sizes (Canvas.text handles native)."""
    _locate_fonts()
    size = max(1, int(size))
    key = (size, bold)
    if key not in _font_cache:
        path = _font_bold_path if bold else _font_path
        if path:
            _font_cache[key] = pygame.font.Font(path, size)
        else:
            font = pygame.font.Font(None, int(size * 1.25))
            font.set_bold(bold)
            _font_cache[key] = font
    return _font_cache[key]


def render(text, size, color, bold=True):
    key = (text, size, color, bold)
    img = _render_cache.get(key)
    if img is None:
        img = get_font(size, bold).render(str(text), True, color)
        if len(_render_cache) > 900:
            _render_cache.clear()
        _render_cache[key] = img
    return img


def text(surface, content, size, color, pos, anchor="center", bold=True):
    if getattr(surface, "is_canvas", False):
        return surface.text(content, size, color, pos, anchor=anchor,
                            bold=bold)
    img = render(content, size, color, bold)
    rect = img.get_rect(**{anchor: pos})
    surface.blit(img, rect)
    return rect


def text_alpha(surface, content, size, color, pos, alpha=255,
               anchor="center", bold=True):
    alpha = int(clamp(alpha, 0, 255))
    if alpha <= 0:
        return None
    if getattr(surface, "is_canvas", False):
        return surface.text(content, size, color, pos, anchor=anchor,
                            bold=bold, alpha=alpha)
    img = render(content, size, (*color[:3],), bold).copy()
    img.set_alpha(alpha)
    rect = img.get_rect(**{anchor: pos})
    surface.blit(img, rect)
    return rect


def text_width(surface, content, size, bold=True):
    """Logical width of *content* as it will actually be rasterised."""
    if getattr(surface, "is_canvas", False):
        return surface.text_width(content, size, bold)
    return get_font(size, bold).size(str(content))[0]


def gradient_surface(size, top=BG_TOP, bottom=BG_BOTTOM):
    key = (size, top, bottom)
    if key in _gradient_cache:
        return _gradient_cache[key]
    w, h = size
    surf = pygame.Surface(size)
    for y in range(h):
        t = y / max(1, h - 1)
        pygame.draw.line(surf, lerp_color(top, bottom, t), (0, y), (w, y))
    _gradient_cache[key] = surf
    return surf


def _shadow_surface(width, height, radius):
    key = (width, height, radius)
    surf = _shadow_cache.get(key)
    if surf is None:
        surf = _soft_shadow(width, height, radius, alpha=120, pad=20, dy=5)
        if len(_shadow_cache) > 64:
            _shadow_cache.clear()
        _shadow_cache[key] = surf
    return surf


def _soft_shadow(width, height, radius, alpha=120, pad=16, dy=4, scale=4):
    """Cheap blurred shadow: draw small, then smooth-scale up."""
    sw = max(8, (width + pad * 2) // scale)
    sh = max(8, (height + pad * 2) // scale)
    small = pygame.Surface((sw, sh), pygame.SRCALPHA)
    r = max(2, radius // scale)
    x = pad // scale
    y = pad // scale + max(1, dy // scale)
    pygame.draw.rect(small, (0, 0, 0, alpha),
                     (x, y, max(4, width // scale - 2),
                      max(4, height // scale - 2)), border_radius=r)
    return pygame.transform.smoothscale(small, (width + pad * 2,
                                                height + pad * 2))


def card_shadow(width, height, radius=18, alpha=80, pad=12):
    """Cached soft shadow used by dashboard cards."""
    key = ("card", width, height, radius, alpha, pad)
    surf = _shadow_cache.get(key)
    if surf is None:
        surf = _soft_shadow(width, height, radius,
                            alpha=min(150, alpha + 30), pad=pad, dy=4)
        if len(_shadow_cache) > 64:
            _shadow_cache.clear()
        _shadow_cache[key] = surf
    return surf


def panel(surface, rect, color=PANEL, border=BORDER, radius=16, width=2,
          shadow=True):
    rect = pygame.Rect(rect)
    if shadow:
        surface.blit(_shadow_surface(rect.width, rect.height, radius),
                     (rect.x - 20, rect.y - 20))
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border and width:
        pygame.draw.rect(surface, border, rect, width=width,
                         border_radius=radius)
    return rect


def _glow_surface(radius, color, layers, strength):
    key = (int(radius), tuple(color[:3]), int(layers), round(strength, 3))
    surf = _glow_cache.get(key)
    if surf is not None:
        return surf
    radius = max(1, int(radius))
    max_r = int(radius * (1 + layers * 0.22))
    surf = pygame.Surface((max_r * 2, max_r * 2), pygame.SRCALPHA)
    for i in range(layers, 0, -1):
        r = int(radius * (1 + i * 0.22))
        add = int(255 * strength * (1 - i / (layers + 1)) * 0.6)
        if add <= 0 or r <= 0:
            continue
        layer = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        tint = tuple(min(255, int(c * add / 255)) for c in color[:3])
        pygame.draw.circle(layer, (*tint, 255), (r, r), r)
        surf.blit(layer, (max_r - r, max_r - r),
                  special_flags=pygame.BLEND_RGB_ADD)
    if len(_glow_cache) > 160:
        _glow_cache.clear()
    _glow_cache[key] = surf
    return surf


def glow(surface, center, radius, color, layers=6, strength=0.10):
    surf = _glow_surface(radius, color, layers, strength)
    max_r = surf.get_width() // 2
    surface.blit(surf, (int(center[0]) - max_r, int(center[1]) - max_r),
                 special_flags=pygame.BLEND_RGB_ADD)


def progress_bar(surface, rect, fraction, color, bg=PANEL_DARK,
                 radius=None, border=BORDER_SOFT):
    rect = pygame.Rect(rect)
    radius = rect.height // 2 if radius is None else radius
    pygame.draw.rect(surface, bg, rect, border_radius=radius)
    frac = clamp(fraction)
    if frac > 0:
        fill = pygame.Rect(rect.x, rect.y, max(rect.height, int(rect.width * frac)),
                           rect.height)
        pygame.draw.rect(surface, color, fill, border_radius=radius)
        highlight = pygame.Rect(fill.x, fill.y, fill.width,
                                max(2, fill.height // 3))
        pygame.draw.rect(surface, lerp_color(color, WHITE, 0.35), highlight,
                         border_radius=radius)
    if border:
        pygame.draw.rect(surface, border, rect, width=1, border_radius=radius)


def alpha_rect(surface, rect, color, alpha=255, radius=0):
    rect = pygame.Rect(rect)
    alpha = int(clamp(alpha, 0, 255))
    if getattr(surface, "is_canvas", False) and not radius and \
            rect.x <= 0 and rect.y <= 0 and rect.right >= WIDTH and \
            rect.bottom >= HEIGHT:
        surface.fill_alpha(color, alpha)
        return
    if getattr(surface, "is_canvas", False):
        surface.blend_rect(rect, color, alpha, radius)
        return
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (*color[:3], alpha), s.get_rect(),
                     border_radius=radius)
    surface.blit(s, rect.topleft)


def _vignette_surface():
    key = ("vignette", (WIDTH, HEIGHT))
    if key not in _gradient_cache:
        w, h = WIDTH, HEIGHT
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(40):
            alpha = int(2 + i * 1.6)
            pygame.draw.rect(s, (0, 0, 0, alpha),
                             (i * 2, i * 2, w - i * 4, h - i * 4),
                             width=2, border_radius=30)
        _gradient_cache[key] = s
    return _gradient_cache[key]


def vignette(surface):
    surface.blit(_vignette_surface(), (0, 0))


def draw_background(surface, starfield):
    if getattr(surface, "is_canvas", False):
        surface.fill_gradient(BG_TOP, BG_BOTTOM)
    # Gradient + nebula + vignette are static: compose them once and upload
    # a single (cached, pre-scaled) layer per frame instead of three.
    entry = _backdrop_cache.get(id(starfield))
    if entry is None or entry[0] is not starfield:
        bg = gradient_surface((WIDTH, HEIGHT)).copy()
        bg.blit(starfield.nebula, (0, 0))
        bg.blit(_vignette_surface(), (0, 0))
        _backdrop_cache.clear()
        _backdrop_cache[id(starfield)] = (starfield, bg)
        entry = _backdrop_cache[id(starfield)]
    surface.blit(entry[1], (0, 0))
    starfield.draw_stars(surface)
    starfield.draw_moon(surface)


def section_label(surface, label, pos, color=MUTED):
    rect = text(surface, label.upper(), 14, color, pos, anchor="midleft", bold=True)
    pygame.draw.line(surface, (*color,), (pos[0], pos[1] + 20),
                     (pos[0] + 40, pos[1] + 20), 2)
    return rect


def draw_keycap(surface, key_text, rect, color=CYAN):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, PANEL_LIGHT, rect, border_radius=8)
    pygame.draw.rect(surface, BORDER, rect, width=1, border_radius=8)
    text(surface, key_text, 14, color, rect.center)
    return rect


def wrap_lines(content, size, max_width, bold=True):
    font = get_font(size, bold)
    words = str(content).split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if font.size(candidate)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines
