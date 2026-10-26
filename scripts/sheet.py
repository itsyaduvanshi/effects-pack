#!/usr/bin/env python3
"""Render one still of every effect on a clip and tile them into a contact sheet.

  sheet.py <video> <out_dir> [--at 0.6] [--only orbit,noise] [--videos]
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw  # noqa: E402

from fxkit.base import LOOKS, REGISTRY  # noqa: E402
from fxkit.draw import font  # noqa: E402
from fxkit.render import render, stills  # noqa: E402
from fxkit.video import probe  # noqa: E402

# where in the window each effect looks most like itself
BEST = {'dot-reveal': 0.45, 'pause-point': 0.85, 'swipe': 0.5, 'countdown-flip': 0.4, 'reject-stamp': 0.5,
        'comment-box': 0.45, 'tap': 0.75, 'uninstall': 0.7, 'split-headline': 0.6, 'broll-split': 0.6,
        'tier-list': 0.85, 'headline-wall': 0.85, 'match-cut': 0.5, 'reel-frame': 0.6, 'led-sign': 0.85}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--at', type=float, default=0.7)
    ap.add_argument('--only')
    ap.add_argument('--videos', action='store_true', help='also render an mp4 per effect')
    ap.add_argument('--width', type=int, default=720)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    info = probe(a.video, a.width)
    names = list(REGISTRY) + list(LOOKS)
    if a.only:
        names = [n.strip() for n in a.only.split(',')]
    tiles, failed = [], []
    for name in names:
        plan = {'effects': [{'fx': name, 'start': 0, 'end': info.duration}]}
        at = BEST.get(name, a.at) * info.duration
        try:
            p = stills(a.video, plan, os.path.join(a.out, name + '.png'), [at], a.width, log=lambda *_: None)[0]
            tiles.append((name, p))
            if a.videos:
                render(a.video, plan, os.path.join(a.out, name + '.mp4'), a.width, log=lambda *_: None)
            print('ok  ', name)
        except Exception:
            failed.append(name)
            print('FAIL', name)
            traceback.print_exc()
    if tiles:
        cols = 7
        tw = 300
        th = int(tw * info.height / info.width)
        lab = 44
        rows = math.ceil(len(tiles) / cols)
        sheet = Image.new('RGB', (cols * tw + (cols + 1) * 10, rows * (th + lab) + (rows + 1) * 10), (14, 14, 16))
        d = ImageDraw.Draw(sheet)
        f = font('sans-b', 22)
        for i, (name, p) in enumerate(tiles):
            r, c = divmod(i, cols)
            x, y = 10 + c * (tw + 10), 10 + r * (th + lab + 10)
            sheet.paste(Image.open(p).convert('RGB').resize((tw, th), Image.LANCZOS), (x, y))
            d.text((x + 4, y + th + 10), f'{i + 1}. {name}', font=f, fill=(235, 235, 235))
        sp = os.path.join(a.out, 'contact_sheet.jpg')
        sheet.save(sp, quality=90)
        print(sp)
    if failed:
        print('failed:', ', '.join(failed))
        sys.exit(1)


if __name__ == '__main__':
    main()
