"""Frame-independent easing functions used across the hub."""

import math


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def approach(current, target, rate, dt):
    """Exponential smoothing that is independent of frame rate."""
    return target + (current - target) * math.exp(-max(0.0, rate) * dt)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    t = clamp(t)
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )


def smoothstep(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_in_quad(t):
    t = clamp(t)
    return t * t


def ease_out_quad(t):
    t = clamp(t)
    return 1 - (1 - t) * (1 - t)


def ease_out_cubic(t):
    t = clamp(t)
    return 1 - pow(1 - t, 3)


def ease_in_out_cubic(t):
    t = clamp(t)
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2


def ease_out_back(t, overshoot=1.70158):
    t = clamp(t)
    c3 = overshoot + 1
    return 1 + c3 * pow(t - 1, 3) + overshoot * pow(t - 1, 2)


def ease_out_elastic(t):
    t = clamp(t)
    if t in (0.0, 1.0):
        return t
    c4 = (2 * math.pi) / 3
    return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def pulse(t, speed=2.0):
    """Sine pulse in [0, 1]."""
    return 0.5 + 0.5 * math.sin(t * speed)
