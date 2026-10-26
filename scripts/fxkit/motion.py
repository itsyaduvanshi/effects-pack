"""Timing helpers: easing curves, springs and windows. All take and return floats."""
from __future__ import annotations

import math


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, t):
    return a + (b - a) * t


def seg(t, a, b):
    """Progress of t through [a, b], clamped to 0..1."""
    if b <= a:
        return 1.0 if t >= b else 0.0
    return clamp((t - a) / (b - a))


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def out_cubic(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def in_cubic(t):
    t = clamp(t)
    return t ** 3


def in_out(t):
    t = clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def out_expo(t):
    t = clamp(t)
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def out_back(t, s=1.7):
    t = clamp(t)
    return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2


def spring(t, freq=2.2, damp=6.0):
    """Damped spring from 0 to 1 with overshoot; t in seconds."""
    if t <= 0:
        return 0.0
    return 1 - math.exp(-damp * t) * math.cos(2 * math.pi * freq * t)


def envelope(t, dur, fade_in=0.25, fade_out=0.25):
    """0 -> 1 -> 0 over an effect window, using local time t in seconds."""
    a = smooth(t / fade_in) if fade_in > 0 else 1.0
    b = smooth((dur - t) / fade_out) if fade_out > 0 else 1.0
    return clamp(min(a, b))


def stagger(t, i, gap, length):
    """Progress of item i in a staggered list: item starts at i*gap, lasts length."""
    return seg(t, i * gap, i * gap + length)
