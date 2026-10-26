"""Small UI pieces shared by effects: canvases, glass, checks, cursors, toggles."""
from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .draw import blur, card_from, font, over, rounded


def canvas(e):
    im = Image.new('RGBA', (e.W, e.H), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def flush(img, im: Image.Image, alpha=1.0):
    """Composite a full-frame RGBA canvas, touching only its used area."""
    box = im.getbbox()
    if not box:
        return img
    x0, y0, x1, y1 = box
    return over(img, np.asarray(im.crop(box)), x0, y0, alpha)


def u(e, v):
    """Scale a size given for a 1080-wide frame."""
    return v * e.W / 1080.0


def glass(img, box, r, tint=(255, 255, 255), tint_a=0.16, blur_px=22, border_a=0.45, dark=False):
    """Frosted glass panel: blurs what's behind, tints it, adds a rim and sheen."""
    H, W = img.shape[:2]
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if cx0 >= cx1 or cy0 >= cy1:
        return img
    w, h = x1 - x0, y1 - y0
    pad = int(blur_px * 2)
    sx0, sy0, sx1, sy1 = max(0, cx0 - pad), max(0, cy0 - pad), min(W, cx1 + pad), min(H, cy1 + pad)
    region = cv2.GaussianBlur(img[sy0:sy1, sx0:sx1], (0, 0), blur_px)
    region = region[cy0 - sy0:cy1 - sy0, cx0 - sx0:cx1 - sx0]
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    m = np.asarray(m, np.float32)[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0, None] / 255.0
    t = np.array(tint, np.float32) / 255.0
    if dark:
        region = region * 0.55 + t * tint_a
    else:
        region = region * (1 - tint_a) + t * tint_a
        region = region * 1.04 + 0.02
    img[cy0:cy1, cx0:cx1] = img[cy0:cy1, cx0:cx1] * (1 - m) + region * m
    # rim and top sheen
    rim = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(rim)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, outline=(255, 255, 255, int(255 * border_a)),
                        width=max(1, int(w / 260)))
    sheen = Image.new('L', (w, h), 0)
    ImageDraw.Draw(sheen).rounded_rectangle([2, 2, w - 3, int(h * 0.45)], radius=r, fill=28)
    sheen = sheen.filter(ImageFilter.GaussianBlur(max(2, h * 0.08)))
    white = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    white.putalpha(sheen)
    rim = Image.alpha_composite(white, rim)
    return over(img, rim, x0, y0)


def check(d: ImageDraw.ImageDraw, cx, cy, size, t, color=(255, 255, 255), width=None):
    """A tick mark drawn on with progress t."""
    if t <= 0:
        return
    width = width or max(2, int(size * 0.16))
    a = (cx - size * 0.32, cy + size * 0.02)
    b = (cx - size * 0.08, cy + size * 0.26)
    c = (cx + size * 0.36, cy - size * 0.24)
    l1, l2 = math.dist(a, b), math.dist(b, c)
    k = t * (l1 + l2)
    if k <= l1:
        pts = [a, (a[0] + (b[0] - a[0]) * k / l1, a[1] + (b[1] - a[1]) * k / l1)]
    else:
        k2 = (k - l1) / l2
        pts = [a, b, (b[0] + (c[0] - b[0]) * k2, b[1] + (c[1] - b[1]) * k2)]
    d.line(pts, fill=color, width=width, joint='curve')
    for p in (pts[0], pts[-1]):
        r = width / 2
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)


def cursor(size, color=(255, 255, 255), outline=(0, 0, 0)):
    """Mac-style arrow pointer sprite; the tip is at (pad, pad)."""
    s = size
    pad = int(s * 0.3)
    im = Image.new('RGBA', (int(s * 0.8) + pad * 2, int(s * 1.1) + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(0, 0), (0, s * 0.92), (s * 0.24, s * 0.7), (s * 0.4, s * 1.04), (s * 0.54, s * 0.97),
           (s * 0.38, s * 0.64), (s * 0.68, s * 0.64)]
    pts = [(x + pad, y + pad) for x, y in pts]
    d.polygon(pts, fill=color, outline=outline)
    d.line(pts + [pts[0]], fill=outline, width=max(2, int(s * 0.06)), joint='curve')
    return im, pad


def avatar(pic_u8, size, ring=None, ring_w=0):
    pic = Image.fromarray(pic_u8).convert('RGB')
    s = min(pic.width, pic.height)
    pic = pic.crop(((pic.width - s) // 2, int((pic.height - s) * 0.25), (pic.width - s) // 2 + s,
                    int((pic.height - s) * 0.25) + s)).resize((size, size), Image.LANCZOS)
    m = Image.new('L', (size, size), 0)
    ImageDraw.Draw(m).ellipse([0, 0, size - 1, size - 1], fill=255)
    pic = pic.convert('RGBA')
    pic.putalpha(m)
    if not ring:
        return pic
    full = size + ring_w * 4
    out = Image.new('RGBA', (full, full), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.ellipse([0, 0, full - 1, full - 1], fill=ring)
    d.ellipse([ring_w, ring_w, full - ring_w - 1, full - ring_w - 1], fill=(255, 255, 255, 255))
    out.alpha_composite(pic, (ring_w * 2, ring_w * 2))
    return out


def toggle(d, x, y, w, on, color=(52, 199, 89)):
    """iOS switch with its knob position on in 0..1."""
    h = w * 0.6
    off = (120, 120, 128)
    col = tuple(int(off[i] + (color[i] - off[i]) * on) for i in range(3))
    d.rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=col)
    k = h - w * 0.08
    kx = x + w * 0.04 + (w - k - w * 0.08) * on
    d.ellipse([kx, y + w * 0.04, kx + k, y + w * 0.04 + k], fill=(255, 255, 255))


def spinner(d, cx, cy, r, angle, color, width):
    d.arc([cx - r, cy - r, cx + r, cy + r], start=angle, end=angle + 270, fill=color, width=width)


def heart(d, cx, cy, s, fill=None, outline=(255, 255, 255), width=3):
    pts = []
    for i in range(60):
        a = i / 60 * 2 * math.pi
        x = 16 * math.sin(a) ** 3
        y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx + x * s / 34, cy + y * s / 34))
    if fill:
        d.polygon(pts, fill=fill)
    d.line(pts + [pts[0]], fill=outline, width=width, joint='curve')


def reel_card(pic_u8, w, border=0, r=None):
    """A 9:16 reel thumbnail card."""
    return card_from(pic_u8, int(w), int(w * 16 / 9), r=r, border=border)


def pill(text, fnt, fill, color=(255, 255, 255), padx=None, pady=None):
    l, t, r, b = fnt.getbbox(text)
    padx = int(fnt.size * 0.7) if padx is None else padx
    pady = int(fnt.size * 0.42) if pady is None else pady
    w, h = r - l + padx * 2, int(fnt.size * 1.0) + pady * 2
    im = rounded(w, h, h // 2, fill)
    ImageDraw.Draw(im).text((w / 2, h / 2), text, font=fnt, fill=color, anchor='mm')
    return im


def dim_background(img, mask, amount, tint=(0, 0, 0)):
    m = mask[..., None]
    t = np.array(tint, np.float32) / 255.0
    bg = img * (1 - amount) + t * amount * 0.4
    return bg * (1 - m) + img * m


def blurred_bg(img, mask, sigma):
    m = mask[..., None]
    return blur(img, sigma) * (1 - m) + img * m
