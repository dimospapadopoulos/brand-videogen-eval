"""Pydantic data models shared across the harness.

These define the on-disk contract for a run directory so runs are reproducible
and resumable. All models round-trip cleanly to/from JSON.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# The fixed rubric dimensions. This ordering is the canonical one used across
# the judge, the run manifests, and the dashboard. Keep in sync with
# judge/rubric.yaml.
RUBRIC_DIMS: tuple[str, ...] = (
    "prompt_adherence",
    "object_deformation",
    "object_cutoff",
    "flickering",
    "fast_camera_movement",
    "video_quality",
    "defied_physics",
    "temporal_object_creation",
    "aesthetics",
)


class JobStatus(StrEnum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class GenRequest(BaseModel):
    """A single image-to-video generation request."""

    job_id: str
    prompt_id: str
    prompt: str
    source_image: str  # path relative to repo root or absolute
    params: dict[str, Any] = Field(default_factory=dict)


class VideoResult(BaseModel):
    """The output of a provider.generate() call."""

    provider: str
    job_id: str
    video_path: str
    seconds: float
    fps: float
    meta: dict[str, Any] = Field(default_factory=dict)


class JobState(BaseModel):
    """Tracks a job's lifecycle for resume/caching. One line in jobs.jsonl."""

    job_id: str
    provider: str
    prompt_id: str
    cache_key: str
    status: JobStatus = JobStatus.pending
    attempts: int = 0
    video_path: str | None = None
    error: str | None = None


class JudgeScore(BaseModel):
    """A judge's assessment of one video. One line in results.jsonl."""

    job_id: str
    provider: str
    prompt_id: str
    # dim name -> integer score on the rubric's scale
    dims: dict[str, int]
    rationale: str = ""
    flags: list[str] = Field(default_factory=list)


class PairwiseVerdict(BaseModel):
    """Pairwise A/B judgement between two providers on the same input."""

    prompt_id: str
    provider_a: str
    provider_b: str
    winner: str  # provider_a | provider_b | "tie"
    rationale: str = ""


class RunManifest(BaseModel):
    """Top-level manifest for a run directory (manifest.json)."""

    run_id: str
    created_at: datetime
    providers: list[str]
    suite_version: str
    rubric_version: str
    jobs: list[JobState] = Field(default_factory=list)
