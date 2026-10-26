#!/usr/bin/env python3
"""Add effects to a talking-head video.

  fx.py <effect> <video> <out.mp4> [--start S] [--end E] [--text T] [--opt key=value ...]
  fx.py --plan plan.json <video> <out.mp4>
  fx.py ... --still 1.5,3.2         write check PNGs instead of a video
  fx.py --list                      show every effect
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fxkit.base import ALIASES, LOOKS, REGISTRY  # noqa: E402
from fxkit.render import render, stills  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description='Add effects to a talking-head video.')
    ap.add_argument('args', nargs='*')
    ap.add_argument('--plan')
    ap.add_argument('--start', type=float)
    ap.add_argument('--end', type=float)
    ap.add_argument('--text')
    ap.add_argument('--opt', action='append', default=[], help='key=value, repeatable')
    ap.add_argument('--width', type=int, default=1080)
    ap.add_argument('--still', help='comma-separated seconds; writes PNGs')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()

    if a.list:
        for name in REGISTRY:
            al = [k for k, v in ALIASES.items() if v == name]
            print(name + (f'  (also: {", ".join(al)})' if al else ''))
        for name, (base, opts) in LOOKS.items():
            print(f'{name}  (look of {base}: {opts})')
        return

    if a.plan:
        if len(a.args) != 2:
            ap.error('with --plan give: <video> <out>')
        video, out = a.args
        with open(a.plan) as f:
            plan = json.load(f)
    else:
        if len(a.args) != 3:
            ap.error('give: <effect> <video> <out>')
        name, video, out = a.args
        spec = {'fx': name}
        if a.start is not None:
            spec['start'] = a.start
        if a.end is not None:
            spec['end'] = a.end
        if a.text is not None:
            spec['text'] = a.text
        for kv in a.opt:
            k, _, v = kv.partition('=')
            spec[k.strip()] = v
        plan = {'effects': [spec]}

    try:
        if a.still:
            times = [float(x) for x in a.still.split(',') if x.strip()]
            for p in stills(video, plan, out, times, a.width):
                print(p)
        else:
            render(video, plan, out, a.width)
    except KeyError as err:
        sys.exit(f'Unknown effect {err}. Run with --list to see them all.')


if __name__ == '__main__':
    main()
