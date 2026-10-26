"""Full looks: rooms, covers, splits and layouts built around the speaker."""
from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .base import effect
from .draw import (behind, blend, cover, fit, font, grade, grain, hexrgb, place, polyline_partial,
                   rounded, shadowed, text_sprite, vignette, zoom_at, over)
from .motion import clamp, envelope, in_out, lerp, out_back, out_cubic, seg, smooth, spring
from .ui import avatar, canvas, check, cursor, flush, pill, reel_card, u

INK = (17, 17, 19)


def _fade(e, fi=0.2, fo=0.25):
    return envelope(e.t, e.dur, fi, fo)


def _cached(e, key, make):
    if key not in e.state:
        e.state[key] = make()
    return e.state[key]


def _barcode(w, h, seed):
    im = Image.new('RGBA', (int(w), int(h)), (255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(seed)
    x = w * 0.08
    while x < w * 0.92:
        bw = rng.choice([1, 1, 2, 3]) * w / 110
        d.rectangle([x, h * 0.1, x + bw, h * 0.78], fill=(0, 0, 0, 255))
        x += bw + rng.choice([1, 2]) * w / 110
    d.text((w / 2, h * 0.9), '9 780000 042420', font=font('mono-r', h * 0.12), fill=(0, 0, 0), anchor='mm')
    return im


@effect('cover-star', 'cover', 'magazine')
def cover_star(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    editorial = e.opt('look', '') == 'editorial'
    mast = str(e.opt('text', 'VOGUE-ISH' if False else ('Muse' if editorial else 'CLAUDE')))
    col = hexrgb(e.opt('color', '#f5efe6' if editorial else '#e3242b'))
    accent = hexrgb(e.opt('accent', '#e3242b' if editorial else '#ffd400'))
    issue = str(e.opt('issue', 'ISSUE 42  ·  THE EDIT ISSUE'))
    lines = e.lines('lines', 'The 42 effects|everyone is copying|One line. Zero plugins.')
    k = _fade(e, 0.25, 0.25)
    graded = grade(img, 'soft' if editorial else 'pop')
    if editorial:
        graded = grain(graded, 0.025, e.index)
    img = blend(img, graded, k)
    fname = 'didone-r' if editorial else 'didone'

    def make_mast():
        f = fit(mast, fname, W * 0.94, W * 0.4)
        return text_sprite(mast, f, fill=col + (255,))
    ms = _cached(e, 'mast', make_mast)
    my = max(ms.height * 0.5 + u(e, 70), e.head_top + fh * 0.3 - ms.height * 0.35)
    drop = out_cubic(seg(e.t, 0, 0.45))
    img = behind(img, lambda o: place(o, ms, W / 2, my - u(e, 40) * (1 - drop), alpha=k * drop), e.mask)
    im, d = canvas(e)
    fi = font('mono-r' if not editorial else 'didone-i', u(e, 26))
    d.text((W / 2, my - ms.height * 0.5 + u(e, 4)), issue, font=fi, fill=(255, 255, 255, int(255 * k)), anchor='mm')
    img = flush(img, im)
    # cover lines down the left
    y = max(e.chin + u(e, 80), H * 0.62)
    for i, line in enumerate(lines[:3]):
        kk = out_back(seg(e.t, 0.3 + 0.12 * i, 0.6 + 0.12 * i), 1.6)
        if kk <= 0:
            continue
        if editorial:
            f = fit(line, 'didone-i' if i % 2 else 'didone-r', W * 0.55, u(e, 60))
        else:
            f = fit(line.upper(), 'display', W * 0.55, u(e, 64 if i == 0 else 46))
        txt = line if editorial else line.upper()
        fill = accent if (i == 0) else (255, 255, 255)
        spr = shadowed(text_sprite(txt, f, fill=fill + (255,)), u(e, 8), (0, int(u(e, 3))), 0.6)
        img = over(img, spr, u(e, 40) - u(e, 80) * (1 - clamp(kk)), y, k * clamp(kk * 2))
        y += f.size * 1.2
    right = e.lines('right', '') if editorial else []
    yr = H * 0.3
    for line in right[:3]:
        f = fit(line, 'didone-i', W * 0.32, u(e, 40))
        spr = text_sprite(line, f, fill=(255, 255, 255, 255))
        img = over(img, spr, W - spr.width - u(e, 30), yr, k)
        yr += f.size * 1.4
    bc = _cached(e, 'bc', lambda: _barcode(u(e, 170), u(e, 110), 4))
    return over(img, bc, W - bc.width - u(e, 40), H - bc.height - u(e, 70), k)


def _wobble(pts, rng, amp):
    return [(x + rng.uniform(-amp, amp), y + rng.uniform(-amp, amp)) for x, y in pts]


@effect('scribble', 'doodle', 'doodles')
def scribble(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    col = hexrgb(e.opt('color', '#ffd400'))
    label = str(e.opt('text', 'main character'))
    rng = e.rng(int(e.t * 8))      # re-jitter ~8x a second for a hand-drawn boil
    amp = u(e, 2.5)
    wpx = max(4, int(u(e, 10)))
    a = _fade(e, 0.05, 0.25)
    im, d = canvas(e)
    strokes = []
    # halo
    hx, hy, hr = cx, e.head_top - fh * 0.1, fw * 0.55
    strokes.append([(hx + math.cos(t) * hr, hy + math.sin(t) * hr * 0.25) for t in np.linspace(0.2, 2 * math.pi + 0.6, 40)])
    # stars on both sides
    for sx, sy, ss in ((cx - fw * 1.15, cy - fh * 0.7, fw * 0.22), (cx + fw * 1.1, cy - fh * 0.2, fw * 0.17)):
        pts = []
        for j in range(11):
            r = ss if j % 2 == 0 else ss * 0.42
            ang = -math.pi / 2 + j * math.pi / 5
            pts.append((sx + math.cos(ang) * r, sy + math.sin(ang) * r))
        strokes.append(pts)
    # emphasis ticks by the cheek
    s = e.side()
    for j in range(3):
        ang = math.radians(-35 + j * 30)
        x0 = cx + s * fw * 0.75 + s * math.cos(ang) * fw * 0.1
        y0 = cy + math.sin(ang) * fh * 0.35
        strokes.append([(x0, y0), (x0 + s * math.cos(ang) * fw * 0.25, y0 + math.sin(ang) * fw * 0.25)])
    # arrow from the label to the shoulder
    lx, ly = cx + s * W * 0.25, min(H * 0.85, e.chin + fh * 0.9)
    tx, ty = cx + s * fw * 0.8, e.chin + fh * 0.25
    arrow = [(lerp(lx, tx, q) + math.sin(q * math.pi) * s * fw * 0.3, lerp(ly - u(e, 50), ty, q)) for q in np.linspace(0, 1, 18)]
    strokes.append(arrow)
    for i, pts in enumerate(strokes):
        k = out_cubic(seg(e.t, 0.1 + i * 0.12, 0.45 + i * 0.12))
        if k <= 0:
            continue
        part = polyline_partial(_wobble(pts, rng, amp), k)
        if len(part) > 1:
            d.line(part, fill=col + (255,), width=wpx, joint='curve')
    ak = seg(e.t, 0.1 + (len(strokes) - 1) * 0.12 + 0.3, 10)
    if ak > 0:
        (ax, ay), (bx, by) = arrow[-3], arrow[-1]
        ang = math.atan2(by - ay, bx - ax)
        L = u(e, 40)
        for da in (2.6, -2.6):
            d.line([(bx, by), (bx + math.cos(ang + da) * L, by + math.sin(ang + da) * L)], fill=col + (255,), width=wpx)
    lk = smooth(seg(e.t, 0.2, 0.5))
    f = fit(label, 'marker', W * 0.5, u(e, 72))
    d.text((lx, ly), label, font=f, fill=col + (int(255 * lk),), anchor='mm')
    return flush(img, im, a)


@effect('red-collage', 'collage')
def red_collage(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    word = str(e.opt('text', 'EDIT')).upper()
    lines = e.lines('lines', 'No templates|No plugins|Just one line')
    tag = str(e.opt('tag', '@you'))
    red = (227, 36, 43)
    k = _fade(e, 0.12, 0.25)
    bw = grade(img, 'bw')
    bw = np.clip((bw - 0.5) * 1.25 + 0.5, 0, 1)

    def make_word():
        f = fit(word, 'tall', W * 0.98, H * 0.5)
        return text_sprite(word, f, fill=red + (255,), pad=0)
    ws = _cached(e, 'word', make_word)
    slam = clamp(spring(e.t, 1.8, 7), 0, 1.25)

    def lay(o):
        o = o * 0.85 + np.array([0.06, 0.06, 0.06], np.float32)
        return place(o, ws, W / 2, cy - fh * 0.3, scale=lerp(1.3, 1, slam), alpha=k)
    out = behind(bw, lay, e.mask)
    out = blend(img, out, k)
    y = max(e.chin + u(e, 90), H * 0.6)
    for i, line in enumerate(lines[:3]):
        t0 = 0.35 + 0.22 * i
        kk = seg(e.t, t0, t0 + 0.12)
        if kk <= 0:
            continue
        f = fit(line.upper(), 'display', W * 0.8, u(e, 66))
        txt = line.upper()
        tw = f.getlength(txt)
        box = rounded(int(tw + u(e, 50)), int(f.size * 1.45), 0, (0, 0, 0, 255) if i != 1 else (255, 255, 255, 255))
        ImageDraw.Draw(box).text((box.width / 2, box.height / 2), txt, font=f, fill=(255, 255, 255) if i != 1 else (0, 0, 0), anchor='mm')
        ang = (-3, 2, -1.5)[i]
        out = place(out, box, W / 2 + (-1) ** i * u(e, 30), y, scale=lerp(1.7, 1, kk ** 2), angle=ang, alpha=k * kk)
        y += f.size * 1.6
    tk = out_back(seg(e.t, 0.9, 1.2), 2)
    if tk > 0:
        p = pill(tag, font('mono', u(e, 30)), (255, 255, 255, 255), INK)
        out = place(out, p, W - p.width / 2 - u(e, 50), u(e, 160), scale=tk, angle=6, alpha=k)
    return out


@effect('split-headline', 'split')
def split_headline(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    lines = e.lines('text', 'Claude can now|edit your reels')
    hl = str(e.opt('hl', 'edit')).lower()
    tag = str(e.opt('pill', 'JUST IN'))
    k = in_out(seg(e.t, 0, 0.45)) * (1 - in_out(seg(e.t, e.dur - 0.35, e.dur)))
    if k <= 0.001:
        return img
    ch = int(H * 0.44 * k)
    # bottom: the speaker, framed on the face
    bh = H - ch
    src_y = int(clamp(cy - bh * 0.42, 0, H - bh))
    out = np.empty_like(img)
    out[int(ch):] = img[src_y:src_y + bh]
    card_h = int(H * 0.44)

    def make():
        im = Image.new('RGB', (W, card_h), (246, 244, 238))
        d = ImageDraw.Draw(im)
        p = pill(tag, font('sans-x', u(e, 30)), (227, 36, 43, 255), (255, 255, 255))
        im.paste(p, (int(u(e, 60)), int(u(e, 120))), p)
        y = u(e, 120) + p.height + u(e, 40)
        for line in lines[:3]:
            f = fit(line, 'sans-x', W - u(e, 120), u(e, 104))
            x = u(e, 60)
            for word in line.split(' '):
                ww = f.getlength(word)
                if word.lower().strip('.,!?') == hl:
                    d.rectangle([x - u(e, 8), y + f.size * 0.35, x + ww + u(e, 8), y + f.size * 1.1], fill=(255, 214, 10))
                d.text((x, y), word, font=f, fill=INK)
                x += ww + f.getlength(' ')
            y += f.size * 1.18
        return np.asarray(im, np.float32) / 255.0
    card = _cached(e, 'card', make)
    c0 = card_h - int(ch)
    out[:int(ch)] = card[c0:]
    out[int(ch):int(ch) + max(2, int(u(e, 4)))] = 0.07
    return out


@effect('pastel-word', 'pastel')
def pastel_word(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    word = str(e.opt('text', 'hello'))
    name = str(e.opt('name', 'You'))
    handle = str(e.opt('handle', '@you'))
    k = _fade(e, 0.3, 0.3)

    def room():
        top, bot = np.array([0.93, 0.9, 1.0], np.float32), np.array([0.77, 0.72, 0.95], np.float32)
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        return np.broadcast_to(top * (1 - g) + bot * g, (H, W, 3)).copy()
    bg = _cached(e, 'room', room)

    def make_word():
        f = fit(word, 'serif-i', W * 0.98, W * 0.55)
        return text_sprite(word, f, fill=(255, 255, 255, 255))
    ws = _cached(e, 'word', make_word)
    rise = out_cubic(seg(e.t, 0.1, 0.6))

    def lay(o):
        o = blend(o, bg, k)
        return place(o, ws, W / 2, cy - fh * 0.55 + u(e, 80) * (1 - rise), alpha=k * rise)
    out = behind(img, lay, e.mask)
    # profile card under the chin
    w, h = W * 0.8, u(e, 200)
    y = clamp(e.chin + u(e, 140), H * 0.55, H - h - u(e, 120))
    ck = out_back(seg(e.t, 0.35, 0.75), 1.4)
    if ck <= 0:
        return out
    pics = e.reels(1)
    av = _cached(e, 'av', lambda: avatar(pics[0], int(u(e, 120))))
    t_click = e.dur * 0.65
    done = e.t > t_click
    card = rounded(int(w), int(h), int(u(e, 40)), (255, 255, 255, 250))
    d = ImageDraw.Draw(card)
    card.alpha_composite(av, (int(u(e, 40)), int((h - av.height) / 2)))
    d.text((u(e, 185), h * 0.38), name, font=fit(name, 'sans-b', w * 0.35, u(e, 40)), fill=INK, anchor='lm')
    d.text((u(e, 185), h * 0.64), handle, font=fit(handle, 'sans', w * 0.35, u(e, 30)), fill=(120, 110, 150), anchor='lm')
    bw2, bh2 = u(e, 220), u(e, 80)
    bx, by = w - bw2 - u(e, 36), (h - bh2) / 2
    d.rounded_rectangle([bx, by, bx + bw2, by + bh2], radius=bh2 / 2, fill=(236, 233, 248) if done else (120, 92, 230))
    d.text((bx + bw2 / 2, by + bh2 / 2), 'Following' if done else 'Follow', font=font('sans-b', u(e, 32)), fill=INK if done else (255, 255, 255), anchor='mm')
    card = shadowed(card, u(e, 22), (0, int(u(e, 10))), 0.25)
    pad = (card.width - w) / 2
    x0 = (W - w) / 2
    out = place(out, card, W / 2, y + h / 2, scale=clamp(ck, 0, 1.1), alpha=k)
    # cursor taps the button
    cur, tip = _cached(e, 'cur', lambda: cursor(int(u(e, 70))))
    mk = out_cubic(seg(e.t, t_click - 0.5, t_click - 0.05))
    if 0 < mk and e.t < t_click + 0.5:
        tx, ty = x0 + bx + bw2 / 2, y + by + bh2 / 2
        px, py = lerp(W + u(e, 50), tx, mk), lerp(H, ty, mk)
        press = 0.9 if abs(e.t - t_click) < 0.08 else 1
        out = over(out, cur.resize((int(cur.width * press), int(cur.height * press))), px - tip, py - tip, k)
    return out


def _grid_paper(W, H, e):
    im = Image.new('RGB', (W, H), (250, 250, 246))
    d = ImageDraw.Draw(im)
    step = u(e, 40)
    i = 0
    x = 0.0
    while x < W:
        d.line([(x, 0), (x, H)], fill=(200, 215, 240) if i % 5 else (160, 185, 230), width=1 if i % 5 else 2)
        x += step
        i += 1
    i = 0
    y = 0.0
    while y < H:
        d.line([(0, y), (W, y)], fill=(200, 215, 240) if i % 5 else (160, 185, 230), width=1 if i % 5 else 2)
        y += step
        i += 1
    return np.asarray(im, np.float32) / 255.0


@effect('check-pills', 'pills')
def check_pills(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    items = e.lines('text', 'Face tracking|Behind the head|1080p export')
    k = _fade(e, 0.3, 0.3)
    paper = _cached(e, 'paper', lambda: _grid_paper(W, H, e))
    pics = e.reels(3)

    def boards():
        out = []
        for i, p in enumerate(pics):
            c = reel_card(p, u(e, 230), border=int(u(e, 10)), r=int(u(e, 10)))
            d = ImageDraw.Draw(c)
            out.append(shadowed(c, u(e, 10), (0, int(u(e, 6))), 0.3))
        return out
    bd = _cached(e, 'boards', boards)
    spots = [(W * 0.18, H * 0.2, -6), (W * 0.82, H * 0.18, 5), (W * 0.5, H * 0.13, -2)]

    def lay(o):
        o = blend(o, paper, k)
        for i, (x, y, r) in enumerate(spots):
            kk = out_back(seg(e.t, 0.15 + 0.1 * i, 0.5 + 0.1 * i), 1.4)
            o = place(o, bd[i], x, y, angle=r, scale=clamp(kk, 0, 1.2), alpha=k)
            im, d = canvas(e)
            d.rectangle([x - u(e, 50), y - bd[i].height * 0.45, x + u(e, 50), y - bd[i].height * 0.45 + u(e, 34)], fill=(255, 236, 160, int(200 * clamp(kk))))
            o = flush(o, im, k)
        return o
    out = behind(img, lay, e.mask)
    f = font('sans-b', u(e, 38))
    n = len(items)
    ticks = e.times('ticks', n)
    y0 = clamp(e.chin + u(e, 100), H * 0.55, H - n * u(e, 120) - u(e, 100))
    blue = (10, 102, 255)
    pos = []
    for i, it in enumerate(items):
        clicked = e.t >= ticks[i]
        txt = ('✓  ' + it) if clicked else it
        p = pill(txt, f, blue + (255,) if clicked else (255, 255, 255, 255), (255, 255, 255) if clicked else blue,
                 padx=int(u(e, 44)), pady=int(u(e, 26)))
        if not clicked:
            ImageDraw.Draw(p).rounded_rectangle([1, 1, p.width - 2, p.height - 2], radius=p.height / 2, outline=blue, width=max(2, int(u(e, 4))))
        y = y0 + i * u(e, 120)
        press = 1 - 0.08 * math.sin(math.pi * seg(e.t, ticks[i] - 0.06, ticks[i] + 0.1))
        kk = out_back(seg(e.t, 0.2 + 0.08 * i, 0.5 + 0.08 * i), 1.6)
        out = place(out, shadowed(p, u(e, 10), (0, int(u(e, 5))), 0.25), W / 2, y, scale=press * clamp(kk, 0, 1.1), alpha=k)
        pos.append((W / 2 + p.width * 0.3, y))
    cur, tip = _cached(e, 'cur', lambda: cursor(int(u(e, 64))))
    # cursor travels between the pills
    px, py = W * 0.9, H * 0.95
    for i, (tx, ty) in enumerate(pos):
        mk = in_out(seg(e.t, ticks[i] - 0.4, ticks[i] - 0.03))
        px, py = lerp(px, tx, mk), lerp(py, ty, mk)
    return over(out, cur, px - tip, py - tip, k)


@effect('timeline', 'editor', 'film')
def timeline(img, e):
    W, H = e.W, e.H
    title = str(e.opt('text', 'Director’s cut'))
    sub = str(e.opt('sub', 'scene 04 · take 2'))
    k = _fade(e, 0.25, 0.25)
    look = grade(img, 'film-red')
    look = vignette(grain(look, 0.035, e.index), 0.55)
    out = blend(img, look, k)
    im, d = canvas(e)
    a = int(255 * k)
    # REC + timecode
    tc0 = str(e.opt('tc', '01:00:00:00'))
    try:
        hh, mm, ss, ff = [int(x) for x in tc0.split(':')]
    except ValueError:
        hh, mm, ss, ff = 1, 0, 0, 0
    total = ((hh * 60 + mm) * 60 + ss) * 24 + ff + int(e.t * 24)
    tc = f'{total // 86400 % 24:02d}:{total // 1440 % 60:02d}:{total // 24 % 60:02d}:{total % 24:02d}'
    fm = font('mono', u(e, 34))
    if int(e.t * 2) % 2 == 0:
        d.ellipse([u(e, 60), u(e, 120), u(e, 88), u(e, 148)], fill=(255, 40, 40, a))
    d.text((u(e, 104), u(e, 134)), 'REC', font=fm, fill=(255, 255, 255, a), anchor='lm')
    d.text((W - u(e, 60), u(e, 134)), tc, font=fm, fill=(255, 255, 255, a), anchor='rm')
    d.text((u(e, 60), u(e, 210)), title, font=font('serif-i', u(e, 76)), fill=(255, 235, 225, a), anchor='lm')
    d.text((u(e, 62), u(e, 270)), sub, font=font('mono-r', u(e, 26)), fill=(255, 200, 190, a), anchor='lm')
    # editor panel
    ph = H * 0.2
    py = H - ph - u(e, 60)
    x0, x1 = u(e, 40), W - u(e, 40)
    d.rounded_rectangle([x0, py, x1, py + ph], radius=u(e, 24), fill=(10, 6, 6, int(205 * k)))
    fr = font('mono-r', u(e, 18))
    tx0, tx1 = x0 + u(e, 30), x1 - u(e, 30)
    for i in range(11):
        x = lerp(tx0, tx1, i / 10)
        d.line([(x, py + u(e, 22)), (x, py + u(e, 40))], fill=(255, 255, 255, int(a * 0.5)), width=2)
        d.text((x + u(e, 6), py + u(e, 30)), f'00:{i * 3:02d}', font=fr, fill=(255, 255, 255, int(a * 0.5)), anchor='lm')
    rng = e.rng(12)
    tracks = [(196, 64, 60), (120, 90, 200), (60, 170, 110)]
    th = (ph - u(e, 80)) / 3
    for j, colr in enumerate(tracks):
        ty = py + u(e, 60) + j * th
        x = tx0
        while x < tx1:
            cw = (tx1 - tx0) * rng.uniform(0.12, 0.3)
            xe = min(tx1, x + cw)
            d.rounded_rectangle([x, ty + u(e, 4), xe - u(e, 6), ty + th - u(e, 4)], radius=u(e, 8), fill=colr + (int(a * 0.85),))
            if j == 2:
                for wx in np.arange(x + u(e, 6), xe - u(e, 10), u(e, 6)):
                    amp = (th * 0.35) * abs(math.sin(wx * 0.07) * math.cos(wx * 0.013))
                    d.line([(wx, ty + th / 2 - amp), (wx, ty + th / 2 + amp)], fill=(220, 255, 230, int(a * 0.7)), width=2)
            x = xe
    hx = lerp(tx0, tx1, e.p)
    out = flush(out, im)
    glow_l = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_l)
    gd.line([(hx, py + u(e, 10)), (hx, py + ph - u(e, 10))], fill=(255, 60, 50, a), width=int(u(e, 14)))
    glow_l = glow_l.filter(ImageFilter.GaussianBlur(u(e, 10)))
    gd = ImageDraw.Draw(glow_l)
    gd.line([(hx, py + u(e, 6)), (hx, py + ph - u(e, 6))], fill=(255, 230, 220, a), width=max(2, int(u(e, 4))))
    gd.polygon([(hx - u(e, 14), py), (hx + u(e, 14), py), (hx, py + u(e, 18))], fill=(255, 230, 220, a))
    return flush(out, glow_l)


@effect('broll-split', 'broll')
def broll_split(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    tag = str(e.opt('text', '$0'))
    k = in_out(seg(e.t, 0, 0.4)) * (1 - in_out(seg(e.t, e.dur - 0.3, e.dur)))
    if k <= 0.001:
        return img
    half = H // 2
    pics = e.reels(1, 'images')
    pic = pics[0] if e.o.get('images') else e.reels(4)[2]
    base = _cached(e, 'broll', lambda: np.asarray(cover(Image.fromarray(pic).convert('RGB'), int(W * 1.12), int(half * 1.12)), np.float32) / 255.0)
    z = 1 + 0.1 * e.p
    top = cv2.resize(base, (int(W * 1.12 / 1.12 * z), int(half * z)), interpolation=cv2.INTER_LINEAR)
    oy, ox = (top.shape[0] - half) // 2, (top.shape[1] - W) // 2
    top = top[oy:oy + half, ox:ox + W]
    out = img.copy()
    src_y = int(clamp(cy - half * 0.45, 0, H - half))
    bottom = img[src_y:src_y + half]
    shift = int(half * (1 - k))
    out[:half] = img[:half]
    out[half:] = blend(img[half:], bottom, k)
    if half - shift > 0:
        out[:half - shift] = top[shift:]
    out[half - 2:half + 2] = 1.0
    # price tag sticker
    pk = out_back(seg(e.t, 0.45, 0.8), 2)
    if pk > 0:
        def make():
            f = font('display', u(e, 80))
            tw = f.getlength(tag)
            w, h = int(tw + u(e, 150)), int(u(e, 130))
            im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.polygon([(0, h / 2), (h * 0.4, 0), (w, 0), (w, h), (h * 0.4, h)], fill=(255, 214, 10, 255))
            d.ellipse([h * 0.32, h / 2 - u(e, 12), h * 0.32 + u(e, 24), h / 2 + u(e, 12)], fill=(0, 0, 0, 0))
            d.text((h * 0.45 + (w - h * 0.45) / 2, h / 2), tag, font=f, fill=INK, anchor='mm')
            return shadowed(im, u(e, 12), (0, int(u(e, 6))), 0.4)
        st = _cached(e, 'tag', make)
        out = place(out, st, W * 0.68, half * 0.72, scale=pk, angle=-9)
    return out
