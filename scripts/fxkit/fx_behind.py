"""Effects that live behind the speaker's head."""
from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .base import effect, fmt_num, parse_num
from .draw import (behind, blend, blur, cover, fit, font, glow, hexrgb, place, rounded,
                   shadowed, text_sprite, over)
from .motion import clamp, envelope, in_out, lerp, out_back, out_cubic, seg, smooth, spring
from .ui import avatar, canvas, flush, pill, reel_card, u


def _cached(e, key, make):
    if key not in e.state:
        e.state[key] = make()
    return e.state[key]


def _fade(e, fi=0.15, fo=0.25):
    return envelope(e.t, e.dur, fi, fo)


@effect('noise', 'pile')
def noise(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    every = max(0.08, e.opt('every', 0.25))
    n = int(e.dur / every) + 1
    w = u(e, e.opt('size', 300))
    pics = e.reels(n)
    rng = e.rng(1)
    spots = []
    for i in range(n):
        ang = rng.uniform(-math.pi * 0.95, -math.pi * 0.05)
        rad = rng.uniform(0.35, 1.0) * W * 0.5
        spots.append((cx + math.cos(ang) * rad * 1.1, cy - fh * 0.3 + math.sin(ang) * rad * 0.9,
                      rng.uniform(-14, 14)))
    cards = _cached(e, 'cards', lambda: [shadowed(reel_card(p, w, border=int(u(e, 7))), u(e, 16), (0, int(u(e, 8))), 0.45) for p in pics])
    fade = _fade(e, 0.01, 0.25)

    def lay(o):
        for i in range(n):
            ti = i * every
            if e.t < ti:
                break
            k = out_back(seg(e.t, ti, ti + 0.22), 2.0)
            x, y, r = spots[i]
            o = place(o, cards[i], x, y, scale=lerp(0.4, 1.0, k), angle=r, alpha=min(1, k * 2) * fade)
        return o
    return behind(img, lay, e.mask)


@effect('lineup', 'tiles')
def lineup(img, e):
    cx, cy, fw, fh = e.face
    W = e.W
    labels = e.lines('text', '1|2|3|4|5')
    n = len(labels)
    pics = e.reels(n)
    tw = u(e, 190)
    th = tw * 1.3
    R = max(fh * 1.45, W * 0.36)
    oy = cy + fh * 0.15

    def make():
        out = []
        for i, (pic, lab) in enumerate(zip(pics, labels)):
            c = reel_card(pic, tw, border=int(u(e, 6)), r=int(u(e, 18))).resize((int(tw), int(th)))
            d = ImageDraw.Draw(c)
            r = u(e, 34)
            d.ellipse([u(e, 14), u(e, 14), u(e, 14) + r * 2, u(e, 14) + r * 2], fill=(255, 255, 255))
            num = str(i + 1)
            d.text((u(e, 14) + r, u(e, 14) + r), num, font=font('display', r * 1.1), fill=(15, 15, 15), anchor='mm')
            if lab and lab != num:
                f = fit(lab, 'sans-b', tw * 0.84, u(e, 34))
                d.rounded_rectangle([u(e, 10), th - f.size * 1.9, tw - u(e, 10), th - u(e, 10)], radius=u(e, 12), fill=(0, 0, 0, 170))
                d.text((tw / 2, th - f.size * 1.05 - u(e, 5)), lab, font=f, fill=(255, 255, 255), anchor='mm')
            out.append(shadowed(c, u(e, 14), (0, int(u(e, 8))), 0.4))
        return out
    cards = _cached(e, 'cards', make)
    spread = math.radians(min(70, 18 * (n - 1) / 2 + 10))
    fade = _fade(e, 0.01, 0.25)

    def lay(o):
        for i in range(n):
            a = -spread + 2 * spread * i / max(1, n - 1)
            k = out_back(seg(e.t, 0.08 * i, 0.08 * i + 0.45), 1.6)
            x = cx + R * math.sin(a) * k
            y = oy - R * math.cos(a) * k
            o = place(o, cards[i], x, y, scale=lerp(0.3, 1, clamp(k, 0, 1.2)), angle=-math.degrees(a) * 0.6,
                      alpha=clamp(k * 3) * fade)
        return o
    return behind(img, lay, e.mask)


@effect('orbit', 'circle')
def orbit(img, e):
    cx, cy, fw, fh = e.face
    W = e.W
    n = max(3, int(e.opt('count', 6)))
    w = u(e, e.opt('size', 200))
    speed = e.opt('speed', 0.32)
    pics = e.reels(n)
    cards = _cached(e, 'cards', lambda: [shadowed(reel_card(p, w, border=int(u(e, 5))), u(e, 12), (0, int(u(e, 6))), 0.4) for p in pics])
    rx, ry = W * 0.42, fh * 0.72
    oy = cy + fh * 0.32
    fade = _fade(e, 0.3, 0.3)
    items = []
    for i in range(n):
        a = 2 * math.pi * i / n + 2 * math.pi * speed * e.t
        depth = math.sin(a)
        items.append((depth, cx + rx * math.cos(a), oy + ry * depth, i))
    items.sort()
    grow = out_back(seg(e.t, 0, 0.5), 1.4)

    def draw(o, front):
        for depth, x, y, i in items:
            if (depth > 0) != front:
                continue
            s = (0.72 + 0.32 * (depth + 1) / 2) * grow
            o = place(o, cards[i], x, y, scale=s, angle=-depth * 4, alpha=fade * (0.7 + 0.3 * (depth + 1) / 2))
        return o
    img = behind(img, lambda o: draw(o, False), e.mask)
    return draw(img, True)


@effect('backdrop-word', 'word', 'big-word')
def backdrop_word(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    word = str(e.opt('text', 'EFFECTS'))
    serif = e.opt('font', 'bold') == 'serif'
    col = hexrgb(e.opt('color', '#ffffff'))

    def make():
        f = fit(word if serif else word.upper(), 'serif' if serif else 'display', W * 0.96, W * 0.42)
        return shadowed(text_sprite(word if serif else word.upper(), f, fill=col + (255,)), u(e, 20), (0, int(u(e, 10))), 0.35)
    spr = _cached(e, 'spr', make)
    k = clamp(spring(e.t, 1.6, 6.5), 0, 1.3)
    y = cy - fh * 0.75 - (1 - k) * H * 0.35
    fade = _fade(e, 0.08, 0.25)
    return behind(img, lambda o: place(o, spr, W / 2, y, alpha=fade), e.mask)


def _keycap(label, w, e):
    f = font('sans-b', w * (0.36 if len(label) <= 2 else 0.22))
    kw = w * (1.0 if len(label) <= 2 else 1.6)
    h = w
    im = Image.new('RGBA', (int(kw), int(h * 1.12)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = w * 0.18
    d.rounded_rectangle([0, h * 0.12, kw - 1, h * 1.12 - 1], radius=r, fill=(170, 170, 176, 255))
    d.rounded_rectangle([0, 0, kw - 1, h - 1], radius=r, fill=(246, 246, 248, 255))
    d.rounded_rectangle([w * 0.08, w * 0.06, kw - w * 0.08, h - w * 0.14], radius=r * 0.8, fill=(255, 255, 255, 255))
    d.text((kw / 2, h * 0.45), label, font=f, fill=(30, 30, 34), anchor='mm')
    return shadowed(im, int(u(e, 10)), (0, int(u(e, 6))), 0.35)


@effect('shortcut-rain', 'rain', 'keys')
def shortcut_rain(img, e):
    W, H = e.W, e.H
    labels = e.lines('text', 'cmd|C|V|Z|shift|opt|S|A|tab|esc|R|K')
    n = max(4, int(e.opt('count', 18)))
    w = u(e, 130)
    rng = e.rng(2)
    keys = _cached(e, 'keys', lambda: {lab: _keycap(lab, w, e) for lab in set(labels)})
    drops = []
    for i in range(n):
        drops.append((i / n * e.dur * 0.75, rng.uniform(0.05, 0.95) * W, rng.uniform(-30, 30),
                      rng.uniform(-90, 90), rng.uniform(0.85, 1.15), labels[i % len(labels)], rng.uniform(0.3, 0.6) * H))
    fade = _fade(e, 0.01, 0.3)
    g = H * 1.6

    def lay(o):
        for t0, x, r0, spin, s, lab, v0 in drops:
            dt = e.t - t0
            if dt < 0:
                continue
            y = -w + v0 * dt + 0.5 * g * dt * dt
            if y > H + w:
                continue
            o = place(o, keys[lab], x, y, scale=s, angle=r0 + spin * dt, alpha=fade)
        return o
    return behind(img, lay, e.mask)


def _flip_card(digit, w, h, e):
    im = rounded(w, h, int(w * 0.12), (24, 24, 26, 255))
    d = ImageDraw.Draw(im)
    d.text((w / 2, h / 2), str(digit), font=font('tall', h * 0.82), fill=(245, 245, 245), anchor='mm')
    d.line([(0, h / 2), (w, h / 2)], fill=(0, 0, 0, 255), width=max(2, int(u(e, 5))))
    return im


@effect('countdown-flip', 'countdown', 'flip-clock')
def countdown_flip(img, e):
    cx, cy, fw, fh = e.face
    W = e.W
    start = max(1, int(e.opt('from', 3)))
    cw, ch = u(e, 300), u(e, 380)
    cards = _cached(e, 'cards', lambda: {d: _flip_card(d, int(cw), int(ch), e) for d in range(0, start + 1)})
    step = e.dur / start
    idx = min(start - 1, int(e.t / step))
    cur = start - idx
    prev = cur + 1 if idx > 0 else None
    lt = e.t - idx * step
    flip = seg(lt, 0, 0.32)
    x, y = cx, max(ch / 2 + u(e, 70), e.head_top - ch * 0.15)
    grow = out_back(seg(e.t, 0, 0.3))
    fade = _fade(e, 0.01, 0.2)

    def composite():
        new = cards[cur]
        if prev is None or flip >= 1:
            return new
        old = cards[prev]
        out = Image.new('RGBA', new.size, (0, 0, 0, 0))
        hh = new.height // 2
        out.paste(new.crop((0, 0, new.width, hh)), (0, 0))
        out.paste(old.crop((0, hh, new.width, new.height)), (0, hh))
        if flip < 0.5:
            s = 1 - flip * 2
            top = old.crop((0, 0, new.width, hh)).resize((new.width, max(1, int(hh * s))))
            shade = Image.new('RGBA', top.size, (0, 0, 0, int(120 * (1 - s))))
            top = Image.alpha_composite(top, shade)
            out.alpha_composite(top, (0, hh - top.height))
        else:
            s = (flip - 0.5) * 2
            bot = new.crop((0, hh, new.width, new.height)).resize((new.width, max(1, int(hh * s))))
            out.alpha_composite(bot, (0, hh))
        return out
    spr = shadowed(composite(), u(e, 18), (0, int(u(e, 10))), 0.5)
    return behind(img, lambda o: place(o, spr, x, y, scale=grow, alpha=fade), e.mask)


@effect('carousel-spin', 'carousel')
def carousel_spin(img, e):
    cx, cy, fw, fh = e.face
    W = e.W
    n = max(4, int(e.opt('count', 8)))
    w = u(e, e.opt('size', 210))
    turns = e.opt('turns', 1.25)
    pics = e.reels(n)
    cards = _cached(e, 'cards', lambda: [reel_card(p, w, border=int(u(e, 5))) for p in pics])
    R = W * 0.44
    ang = turns * 2 * math.pi * (1 - (1 - e.p) ** 2.4)
    fade = _fade(e, 0.25, 0.25)
    ch = w * 16 / 9
    items = []
    for i in range(n):
        a = 2 * math.pi * i / n + ang
        z = math.cos(a)
        x = cx + R * math.sin(a)
        y = lerp(cy - fh * 0.2, e.chin + ch * 0.62, (z + 1) / 2)
        items.append((z, x, y, i, a))
    items.sort()

    def draw(o, front):
        for z, x, y, i, a in items:
            if (z > 0) != front:
                continue
            c = cards[i]
            sq = max(0.1, abs(math.cos(a)) ** 0.8)
            s = 0.75 + 0.3 * (z + 1) / 2
            spr = c.resize((max(2, int(c.width * sq * s)), max(2, int(c.height * s))), Image.BICUBIC)
            if z < 0:
                spr = Image.alpha_composite(spr, Image.new('RGBA', spr.size, (0, 0, 0, int(90 * -z))))
                spr.putalpha(Image.fromarray(np.asarray(c.getchannel('A').resize(spr.size))))
            o = place(o, spr, x, y, alpha=fade)
        return o
    img = behind(img, lambda o: draw(o, False), e.mask)
    return draw(img, True)


def _phone(pic, w, e):
    h = w * 2.05
    b = int(w * 0.045)
    im = rounded(int(w), int(h), int(w * 0.16), (18, 18, 20, 255))
    scr = reel_card(pic, w - b * 2, r=int(w * 0.13)).resize((int(w - b * 2), int(h - b * 2)))
    im.alpha_composite(scr, (b, b))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([w * 0.36, b + w * 0.04, w * 0.64, b + w * 0.11], radius=w * 0.035, fill=(0, 0, 0, 255))
    return shadowed(im, u(e, 18), (0, int(u(e, 10))), 0.5)


@effect('phone-fan', 'phones')
def phone_fan(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    n = 5
    pics = e.reels(n)
    pw = u(e, 230)
    phones = _cached(e, 'phones', lambda: [_phone(p, pw, e) for p in pics])
    px, py = cx, cy + fh * 1.9
    L = fh * 1.6 + pw * 0.4
    fade = _fade(e, 0.01, 0.25)
    open_ = out_back(seg(e.t, 0.05, 0.6), 1.3)

    def lay(o):
        order = [0, 4, 1, 3, 2]
        for i in order:
            a = math.radians((-46 + 23 * i) * open_)
            x = px + L * math.sin(a)
            y = py - L * math.cos(a)
            o = place(o, phones[i], x, y, angle=-math.degrees(a), alpha=fade * clamp(open_ * 3))
        return o
    img = behind(img, lay, e.mask)
    lines = e.lines('text', 'Every reel|this month')
    y = u(e, 150)
    for j, line in enumerate(lines[:2]):
        f = fit(line, 'display', W * 0.88, u(e, 92))
        spr = shadowed(text_sprite(line, f, fill=(255, 255, 255, 255)), u(e, 12), (0, int(u(e, 4))), 0.6)
        k = out_cubic(seg(e.t, 0.1 + 0.1 * j, 0.5 + 0.1 * j))
        img = place(img, spr, W / 2, y + u(e, 40) * (1 - k), alpha=k * fade)
        y += f.size * 1.15
    return img


def _wrap(text, fnt, max_w):
    words, lines, cur = text.split(), [], ''
    for wd in words:
        t = (cur + ' ' + wd).strip()
        if fnt.getlength(t) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def _headline_card(title, meta, w, e):
    f = font('sans-x', u(e, 44))
    fm = font('sans-m', u(e, 26))
    lines = _wrap(title, f, w - u(e, 60))[:3]
    h = u(e, 40) + len(lines) * f.size * 1.2 + (fm.size * 1.8 if meta else 0) + u(e, 30)
    im = rounded(int(w), int(h), int(u(e, 22)), (255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    y = u(e, 36)
    if meta:
        d.text((u(e, 30), y), meta.upper(), font=fm, fill=(200, 30, 40))
        y += fm.size * 1.8
    for line in lines:
        d.text((u(e, 30), y), line, font=f, fill=(15, 15, 18))
        y += f.size * 1.2
    return shadowed(im, u(e, 16), (0, int(u(e, 8))), 0.4)


@effect('headline-wall', 'headlines')
def headline_wall(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    items = e.pairs('text', 'I edit reels with Claude now::@you|42 effects in one line::Reels|My views tripled::Insights|No more manual keyframes::Workflow')
    cards = _cached(e, 'cards', lambda: [_headline_card(t, m, W * 0.6, e) for t, m in items])
    rng = e.rng(4)
    n = len(items)
    spots = [(lerp(W * 0.3, W * 0.7, rng.random()), lerp(H * 0.12, cy - fh * 0.2, rng.random()), rng.uniform(-9, 9)) for _ in items]
    gap = e.dur * 0.55 / max(1, n)
    fade = _fade(e, 0.01, 0.25)

    def lay(o):
        for i in range(n):
            k = out_back(seg(e.t, i * gap, i * gap + 0.3), 1.8)
            if k <= 0:
                continue
            x, y, r = spots[i]
            o = place(o, cards[i], x, y, scale=lerp(1.4, 1, clamp(k, 0, 1)), angle=r, alpha=clamp(k * 2) * fade)
        return o
    img = behind(img, lay, e.mask)
    total = str(e.opt('total', '') or '')
    if total:
        label = str(e.opt('label', 'total views'))
        k = out_back(seg(e.t, e.dur * 0.62, e.dur * 0.62 + 0.35), 2.2)
        if k > 0:
            f = font('display', u(e, 96))
            fl = font('sans-b', u(e, 32))
            w = max(f.getlength(total), fl.getlength(label)) + u(e, 90)
            card = rounded(int(w), int(u(e, 200)), int(u(e, 36)), (255, 214, 10, 255))
            d = ImageDraw.Draw(card)
            d.text((w / 2, u(e, 82)), total, font=f, fill=(10, 10, 10), anchor='mm')
            d.text((w / 2, u(e, 158)), label, font=fl, fill=(10, 10, 10), anchor='mm')
            card = shadowed(card, u(e, 18), (0, int(u(e, 10))), 0.45)
            y = min(H - u(e, 220), e.chin + u(e, 170))
            img = place(img, card, W / 2, y, scale=k, angle=-3, alpha=fade)
    return img


PAGE_STYLES = [
    ((250, 248, 242), (20, 20, 20), 'THE DAILY WIRE'),
    ((236, 230, 214), (30, 25, 20), 'Tech Chronicle'),
    ((18, 18, 20), (240, 240, 240), 'NIGHT EDITION'),
    ((255, 255, 255), (200, 20, 30), 'BREAKING'),
    ((232, 238, 244), (20, 40, 70), 'The Ledger'),
]


def _news_page(i, word, e, word_box):
    W, H = e.W, e.H
    bg, ink, mast = PAGE_STYLES[i % len(PAGE_STYLES)]
    im = Image.new('RGB', (W, H), bg)
    d = ImageDraw.Draw(im)
    rng = e.rng(100 + i)
    mf = font('didone' if i % 2 == 0 else 'display', u(e, 92))
    d.text((W / 2, u(e, 110)), mast, font=mf, fill=ink, anchor='mm')
    d.line([(u(e, 50), u(e, 180)), (W - u(e, 50), u(e, 180))], fill=ink, width=int(u(e, 4)))
    d.text((u(e, 50), u(e, 200)), f'VOL. {rng.randint(10, 99)}  ·  No. {rng.randint(100, 999)}', font=font('mono-r', u(e, 22)), fill=ink)
    grey = tuple(int(c * 0.55 + b * 0.45) for c, b in zip(ink, bg))
    cols = 3
    gw = (W - u(e, 100)) / cols
    for c in range(cols):
        x0 = u(e, 50) + c * gw + u(e, 12)
        y = u(e, 260) + rng.uniform(0, u(e, 60))
        while y < H - u(e, 60):
            if rng.random() < 0.12:
                d.rectangle([x0, y, x0 + gw - u(e, 24), y + u(e, 180)], fill=tuple(int(v * 0.85) for v in grey))
                y += u(e, 200)
                continue
            lw = (gw - u(e, 24)) * rng.uniform(0.7, 1.0)
            d.rectangle([x0, y, x0 + lw, y + u(e, 9)], fill=grey)
            y += u(e, 22)
    # headline line holding the word
    x0, y0, x1, y1 = word_box
    d.rectangle([u(e, 40), y0 - u(e, 30), W - u(e, 40), y1 + u(e, 30)], fill=bg)
    hf = font('didone' if i % 2 else 'display', (y1 - y0) * 0.72)
    d.text(((x0 + x1) / 2, (y0 + y1) / 2), word, font=hf, fill=ink, anchor='mm')
    left = ['Why everyone is', 'The rise of', 'How', 'Inside', 'Meet'][i % 5]
    lf = font('sans-b', u(e, 36))
    d.text((u(e, 60), y0 - u(e, 60)), left, font=lf, fill=ink)
    return np.asarray(im, np.float32) / 255.0


@effect('match-cut', 'news')
def match_cut(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    word = str(e.opt('text', 'Claude'))
    col = hexrgb(e.opt('color', '#e5262e'))
    every = max(0.12, e.opt('every', 0.32))
    bh = u(e, 150)
    f = font('display', bh * 0.72)
    bw = f.getlength(word) + u(e, 70)
    y0 = clamp(e.head_top - bh * 1.4, u(e, 260), e.H)
    box = (W / 2 - bw / 2, y0, W / 2 + bw / 2, y0 + bh)
    pages = _cached(e, 'pages', lambda: [_news_page(i, word, e, box) for i in range(len(PAGE_STYLES))])
    page = pages[int(e.t / every) % len(pages)]
    k = _fade(e, 0.05, 0.1)

    def lay(o):
        o = blend(o, page, k)
        im, d = canvas(e)
        th = int(u(e, 9))
        d.rectangle([box[0], box[1], box[2], box[3]], outline=col + (255,), width=th)
        return flush(o, im, k)
    return behind(img, lay, e.mask)


def _led_bitmap(lines, cols, chars):
    """Render text as a low-res on/off grid."""
    rows_per_line = 9
    gap = 3
    H = len(lines) * rows_per_line + (len(lines) - 1) * gap + 4
    im = Image.new('L', (cols, H), 0)
    d = ImageDraw.Draw(im)
    f = font('mono', 11)
    shown = chars
    y = 2
    for line in lines:
        part = line[:max(0, shown)]
        shown -= len(line)
        tw = f.getlength(line)
        d.text(((cols - tw) / 2, y - 3), part, font=f, fill=255)
        y += rows_per_line + gap
    return (np.asarray(im) > 110).astype(np.float32)


@effect('led-sign', 'led')
def led_sign(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    lines = [l.upper() for l in e.lines('text', 'ON AIR|NOW')]
    col = np.array(hexrgb(e.opt('color', '#ff3b2f')), np.float32) / 255.0
    longest = max(len(l) for l in lines)
    cols = max(30, int(longest * 7.2) + 6)
    total = sum(len(l) for l in lines)
    chars = int(total * seg(e.t, 0.35, max(0.5, e.dur * 0.6))) if e.t > 0.35 else 0
    grid = _led_bitmap(lines, cols, chars)
    rows = grid.shape[0]
    pitch = (W * 0.9) / cols
    sw, sh = int(cols * pitch), int(rows * pitch)
    yy, xx = np.mgrid[:sh, :sw]
    gx = np.minimum((xx / pitch).astype(int), cols - 1)
    gy = np.minimum((yy / pitch).astype(int), rows - 1)
    lx = (xx % pitch) - pitch / 2
    ly = (yy % pitch) - pitch / 2
    dot = np.clip(pitch * 0.38 - np.sqrt(lx * lx + ly * ly) + 0.5, 0, 1)
    on = grid[gy, gx]
    flick = 0.92 + 0.08 * math.sin(e.t * 40)
    sign = (dot * (0.07 + on * 0.93 * flick))[..., None] * col
    sign = sign + blur(sign, pitch * 1.4) * 1.6
    dark = _fade(e, 0.2, 0.25)
    m = e.mask[..., None]
    x0 = int((W - sw) / 2)
    y0 = int(clamp(e.head_top - sh * 0.95, u(e, 120), H - sh))

    def lay(o):
        o = o * (1 - 0.86 * dark)
        x1, y1 = min(W, x0 + sw), min(H, y0 + sh)
        panel = o[y0:y1, x0:x1]
        o[y0:y1, x0:x1] = panel * 0.4 + sign[:y1 - y0, :x1 - x0] * dark
        return o
    out = behind(img, lay, e.mask)
    # a little sign light on the speaker
    glow_y = np.clip(1 - np.abs(np.arange(H) - (y0 + sh)) / (H * 0.35), 0, 1)[:, None, None]
    return out + m * glow_y * col * 0.12 * dark


@effect('the-bill', 'bill', 'receipt')
def the_bill(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    lines = e.lines('text', 'Track my face|Words behind my head|Make it pop|No captions|Ship it')
    rw = W * 0.6

    def make():
        fm = font('mono', u(e, 34))
        fr = font('mono-r', u(e, 28))
        lh = fm.size * 1.55
        h = u(e, 200) + len(lines) * lh + u(e, 230)
        im = Image.new('RGBA', (int(rw), int(h)), (250, 248, 241, 255))
        d = ImageDraw.Draw(im)
        d.text((rw / 2, u(e, 60)), 'ORDER #0042', font=fm, fill=(20, 20, 20), anchor='mm')
        d.text((rw / 2, u(e, 105)), 'table: you  ·  chef: claude', font=fr, fill=(90, 90, 90), anchor='mm')
        y = u(e, 160)
        dash = '-' * 40
        d.text((rw / 2, y), dash, font=fr, fill=(150, 150, 150), anchor='mm')
        y += u(e, 40)
        for i, line in enumerate(lines):
            d.text((u(e, 36), y), f'{i + 1:02d} {line}'[:30], font=fm, fill=(20, 20, 20))
            d.text((rw - u(e, 36), y), '✓', font=font('sans-b', u(e, 34)), fill=(20, 20, 20), anchor='ra')
            y += lh
        d.text((rw / 2, y + u(e, 10)), dash, font=fr, fill=(150, 150, 150), anchor='mm')
        d.text((u(e, 36), y + u(e, 50)), 'TOTAL', font=fm, fill=(20, 20, 20))
        d.text((rw - u(e, 36), y + u(e, 50)), '1 REEL', font=fm, fill=(20, 20, 20), anchor='ra')
        d.text((rw / 2, y + u(e, 150)), 'thank you, come again', font=fr, fill=(90, 90, 90), anchor='mm')
        # torn zigzag bottom
        z = u(e, 18)
        a = Image.new('L', im.size, 255)
        ad = ImageDraw.Draw(a)
        pts = [(0, h)]
        x = 0
        while x <= rw:
            pts.append((x, h - z if int(x / z) % 2 else h))
            x += z
        pts.append((rw, h))
        ad.polygon(pts, fill=0)
        im.putalpha(a)
        return im
    paper = _cached(e, 'paper', make)
    slot_y = u(e, 80)
    L = paper.height * out_cubic(seg(e.t, 0.1, e.dur * 0.75)) ** 0.9
    fade = _fade(e, 0.01, 0.25)
    if L < 2:
        return img
    piece = paper.crop((0, 0, paper.width, int(L)))
    piece = shadowed(piece, u(e, 14), (0, int(u(e, 8))), 0.35)
    sway = math.sin(e.t * 2.2) * 1.5
    x = clamp(cx, rw / 2 + u(e, 30), W - rw / 2 - u(e, 30))

    def lay(o):
        o = place(o, piece, x, slot_y + piece.height / 2 - u(e, 30), angle=sway, alpha=fade)
        im, d = canvas(e)
        d.rounded_rectangle([x - rw * 0.58, slot_y - u(e, 30), x + rw * 0.58, slot_y + u(e, 6)], radius=u(e, 14), fill=(30, 30, 32, 255))
        return flush(o, im, fade)
    return behind(img, lay, e.mask)


@effect('profile-wall', 'grid', 'wall')
def profile_wall(img, e):
    cx, cy, fw, fh = e.face
    W, H = e.W, e.H
    cols = 3
    gap = u(e, 6)
    tw = (W - gap * (cols - 1)) / cols
    th = tw * 4 / 3
    rows = int(H / th) + 3
    n = rows * cols
    pics = e.reels(max(10, n))

    def make():
        sheet = Image.new('RGB', (W, int(rows * (th + gap))), (8, 8, 8))
        for i in range(n):
            r, c = divmod(i, cols)
            tile = cover(Image.fromarray(pics[i]).convert('RGB'), int(tw), int(th))
            sheet.paste(tile, (int(c * (tw + gap)), int(r * (th + gap))))
        return np.asarray(sheet, np.float32) / 255.0
    sheet = _cached(e, 'sheet', make)
    k = _fade(e, 0.3, 0.3)
    scroll = (th + gap) * 1.2 * in_out(e.p)
    y0 = int(scroll)
    view = sheet[y0:y0 + H]
    if view.shape[0] < H:
        view = np.pad(view, ((0, H - view.shape[0]), (0, 0), (0, 0)))
    view = view * 0.85
    target = str(e.opt('count', '10K'))
    label = str(e.opt('label', 'followers'))
    v, mult, post = parse_num(target)
    shown = fmt_num(v * out_cubic(seg(e.t, 0.2, e.dur * 0.8)), (v, mult, post))
    out = behind(img, lambda o: blend(o, view, k), e.mask)
    im, d = canvas(e)
    f = font('display', u(e, 110))
    fl = font('sans-b', u(e, 36))
    hy = u(e, 150)
    w = max(f.getlength(target), fl.getlength(label)) + u(e, 80)
    d.rounded_rectangle([W / 2 - w / 2, hy - u(e, 30), W / 2 + w / 2, hy + u(e, 190)], radius=u(e, 34), fill=(0, 0, 0, 170))
    d.text((W / 2, hy + u(e, 55)), shown, font=f, fill=(255, 255, 255, 255), anchor='mm')
    d.text((W / 2, hy + u(e, 145)), label, font=fl, fill=(220, 220, 225, 255), anchor='mm')
    return flush(out, im, k)
