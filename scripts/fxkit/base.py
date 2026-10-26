"""Effect registry and the per-frame context every effect receives."""
from __future__ import annotations

import os
import random
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

REGISTRY: dict = {}
ALIASES: dict = {}
LOOKS: dict = {}   # named looks: name -> (effect, extra opts)


def effect(name, *aliases, layer='overlay'):
    """Register an effect function fn(img, e) -> img.

    layer is only a hint for ordering: 'camera' effects run before others
    when windows overlap.
    """
    def deco(fn):
        fn.fx_name = name
        fn.fx_layer = layer
        REGISTRY[name] = fn
        for a in aliases:
            ALIASES[a] = name
        return fn
    return deco


def look(name, base, **opts):
    LOOKS[name] = (base, opts)


def resolve(name: str):
    name = name.strip().lower().replace('_', '-').replace(' ', '-')
    if name in LOOKS:
        base, opts = LOOKS[name]
        return REGISTRY[base], dict(opts)
    name = ALIASES.get(name, name)
    if name not in REGISTRY:
        raise KeyError(name)
    return REGISTRY[name], {}


IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.bmp'}
VIDEO_EXT = {'.mp4', '.mov', '.m4v', '.webm'}


@lru_cache(maxsize=16)
def _load_folder(folder: str):
    out = []
    for p in sorted(Path(folder).expanduser().iterdir()):
        ext = p.suffix.lower()
        try:
            if ext in IMAGE_EXT:
                out.append(np.asarray(Image.open(p).convert('RGB')))
            elif ext in VIDEO_EXT:
                from .video import probe, frame_at
                info = probe(str(p), 540)
                out.append(frame_at(info, min(1.0, info.duration / 3)))
        except Exception:
            continue
    return out


class Ctx:
    """Everything an effect can read for the current frame.

    t     local seconds since the effect started
    p     0..1 through the effect window
    T     global seconds in the video
    W, H  frame size
    face  (cx, cy, w, h) of the speaker's face
    mask  float HxW person mask (1 = person)
    o     options dict
    state per-effect dict that survives across frames
    """

    def __init__(self, spec, video, analysis):
        self.spec = spec
        self.o = dict(spec.get('opts', {}))
        for k in ('text', 'color'):
            if spec.get(k) is not None and k not in self.o:
                self.o[k] = spec[k]
        self.start = float(spec['start'])
        self.end = float(spec['end'])
        self.dur = max(0.05, self.end - self.start)
        self.video = video
        self.an = analysis
        self.W, self.H = video.width, video.height
        self.fps = video.fps
        self.state = {}
        self.seed = abs(hash((spec.get('fx'), round(self.start, 2)))) % (2 ** 31)
        self._mask = None

    # called by the renderer
    def at(self, T, index):
        self.T = T
        self.index = index
        self.t = T - self.start
        self.p = min(1.0, max(0.0, self.t / self.dur))
        self.face = self.an.face(index)
        self._mask = None
        return self

    @property
    def mask(self):
        if self._mask is None:
            self._mask = self.an.mask(self.index, self.W, self.H)
        return self._mask

    # ---- options ----
    def opt(self, key, default=None):
        v = self.o.get(key, default)
        if isinstance(default, bool) and isinstance(v, str):
            return v.lower() in ('1', 'true', 'yes', 'on')
        if isinstance(default, (int, float)) and not isinstance(default, bool) and isinstance(v, str):
            try:
                return type(default)(float(v))
            except ValueError:
                return default
        return v

    def lines(self, key='text', default=''):
        v = self.o.get(key, default)
        if isinstance(v, (list, tuple)):
            return [str(x) for x in v]
        v = str(v or '')
        return [s.strip() for s in v.split('|')] if v else []

    def pairs(self, key='text', default=''):
        """'a::b|c::d' -> [('a','b'), ('c','d')]"""
        out = []
        for item in self.lines(key, default):
            a, _, b = item.partition('::')
            out.append((a.strip(), b.strip()))
        return out

    def times(self, key, n):
        """Explicit video seconds from 'ticks', else spread across the window."""
        given = [float(x) for x in self.lines(key) if re.match(r'^-?\d+(\.\d+)?$', x)]
        if len(given) >= n:
            return [g - self.start for g in given[:n]]
        span = self.dur * 0.75
        return [self.dur * 0.15 + span * (i + 0.5) / max(1, n) for i in range(n)]

    def rng(self, salt=0):
        return random.Random(self.seed + salt)

    # ---- the speaker ----
    @property
    def head_top(self):
        cx, cy, fw, fh = self.face
        return cy - fh * 0.85

    @property
    def chin(self):
        cx, cy, fw, fh = self.face
        return cy + fh * 0.62

    def side(self):
        """+1 if there's more room on the right of the face, else -1."""
        return 1 if self.face[0] < self.W / 2 else -1

    # ---- media ----
    def reels(self, n=8, key='images'):
        """Images for reel thumbnails: the user's folder, else frames from this video."""
        folder = self.o.get(key)
        pics = []
        if folder and os.path.isdir(os.path.expanduser(str(folder))):
            pics = _load_folder(str(folder))
        if not pics:
            pics = [np.asarray(s) for s in self.an.samples]
        if not pics:
            pics = [np.full((480, 270, 3), 40, np.uint8)]
        return [pics[i % len(pics)] for i in range(n)]

    def frame(self, t_global):
        from .video import frame_at
        return frame_at(self.video, t_global)


def parse_num(s, default=0.0):
    """'197K' -> (197000, 'K', ''), '59%' -> (59, '', '%')."""
    m = re.match(r'^\s*([^\d\-.]*)(-?[\d,.]+)\s*([kKmMbB]?)\s*(.*)$', str(s))
    if not m:
        return default, '', ''
    pre, num, mult, post = m.groups()
    try:
        v = float(num.replace(',', ''))
    except ValueError:
        return default, '', ''
    return v, (pre or '') + '|' + mult.upper(), post


def fmt_num(v, like):
    pre_mult, post = like[1], like[2]
    pre, _, mult = pre_mult.partition('|')
    decimals = 1 if (mult and v < 10) else 0
    s = f'{v:,.{decimals}f}' if not mult else f'{v:.{decimals}f}'
    return f'{pre}{s}{mult}{post}'
