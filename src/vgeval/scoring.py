"""Judge a completed run with the hybrid engine.

Routing per rubric dimension:
  * deterministic dims  -> CV scorers in judge/scorers.py (keyless, always run)
  * vlm / human dims     -> the VLM judge (Opus 4.8) or the keyless StubJudge

Deterministic scores run even in stub mode, so the keyless canary still
exercises the real ΔE / loop-seam math. The rubric is snapshotted into the run
for auditability.
"""

from __future__ import annotations

from pathlib import Path

from vgeval.judge.base import Judge, StubJudge
from vgeval.judge.rubric import Rubric, resolve_rubric
from vgeval.judge.scorers import ScoreContext, run_deterministic
from vgeval.schemas import JobStatus, JudgeScore, VideoResult
from vgeval.store import RunStore


def _build_judge(rubric: Rubric, use_stub: bool) -> Judge:
    if use_stub:
        return StubJudge(rubric)
    from vgeval.judge.claude_judge import ClaudeJudge

    return ClaudeJudge(rubric)


def _score_deterministic(
    rubric: Rubric, ctx: ScoreContext
) -> tuple[dict[str, int], dict[str, str], list[str], list[str]]:
    """Compute only the deterministic dims -> (dims, methods, skipped, notes)."""
    dims: dict[str, int] = {}
    methods: dict[str, str] = {}
    skipped: list[str] = []
    notes: list[str] = []
    for d in rubric.deterministic_dims():
        score, note = run_deterministic(d.name, ctx)
        methods[d.name] = d.method.value
        notes.append(f"{d.name}: {note}")
        if score is None:
            skipped.append(d.name)
        else:
            dims[d.name] = score
    return dims, methods, skipped, notes


def judge_run(
    run_id: str,
    *,
    use_stub: bool = False,
    force: bool = False,
    rubric_name: str | None = None,
) -> list[JudgeScore]:
    """Score every `done` job in the run. Idempotent unless `force`."""
    store = RunStore.open(run_id)
    manifest = store.read_manifest()
    rubric = resolve_rubric(rubric_name or manifest.rubric_version)
    store.write_rubric_snapshot(_rubric_yaml(rubric))

    requests = store.read_requests()
    states = store.read_job_states()
    if force and store.results_path.exists():
        store.results_path.unlink()  # fresh re-score, don't append to stale results
    already = {s.job_id for s in store.read_results()} if not force else set()
    judge = _build_judge(rubric, use_stub)
    vlm_dims = rubric.vlm_dims()

    scored: list[JudgeScore] = []
    for job_id, state in states.items():
        if state.status != JobStatus.done or not state.video_path:
            continue
        if job_id in already:
            continue
        req = requests.get(job_id)
        if req is None:
            continue
        frames = [Path(f) for f in sorted((store.frames_dir / job_id).glob("frame_*.png"))]

        # 1. deterministic band (keyless, always runs)
        ctx = ScoreContext(
            frames=frames,
            brand_palette=req.brand_palette,
            scale_min=rubric.scale.min,
            scale_max=rubric.scale.max,
        )
        det_dims, det_methods, det_skipped, det_notes = _score_deterministic(rubric, ctx)

        # 2. vlm / human band
        result = VideoResult(
            provider=state.provider, job_id=job_id, video_path=state.video_path,
            seconds=0.0, fps=0.0,
        )
        vlm_score = judge.score(req, result, frames, vlm_dims)

        # 3. merge
        merged = JudgeScore(
            job_id=job_id,
            provider=state.provider,
            prompt_id=req.prompt_id,
            dims={**vlm_score.dims, **det_dims},
            methods={**vlm_score.methods, **det_methods},
            rationale=vlm_score.rationale,
            flags=vlm_score.flags + det_notes,
            skipped=vlm_score.skipped + det_skipped,
            # Rubric-driven so it's consistent for both the stub and real judge.
            needs_review=[d.name for d in rubric.human_dims()],
            transcribed_text=vlm_score.transcribed_text,
        )
        store.append_result(merged)
        scored.append(merged)
    return scored


def _rubric_yaml(rubric: Rubric) -> str:
    import yaml

    return yaml.safe_dump(rubric.model_dump(mode="json"), sort_keys=False)
