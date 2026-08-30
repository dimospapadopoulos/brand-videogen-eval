"""Mock image-to-video provider.

Serves a bundled sample video for each request so the entire harness runs fully
offline with zero API keys and zero cost. Two behaviours:

1. If `assets/samples/videos/` contains videos, it deterministically picks one
   per job (stable by job_id) and copies it into the run's output dir.
2. Otherwise it synthesises a short procedural clip seeded from the source image
   (a gentle pan/zoom + tint), so the pipeline is demonstrable before you drop
   in your own sample assets.

Replace this behaviour with a real SDK call to ship a real provider — see
`docs/adding-a-provider.md` and `providers/_stubs.py`.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import imageio.v3 as iio
import numpy as np

from vgeval.config import get_settings
from vgeval.providers.base import ImageToVideoProvider
from vgeval.providers.registry import register
from vgeval.schemas import GenRequest, VideoResult

_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".gif"}


def _stable_index(key: str, n: int) -> int:
    digest = hashlib.sha256(key.encode()).hexdigest()
    return int(digest, 16) % n


def _load_source_rgb(path: Path, size: int = 256) -> np.ndarray:
    """Load a source image as an (size, size, 3) uint8 array, tolerant of errors."""
    try:
        img = iio.imread(path)
        if img.ndim == 2:  # grayscale
            img = np.stack([img] * 3, axis=-1)
        img = img[..., :3]
        # Cheap center-crop-ish resize via slicing/repeat to avoid a Pillow dep.
        h, w = img.shape[:2]
        step_h, step_w = max(1, h // size), max(1, w // size)
        img = img[::step_h, ::step_w][:size, :size]
        canvas = np.zeros((size, size, 3), dtype=np.uint8)
        canvas[: img.shape[0], : img.shape[1]] = img
        return canvas
    except Exception:
        # Fall back to a neutral gray frame if the image can't be read.
        return np.full((size, size, 3), 127, dtype=np.uint8)


def _synthesize_clip(source: Path, dest: Path, *, seconds: float, fps: int) -> None:
    """Write a short procedural mp4 seeded from the source image."""
    base = _load_source_rgb(source)
    n_frames = max(1, int(seconds * fps))
    frames = []
    for i in range(n_frames):
        t = i / max(1, n_frames - 1)
        # Gentle horizontal pan by rolling the image, plus a warm tint ramp.
        shifted = np.roll(base, shift=int(t * 24), axis=1)
        tint = np.array([1.0 + 0.15 * t, 1.0, 1.0 - 0.1 * t])
        frame = np.clip(shifted.astype(np.float32) * tint, 0, 255).astype(np.uint8)
        frames.append(frame)
    dest.parent.mkdir(parents=True, exist_ok=True)
    iio.imwrite(dest, np.stack(frames), fps=fps, codec="libx264")


@register("mock")
class MockProvider(ImageToVideoProvider):
    """Zero-cost provider used for v1, tests, CI, and the shadow canary."""

    def __init__(self, *, seconds: float = 2.0, fps: int = 12, **config: object) -> None:
        super().__init__(**config)
        self.seconds = seconds
        self.fps = fps
        self._videos_dir = get_settings().assets_dir / "videos"

    def _bundled_videos(self) -> list[Path]:
        if not self._videos_dir.exists():
            return []
        return sorted(p for p in self._videos_dir.iterdir() if p.suffix.lower() in _VIDEO_EXTS)

    async def generate(self, req: GenRequest, *, out_dir: str) -> VideoResult:
        dest = Path(out_dir) / f"{req.job_id}.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)

        bundled = self._bundled_videos()
        if bundled:
            chosen = bundled[_stable_index(req.job_id, len(bundled))]
            shutil.copyfile(chosen, dest)
            source_kind = "bundled"
            meta_src = chosen.name
        else:
            _synthesize_clip(Path(req.source_image), dest, seconds=self.seconds, fps=self.fps)
            source_kind = "synthetic"
            meta_src = None

        return VideoResult(
            provider=self.name,
            job_id=req.job_id,
            video_path=str(dest),
            seconds=self.seconds,
            fps=float(self.fps),
            meta={"source_kind": source_kind, "sample_file": meta_src, "prompt": req.prompt},
        )
