"""Turn a plan (list of effects with times) into frames."""
from __future__ import annotations

import sys
import time

import numpy as np
from PIL import Image

from . import fx_behind, fx_camera, fx_looks, fx_ui  # noqa: F401  (registers effects)
from .analyze import analyze
from .base import Ctx, resolve
from .draw import to_float, to_u8
from .video import Writer, frame_at, probe, read_frames

RESERVED = {'fx', 'start', 'end'}


def normalise(plan: dict, duration: float):
    specs = []
    for raw in plan.get('effects', []):
        fn, extra = resolve(raw['fx'])
        opts = dict(extra)
        opts.update({k: v for k, v in raw.items() if k not in RESERVED})
        start = float(raw.get('start', 0) or 0)
        end = float(raw.get('end', duration) or duration)
        end = min(end, duration) if duration else end
        if end <= start:
            raise ValueError(f"{raw['fx']}: end ({end}) must be after start ({start})")
        specs.append((fn, {'fx': raw['fx'], 'start': start, 'end': end, 'opts': opts}))
    # camera moves first when windows overlap, otherwise keep the plan's order
    specs.sort(key=lambda s: 0 if getattr(s[0], 'fx_layer', '') == 'camera' else 1)
    return specs


def _apply(img_u8, T, index, chain):
    img = None
    for fn, ctx in chain:
        if ctx.start <= T < ctx.end:
            if img is None:
                img = to_float(img_u8)
            img = fn(img, ctx.at(T, index))
    return img_u8 if img is None else to_u8(img)


def render(video: str, plan: dict, out: str, width: int = 1080, log=print):
    info = probe(video, width)
    an = analyze(info, log)
    chain = [(fn, Ctx(spec, info, an)) for fn, spec in normalise(plan, info.duration)]
    writer = Writer(info, out)
    t0 = time.time()
    n = max(1, info.frames)
    for i, frame in enumerate(read_frames(info)):
        writer.write(_apply(frame, i / info.fps, i, chain))
        if i % 15 == 0:
            sys.stdout.write(f'\rRendering {min(100, int(i * 100 / n))}%')
            sys.stdout.flush()
    writer.close()
    sys.stdout.write(f'\rRendered in {time.time() - t0:.0f}s -> {out}\n')


def stills(video: str, plan: dict, out_png: str, times, width: int = 1080, log=print):
    """Render single frames for quick checks. Returns the written paths."""
    info = probe(video, width)
    an = analyze(info, log)
    chain = [(fn, Ctx(spec, info, an)) for fn, spec in normalise(plan, info.duration)]
    paths = []
    base = out_png[:-4] if out_png.lower().endswith('.png') else out_png
    for T in times:
        T = min(max(0.0, T), max(0.0, info.duration - 1.0 / info.fps))
        i = int(round(T * info.fps))
        frame = frame_at(info, i / info.fps)
        img = _apply(frame, i / info.fps, i, chain)
        p = f'{base}_{T:.2f}s.png'
        Image.fromarray(img).save(p)
        paths.append(p)
    return paths
