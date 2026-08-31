"""Bring-your-own-clips provider.

Lets you evaluate and compare *real* model outputs without wiring each vendor's
API: generate clips in Sora / Veo / Runway / Kling (their UIs or your own
pipeline), drop them into a per-model folder, and each folder becomes a provider.

Layout (one subfolder per model; filename == prompt id):

    assets/samples/videos/
      sora/   nike_basketball.mp4   lipton_icetea.mp4
      veo/    nike_basketball.mp4   lipton_icetea.mp4
      runway/ nike_basketball.mp4   lipton_icetea.mp4

Then:  vgeval run --suite promo_v1 --provider sora --provider veo --rubric rubric_v2

Only the judge costs money — there is no generation API call. Discovery is
explicit (call `register_local_providers()`), so it picks up folders added since
process start; the CLI calls it for you.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from vgeval.config import get_settings
from vgeval.providers.base import ImageToVideoProvider
from vgeval.providers.registry import available, register
from vgeval.schemas import GenRequest, VideoResult

_VIDEO_EXTS = (".mp4", ".mov", ".webm", ".gif")


def _videos_root() -> Path:
    return get_settings().assets_dir / "videos"


def _find_clip(model_dir: Path, prompt_id: str) -> Path | None:
    if not model_dir.exists():
        return None
    for ext in _VIDEO_EXTS:
        p = model_dir / f"{prompt_id}{ext}"
        if p.exists():
            return p
    for p in sorted(model_dir.glob(f"{prompt_id}.*")):
        if p.suffix.lower() in _VIDEO_EXTS:
            return p
    return None


class LocalClipProvider(ImageToVideoProvider):
    """Serves a pre-generated clip matching the prompt id from this model's folder."""

    async def generate(self, req: GenRequest, *, out_dir: str) -> VideoResult:
        model_dir = _videos_root() / self.name
        src = _find_clip(model_dir, req.prompt_id)
        if src is None:
            raise FileNotFoundError(
                f"No clip for prompt {req.prompt_id!r} in {model_dir}. "
                f"Expected {req.prompt_id}.mp4 (or .mov/.webm/.gif)."
            )
        dest = Path(out_dir) / f"{req.job_id}.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        return VideoResult(
            provider=self.name,
            job_id=req.job_id,
            video_path=str(dest),
            seconds=0.0,
            fps=0.0,
            meta={"source_kind": "local", "sample_file": src.name, "prompt": req.prompt},
        )


def discover_models() -> list[str]:
    """Model subfolder names under assets/samples/videos/ (excluding loose files)."""
    root = _videos_root()
    if not root.exists():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir())


def register_local_providers() -> list[str]:
    """Register one provider per model subfolder. Idempotent; skips name clashes."""
    newly: list[str] = []
    existing = set(available())
    for model in discover_models():
        if model in existing:
            continue  # don't shadow built-ins like `mock`
        # A distinct subclass per model so each carries its own `name`.
        cls = type(f"Local_{model}", (LocalClipProvider,), {})
        register(model)(cls)
        newly.append(model)
    return newly
