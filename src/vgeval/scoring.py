"""Judge a completed run: read done jobs, score each, append results.jsonl."""

from __future__ import annotations

from pathlib import Path

from vgeval.judge.base import Judge, StubJudge
from vgeval.judge.rubric import load_rubric
from vgeval.schemas import JobStatus, JudgeScore, VideoResult
from vgeval.store import RunStore


def _build_judge(use_stub: bool) -> tuple[Judge, str]:
    rubric = load_rubric()
    if use_stub:
        return StubJudge(rubric), rubric.version
    from vgeval.judge.claude_judge import ClaudeJudge

    return ClaudeJudge(rubric), rubric.version


def judge_run(run_id: str, *, use_stub: bool = False, force: bool = False) -> list[JudgeScore]:
    """Score every `done` job in the run. Idempotent unless `force`."""
    store = RunStore.open(run_id)
    requests = store.read_requests()
    states = store.read_job_states()

    already = {s.job_id for s in store.read_results()} if not force else set()
    judge, _ = _build_judge(use_stub)

    scored: list[JudgeScore] = []
    for job_id, state in states.items():
        if state.status != JobStatus.done or not state.video_path:
            continue
        if job_id in already:
            continue
        req = requests.get(job_id)
        if req is None:
            continue
        frames = sorted((store.frames_dir / job_id).glob("frame_*.png"))
        result = VideoResult(
            provider=state.provider,
            job_id=job_id,
            video_path=state.video_path,
            seconds=0.0,
            fps=0.0,
        )
        score = judge.score(req, result, [Path(f) for f in frames])
        store.append_result(score)
        scored.append(score)
    return scored
