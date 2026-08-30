"""Resume: a re-run reuses done jobs instead of regenerating them."""

import asyncio

from vgeval.runner import run_batch
from vgeval.schemas import JobStatus
from vgeval.store import RunStore


def test_rerun_skips_completed_jobs(temp_suite):
    rid = asyncio.run(run_batch(["mock"], temp_suite, run_id="fixed"))
    store = RunStore.open(rid)
    states = store.read_job_states()
    assert states and all(s.status == JobStatus.done for s in states.values())

    # Capture mtimes of generated videos.
    first = {p.name: p.stat().st_mtime_ns for p in store.videos_dir.glob("*.mp4")}
    assert first

    # Re-run the same run id: jobs are already done -> videos untouched.
    asyncio.run(run_batch(["mock"], temp_suite, run_id="fixed"))
    second = {p.name: p.stat().st_mtime_ns for p in store.videos_dir.glob("*.mp4")}
    assert first == second  # no regeneration happened
