"""Deterministic scorers: color ΔE adherence and loop-seam diff."""

from pathlib import Path

import imageio.v3 as iio
import numpy as np

from vgeval.judge.scorers import ScoreContext, brand_color_adherence, loopability


def _write_solid_frames(dirp: Path, rgb, n=4, size=32):
    dirp.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(n):
        arr = np.zeros((size, size, 3), np.uint8)
        arr[:] = rgb
        p = dirp / f"frame_{i:02d}.png"
        iio.imwrite(p, arr)
        paths.append(p)
    return paths


def test_brand_color_adherence_on_palette_scores_high(tmp_path):
    # Frames are pure brand red -> ΔE ~ 0 -> top score.
    frames = _write_solid_frames(tmp_path / "red", (228, 0, 43))  # ~#E4002B
    ctx = ScoreContext(frames=frames, brand_palette=["#E4002B"], scale_min=1, scale_max=5)
    score, note = brand_color_adherence(ctx)
    assert score == 5, note


def test_brand_color_adherence_off_palette_scores_low(tmp_path):
    # Brand wants red; frames are green -> large ΔE -> low score.
    frames = _write_solid_frames(tmp_path / "green", (0, 180, 0))
    ctx = ScoreContext(frames=frames, brand_palette=["#E4002B"], scale_min=1, scale_max=5)
    score, _ = brand_color_adherence(ctx)
    assert score <= 2


def test_brand_color_skipped_without_palette(tmp_path):
    frames = _write_solid_frames(tmp_path / "x", (10, 10, 10))
    ctx = ScoreContext(frames=frames, brand_palette=[], scale_min=1, scale_max=5)
    score, note = brand_color_adherence(ctx)
    assert score is None and "skipped" in note


def test_loopability_identical_first_last_high(tmp_path):
    frames = _write_solid_frames(tmp_path / "same", (100, 100, 100))
    ctx = ScoreContext(frames=frames, brand_palette=[], scale_min=1, scale_max=5)
    score, _ = loopability(ctx)
    assert score == 5


def test_loopability_different_first_last_low(tmp_path):
    # First frame black, last frame white -> max MSE -> low score.
    frames = _write_solid_frames(tmp_path / "diff", (0, 0, 0), n=1)
    frames += _write_solid_frames(tmp_path / "diff2", (255, 255, 255), n=1)
    ctx = ScoreContext(frames=frames, brand_palette=[], scale_min=1, scale_max=5)
    score, _ = loopability(ctx)
    assert score == 1
