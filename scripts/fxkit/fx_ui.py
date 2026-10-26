"""App-style overlays: cards, buttons, lists, widgets."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .base import effect, fmt_num, parse_num
from .draw import (behind, blend, blur, cover, fit, font, hexrgb, mask_round, place, rounded,
                   shadowed, text_sprite, zoom_at, view_point, over)
from .motion import clamp, envelope, in_out, lerp, out_back, out_cubic, seg, smooth, spring
from .ui import avatar, canvas, check, cursor, flush, glass, heart, pill, reel_card, spinner, toggle, u

INK = (17, 17, 19)
BLUE = (0, 149, 246)
GREEN = (52, 199, 89)


def _fade(e, fi=0.2, fo=0.25):
    return envelope(e.t, e.dur, fi, fo)


def _cached(e, key, make):
    if key not in e.state:
        e.state[key] = make()
    return e.state[key]


def _beside(e, w, h):
    """Top-left for a card beside the head, on the roomier side."""
    cx, cy, fw, fh = e.face
    s = e.side()
    x = cx + s * (fw * 0.75) + (0 if s > 0 else -w)
    x = clamp(x, u(e, 30), e.W - w - u(e, 30))
    y = clamp(cy - h * 0.55, u(e, 120), e.H - h - u(e, 120))
    return x, y


def _under_chin(e, h):
    return clamp(e.chin + u(e, 50), e.H * 0.45, e.H - h - u(e, 90))


@effect('todo', 'to-do')
def todo(img, e):
    items = e.lines('text', 'Hook in 2 sec|Add effects|Post it')
    title = str(e.opt('title', 'Today'))
    ticks = e.times('ticks', len(items))
    w = u(e, 470)
    f = font('sans-b', u(e, 34))
    ft = font('sans-x', u(e, 40))
    lh = u(e, 74)
    h = u(e, 110) + lh * len(items) + u(e, 20)
    x, y = _beside(e, w, h)
    a = _fade(e)
    slide = out_cubic(seg(e.t, 0, 0.35))
    x += e.side() * u(e, 60) * (1 - slide)
    card = rounded(w, h, int(u(e, 30)), (255, 255, 255, 245))
    d = ImageDraw.Draw(card)
    d.text((u(e, 34), u(e, 62)), title, font=ft, fill=INK, anchor='lm')
    for i, item in enumerate(items):
        k = seg(e.t, ticks[i], ticks[i] + 0.25)
        yy = u(e, 140) + i * lh
        bs = u(e, 40)
        bx = u(e, 34)
        if k > 0:
            d.rounded_rectangle([bx, yy - bs / 2, bx + bs, yy + bs / 2], radius=u(e, 10), fill=GREEN)
            check(d, bx + bs / 2, yy, bs * 0.9, k, (255, 255, 255))
        else:
            d.rounded_rectangle([bx, yy - bs / 2, bx + bs, yy + bs / 2], radius=u(e, 10), outline=(190, 190, 196), width=max(2, int(u(e, 4))))
        col = tuple(int(lerp(c, 160, k)) for c in INK)
        tx = bx + bs + u(e, 22)
        d.text((tx, yy), item, font=f, fill=col, anchor='lm')
        if k > 0:
            d.line([(tx, yy), (tx + f.getlength(item) * k, yy)], fill=(140, 140, 146), width=max(2, int(u(e, 4))))
    card = shadowed(card, u(e, 20), (0, int(u(e, 10))), 0.3)
    pad = (card.width - w) / 2
    return over(img, card, x - pad, y - pad, a)


@effect('comment-box', 'comment')
def comment_box(img, e):
    W, H = e.W, e.H
    text = str(e.opt('text', 'EFFECTS'))
    a = _fade(e, 0.15, 0.2)
    bw, bh = W * 0.9, u(e, 120)
    x0 = (W - bw) / 2
    y0 = H - bh - u(e, 230)
    typed_end = e.dur * 0.6
    n = int(len(text) * seg(e.t, 0.3, typed_end))
    posted = e.t > typed_end + 0.25
    pk = out_back(seg(e.t, typed_end + 0.25, typed_end + 0.6), 1.5)
    pics = e.reels(1)
    av = _cached(e, 'av', lambda: avatar(pics[0], int(bh * 0.7)))
    im, d = canvas(e)
    if not posted:
        d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=bh / 2, fill=(255, 255, 255, 250))
        im.alpha_composite(av, (int(x0 + bh * 0.15), int(y0 + bh * 0.15)))
        f = font('sans-m', u(e, 40))
        tx = x0 + bh * 1.05
        shown = text[:n]
        if shown:
            d.text((tx, y0 + bh / 2), shown, font=f, fill=INK, anchor='lm')
        else:
            d.text((tx, y0 + bh / 2), 'Add a comment…', font=f, fill=(150, 150, 155), anchor='lm')
        if int(e.t * 2.5) % 2 == 0:
            cxp = tx + (f.getlength(shown) if shown else 0) + u(e, 4)
            d.line([(cxp, y0 + bh * 0.3), (cxp, y0 + bh * 0.7)], fill=BLUE, width=max(2, int(u(e, 4))))
        ready = n >= len(text)
        press = 1 - 0.1 * math.sin(math.pi * seg(e.t, typed_end, typed_end + 0.25))
        pf = font('sans-x', u(e, 38) * press)
        d.text((x0 + bw - bh * 0.4, y0 + bh / 2), 'Post', font=pf, fill=BLUE if ready else (170, 200, 240), anchor='rm')
        return flush(img, im, a)
    # posted comment floats up as a bubble
    f = font('sans-b', u(e, 34))
    fm = font('sans', u(e, 34))
    by = lerp(y0, y0 - u(e, 140), out_cubic(seg(e.t, typed_end + 0.25, typed_end + 0.7)))
    w = max(f.getlength('you'), fm.getlength(text)) + bh * 1.2 + u(e, 40)
    card = rounded(int(w), int(bh * 1.25), int(u(e, 30)), (255, 255, 255, 245))
    cd = ImageDraw.Draw(card)
    card.alpha_composite(av, (int(bh * 0.15), int(bh * 0.25)))
    cd.text((bh * 1.0, bh * 0.38), 'you  ·  now', font=font('sans-b', u(e, 28)), fill=(120, 120, 125), anchor='lm')
    cd.text((bh * 1.0, bh * 0.82), text, font=fm, fill=INK, anchor='lm')
    heart(cd, w - u(e, 40), bh * 0.62, u(e, 26), outline=(150, 150, 155), width=max(2, int(u(e, 3))))
    card = shadowed(card, u(e, 16), (0, int(u(e, 8))), 0.35)
    return place(img, card, W / 2, by + bh / 2, scale=lerp(0.8, 1, clamp(pk)), alpha=a)


@effect('tap', 'follow')
def tap(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    at = e.opt('at', None)
    t_tap = (float(at) - e.start) if at is not None else e.dur * 0.45
    x = e.opt('x', None)
    y = e.opt('y', None)
    x = float(x) * W if x is not None else W / 2
    y = float(y) * H if y is not None else min(H - u(e, 260), e.chin + u(e, 200))
    col = hexrgb(e.opt('color', '#0095f6'))
    done = e.t >= t_tap
    press = 1 - 0.1 * math.sin(math.pi * seg(e.t, t_tap - 0.08, t_tap + 0.12))
    pop = out_back(seg(e.t, 0, 0.3), 2)
    a = _fade(e, 0.01, 0.2)
    f = font('sans-b', u(e, 52))
    if done:
        b = pill('Following  ✓', f, (239, 239, 242, 255), INK, padx=int(u(e, 70)), pady=int(u(e, 30)))
    else:
        b = pill('Follow', f, col + (255,), (255, 255, 255), padx=int(u(e, 110)), pady=int(u(e, 30)))
    b = shadowed(b, u(e, 18), (0, int(u(e, 10))), 0.35)
    img = place(img, b, x, y, scale=pop * press, alpha=a)
    im, d = canvas(e)
    # finger tap ripple
    rk = seg(e.t, t_tap, t_tap + 0.45)
    if 0 < rk < 1:
        r = u(e, 30) + u(e, 140) * out_cubic(rk)
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255, int(220 * (1 - rk))), width=max(3, int(u(e, 6))))
    fk = seg(e.t, t_tap - 0.45, t_tap)
    if e.t < t_tap + 0.3 and fk > 0:
        r = u(e, 40)
        fx = lerp(x + u(e, 260), x + u(e, 40), out_cubic(fk))
        fy = lerp(y + u(e, 300), y + u(e, 30), out_cubic(fk))
        d.ellipse([fx - r, fy - r, fx + r, fy + r], fill=(255, 255, 255, 190), outline=(0, 0, 0, 60), width=2)
    return flush(img, im, a)


@effect('reject-stamp', 'stamp', 'rejected')
def reject_stamp(img, e):
    W, H = e.W, e.H
    word = str(e.opt('text', 'REJECTED')).upper()
    col = hexrgb(e.opt('color', '#e3242b'))
    ang = e.opt('angle', -12.0)
    y = e.opt('y', None)
    y = float(y) * H if y is not None else min(H * 0.8, e.chin + u(e, 230))

    def make():
        f = fit(word, 'display', W * 0.7, u(e, 150))
        tw = f.getlength(word)
        w, h = int(tw + u(e, 110)), int(f.size * 1.55)
        im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        th = int(u(e, 12))
        d.rounded_rectangle([th, th, w - th, h - th], radius=u(e, 24), outline=col + (255,), width=th)
        d.rounded_rectangle([th * 2.6, th * 2.6, w - th * 2.6, h - th * 2.6], radius=u(e, 14), outline=col + (255,), width=max(2, th // 3))
        d.text((w / 2, h / 2), word, font=f, fill=col + (255,), anchor='mm')
        # worn ink
        rng = np.random.default_rng(7)
        a = np.asarray(im.getchannel('A'), np.float32)
        noise = rng.random(a.shape)
        noise = np.asarray(Image.fromarray((noise * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6)), np.float32) / 255
        a = a * np.clip((noise - 0.3) * 3.2, 0.35, 1) * 0.92
        im.putalpha(Image.fromarray(a.astype(np.uint8)))
        return im
    stamp = _cached(e, 'stamp', make)
    k = seg(e.t, 0, 0.14)
    s = lerp(2.4, 1.0, k ** 2)
    hit = seg(e.t, 0.14, 0.4)
    shake = (1 - hit) * u(e, 14) * math.sin(e.t * 90) if e.t > 0.14 else 0
    img = zoom_at(img, 1 + 0.03 * (1 - hit) * (e.t > 0.14), W / 2, H / 2, shake=(shake, shake * 0.6))
    a = _fade(e, 0.01, 0.2) * (0.3 + 0.7 * k)
    return place(img, stamp, W / 2, y, scale=s, angle=ang, alpha=a)


@effect('checklist', 'claude-tasks')
def checklist(img, e):
    W, H = e.W, e.H
    steps = e.pairs('text', 'Find the hook::0.4s|Track the face::done|Add the effect::orbit|Render 1080p::ready')
    title = str(e.opt('title', 'Claude is editing'))
    w = W * 0.86
    lh = u(e, 88)
    h = u(e, 120) + lh * len(steps) + u(e, 16)
    y = _under_chin(e, h)
    x = (W - w) / 2
    ticks = e.times('ticks', len(steps))
    a = _fade(e)
    rise = out_cubic(seg(e.t, 0, 0.35))
    card = rounded(int(w), int(h), int(u(e, 32)), (250, 249, 245, 248))
    d = ImageDraw.Draw(card)
    # small sunburst mark
    mx, my, mr = u(e, 50), u(e, 62), u(e, 18)
    for i in range(8):
        aa = i * math.pi / 4 + e.t * 1.5
        d.line([(mx + math.cos(aa) * mr * 0.3, my + math.sin(aa) * mr * 0.3), (mx + math.cos(aa) * mr, my + math.sin(aa) * mr)],
               fill=(217, 119, 87), width=max(2, int(u(e, 5))))
    d.text((u(e, 84), my), title, font=font('sans-b', u(e, 36)), fill=INK, anchor='lm')
    f = font('sans-m', u(e, 34))
    fm = font('sans', u(e, 28))
    for i, (step, meta) in enumerate(steps):
        yy = u(e, 140) + i * lh
        start = ticks[i] - 0.55
        k = seg(e.t, ticks[i], ticks[i] + 0.22)
        bx = u(e, 52)
        r = u(e, 20)
        if k > 0:
            d.ellipse([bx - r, yy - r, bx + r, yy + r], fill=GREEN)
            check(d, bx, yy, r * 1.6, k, (255, 255, 255))
        elif e.t > start:
            spinner(d, bx, yy, r * 0.9, e.t * 400, (217, 119, 87), max(2, int(u(e, 5))))
        else:
            d.ellipse([bx - r, yy - r, bx + r, yy + r], outline=(200, 200, 205), width=max(2, int(u(e, 3))))
        col = INK if e.t > start else (150, 150, 155)
        d.text((u(e, 96), yy), step, font=f, fill=col, anchor='lm')
        if meta:
            d.text((w - u(e, 36), yy), meta, font=fm, fill=(130, 130, 136), anchor='rm')
    card = shadowed(card, u(e, 20), (0, int(u(e, 10))), 0.3)
    pad = (card.width - w) / 2
    return over(img, card, x - pad, y - pad + u(e, 50) * (1 - rise), a)


@effect('apple-toggles', 'toggles')
def apple_toggles(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    rows = e.lines('text', 'Face tracking|Behind my head|Auto zoom|Good vibes')
    col = hexrgb(e.opt('color', '#34c759'))
    ticks = e.times('ticks', len(rows))
    below = e.opt('pos', 'above') == 'below'
    w = W * 0.8
    lh = u(e, 104)
    h = lh * len(rows)
    card = rounded(int(w), int(h), int(u(e, 34)), (255, 255, 255, 250))
    d = ImageDraw.Draw(card)
    f = font('sans-m', u(e, 40))
    for i, row in enumerate(rows):
        yy = i * lh
        k = out_cubic(seg(e.t, ticks[i], ticks[i] + 0.22))
        d.text((u(e, 40), yy + lh / 2), row, font=f, fill=INK, anchor='lm')
        tw = u(e, 110)
        toggle(d, w - tw - u(e, 36), yy + (lh - tw * 0.6) / 2, tw, k, col)
        if i < len(rows) - 1:
            d.line([(u(e, 40), yy + lh), (w, yy + lh)], fill=(225, 225, 230), width=max(1, int(u(e, 2))))
    card = shadowed(card, u(e, 22), (0, int(u(e, 12))), 0.3)
    a = _fade(e)
    rise = out_cubic(seg(e.t, 0, 0.4))
    if below:
        y = _under_chin(e, h) + h / 2
        return place(img, card, W / 2, y + u(e, 60) * (1 - rise), alpha=a)
    z = lerp(1.0, min(2.0, e.opt('zoom', 1.1)), in_out(e.p))
    img = zoom_at(img, z, cx, cy)
    overlap = e.opt('overlap', 0.25)
    y = max(h / 2 + u(e, 100), e.head_top - h / 2 + fh * overlap)
    return behind(img, lambda o: place(o, card, W / 2, y - u(e, 60) * (1 - rise), alpha=a),
                  _zoomed_mask(e, z))


def _zoomed_mask(e, z):
    cx, cy, _, _ = e.face
    return zoom_at(e.mask[..., None].repeat(3, axis=2), z, cx, cy)[..., 0] if z > 1.001 else e.mask


def _graph_points(n, seed):
    rng = np.random.default_rng(seed)
    ys = np.cumsum(rng.uniform(0.2, 1.0, n))
    ys += np.sin(np.linspace(0, 6, n)) * 0.6
    ys = (ys - ys.min()) / (ys.max() - ys.min())
    return ys


def _graph(d, x0, y0, w, h, prog, col, ys, width):
    n = len(ys)
    m = max(2, int(n * prog))
    pts = [(x0 + w * i / (n - 1), y0 + h * (1 - ys[i])) for i in range(m)]
    if len(pts) >= 2:
        d.polygon(pts + [(pts[-1][0], y0 + h), (x0, y0 + h)], fill=col + (50,))
        d.line(pts, fill=col + (255,), width=width, joint='curve')
        ex, ey = pts[-1]
        r = width * 1.4
        d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(255, 255, 255, 255), outline=col + (255,), width=max(2, width // 2))


def _count(e, frm, to, k):
    v0, _, _ = parse_num(frm)
    v1, mult, post = parse_num(to)
    return fmt_num(lerp(v0, v1, k), (v1, mult, post))


@effect('liquid-glass-graph', 'graph')
def liquid_glass_graph(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    label = str(e.opt('text', 'Views this week'))
    frm, to = str(e.opt('from', '0')), str(e.opt('to', '197K'))
    col = hexrgb(e.opt('color', '#30d158'))
    bento = e.opt('look', '') == 'bento'
    ys = _cached(e, 'ys', lambda: _graph_points(40, e.seed % 1000))
    prog = in_out(seg(e.t, 0.3, e.dur * 0.85))
    a = _fade(e)
    if bento:
        return _bento(img, e, label, frm, to, col, ys, prog, a)
    w, h = W * 0.84, u(e, 420)
    x0 = (W - w) / 2
    y0 = _under_chin(e, h) + u(e, 40) * (1 - out_cubic(seg(e.t, 0, 0.4)))
    base = img.copy()
    img = glass(img, (x0, y0, x0 + w, y0 + h), int(u(e, 44)), tint_a=0.14, blur_px=u(e, 26))
    img = blend(base, img, a)
    im, d = canvas(e)
    d.text((x0 + u(e, 44), y0 + u(e, 60)), label, font=font('sans-m', u(e, 32)), fill=(255, 255, 255, 230), anchor='lm')
    d.text((x0 + u(e, 44), y0 + u(e, 140)), _count(e, frm, to, prog), font=font('sans-x', u(e, 96)), fill=(255, 255, 255, 255), anchor='lm')
    _graph(d, x0 + u(e, 44), y0 + u(e, 210), w - u(e, 88), h - u(e, 250), prog, col, ys, max(3, int(u(e, 7))))
    return flush(img, im, a)


def _bento(img, e, label, frm, to, col, ys, prog, a):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    sw, sh = W * 0.86, u(e, 520)
    sx, sy = (W - sw) / 2, max(u(e, 110), e.head_top - sh * 0.75)

    def screen(o):
        base = o.copy()
        o = glass(o, (sx, sy, sx + sw, sy + sh), int(u(e, 40)), tint=(10, 10, 14), tint_a=0.6, blur_px=u(e, 30), dark=True)
        im, d = canvas(e)
        d.text((sx + u(e, 44), sy + u(e, 64)), label, font=font('sans-m', u(e, 32)), fill=(255, 255, 255, 220), anchor='lm')
        d.text((sx + u(e, 44), sy + u(e, 150)), _count(e, frm, to, prog), font=font('sans-x', u(e, 100)), fill=(255, 255, 255, 255), anchor='lm')
        _graph(d, sx + u(e, 44), sy + u(e, 230), sw - u(e, 88), sh - u(e, 270), prog, col, ys, max(3, int(u(e, 7))))
        return blend(base, flush(o, im), a)
    img = behind(img, screen, e.mask)
    # bento tiles under the chin
    tw, th = (W * 0.86 - u(e, 40)) / 3, u(e, 280)
    ty = _under_chin(e, th)
    tiles = [('donut', e.opt('donut', '29%::retention')), ('kpi', e.opt('kpi', '672K::reach')), ('bars', e.opt('bars', '197|140|124::by week'))]
    for i, (kind, spec) in enumerate(tiles):
        val, _, lab = str(spec).partition('::')
        k = out_back(seg(e.t, 0.2 + 0.1 * i, 0.6 + 0.1 * i), 1.5)
        tx = (W - W * 0.86) / 2 + i * (tw + u(e, 20))
        yy = ty + u(e, 60) * (1 - clamp(k))
        base = img.copy()
        img = glass(img, (tx, yy, tx + tw, yy + th), int(u(e, 34)), tint_a=0.16, blur_px=u(e, 22))
        img = blend(base, img, a * clamp(k * 2))
        im, d = canvas(e)
        fl = font('sans-m', u(e, 26))
        d.text((tx + tw / 2, yy + th - u(e, 36)), lab, font=fl, fill=(255, 255, 255, 220), anchor='mm')
        if kind == 'donut':
            pct = parse_num(val)[0] / 100 * prog
            r = th * 0.3
            ccx, ccy = tx + tw / 2, yy + th * 0.42
            d.ellipse([ccx - r, ccy - r, ccx + r, ccy + r], outline=(255, 255, 255, 70), width=int(u(e, 16)))
            d.arc([ccx - r, ccy - r, ccx + r, ccy + r], -90, -90 + 360 * pct, fill=col + (255,), width=int(u(e, 16)))
            d.text((ccx, ccy), f'{int(round(parse_num(val)[0] * prog))}%', font=font('sans-x', u(e, 38)), fill=(255, 255, 255, 255), anchor='mm')
        elif kind == 'kpi':
            d.text((tx + tw / 2, yy + th * 0.42), _count(e, '0', val, prog), font=fit(val, 'sans-x', tw * 0.85, u(e, 70)), fill=(255, 255, 255, 255), anchor='mm')
        else:
            vals = [parse_num(v)[0] for v in val.split('|')] or [1]
            mx = max(vals) or 1
            bw = tw * 0.6 / len(vals)
            for j, v in enumerate(vals):
                bh = th * 0.5 * v / mx * prog
                bx = tx + tw * 0.2 + j * bw
                d.rounded_rectangle([bx + bw * 0.15, yy + th * 0.68 - bh, bx + bw * 0.85, yy + th * 0.68], radius=u(e, 8), fill=col + (255,))
        img = flush(img, im, a * clamp(k * 2))
    return img


@effect('glass-widgets', 'widgets')
def glass_widgets(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    big = str(e.opt('text', '1.2M'))
    name = str(e.opt('name', 'You'))
    handle = str(e.opt('handle', '@you'))
    simple = e.opt('look', '') == 'simple'
    a = _fade(e, 0.25, 0.25)
    t = e.t
    s = e.side()
    # widget boxes relative to the face; each bobs gently
    gw = W * 0.4
    specs = [
        ('stat', cx - s * fw * 0.6 - (gw if s > 0 else 0), cy - fh * 1.55, gw, u(e, 250)),
        ('profile', cx + s * fw * 0.65 + (0 if s > 0 else -gw), cy - fh * 0.5, gw, u(e, 260)),
        ('chart', cx - s * fw * 0.7 - (gw if s > 0 else 0), cy + fh * 0.1, gw, u(e, 300)),
        ('music', (W - W * 0.8) / 2, e.chin + u(e, 330), W * 0.8, u(e, 170)),
        ('weather', cx + s * fw * 0.6 + (0 if s > 0 else -gw * 0.8), cy - fh * 1.6, gw * 0.8, u(e, 230)),
    ]
    if simple:
        specs = specs[:3]
    pics = e.reels(2)
    av = _cached(e, 'av', lambda: avatar(pics[0], int(u(e, 110))))
    for i, (kind, x, y, w, h) in enumerate(specs):
        k = out_back(seg(t, 0.08 * i, 0.08 * i + 0.45), 1.4)
        if k <= 0:
            continue
        x = clamp(x, u(e, 24), W - w - u(e, 24))
        y = clamp(y + math.sin(t * 1.8 + i) * u(e, 8), u(e, 90), H - h - u(e, 90)) + u(e, 50) * (1 - clamp(k))
        base = img.copy()
        img = glass(img, (x, y, x + w, y + h), int(u(e, 40)), tint_a=0.18, blur_px=u(e, 24))
        img = blend(base, img, a * clamp(k * 2))
        im, d = canvas(e)
        W8 = (255, 255, 255, 255)
        if kind == 'stat':
            d.text((x + u(e, 36), y + u(e, 56)), 'Views', font=font('sans-m', u(e, 30)), fill=(255, 255, 255, 210), anchor='lm')
            d.text((x + u(e, 36), y + u(e, 150)), big, font=fit(big, 'sans-x', w - u(e, 72), u(e, 110)), fill=W8, anchor='lm')
            d.text((x + u(e, 36), y + h - u(e, 40)), '↑ 38% this week', font=font('sans-b', u(e, 26)), fill=(120, 255, 160, 255), anchor='lm')
        elif kind == 'profile':
            im.alpha_composite(av, (int(x + u(e, 30)), int(y + u(e, 30))))
            d.text((x + u(e, 160), y + u(e, 66)), name, font=fit(name, 'sans-b', w - u(e, 190), u(e, 36)), fill=W8, anchor='lm')
            d.text((x + u(e, 160), y + u(e, 112)), handle, font=fit(handle, 'sans', w - u(e, 190), u(e, 28)), fill=(255, 255, 255, 200), anchor='lm')
            fk = seg(t, e.dur * 0.5, e.dur * 0.5 + 0.2)
            bf = font('sans-b', u(e, 30))
            d.rounded_rectangle([x + u(e, 30), y + h - u(e, 92), x + w - u(e, 30), y + h - u(e, 30)], radius=u(e, 20),
                                fill=(0, 149, 246, 255) if fk < 1 else (255, 255, 255, 60))
            d.text((x + w / 2, y + h - u(e, 61)), 'Following' if fk >= 1 else 'Follow', font=bf, fill=W8, anchor='mm')
        elif kind == 'chart':
            d.text((x + u(e, 36), y + u(e, 52)), 'Watch time', font=font('sans-m', u(e, 28)), fill=(255, 255, 255, 210), anchor='lm')
            vals = [0.35, 0.5, 0.42, 0.7, 0.62, 0.9, 1.0]
            bw = (w - u(e, 72)) / len(vals)
            gk = out_cubic(seg(t, 0.3, 1.2))
            for j, v in enumerate(vals):
                bh = (h - u(e, 120)) * v * gk
                bx = x + u(e, 36) + j * bw
                d.rounded_rectangle([bx + bw * 0.18, y + h - u(e, 34) - bh, bx + bw * 0.82, y + h - u(e, 34)], radius=u(e, 8),
                                    fill=(255, 255, 255, 230 if j == len(vals) - 1 else 140))
        elif kind == 'music':
            if pics:
                cov = mask_round(cover(Image.fromarray(pics[1 % len(pics)]), int(h - u(e, 50)), int(h - u(e, 50))), int(u(e, 18)))
                im.alpha_composite(cov, (int(x + u(e, 25)), int(y + u(e, 25))))
            d.text((x + h + u(e, 10), y + u(e, 60)), 'Edited by Claude', font=font('sans-b', u(e, 32)), fill=W8, anchor='lm')
            d.text((x + h + u(e, 10), y + u(e, 104)), 'your reel · 0:' + f'{int(t) % 60:02d}', font=font('sans', u(e, 26)), fill=(255, 255, 255, 200), anchor='lm')
            px0, px1 = x + h + u(e, 10), x + w - u(e, 40)
            py = y + h - u(e, 36)
            d.rounded_rectangle([px0, py - u(e, 4), px1, py + u(e, 4)], radius=u(e, 4), fill=(255, 255, 255, 80))
            d.rounded_rectangle([px0, py - u(e, 4), px0 + (px1 - px0) * e.p, py + u(e, 4)], radius=u(e, 4), fill=W8)
        else:
            d.text((x + u(e, 32), y + u(e, 50)), 'Mumbai', font=font('sans-b', u(e, 30)), fill=W8, anchor='lm')
            d.text((x + u(e, 32), y + u(e, 130)), '31°', font=font('sans', u(e, 96)), fill=W8, anchor='lm')
            d.text((x + u(e, 32), y + h - u(e, 36)), 'Sunny · H:33°', font=font('sans-m', u(e, 24)), fill=(255, 255, 255, 210), anchor='lm')
        img = flush(img, im, a * clamp(k * 2))
    # "Edited by Claude" pill
    if not simple:
        pk = out_back(seg(t, 0.5, 0.9), 1.6)
        p = pill('✱  Edited by Claude', font('sans-b', u(e, 30)), (20, 20, 22, 200), (255, 255, 255))
        img = place(img, p, W / 2, u(e, 90), scale=clamp(pk, 0, 1.2), alpha=a)
    return img


TIER_COLORS = [(255, 127, 127), (255, 191, 127), (255, 223, 127), (191, 255, 127), (127, 191, 255)]


@effect('tier-list', 'tiers')
def tier_list(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    title = str(e.opt('title', 'AI tools tier list'))
    item = str(e.opt('item', 'Claude'))
    others = e.lines('others', 'Tool A|Tool B|Tool C|Tool D|Tool E|Tool F')
    bw = W * 0.92
    rh = u(e, 112)
    tiers = ['S', 'A', 'B', 'C', 'D']
    bh = rh * len(tiers) + u(e, 100)
    bx = (W - bw) / 2
    drop = out_back(seg(e.t, 0, 0.45), 1.2)
    by = lerp(-bh, u(e, 110), drop)
    lw = u(e, 112)
    chip_f = font('sans-b', u(e, 30))

    def chip(text, fill=(40, 40, 44, 255), fg=(255, 255, 255)):
        return pill(text, chip_f, fill, fg, padx=int(u(e, 22)), pady=int(u(e, 18)))

    def board():
        im = rounded(int(bw), int(bh), int(u(e, 26)), (24, 24, 27, 245))
        d = ImageDraw.Draw(im)
        d.text((bw / 2, u(e, 50)), title, font=fit(title, 'sans-x', bw * 0.9, u(e, 44)), fill=(255, 255, 255), anchor='mm')
        rng = e.rng(9)
        for i, tname in enumerate(tiers):
            y = u(e, 100) + i * rh
            d.rectangle([0, y, lw, y + rh - u(e, 4)], fill=TIER_COLORS[i])
            d.text((lw / 2, y + rh / 2), tname, font=font('display', u(e, 52)), fill=(20, 20, 20), anchor='mm')
        # spread the others over tiers A..D
        slots = {i: [] for i in range(len(tiers))}
        for j, o in enumerate(others):
            slots[1 + j % (len(tiers) - 1)].append(o)
        for i, lst in slots.items():
            x = lw + u(e, 18)
            y = u(e, 100) + i * rh
            for o in lst:
                c = chip(o)
                im.alpha_composite(c, (int(x), int(y + (rh - c.height) / 2)))
                x += c.width + u(e, 12)
        return im
    brd = _cached(e, 'board', board)
    a = _fade(e, 0.01, 0.25)

    def lay(o):
        return over(o, brd, bx, by, a)
    img = behind(img, lay, e.mask)
    # the item flies from below into S tier
    fly = seg(e.t, e.dur * 0.35, e.dur * 0.35 + 0.6)
    c = _cached(e, 'chip', lambda: shadowed(chip(item, (217, 119, 87, 255)), u(e, 14), (0, int(u(e, 8))), 0.5))
    tx, ty = bx + lw + u(e, 18) + c.width / 2, by + u(e, 100) + rh / 2
    sx, sy = W / 2, e.chin + u(e, 220)
    k = out_cubic(fly)
    x = lerp(sx, tx, k)
    y = lerp(sy, ty, k) - math.sin(math.pi * k) * u(e, 220)
    land = 1 + 0.25 * math.sin(math.pi * seg(e.t, e.dur * 0.35 + 0.6, e.dur * 0.35 + 0.85))
    pop = out_back(seg(e.t, 0.2, 0.45), 2)
    return place(img, c, x, y, scale=pop * land * lerp(1.3, 1, k), angle=lerp(-8, 0, k), alpha=a)


@effect('reel-frame', 'reel-card')
def reel_frame(img, e):
    W, H = e.W, e.H
    handle = str(e.opt('text', '@you'))
    k = in_out(seg(e.t, 0, 0.5)) * (1 - in_out(seg(e.t, e.dur - 0.4, e.dur)))
    if k <= 0.001:
        return img
    s = lerp(1.0, 0.72, k)
    bg = blur(img, u(e, 30)) * lerp(1, 0.45, k)
    cw, ch = int(W * s), int(H * s)
    small = np.asarray(Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((cw, ch), Image.LANCZOS))
    card = mask_round(Image.fromarray(small), int(u(e, 44) * k))
    card = shadowed(card, u(e, 30), (0, int(u(e, 16))), 0.5 * k)
    out = place(bg, card, W / 2, H / 2 - u(e, 20) * k)
    im, d = canvas(e)
    a = int(255 * smooth(seg(e.t, 0.3, 0.6)) * (1 - smooth(seg(e.t, e.dur - 0.35, e.dur))))
    if a > 0:
        x0, y0 = (W - cw) / 2, (H - ch) / 2 - u(e, 20)
        pics = e.reels(1)
        av = _cached(e, 'av', lambda: avatar(pics[0], int(u(e, 60)), ring=(255, 255, 255, 255), ring_w=int(u(e, 2))))
        avs = av.copy()
        avs.putalpha(Image.fromarray((np.asarray(av.getchannel('A')) * (a / 255)).astype(np.uint8)))
        im.alpha_composite(avs, (int(x0 + u(e, 26)), int(y0 + ch - u(e, 160))))
        d.text((x0 + u(e, 106), y0 + ch - u(e, 128)), handle, font=font('sans-b', u(e, 30)), fill=(255, 255, 255, a), anchor='lm')
        fb = font('sans-b', u(e, 24))
        d.rounded_rectangle([x0 + u(e, 120) + fb.getlength(handle) * 1.25, y0 + ch - u(e, 148), x0 + u(e, 230) + fb.getlength(handle) * 1.25, y0 + ch - u(e, 108)],
                            radius=u(e, 10), outline=(255, 255, 255, a), width=2)
        d.text((x0 + u(e, 175) + fb.getlength(handle) * 1.25, y0 + ch - u(e, 128)), 'Follow', font=fb, fill=(255, 255, 255, a), anchor='mm')
        d.text((x0 + u(e, 26), y0 + ch - u(e, 70)), 'made this with one line ✨', font=font('sans', u(e, 26)), fill=(255, 255, 255, a), anchor='lm')
        ix = x0 + cw - u(e, 56)
        for j, label in enumerate(('24.1K', '318', '1.2K')):
            iy = y0 + ch * 0.55 + j * u(e, 120)
            if j == 0:
                heart(d, ix, iy, u(e, 44), fill=(255, 48, 64, a) if e.t > e.dur * 0.55 else None, outline=(255, 255, 255, a), width=max(2, int(u(e, 4))))
            elif j == 1:
                d.ellipse([ix - u(e, 24), iy - u(e, 22), ix + u(e, 24), iy + u(e, 22)], outline=(255, 255, 255, a), width=max(2, int(u(e, 4))))
            else:
                d.polygon([(ix - u(e, 24), iy - u(e, 8)), (ix + u(e, 26), iy - u(e, 26)), (ix + u(e, 6), iy + u(e, 26)), (ix - u(e, 2), iy + u(e, 2))],
                          outline=(255, 255, 255, a), width=max(2, int(u(e, 4))))
            d.text((ix, iy + u(e, 46)), label, font=font('sans-b', u(e, 22)), fill=(255, 255, 255, a), anchor='mm')
    return flush(out, im)
