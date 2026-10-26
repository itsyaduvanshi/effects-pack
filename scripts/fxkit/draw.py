"""Drawing and compositing.

Frames are float32 RGB in 0..1 while effects run. Graphics are drawn with
Pillow into RGBA "sprites" and composited with numpy.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / 'fonts'

FONT_FILES = {
    'display': ('ArchivoBlack-Regular.ttf', None),
    'serif': ('InstrumentSerif-Regular.ttf', None),
    'serif-i': ('InstrumentSerif-Italic.ttf', None),
    'mono': ('SpaceMono-Bold.ttf', None),
    'mono-r': ('SpaceMono-Regular.ttf', None),
    'sans': ('Inter.ttf', 400),
    'sans-m': ('Inter.ttf', 500),
    'sans-b': ('Inter.ttf', 700),
    'sans-x': ('Inter.ttf', 800),
    'tall': ('Anton-Regular.ttf', None),
    'marker': ('PermanentMarker-Regular.ttf', None),
    'didone': ('PlayfairDisplay.ttf', 800),
    'didone-r': ('PlayfairDisplay.ttf', 400),
    'didone-i': ('PlayfairDisplay-Italic.ttf', 500),
}


def hexrgb(h, default=(255, 255, 255)):
    if isinstance(h, (tuple, list)):
        return tuple(int(v) for v in h[:3])
    try:
        h = str(h).lstrip('#')
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, TypeError):
        return default


@lru_cache(maxsize=256)
def font(name: str, size: int):
    size = max(6, int(size))
    file, weight = FONT_FILES.get(name, FONT_FILES['sans'])
    try:
        f = ImageFont.truetype(str(FONTS / file), size)
        if weight is not None:
            try:
                axes = f.get_variation_axes()
                vals = [weight if a.get('name', b'') in (b'Weight', 'Weight') else a['default'] for a in axes]
                f.set_variation_by_axes(vals)
            except Exception:
                pass
        return f
    except OSError:
        return ImageFont.load_default()


def text_w(text, fnt):
    if not text:
        return 0
    l, _, r, _ = fnt.getbbox(text)
    return r - l


def fit(text, name, max_w, max_size, min_size=10):
    """Largest font of this family that fits text in max_w."""
    size = int(max_size)
    while size > min_size and text_w(text, font(name, size)) > max_w:
        size = int(size * 0.94)
    return font(name, size)


# ---------- conversion ----------

def to_float(img_u8):
    return img_u8.astype(np.float32) / 255.0


def to_u8(img):
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def pil_rgba(arr_float_rgb, alpha=1.0):
    im = Image.fromarray(to_u8(arr_float_rgb)).convert('RGBA')
    if alpha < 1:
        im.putalpha(int(255 * alpha))
    return im


# ---------- compositing ----------

def over(img, rgba, x=0, y=0, alpha=1.0):
    """Alpha-composite an RGBA sprite (PIL or uint8/float array) onto img at top-left (x, y)."""
    if isinstance(rgba, Image.Image):
        rgba = np.asarray(rgba)
    if rgba.dtype == np.uint8:
        rgba = rgba.astype(np.float32) / 255.0
    H, W = img.shape[:2]
    h, w = rgba.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1 or alpha <= 0:
        return img
    src = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = src[..., 3:4] * alpha
    dst = img[y0:y1, x0:x1]
    img[y0:y1, x0:x1] = dst * (1 - a) + src[..., :3] * a
    return img


def place(img, sprite: Image.Image, cx, cy, scale=1.0, angle=0.0, alpha=1.0):
    """Composite a PIL sprite centred at (cx, cy) with scale and rotation (degrees)."""
    if alpha <= 0.002 or scale <= 0.01:
        return img
    s = sprite
    if abs(scale - 1) > 1e-3:
        s = s.resize((max(1, int(s.width * scale)), max(1, int(s.height * scale))), Image.BICUBIC)
    if abs(angle) > 0.05:
        s = s.rotate(angle, resample=Image.BICUBIC, expand=True)
    return over(img, s, cx - s.width / 2, cy - s.height / 2, alpha)


def behind(img, layer_fn, mask):
    """Draw something into the frame, then put the person back on top."""
    person = img.copy()
    out = layer_fn(img)
    m = mask[..., None]
    return out * (1 - m) + person * m


def blend(a, b, t):
    return a * (1 - t) + b * t


# ---------- sprites ----------

def rounded(w, h, r, fill, border=None, bw=0):
    im = Image.new('RGBA', (int(w), int(h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=fill, outline=border, width=bw)
    return im


def shadowed(sprite: Image.Image, blur=18, offset=(0, 10), opacity=0.35, color=(0, 0, 0)):
    pad = int(blur * 2.5 + max(abs(offset[0]), abs(offset[1])))
    W, H = sprite.width + pad * 2, sprite.height + pad * 2
    sh = Image.new('RGBA', (W, H), color + (0,))
    a = Image.new('L', (W, H), 0)
    a.paste(sprite.getchannel('A'), (pad + offset[0], pad + offset[1]))
    a = a.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * opacity))
    sh.putalpha(a)
    sh.alpha_composite(sprite, (pad, pad))
    return sh


def mask_round(img: Image.Image, r):
    m = Image.new('L', img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=r, fill=255)
    out = img.convert('RGBA')
    out.putalpha(Image.fromarray(np.minimum(np.asarray(out.getchannel('A')), np.asarray(m))))
    return out


def cover(img: Image.Image, w, h):
    """Scale and centre-crop to exactly w x h."""
    s = max(w / img.width, h / img.height)
    im = img.resize((max(1, int(img.width * s + 0.5)), max(1, int(img.height * s + 0.5))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def card_from(img_u8, w, h, r=None, border=0, border_color=(255, 255, 255)):
    """A rounded photo card, optionally with a border."""
    r = int(w * 0.07) if r is None else r
    pic = cover(Image.fromarray(img_u8).convert('RGB'), w - border * 2, h - border * 2)
    pic = mask_round(pic, max(0, r - border))
    if not border:
        return pic
    base = rounded(w, h, r, border_color + (255,))
    base.alpha_composite(pic, (border, border))
    return base


def text_sprite(text, fnt, fill=(255, 255, 255), stroke=0, stroke_fill=(0, 0, 0), pad=None):
    pad = int(fnt.size * 0.25) if pad is None else pad
    l, t, r, b = fnt.getbbox(text, stroke_width=stroke)
    im = Image.new('RGBA', (r - l + pad * 2, b - t + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - l, pad - t), text, font=fnt, fill=fill,
                            stroke_width=stroke, stroke_fill=stroke_fill)
    return im


def glow(sprite: Image.Image, radius, color, strength=1.0):
    a = sprite.getchannel('A').filter(ImageFilter.GaussianBlur(radius))
    pad = int(radius * 2)
    W, H = sprite.width + pad * 2, sprite.height + pad * 2
    g = Image.new('RGBA', (W, H), tuple(color) + (0,))
    big = Image.new('L', (W, H), 0)
    big.paste(a, (pad, pad))
    g.putalpha(big.point(lambda v: min(255, int(v * strength))))
    g.alpha_composite(sprite, (pad, pad))
    return g


def polyline_partial(pts, t):
    """First fraction t (0..1) of a polyline, measured by length."""
    if t <= 0 or len(pts) < 2:
        return pts[:1]
    seglen = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seglen) * min(1.0, t)
    out = [pts[0]]
    for i, L in enumerate(seglen):
        if total <= L:
            k = total / L if L else 0
            out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * k, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * k))
            return out
        total -= L
        out.append(pts[i + 1])
    return out


# ---------- camera ----------

def zoom_at(img, zoom, cx, cy, shake=(0.0, 0.0), rot=0.0):
    """Zoom into (cx, cy), keeping the frame filled."""
    if zoom <= 1.0005 and not any(shake) and not rot:
        return img
    H, W = img.shape[:2]
    zoom = max(1.0, zoom)
    vw, vh = W / zoom, H / zoom
    cx = min(max(cx, vw / 2), W - vw / 2) + shake[0]
    cy = min(max(cy, vh / 2), H - vh / 2) + shake[1]
    M = cv2.getRotationMatrix2D((cx, cy), rot, zoom)
    M[0, 2] += W / 2 - cx
    M[1, 2] += H / 2 - cy
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def view_point(x, y, zoom, cx, cy, W, H):
    """Where a source point lands after zoom_at with the same args."""
    zoom = max(1.0, zoom)
    vw, vh = W / zoom, H / zoom
    cx = min(max(cx, vw / 2), W - vw / 2)
    cy = min(max(cy, vh / 2), H - vh / 2)
    return (x - cx) * zoom + W / 2, (y - cy) * zoom + H / 2


def blur(img, sigma):
    if sigma <= 0.3:
        return img
    H, W = img.shape[:2]
    k = 4 if sigma > 8 else 2 if sigma > 3 else 1
    small = cv2.resize(img, (W // k, H // k), interpolation=cv2.INTER_AREA) if k > 1 else img
    small = cv2.GaussianBlur(small, (0, 0), sigma / k)
    return cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR) if k > 1 else small


def vignette(img, strength=0.5, softness=0.6):
    H, W = img.shape[:2]
    y, x = np.ogrid[:H, :W]
    d = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
    v = 1 - strength * np.clip((d - (1 - softness)) / softness, 0, 1) ** 1.5
    return img * v[..., None].astype(np.float32)


def radial(W, H, cx, cy, r, inner=1.0, outer=0.0):
    y, x = np.ogrid[:H, :W]
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max(r, 1)
    return (outer + (inner - outer) * np.clip(1 - d, 0, 1) ** 1.6).astype(np.float32)


def grain(img, amount, seed):
    H, W = img.shape[:2]
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amount, (H // 2, W // 2)).astype(np.float32)
    n = cv2.resize(n, (W, H), interpolation=cv2.INTER_LINEAR)
    return img + n[..., None]


# ---------- grades ----------

def luma(img):
    return img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114


def saturate(img, s):
    l = luma(img)[..., None]
    return l + (img - l) * s


def contrast(img, c, pivot=0.45):
    return (img - pivot) * c + pivot


def curve(img, lift=0.0, gamma=1.0, gain=1.0):
    return np.power(np.clip(img * gain + lift * (1 - img), 0, 1), gamma)


def grade(img, name):
    name = (name or 'moody').lower()
    if name == 'bw':
        l = contrast(luma(img), 1.25)
        return np.repeat(np.clip(l, 0, 1)[..., None], 3, axis=2)
    if name == 'warm':
        out = img * np.array([1.08, 1.0, 0.86], np.float32)
        return saturate(contrast(out, 1.05), 1.08)
    if name == 'cool':
        out = img * np.array([0.9, 0.99, 1.1], np.float32)
        return contrast(out, 1.06)
    if name == 'pop':
        return contrast(saturate(img, 1.35), 1.12)
    if name == 'film-red':
        l = luma(img)[..., None]
        tint = np.array([0.95, 0.22, 0.2], np.float32)
        out = l * tint * 1.25 + img * 0.18
        out = curve(out, lift=0.03, gamma=1.08)
        return out
    if name == 'soft':
        out = curve(img, lift=0.05, gamma=0.96) * np.array([1.04, 1.0, 0.93], np.float32)
        return saturate(out, 0.88)
    # moody: cool shadows, warm highlights, less saturation, crushed blacks
    l = luma(img)[..., None]
    shadow = np.array([0.82, 0.95, 1.06], np.float32)
    high = np.array([1.06, 1.0, 0.9], np.float32)
    out = img * (shadow * (1 - l) + high * l)
    out = saturate(out, 0.72)
    out = curve(contrast(out, 1.18, 0.5), gamma=1.12)
    return vignette(out, 0.45)
