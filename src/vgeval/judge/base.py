"""Judge protocol + a deterministic stub used for offline tests, CI, and canary."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol, runtime_checkable

from vgeval.judge.rubric import Rubric
from vgeval.schemas import GenRequest, JudgeScore, VideoResult


@runtime_checkable
class Judge(Protocol):
    def score(self, req: GenRequest, result: VideoResult, frames: list[Path]) -> JudgeScore: ...


class StubJudge:
    """Keyless judge that returns deterministic pseudo-scores.

    Used by tests, CI, and the shadow canary so the whole pipeline exercises
    end-to-end without an API key. Scores are stable per job_id.
    """

    def __init__(self, rubric: Rubric) -> None:
        self.rubric = rubric

    def score(self, req: GenRequest, result: VideoResult, frames: list[Path]) -> JudgeScore:
        lo, hi = self.rubric.scale.min, self.rubric.scale.max
        span = hi - lo + 1
        dims: dict[str, int] = {}
        for d in self.rubric.dims:
            seed = f"{req.job_id}:{d.name}"
            h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
            dims[d.name] = lo + (h % span)
        return JudgeScore(
            job_id=req.job_id,
            provider=result.provider,
            prompt_id=req.prompt_id,
            dims=dims,
            rationale="stub judge (deterministic; no API call)",
            flags=[],
        )
