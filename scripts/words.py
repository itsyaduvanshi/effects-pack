#!/usr/bin/env python3
"""Print every spoken word with its start and end time, so effects can land on a word.

  words.py <video> [--find "kill the lights"]

Uses faster-whisper (installed on first use, about 150 MB with the small model).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


def ensure():
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        print('Installing speech-to-text (one time)...', file=sys.stderr)
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'faster-whisper'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--find', help='phrase to look for; prints only its matches')
    ap.add_argument('--model', default=os.environ.get('FX_WHISPER', 'small'))
    a = ap.parse_args()
    ensure()
    from faster_whisper import WhisperModel
    model = WhisperModel(a.model, device='auto', compute_type='int8')
    segments, _ = model.transcribe(a.video, word_timestamps=True, vad_filter=True)
    words = [(w.word.strip(), w.start, w.end) for s in segments for w in (s.words or [])]
    if not a.find:
        for w, s, e in words:
            print(f'{s:7.2f} {e:7.2f}  {w}')
        return
    target = [t.strip('.,!?"\'').lower() for t in a.find.split()]
    norm = [w.strip('.,!?"\'').lower() for w, _, _ in words]
    hits = 0
    for i in range(len(norm) - len(target) + 1):
        if norm[i:i + len(target)] == target:
            hits += 1
            print(f'{words[i][1]:.2f} {words[i + len(target) - 1][2]:.2f}  {a.find}')
    if not hits:
        print('not found', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
