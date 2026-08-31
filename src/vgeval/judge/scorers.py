"""Deterministic (non-VLM) scorers for rubric dimensions.

These are CV/text checks that are more reliable and auditable than asking a VLM
for a number. All numpy-only — no extra dependencies.

  * brand_color_adherence — dominant palette vs brand palette via CIE ΔE (Lab)
  * loopability          — first-vs-last frame difference (loop seam)

A deterministic OCR path for copy/language (e.g. rapidocr-onnxruntime) is a
documented future drop-in; today copy is scored VLM-with-ground-truth and the
VLM's transcription is logged for audit. See docs/creative-rubric.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import imageio.v3 as iio
import numpy as np


@dataclass
class ScoreContext:
    frames: list[Path]
    brand_palette: list[str]
    scale_min: int
    scale_max: int


# --------------------------------------------------------------------------- #
# color science (sRGB -> CIE Lab, ΔE76)
# --------------------------------------------------------------------------- #
def _hex_to_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float64)


def _srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """rgb: (..., 3) in 0-255 -> Lab (..., 3). D65."""
    rgb = rgb.astype(np.float64) / 255.0
    mask = rgb > 0.04045
    lin = np.where(mask, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    m = np.array(
        [
            [0.4124, 0.3576, 0.1805],
            [0.2126, 0.7152, 0.0722],
            [0.0193, 0.1192, 0.9505],
        ]
    )
    xyz = lin @ m.T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    e = 216 / 24389
    k = 24389 / 27
    f = np.where(xyz > e, np.cbrt(xyz), (k * xyz + 16) / 116)
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    lab = np.stack([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)], axis=-1)
    return lab


def _delta_e76(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.sqrt(np.sum((a - b) ** 2, axis=-1))


def _dominant_colors(frames_rgb: np.ndarray, k: int = 6) -> np.ndarray:
    """Top-k dominant colors by frequency using coarse quantization. Returns (m,3)."""
    px = frames_rgb.reshape(-1, 3)
    if px.shape[0] > 20000:  # subsample for speed
        idx = np.linspace(0, px.shape[0] - 1, 20000).astype(int)
        px = px[idx]
    q = (px // 32) * 32 + 16  # 8 levels/channel
    colors, counts = np.unique(q, axis=0, return_counts=True)
    order = np.argsort(counts)[::-1][:k]
    return colors[order].astype(np.float64)


def _load_frames(paths: list[Path]) -> np.ndarray:
    arrs = []
    for p in paths:
        a = np.asarray(iio.imread(p))
        if a.ndim == 3:
            arrs.append(a[..., :3])
    if not arrs:
        return np.zeros((1, 1, 1, 3), dtype=np.uint8)
    h = min(a.shape[0] for a in arrs)
    w = min(a.shape[1] for a in arrs)
    return np.stack([a[:h, :w] for a in arrs])


def _map_delta_e_to_score(mean_de: float, lo: int, hi: int) -> int:
    """Lower ΔE -> higher score. Thresholds tuned for promo palettes."""
    span = hi - lo
    if mean_de < 10:
        frac = 1.0
    elif mean_de < 20:
        frac = 0.75
    elif mean_de < 35:
        frac = 0.5
    elif mean_de < 55:
        frac = 0.25
    else:
        frac = 0.0
    return int(round(lo + frac * span))


def brand_color_adherence(ctx: ScoreContext) -> tuple[int | None, str]:
    if not ctx.brand_palette:
        return None, "skipped: no brand_palette provided"
    frames = _load_frames(ctx.frames)
    dominant = _dominant_colors(frames)
    brand_lab = _srgb_to_lab(np.stack([_hex_to_rgb(h) for h in ctx.brand_palette]))
    dom_lab = _srgb_to_lab(dominant)
    # For each dominant color, distance to nearest brand color.
    de = np.min(
        _delta_e76(dom_lab[:, None, :], brand_lab[None, :, :]), axis=1
    )  # (n_dominant,)
    # Weight toward the closest few dominant colors (a promo frame is mostly
    # background; brand colors need only be present and accurate, not dominant).
    closest = np.sort(de)[: max(1, len(de) // 2)]
    mean_de = float(np.mean(closest))
    score = _map_delta_e_to_score(mean_de, ctx.scale_min, ctx.scale_max)
    return score, f"mean ΔE(top matches)={mean_de:.1f} vs {len(ctx.brand_palette)} brand colors"


def loopability(ctx: ScoreContext) -> tuple[int | None, str]:
    frames = _load_frames(ctx.frames)
    if frames.shape[0] < 2:
        return None, "skipped: need >=2 frames"
    a = frames[0].astype(np.float64) / 255.0
    b = frames[-1].astype(np.float64) / 255.0
    diff = float(np.mean((a - b) ** 2))
    lo, span = ctx.scale_min, ctx.scale_max - ctx.scale_min
    if diff < 0.002:
        frac = 1.0
    elif diff < 0.01:
        frac = 0.75
    elif diff < 0.03:
        frac = 0.5
    elif diff < 0.08:
        frac = 0.25
    else:
        frac = 0.0
    return int(round(lo + frac * span)), f"first/last MSE={diff:.4f}"


# dim name -> scorer
DETERMINISTIC_SCORERS = {
    "brand_color_adherence": brand_color_adherence,
    "loopability": loopability,
    "loopability_edit_readiness": loopability,
}


def run_deterministic(dim_name: str, ctx: ScoreContext) -> tuple[int | None, str]:
    fn = DETERMINISTIC_SCORERS.get(dim_name)
    if fn is None:
        return None, f"no deterministic scorer for {dim_name!r}"
    return fn(ctx)
