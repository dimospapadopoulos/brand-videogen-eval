"""Provider abstraction — the extensibility core.

Adding a new image-to-video model means writing one subclass of
`ImageToVideoProvider`, decorating it with `@register("<name>")`, and nothing
else. The runner, judge, store, and dashboard never change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from vgeval.schemas import GenRequest, VideoResult


class ImageToVideoProvider(ABC):
    """Turns a (source image + prompt) into a video.

    Implementations should be safe to instantiate cheaply; heavy clients (SDKs,
    sessions) may be created lazily. `generate` is async so the runner can drive
    many in flight at once.
    """

    #: Stable, unique provider name used on the CLI and in run manifests.
    name: str = "base"

    def __init__(self, **config: object) -> None:
        self.config = config

    @abstractmethod
    async def generate(self, req: GenRequest, *, out_dir: str) -> VideoResult:
        """Generate a video for `req`, writing the mp4 under `out_dir`.

        Must return a `VideoResult` whose `video_path` points at the written
        file. Should raise on failure so the runner can mark the job failed and
        retry per policy.
        """
        raise NotImplementedError
