"""Skeletons for real image-to-video providers.

These are intentionally NOT registered (the bodies are commented out) so v1 runs
with zero external dependencies. To ship a real provider: copy one skeleton into
its own module, uncomment, implement `generate`, add the SDK to pyproject
dependencies, and it becomes available on the CLI automatically.

See docs/adding-a-provider.md for the full walkthrough.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Runway (Gen-family image-to-video)
# --------------------------------------------------------------------------- #
# from vgeval.providers.base import ImageToVideoProvider
# from vgeval.providers.registry import register
# from vgeval.schemas import GenRequest, VideoResult
#
# @register("runway")
# class RunwayProvider(ImageToVideoProvider):
#     def __init__(self, *, model: str = "gen-latest", **config):
#         super().__init__(**config)
#         import runwayml  # add to dependencies
#         self.client = runwayml.AsyncClient()
#         self.model = model
#
#     async def generate(self, req: GenRequest, *, out_dir: str) -> VideoResult:
#         # 1. upload / reference req.source_image
#         # 2. create image-to-video task with req.prompt + req.params
#         # 3. poll until complete, download the mp4 into out_dir/<job_id>.mp4
#         # 4. return VideoResult(provider=self.name, job_id=req.job_id, video_path=..., ...)
#         ...


# --------------------------------------------------------------------------- #
# Kling
# --------------------------------------------------------------------------- #
# @register("kling")
# class KlingProvider(ImageToVideoProvider):
#     async def generate(self, req: GenRequest, *, out_dir: str) -> VideoResult:
#         ...


# --------------------------------------------------------------------------- #
# Google Veo (image-to-video)
# --------------------------------------------------------------------------- #
# @register("veo")
# class VeoProvider(ImageToVideoProvider):
#     async def generate(self, req: GenRequest, *, out_dir: str) -> VideoResult:
#         ...


# --------------------------------------------------------------------------- #
# OpenAI Sora (image-to-video)
# --------------------------------------------------------------------------- #
# @register("sora")
# class SoraProvider(ImageToVideoProvider):
#     async def generate(self, req: GenRequest, *, out_dir: str) -> VideoResult:
#         ...
