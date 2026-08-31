# Adding a new image-to-video provider

The whole point of the harness: shipping support for a new model is **one file**.
The runner, judge, store, and dashboard never change.

> **Just want to compare clips you already generated?** You don't need to write an
> adapter at all — use the bring-your-own-clips `local` provider: drop each model's
> clips into `assets/samples/videos/<model>/<prompt_id>.mp4` and each folder becomes
> a provider automatically. See the README's *"Compare real model outputs"* section.
> The steps below are for wiring a model's **generation API** end-to-end.

## 1. Write the adapter

Create `src/vgeval/providers/<name>.py`:

```python
from vgeval.providers.base import ImageToVideoProvider
from vgeval.providers.registry import register
from vgeval.schemas import GenRequest, VideoResult


@register("runway")
class RunwayProvider(ImageToVideoProvider):
    def __init__(self, *, model: str = "gen-latest", **config):
        super().__init__(**config)
        import runwayml  # add to pyproject dependencies
        self.client = runwayml.AsyncClient()
        self.model = model

    async def generate(self, req: GenRequest, *, out_dir: str) -> VideoResult:
        # 1. upload / reference req.source_image
        # 2. start an image-to-video job with req.prompt + req.params
        # 3. poll to completion, download the mp4 to out_dir/<job_id>.mp4
        from pathlib import Path
        dest = Path(out_dir) / f"{req.job_id}.mp4"
        # ... write the file ...
        return VideoResult(
            provider=self.name,
            job_id=req.job_id,
            video_path=str(dest),
            seconds=4.0,
            fps=24.0,
            meta={"model": self.model},
        )
```

Skeletons for Runway / Kling / Veo / Sora already live in
[`src/vgeval/providers/_stubs.py`](../src/vgeval/providers/_stubs.py).

## 2. Register it for import

Add the import to `src/vgeval/providers/__init__.py` so the decorator runs:

```python
from vgeval.providers import mock, runway  # noqa: F401
```

## 3. Add the SDK dependency

```toml
# pyproject.toml
dependencies = [ ..., "runwayml>=x.y" ]
```
Then `uv pip install -e ".[dev]"`.

## 4. Use it

```bash
uv run vgeval providers                     # runway now listed
uv run vgeval run --provider mock --provider runway
uv run vgeval judge                         # Opus 4.8 scores both
uv run vgeval dashboard                     # Compare tab shows them side by side
```

## Contract & tips

- `generate` is **async** — the runner drives many concurrently (`VGEVAL_CONCURRENCY`).
- **Raise on failure.** The runner retries up to `MAX_ATTEMPTS`, then marks the
  job `failed` without aborting the batch.
- Write the mp4 under the given `out_dir`; return its path in `VideoResult`.
- Outputs are **content-cached** by `(provider, prompt, source_image, params)`,
  so identical re-runs are free — vary `params` to force a fresh generation.
- Keep provider names **stable**; they appear in run manifests and the leaderboard.
