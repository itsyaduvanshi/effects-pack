"""One pass over the video: face track, person mask and a few sample frames.

Results are cached next to the skill, keyed by the file and the render size,
so a check render and the final render only analyse once.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .video import VideoInfo, read_frames

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / 'models'
CACHE = ROOT / '.cache'

MASK_SCALE = 0.5      # masks are stored at half size
DETECT_W = 480        # face detection runs at this width


@dataclass
class Analysis:
    faces: np.ndarray       # (n, 4) cx, cy, w, h in output pixels, smoothed
    masks: np.ndarray       # (n, mh, mw) uint8 person confidence
    samples: list           # small RGB frames for reel thumbnails
    found_face: bool

    def face(self, i: int):
        i = int(np.clip(i, 0, len(self.faces) - 1))
        return tuple(float(v) for v in self.faces[i])

    def mask(self, i: int, w: int, h: int) -> np.ndarray:
        i = int(np.clip(i, 0, len(self.masks) - 1))
        m = cv2.resize(self.masks[i], (w, h), interpolation=cv2.INTER_LINEAR)
        return m.astype(np.float32) / 255.0


def _key(info: VideoInfo) -> str:
    st = os.stat(info.path)
    raw = f'{os.path.abspath(info.path)}|{st.st_size}|{st.st_mtime}|{info.width}|v2'
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


class _Faces:
    def __init__(self, w: int, h: int):
        self.scale = DETECT_W / w
        self.size = (DETECT_W, max(2, int(h * self.scale)))
        self.det = cv2.FaceDetectorYN.create(str(MODELS / 'yunet.onnx'), '', self.size, 0.6, 0.3, 50)

    def __call__(self, rgb: np.ndarray):
        small = cv2.resize(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), self.size, interpolation=cv2.INTER_AREA)
        _, found = self.det.detect(small)
        if found is None or len(found) == 0:
            return None
        x, y, w, h = max(found, key=lambda r: r[2] * r[3])[:4] / self.scale
        return (x + w / 2, y + h / 2, w, h)


class _Segmenter:
    def __init__(self):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python import vision
        self.mp = mp
        opts = vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=str(MODELS / 'selfie_segmenter.tflite')),
            running_mode=vision.RunningMode.VIDEO,
            output_confidence_masks=True, output_category_mask=False)
        self.seg = vision.ImageSegmenter.create_from_options(opts)

    def __call__(self, rgb: np.ndarray, ms: int) -> np.ndarray:
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        res = self.seg.segment_for_video(img, ms)
        return res.confidence_masks[0].numpy_view().copy()


def _smooth_track(raw: list, n: int, w: int, h: int):
    """Fill gaps by interpolation, then smooth over time."""
    have = [i for i, f in enumerate(raw) if f is not None]
    if not have:
        fw = w * 0.28
        return np.tile([w / 2, h * 0.36, fw, fw * 1.25], (n, 1)).astype(np.float32), False
    arr = np.zeros((n, 4), np.float32)
    known = np.array([raw[i] for i in have], np.float32)
    for c in range(4):
        arr[:, c] = np.interp(np.arange(n), have, known[:, c])
    # size moves slower than position: different smoothing windows
    out = arr.copy()
    for c, sigma in ((0, 2.5), (1, 2.5), (2, 6.0), (3, 6.0)):
        k = int(sigma * 3) * 2 + 1
        pad = np.pad(arr[:, c], (k // 2, k // 2), mode='edge')
        g = cv2.getGaussianKernel(k, sigma).ravel()
        out[:, c] = np.convolve(pad, g, mode='valid')
    return out, True


def _refine(conf: np.ndarray, prev, size) -> np.ndarray:
    m = cv2.resize(conf, size, interpolation=cv2.INTER_LINEAR)
    # tighten the soft edge a little, then feather
    m = np.clip((m - 0.25) / 0.5, 0, 1)
    m = cv2.GaussianBlur(m, (0, 0), 1.2)
    if prev is not None:
        m = 0.6 * m + 0.4 * prev   # calm the flicker
    return m


def analyze(info: VideoInfo, log=print) -> Analysis:
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f'{_key(info)}.npz'
    if path.exists():
        d = np.load(path, allow_pickle=True)
        return Analysis(d['faces'], d['masks'], list(d['samples']), bool(d['found']))

    log('Analysing the video (face + person cut-out)...')
    faces = _Faces(info.width, info.height)
    seg = _Segmenter()
    msize = (int(info.width * MASK_SCALE), int(info.height * MASK_SCALE))
    raw, masks, frames_small = [], [], []
    prev = None
    n_est = max(1, info.frames)
    sample_at = set(int(x) for x in np.linspace(0, n_est - 1, 10))
    for i, frame in enumerate(read_frames(info)):
        raw.append(faces(frame))
        prev = _refine(seg(frame, int(i * 1000 / info.fps)), prev, msize)
        masks.append((prev * 255).astype(np.uint8))
        if i in sample_at:
            frames_small.append(cv2.resize(frame, (270, int(270 * info.height / info.width)),
                                           interpolation=cv2.INTER_AREA))
    n = len(masks)
    track, found = _smooth_track(raw, n, info.width, info.height)
    masks = np.stack(masks)
    if not frames_small:
        frames_small = [np.zeros((480, 270, 3), np.uint8)]
    samples = np.empty(len(frames_small), dtype=object)
    samples[:] = frames_small
    np.savez(path, faces=track, masks=masks, samples=samples, found=found)
    if not found:
        log('No face found; effects will use the centre of the frame.')
    return Analysis(track, masks, list(frames_small), found)
