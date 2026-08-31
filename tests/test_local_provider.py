"""Bring-your-own-clips (`local`) provider: one provider per model subfolder."""

import asyncio

import imageio.v3 as iio
import numpy as np
import pytest

from vgeval.providers import available, get_provider, register_local_providers
from vgeval.schemas import GenRequest


def _write_clip(path, n=6, size=32):
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = (np.random.default_rng(2).random((n, size, size, 3)) * 255).astype(np.uint8)
    iio.imwrite(path, frames, fps=8, codec="libx264")


@pytest.fixture
def byo_videos(tmp_path, monkeypatch):
    """Two model folders (sora, veo) each with a clip for prompt 'p1'."""
    assets = tmp_path / "samples"
    monkeypatch.setenv("VGEVAL_ASSETS_DIR", str(assets))
    for model in ("sora", "veo"):
        _write_clip(assets / "videos" / model / "p1.mp4")
    return assets


def test_discovers_and_registers_model_folders(byo_videos):
    register_local_providers()
    assert {"sora", "veo"} <= set(available())


def test_local_provider_serves_matching_clip(byo_videos, tmp_path):
    register_local_providers()
    prov = get_provider("sora")
    req = GenRequest(job_id="sora__p1", prompt_id="p1", prompt="x", source_image="na.png")
    out = tmp_path / "out"
    result = asyncio.run(prov.generate(req, out_dir=str(out)))
    assert result.provider == "sora"
    assert (out / "sora__p1.mp4").exists()
    assert result.meta["source_kind"] == "local"


def test_missing_clip_raises(byo_videos, tmp_path):
    register_local_providers()
    prov = get_provider("veo")
    req = GenRequest(job_id="veo__missing", prompt_id="missing", prompt="x", source_image="na.png")
    with pytest.raises(FileNotFoundError):
        asyncio.run(prov.generate(req, out_dir=str(tmp_path / "o")))
