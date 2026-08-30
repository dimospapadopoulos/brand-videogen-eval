"""Extract evenly-spaced frames from a video for judging and thumbnails.

Uses imageio (which pulls a bundled ffmpeg via imageio-ffmpeg), so no system
ffmpeg install is required.
"""

from __future__ import annotations

from pathlib import Path

import imageio.v3 as iio
import numpy as np


def extract_frames(video_path: str | Path, n: int = 6) -> list[np.ndarray]:
    """Return `n` evenly-spaced RGB frames as uint8 arrays."""
    video_path = Path(video_path)
    frames = iio.imread(video_path, index=None)  # (T, H, W, C)
    frames = np.asarray(frames)
    if frames.ndim == 3:  # single frame
        frames = frames[None, ...]
    total = frames.shape[0]
    if total == 0:
        return []
    n = min(n, total)
    idx = np.linspace(0, total - 1, n).round().astype(int)
    return [frames[i][..., :3] for i in idx]


def save_frames(video_path: str | Path, out_dir: str | Path, n: int = 6) -> list[Path]:
    """Extract frames and write them as PNGs; return the written paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, frame in enumerate(extract_frames(video_path, n=n)):
        p = out_dir / f"frame_{i:02d}.png"
        iio.imwrite(p, frame)
        paths.append(p)
    return paths
