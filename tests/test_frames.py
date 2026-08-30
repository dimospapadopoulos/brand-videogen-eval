import imageio.v3 as iio
import numpy as np

from vgeval.frames import extract_frames, save_frames


def _write_video(path, n=10, size=32):
    frames = (np.random.default_rng(1).random((n, size, size, 3)) * 255).astype(np.uint8)
    iio.imwrite(path, frames, fps=8, codec="libx264")


def test_extract_frames_count(tmp_path):
    vid = tmp_path / "v.mp4"
    _write_video(vid)
    frames = extract_frames(vid, n=4)
    assert len(frames) == 4
    assert frames[0].ndim == 3 and frames[0].shape[-1] == 3


def test_save_frames_writes_pngs(tmp_path):
    vid = tmp_path / "v.mp4"
    _write_video(vid)
    out = tmp_path / "frames"
    paths = save_frames(vid, out, n=3)
    assert len(paths) == 3
    assert all(p.exists() and p.suffix == ".png" for p in paths)
