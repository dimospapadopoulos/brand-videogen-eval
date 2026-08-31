"""Async generation runner: provider × prompt matrix, resumable and cached.

Sized for hundreds of jobs per batch:
  * bounded asyncio worker pool (concurrency from settings)
  * resume: a re-run reads jobs.jsonl and skips jobs already `done`
  * cache: identical (provider, prompt, source_image, params) reuse a prior
    output from an on-disk content cache, so re-runs and duplicate inputs are
    near-free
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from vgeval.config import REPO_ROOT, get_settings
from vgeval.frames import save_frames
from vgeval.prompts import Suite, load_suite
from vgeval.providers import get_provider
from vgeval.schemas import GenRequest, JobState, JobStatus, RunManifest
from vgeval.store import RunStore

MAX_ATTEMPTS = 2


def _cache_key(provider: str, prompt: str, source_image: str, params: dict) -> str:
    payload = json.dumps(
        {"provider": provider, "prompt": prompt, "src": source_image, "params": params},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _job_id(provider: str, prompt_id: str) -> str:
    return f"{provider}__{prompt_id}"


def _resolve_image(path: str) -> str:
    p = Path(path)
    return str(p if p.is_absolute() else REPO_ROOT / p)


def build_jobs(providers: list[str], suite: Suite) -> list[tuple[str, GenRequest]]:
    """Cartesian product of providers × prompts -> (provider, GenRequest)."""
    jobs: list[tuple[str, GenRequest]] = []
    for provider in providers:
        for entry in suite.prompts:
            req = GenRequest(
                job_id=_job_id(provider, entry.id),
                prompt_id=entry.id,
                prompt=entry.prompt,
                source_image=_resolve_image(entry.source_image),
                params={},
                expected_copy=entry.expected_copy,
                locale=entry.locale,
                brand_palette=entry.brand_palette,
                logo_ref=_resolve_image(entry.logo_ref) if entry.logo_ref else None,
            )
            jobs.append((provider, req))
    return jobs


def _new_run_id() -> str:
    return datetime.now(UTC).strftime("run_%Y%m%d_%H%M%S")


async def run_batch(
    providers: list[str],
    suite_name: str = "example_suite",
    *,
    concurrency: int | None = None,
    run_id: str | None = None,
    rubric_version: str = "rubric_v1",
) -> str:
    """Generate all videos for the matrix. Returns the run_id.

    If `run_id` names an existing run, generation resumes (done jobs skipped).
    """
    settings = get_settings()
    concurrency = concurrency or settings.concurrency
    cache_dir = settings.cache_dir
    suite = load_suite(suite_name)
    jobs = build_jobs(providers, suite)

    # Open-or-create the run.
    if run_id and (settings.runs_dir / run_id / "manifest.json").exists():
        store = RunStore.open(run_id)
        manifest = store.read_manifest()
    else:
        run_id = run_id or _new_run_id()
        manifest = RunManifest(
            run_id=run_id,
            created_at=datetime.now(UTC),
            providers=providers,
            suite_version=suite.version,
            rubric_version=rubric_version,
            jobs=[],
        )
        store = RunStore.create(run_id, manifest)

    existing = store.read_job_states()
    provider_cache = {name: get_provider(name) for name in providers}
    sem = asyncio.Semaphore(concurrency)

    async def worker(provider_name: str, req: GenRequest) -> JobState:
        prior = existing.get(req.job_id)
        if prior and prior.status == JobStatus.done:
            return prior  # resume: already generated

        store.append_request(req)
        ckey = _cache_key(provider_name, req.prompt, req.source_image, req.params)
        state = JobState(
            job_id=req.job_id,
            provider=provider_name,
            prompt_id=req.prompt_id,
            cache_key=ckey,
            status=JobStatus.running,
        )
        async with sem:
            cached = cache_dir / f"{ckey}.mp4"
            dest = store.videos_dir / f"{req.job_id}.mp4"
            try:
                if cached.exists():
                    shutil.copyfile(cached, dest)
                    state.video_path = str(dest)
                else:
                    for attempt in range(1, MAX_ATTEMPTS + 1):
                        state.attempts = attempt
                        try:
                            result = await provider_cache[provider_name].generate(
                                req, out_dir=str(store.videos_dir)
                            )
                            state.video_path = result.video_path
                            cache_dir.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(result.video_path, cached)
                            break
                        except Exception as exc:  # noqa: BLE001
                            if attempt >= MAX_ATTEMPTS:
                                raise
                            state.error = f"attempt {attempt}: {exc}"
                # Sample frames for the judge / dashboard.
                save_frames(
                    state.video_path,
                    store.frames_dir / req.job_id,
                    n=settings.judge_frames,
                )
                state.status = JobStatus.done
                state.error = None
            except Exception as exc:  # noqa: BLE001
                state.status = JobStatus.failed
                state.error = str(exc)
        store.append_job(state)
        return state

    await asyncio.gather(*(worker(p, r) for p, r in jobs))

    # Refresh manifest job list with final states.
    final_states = store.read_job_states()
    manifest.jobs = list(final_states.values())
    store.write_manifest(manifest)
    return run_id
