"""Read/write a run directory.

Layout:
    runs/<run_id>/
      manifest.json      # RunManifest (providers, versions, job states)
      jobs.jsonl         # append-only JobState log (source of truth for resume)
      videos/<job>.mp4   # generated outputs
      frames/<job>/*.png # sampled frames for the judge / dashboard
      results.jsonl      # append-only JudgeScore log
      pairwise.jsonl     # append-only PairwiseVerdict log (optional)
"""

from __future__ import annotations

import json
from pathlib import Path

from vgeval.config import get_settings
from vgeval.schemas import (
    ExternalScore,
    GenRequest,
    JobState,
    JudgeScore,
    PairwiseVerdict,
    RunManifest,
)


class RunStore:
    def __init__(self, run_dir: str | Path) -> None:
        self.dir = Path(run_dir)
        self.videos_dir = self.dir / "videos"
        self.frames_dir = self.dir / "frames"
        self.manifest_path = self.dir / "manifest.json"
        self.jobs_path = self.dir / "jobs.jsonl"
        self.requests_path = self.dir / "requests.jsonl"
        self.results_path = self.dir / "results.jsonl"
        self.pairwise_path = self.dir / "pairwise.jsonl"
        self.external_path = self.dir / "external.jsonl"
        self.rubric_path = self.dir / "rubric.snapshot.yaml"

    # -- creation / discovery ------------------------------------------------ #
    @classmethod
    def create(cls, run_id: str, manifest: RunManifest) -> RunStore:
        store = cls(get_settings().runs_dir / run_id)
        store.videos_dir.mkdir(parents=True, exist_ok=True)
        store.frames_dir.mkdir(parents=True, exist_ok=True)
        store.write_manifest(manifest)
        return store

    @classmethod
    def open(cls, run_id: str) -> RunStore:
        store = cls(get_settings().runs_dir / run_id)
        if not store.manifest_path.exists():
            raise FileNotFoundError(f"No run {run_id!r} at {store.dir}")
        return store

    @staticmethod
    def latest_run_id() -> str | None:
        runs_dir = get_settings().runs_dir
        if not runs_dir.exists():
            return None
        candidates = [p for p in runs_dir.iterdir() if (p / "manifest.json").exists()]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime).name

    # -- manifest ------------------------------------------------------------ #
    def write_manifest(self, manifest: RunManifest) -> None:
        self.manifest_path.write_text(manifest.model_dump_json(indent=2))

    def read_manifest(self) -> RunManifest:
        return RunManifest.model_validate_json(self.manifest_path.read_text())

    # -- append-only logs ---------------------------------------------------- #
    def append_job(self, state: JobState) -> None:
        _append_jsonl(self.jobs_path, state.model_dump())

    def append_request(self, req: GenRequest) -> None:
        _append_jsonl(self.requests_path, req.model_dump())

    def append_result(self, score: JudgeScore) -> None:
        _append_jsonl(self.results_path, score.model_dump())

    def append_pairwise(self, verdict: PairwiseVerdict) -> None:
        _append_jsonl(self.pairwise_path, verdict.model_dump())

    def append_external(self, score: ExternalScore) -> None:
        _append_jsonl(self.external_path, score.model_dump())

    def write_rubric_snapshot(self, text: str) -> None:
        """Freeze the rubric used for scoring into the run (auditability)."""
        self.rubric_path.write_text(text)

    def read_rubric_snapshot(self) -> str | None:
        return self.rubric_path.read_text() if self.rubric_path.exists() else None

    # -- reads --------------------------------------------------------------- #
    def read_job_states(self) -> dict[str, JobState]:
        """Latest JobState per job_id (last write wins), for resume."""
        states: dict[str, JobState] = {}
        for row in _read_jsonl(self.jobs_path):
            s = JobState.model_validate(row)
            states[s.job_id] = s
        return states

    def read_requests(self) -> dict[str, GenRequest]:
        reqs: dict[str, GenRequest] = {}
        for row in _read_jsonl(self.requests_path):
            r = GenRequest.model_validate(row)
            reqs[r.job_id] = r
        return reqs

    def read_results(self) -> list[JudgeScore]:
        return [JudgeScore.model_validate(r) for r in _read_jsonl(self.results_path)]

    def read_pairwise(self) -> list[PairwiseVerdict]:
        return [PairwiseVerdict.model_validate(r) for r in _read_jsonl(self.pairwise_path)]

    def read_external(self) -> list[ExternalScore]:
        return [ExternalScore.model_validate(r) for r in _read_jsonl(self.external_path)]


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(obj, default=str) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
