"""Camera moves, grades and whole-frame effects."""
from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .base import effect, look
from .draw import (blend, blur, font, glow, grade, hexrgb, luma, place, polyline_partial,
                   radial, text_sprite, to_float, view_point, vignette, zoom_at, fit, over)
from .motion import clamp, envelope, in_out, lerp, out_back, out_cubic, seg, smooth, spring
from .ui import canvas, flush, u


def _hold(e, t_in, t_out):
    """1 while the effect is held, easing in and out at the ends."""
    return out_cubic(seg(e.t, 0, t_in)) * (1 - in_out(seg(e.t, e.dur - t_out, e.dur)))


@effect('locked-on', 'lock', 'lock-on', layer='camera')
def locked_on(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    z = lerp(1.0, min(2.0, e.opt('zoom', 1.35)), _hold(e, 0.5, 0.35))
    img = zoom_at(img, z, cx, cy)
    fx, fy = view_point(cx, cy, z, cx, cy, W, H)
    snap = clamp(spring(e.t - 0.08, 2.0, 7.5), 0, 1.4)
    s = lerp(1.9, 1.0, snap)
    bw, bh = fw * z * 1.5 * s, fh * z * 1.55 * s
    a = envelope(e.t, e.dur, 0.12, 0.2)
    col = hexrgb(e.opt('color', '#ffffff'))
    im, d = canvas(e)
    L, th = bw * 0.2, max(3, int(u(e, 7)))
    x0, y0, x1, y1 = fx - bw / 2, fy - bh / 2, fx + bw / 2, fy + bh / 2
    for (px, py, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(px, py + sy * L), (px, py), (px + sx * L, py)], fill=col + (255,), width=th, joint='curve')
    # thin crosshair ticks
    for k in (-1, 1):
        d.line([(fx + k * bw * 0.5, fy), (fx + k * bw * 0.42, fy)], fill=col + (180,), width=max(2, th // 2))
    tag = str(e.opt('text', 'LOCKED ON'))
    f = font('mono', u(e, 42))
    tx, ty = x0, y1 + u(e, 18)
    blink = 1 if int(e.t * 3) % 2 == 0 else 0.25
    r = u(e, 9)
    d.ellipse([tx, ty + u(e, 10), tx + r * 2, ty + u(e, 10) + r * 2], fill=(255, 59, 48, int(255 * blink)))
    d.text((tx + r * 2 + u(e, 12), ty), tag, font=f, fill=col + (255,))
    return flush(img, im, a)


@effect('lean-in', 'punch-in', 'zoom', layer='camera')
def lean_in(img, e):
    cx, cy, fw, fh = e.face
    speed = max(0.3, e.opt('speed', 1.0))
    zmax = min(2.0, e.opt('zoom', 1.45))
    k = out_back(seg(e.t, 0, 0.22 / speed), 1.4) * (1 - in_out(seg(e.t, e.dur - 0.25 / speed, e.dur)))
    return zoom_at(img, lerp(1.0, zmax, k), cx, cy - fh * 0.1)


@effect('slow-push', 'push', layer='camera')
def slow_push(img, e):
    cx, cy, fw, fh = e.face
    zmax = min(2.0, e.opt('zoom', 1.6))
    sigma = e.opt('blur', 14.0) * u(e, 1) * smooth(seg(e.t, 0, e.dur * 0.7))
    m = e.mask[..., None]
    img = blur(img, sigma) * (1 - m) + img * m
    return zoom_at(img, lerp(1.0, zmax, in_out(e.p)), cx, cy)


def _sparkles(d, e, rng, n, color, area):
    x0, y0, x1, y1 = area
    for i in range(n):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        ph = rng.uniform(0, 6.28)
        sp = rng.uniform(2, 5)
        s = u(e, rng.uniform(10, 26)) * max(0, math.sin(e.t * sp + ph)) ** 2
        if s < 1:
            continue
        a = int(255 * min(1, s / u(e, 14)))
        d.polygon([(x, y - s), (x + s * 0.22, y - s * 0.22), (x + s, y), (x + s * 0.22, y + s * 0.22),
                   (x, y + s), (x - s * 0.22, y + s * 0.22), (x - s, y), (x - s * 0.22, y - s * 0.22)],
                  fill=color + (a,))


@effect('spotlight', 'kill-the-lights', layer='camera')
def spotlight(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    k = envelope(e.t, e.dur, 0.18, 0.3)
    sparkle = e.opt('look', '') == 'sparkle'
    m = e.mask[..., None]
    col = hexrgb(e.opt('color', '#ffcf5a' if sparkle else '#ffffff'))
    dark = img * (0.08 if sparkle else 0.1) * np.array([0.9, 0.95, 1.1] if not sparkle else [1.1, 0.95, 0.8], np.float32)
    pool = radial(W, H, cx, cy + fh * 0.4, W * 0.62, 0.32, 0.0)[..., None]
    dark = dark + pool * (np.array(col, np.float32) / 255.0) * (0.35 if sparkle else 0.22)
    word = str(e.opt('text', '') or '')
    if sparkle:
        rays = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(rays)
        n = 14
        ox, oy = cx, cy - fh * 0.2
        R = H
        for i in range(n):
            a0 = i / n * 2 * math.pi + e.t * 0.25
            a1 = a0 + 0.11
            dr.polygon([(ox, oy), (ox + math.cos(a0) * R, oy + math.sin(a0) * R),
                        (ox + math.cos(a1) * R, oy + math.sin(a1) * R)], fill=col + (60,))
        rays = rays.filter(ImageFilter.GaussianBlur(u(e, 10)))
        dark = over(dark, rays)
    if word:
        f = fit(word.upper() if sparkle else word, 'display', W * 0.9, W * 0.3)
        spr = text_sprite(word.upper() if sparkle else word, f, fill=col + (255,))
        if sparkle:
            # shine band sweeps across the letters
            band = Image.new('L', spr.size, 0)
            bx = (seg(e.t, 0.3, 1.3) * 1.6 - 0.3) * spr.width
            ImageDraw.Draw(band).polygon([(bx, 0), (bx + spr.width * 0.12, 0), (bx - spr.height * 0.4 + spr.width * 0.12, spr.height),
                                          (bx - spr.height * 0.4, spr.height)], fill=200)
            band = band.filter(ImageFilter.GaussianBlur(u(e, 6)))
            white = Image.new('RGBA', spr.size, (255, 255, 240, 0))
            white.putalpha(Image.fromarray(np.minimum(np.asarray(band), np.asarray(spr.getchannel('A')))))
            spr = Image.alpha_composite(spr, white)
        spr = glow(spr, u(e, 28), col, 1.4)
        rise = out_cubic(seg(e.t, 0.1, 0.6))
        dark = place(dark, spr, W / 2, cy - fh * 1.25 + u(e, 40) * (1 - rise), alpha=rise)
    lit = img * 1.04
    if sparkle:
        halo = cv2.GaussianBlur(e.mask, (0, 0), u(e, 26))[..., None]
        dark = dark + np.clip(halo - m, 0, 1) * (np.array(col, np.float32) / 255.0) * 0.9
    out = dark * (1 - m) + lit * m
    if sparkle:
        im, d = canvas(e)
        _sparkles(d, e, e.rng(3), 40, (255, 240, 200), (0, 0, W, H * 0.8))
        out = flush(out, im)
    out = blend(img, out, k)
    push = e.opt('push', 1.08)
    return zoom_at(out, lerp(1.0, min(2.0, float(push)), in_out(e.p)), cx, cy)


look('glitter-spotlight', 'spotlight', look='sparkle')


@effect('moody', 'grade', layer='camera')
def moody(img, e):
    return blend(img, grade(img, e.opt('grade', 'moody')), envelope(e.t, e.dur, 0.3, 0.3))


@effect('swipe', 'before-after', layer='camera')
def swipe(img, e):
    W, H = e.W, e.H
    after = grade(img, e.opt('grade', 'moody'))
    x = W * in_out(seg(e.t, e.dur * 0.1, e.dur * 0.8))
    xi = int(x)
    out = img.copy()
    if xi > 0:
        out[:, :xi] = after[:, :xi]
    back = smooth(seg(e.t, e.dur - 0.2, e.dur))
    out = blend(out, img, back)
    im, d = canvas(e)
    a = int(255 * (1 - back) * smooth(seg(e.t, 0, 0.15)))
    d.line([(x, 0), (x, H)], fill=(255, 255, 255, a), width=max(3, int(u(e, 6))))
    r = u(e, 38)
    hy = H * 0.72
    d.ellipse([x - r, hy - r, x + r, hy + r], fill=(255, 255, 255, a))
    for s in (-1, 1):
        d.polygon([(x + s * r * 0.25, hy - r * 0.3), (x + s * r * 0.6, hy), (x + s * r * 0.25, hy + r * 0.3)], fill=(20, 20, 20, a))
    f = font('sans-b', u(e, 30))
    for label, lx in (('AFTER', u(e, 40)), ('BEFORE', W - u(e, 40))):
        anchor = 'lm' if lx < W / 2 else 'rm'
        tw = f.getlength(label)
        bx = lx if anchor == 'lm' else lx - tw
        d.rounded_rectangle([bx - u(e, 18), u(e, 120), bx + tw + u(e, 18), u(e, 176)], radius=u(e, 28), fill=(0, 0, 0, int(a * 0.55)))
        d.text((lx, u(e, 148)), label, font=f, fill=(255, 255, 255, a), anchor=anchor)
    return flush(out, im)


@effect('rabbit-hole', 'tunnel', layer='camera')
def rabbit_hole(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    ratio = clamp(e.opt('ratio', 0.74), 0.4, 0.92)
    speed = e.opt('speed', 0.7)
    spin = e.opt('spin', 6.0)
    k = envelope(e.t, e.dur, 0.35, 0.3)
    phase = (e.t * speed) % 1.0
    oy = cy - fh * 0.1
    rgba = np.dstack([img, np.ones((H, W, 1), np.float32)])
    out = img.copy()
    levels = 9
    for i in range(levels):
        s = (1 / ratio) ** phase * ratio ** i
        if s < 0.03:
            break
        ang = spin * (i - phase)
        M = cv2.getRotationMatrix2D((cx, oy), ang, s)
        lay = cv2.warpAffine(rgba, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        shade = 0.93 ** i
        a = lay[..., 3:4]
        # thin dark rim on each level gives the tunnel its depth
        rim = np.clip(a - cv2.erode(lay[..., 3], np.ones((7, 7), np.uint8))[..., None], 0, 1)
        out = out * (1 - a) + lay[..., :3] * shade * a
        out = out * (1 - rim * 0.6)
    m = e.mask[..., None]
    out = out * (1 - m) + img * m
    return blend(img, out, k)


@effect('dot-reveal', 'dots', layer='camera')
def dot_reveal(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    cell = max(6, int(u(e, e.opt('cell', 18))))
    snap = e.dur * 0.68
    if e.t >= snap + 0.25:
        return img
    gw, gh = W // cell + 1, H // cell + 1
    small = cv2.resize(img, (gw, gh), interpolation=cv2.INTER_AREA)
    lum = np.clip(luma(small), 0, 1)
    # dots grow outward from the face
    yy, xx = np.mgrid[:gh, :gw]
    dist = np.sqrt((xx * cell - cx) ** 2 + (yy * cell - cy) ** 2) / math.hypot(W, H)
    grow = np.clip((e.t / max(0.1, snap * 0.8) - dist * 1.3) * 2.2, 0, 1)
    rad = cell * 0.5 * (0.25 + 0.75 * np.sqrt(lum)) * grow
    radf = cv2.resize(rad.astype(np.float32), (gw * cell, gh * cell), interpolation=cv2.INTER_NEAREST)[:H, :W]
    tint = e.opt('color', None)
    if tint:
        c = np.array(hexrgb(tint), np.float32) / 255.0
        colors = (0.2 + lum[..., None] * 0.95) * c
    else:
        colors = small * 1.1
    colf = cv2.resize(colors.astype(np.float32), (gw * cell, gh * cell), interpolation=cv2.INTER_NEAREST)[:H, :W]
    py, px = np.mgrid[:H, :W]
    lx = (px % cell) - cell / 2 + 0.5
    ly = (py % cell) - cell / 2 + 0.5
    d = np.sqrt(lx * lx + ly * ly).astype(np.float32)
    a = np.clip(radf - d + 0.5, 0, 1)[..., None]
    dots = colf * a
    dots = dots + blur(dots, u(e, 8)) * 0.9
    if e.t < snap:
        return np.clip(dots, 0, 1.2)
    k = seg(e.t, snap, snap + 0.25)
    flash = (1 - k) * 0.9
    return blend(dots, img, smooth(k)) + flash


@effect('pause-point', 'pause', 'freeze', layer='camera')
def pause_point(img, e):
    W, H = e.W, e.H
    if 'still' not in e.state:
        e.state['still'] = img.copy() if e.t <= 1.5 / e.fps else to_float(e.frame(e.start))
        e.state['face'] = e.an.face(int(e.start * e.fps))
    cx, cy, fw, fh = e.state['face']
    z = lerp(1.0, 1.05, out_cubic(seg(e.t, 0, 0.4)))
    out = zoom_at(e.state['still'], z, cx, cy)
    out = blend(out, grade(out, 'soft'), 0.6)
    fx, fy = view_point(cx, cy, z, cx, cy, W, H)
    col = hexrgb(e.opt('color', '#ffd400'))
    side = -1 if fx > W / 2 else 1
    lx = e.opt('label_x', None)
    lx = float(lx) * W if lx is not None else (fx + side * W * 0.3)
    lx = clamp(lx, W * 0.2, W * 0.8)
    ly = fy + fh * 1.5
    tx, ty = fx + side * fw * 0.7, fy + fh * 0.35
    rng = e.rng(7)
    pts = []
    for i in range(24):
        s = i / 23
        bx = lerp(lx, tx, s) + math.sin(s * math.pi) * side * W * 0.1
        by = lerp(ly - u(e, 50), ty, s) + math.sin(s * math.pi) * u(e, 40)
        pts.append((bx + rng.uniform(-1.5, 1.5), by + rng.uniform(-1.5, 1.5)))
    draw = out_cubic(seg(e.t, 0.2, 0.75))
    im, d = canvas(e)
    wpx = max(4, int(u(e, 11)))
    part = polyline_partial(pts, draw)
    if len(part) > 1:
        d.line(part, fill=col + (255,), width=wpx, joint='curve')
    if draw >= 1:
        (ax, ay), (bx2, by2) = pts[-3], pts[-1]
        ang = math.atan2(by2 - ay, bx2 - ax)
        L = u(e, 42)
        for da in (2.6, -2.6):
            d.line([(bx2, by2), (bx2 + math.cos(ang + da) * L, by2 + math.sin(ang + da) * L)], fill=col + (255,), width=wpx)
    label = str(e.opt('text', 'this guy'))
    f = fit(label, 'marker', W * 0.5, u(e, 78))
    la = smooth(seg(e.t, 0.05, 0.3))
    d.text((lx, ly), label, font=f, fill=col + (int(255 * la),), anchor='mm')
    # pause badge
    bx, by, bs = u(e, 60), u(e, 120), u(e, 70)
    d.rounded_rectangle([bx, by, bx + bs * 2.6, by + bs], radius=bs / 2, fill=(0, 0, 0, 150))
    for i in range(2):
        d.rounded_rectangle([bx + bs * (0.38 + i * 0.28), by + bs * 0.27, bx + bs * (0.52 + i * 0.28), by + bs * 0.73], radius=3, fill=(255, 255, 255, 255))
    d.text((bx + bs * 1.05, by + bs / 2), 'PAUSED', font=font('mono', bs * 0.36), fill=(255, 255, 255, 255), anchor='lm')
    out = flush(out, im)
    flash = (1 - smooth(seg(e.t, 0, 0.15))) * 0.8
    return out + flash


@effect('uninstall', 'glitch', layer='camera')
def uninstall(img, e):
    W, H = e.W, e.H
    out = img.copy()
    name = str(e.opt('text', 'Old habits'))
    prog = clamp(in_out(seg(e.t, 0.15, e.dur * 0.8)) + math.sin(e.t * 17) * 0.01, 0, 1)
    failed = e.p > 0.82
    bw, bh = W * 0.78, u(e, 210)
    x0 = (W - bw) / 2
    y0 = max(e.chin + u(e, 60), H * 0.62)
    y0 = min(y0, H - bh - u(e, 120))
    im, d = canvas(e)
    a = int(255 * smooth(seg(e.t, 0, 0.15)))
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=u(e, 26), fill=(28, 28, 30, int(a * 0.94)))
    f = font('sans-b', u(e, 38))
    title = f'Couldn’t uninstall {name}' if failed else f'Uninstalling {name}…'
    d.text((x0 + u(e, 34), y0 + u(e, 62)), title, font=f, fill=(255, 255, 255, a), anchor='lm')
    pct = font('mono-r', u(e, 30))
    d.text((x0 + bw - u(e, 34), y0 + u(e, 62)), f'{int(prog * 100)}%', font=pct, fill=(170, 170, 175, a), anchor='rm')
    tx0, ty0, tw, th = x0 + u(e, 34), y0 + u(e, 120), bw - u(e, 68), u(e, 22)
    d.rounded_rectangle([tx0, ty0, tx0 + tw, ty0 + th], radius=th / 2, fill=(70, 70, 74, a))
    fill = (255, 69, 58) if failed else (10, 132, 255)
    if prog > 0.02:
        d.rounded_rectangle([tx0, ty0, tx0 + tw * prog, ty0 + th], radius=th / 2, fill=fill + (a,))
    g = smooth(seg(e.t, e.dur * 0.25, e.dur * 0.85)) * (1 - smooth(seg(e.t, e.dur - 0.12, e.dur)))
    if g <= 0.01:
        return flush(out, im)
    out = _glitch(out, e, g)
    # the dialog stays readable on top, with only a light colour split
    out = flush(out, im)
    dx = int(u(e, 6) * g)
    if dx:
        out[..., 0] = np.roll(out[..., 0], dx, axis=1)
    return out


def _glitch(out, e, g):
    W, H = e.W, e.H
    rng = np.random.default_rng(e.index * 31 + 5)
    dx = int(u(e, 22) * g)
    if dx:
        out[..., 0] = np.roll(out[..., 0], dx, axis=1)
        out[..., 2] = np.roll(out[..., 2], -dx, axis=1)
    for _ in range(int(3 + 10 * g)):
        y = int(rng.integers(0, H - 10))
        h = int(rng.integers(6, max(8, int(H * 0.05 * g) + 8)))
        out[y:y + h] = np.roll(out[y:y + h], int(rng.integers(-1, 2) * u(e, 80) * g * rng.random()), axis=1)
    for _ in range(int(4 * g)):
        bx, by = int(rng.integers(0, W - 60)), int(rng.integers(0, H - 60))
        bw2, bh2 = int(rng.integers(40, 260)), int(rng.integers(10, 80))
        blk = out[by:by + bh2, bx:bx + bw2]
        if blk.size:
            small = cv2.resize(blk, (max(1, blk.shape[1] // 12), max(1, blk.shape[0] // 6)), interpolation=cv2.INTER_AREA)
            out[by:by + bh2, bx:bx + bw2] = cv2.resize(small, (blk.shape[1], blk.shape[0]), interpolation=cv2.INTER_NEAREST)
    return out


@effect('headline-box', 'headline', layer='camera')
def headline_box(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    z = lerp(1.0, min(2.0, e.opt('zoom', 1.22)), _hold(e, 0.45, 0.3))
    img = zoom_at(img, z, cx, cy)
    lines = e.lines('text', 'This changes|everything') + ['']
    l1, l2 = lines[0], lines[1]
    _, chin_v = view_point(cx, cy + fh * 0.62, z, cx, cy, W, H)
    y = clamp(max(H * 0.68, chin_v + u(e, 60)), 0, H * 0.82)
    f1 = fit(l1, 'sans-x', W * 0.86, u(e, 84))
    f2 = fit(l2, 'sans-x', W * 0.8, u(e, 84))
    s1 = text_sprite(l1, f1, fill=(255, 255, 255, 255))
    a1 = out_cubic(seg(e.t, 0.1, 0.45))
    a2 = out_cubic(seg(e.t, 0.25, 0.6))
    fade = 1 - smooth(seg(e.t, e.dur - 0.2, e.dur))
    from .draw import shadowed, rounded
    s1 = shadowed(s1, blur=u(e, 10), offset=(0, int(u(e, 4))), opacity=0.6)
    img = place(img, s1, W / 2 - (1 - a1) * u(e, 60), y, alpha=a1 * fade)
    if l2:
        tw = f2.getlength(l2)
        box = rounded(tw + u(e, 50), f2.size * 1.35, u(e, 10), (255, 255, 255, 255))
        ImageDraw.Draw(box).text((box.width / 2, box.height / 2), l2, font=f2, fill=(12, 12, 12), anchor='mm')
        img = place(img, box, W / 2 + (1 - a2) * u(e, 60), y + f1.size * 1.25, alpha=a2 * fade)
    return img
