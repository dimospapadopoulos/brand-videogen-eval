"""Shared fixtures: isolate runs/cache/assets into a tmp dir per test session."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Point vgeval at a temp runs dir and disable any real API key."""
    monkeypatch.setenv("VGEVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("VGEVAL_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("VGEVAL_JUDGE_FRAMES", "4")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Run from a scratch dir so a developer's real ./.env can't leak into tests.
    monkeypatch.chdir(tmp_path)
    # Clear cached settings singletons if any imported module memoized them.
    yield


@pytest.fixture
def sample_image(tmp_path):
    """A tiny valid PNG source image."""
    import imageio.v3 as iio

    p = tmp_path / "src.png"
    arr = (np.random.default_rng(0).random((64, 64, 3)) * 255).astype(np.uint8)
    iio.imwrite(p, arr)
    return p


@pytest.fixture
def temp_suite(tmp_path, monkeypatch):
    """Write a 2-prompt suite with real source images; return its suite name."""
    import imageio.v3 as iio
    import yaml

    prompts_dir = tmp_path / "prompts"
    img_dir = tmp_path / "imgs"
    prompts_dir.mkdir()
    img_dir.mkdir()
    monkeypatch.setenv("VGEVAL_PROMPTS_DIR", str(prompts_dir))

    entries = []
    for i in (1, 2):
        img = img_dir / f"p{i}.png"
        arr = (np.random.default_rng(i).random((48, 48, 3)) * 255).astype(np.uint8)
        iio.imwrite(img, arr)
        entries.append(
            {"id": f"p{i}", "prompt": f"prompt {i}", "source_image": str(img), "category": "test"}
        )
    suite = {"version": "test_v1", "prompts": entries}
    (prompts_dir / "t_suite.yaml").write_text(yaml.safe_dump(suite))
    return "t_suite"
