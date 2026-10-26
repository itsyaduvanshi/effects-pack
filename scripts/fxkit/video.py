"""Reading and writing video through ffmpeg pipes."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

import numpy as np


@dataclass
class VideoInfo:
    path: str
    width: int        # output width (after scaling)
    height: int       # output height
    fps: float
    duration: float
    frames: int
    has_audio: bool


def _even(x: float) -> int:
    return max(2, int(round(x / 2.0)) * 2)


def probe(path: str, width: int = 1080) -> VideoInfo:
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path],
        capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    vs = next(s for s in data['streams'] if s['codec_type'] == 'video')
    has_audio = any(s['codec_type'] == 'audio' for s in data['streams'])
    w, h = int(vs['width']), int(vs['height'])
    rot = 0
    for sd in vs.get('side_data_list', []) or []:
        if 'rotation' in sd:
            rot = int(float(sd['rotation']))
    if 'rotate' in vs.get('tags', {}):
        rot = int(vs['tags']['rotate'])
    if abs(rot) % 180 == 90:
        w, h = h, w
    num, den = vs.get('avg_frame_rate', '30/1').split('/')
    fps = float(num) / float(den) if float(den) else 30.0
    if fps <= 0 or fps > 240:
        fps = 30.0
    duration = float(vs.get('duration') or data['format'].get('duration') or 0)
    ow = _even(width)
    oh = _even(h * ow / w)
    frames = int(vs.get('nb_frames') or 0) or int(round(duration * fps))
    return VideoInfo(path, ow, oh, fps, duration, frames, has_audio)


def read_frames(info: VideoInfo, start: float = 0.0):
    """Yield RGB uint8 frames at the output size."""
    cmd = ['ffmpeg', '-v', 'error']
    if start > 0:
        cmd += ['-ss', f'{start:.3f}']
    cmd += ['-i', info.path, '-vf', f'scale={info.width}:{info.height}:flags=lanczos',
            '-r', f'{info.fps}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = info.width * info.height * 3
    try:
        while True:
            buf = proc.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape(info.height, info.width, 3)
    finally:
        proc.stdout.close()
        proc.wait()


def frame_at(info: VideoInfo, t: float) -> np.ndarray:
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{max(0.0, t):.3f}', '-i', info.path,
           '-vf', f'scale={info.width}:{info.height}:flags=lanczos', '-frames:v', '1',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    buf = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = info.width * info.height * 3
    if len(buf) < n:
        raise RuntimeError(f'no frame at {t}s')
    return np.frombuffer(buf[:n], np.uint8).reshape(info.height, info.width, 3).copy()


class Writer:
    def __init__(self, info: VideoInfo, out: str, crf: int = 17):
        self.info = info
        cmd = ['ffmpeg', '-v', 'error', '-y',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{info.width}x{info.height}',
               '-r', f'{info.fps}', '-i', '-']
        if info.has_audio:
            cmd += ['-i', info.path, '-map', '0:v', '-map', '1:a:0', '-c:a', 'aac', '-b:a', '192k']
        cmd += ['-c:v', 'libx264', '-preset', 'medium', '-crf', str(crf),
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-shortest', out]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, frame: np.ndarray):
        self.proc.stdin.write(np.ascontiguousarray(frame, dtype=np.uint8).tobytes())

    def close(self):
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError('ffmpeg failed while writing the video')
