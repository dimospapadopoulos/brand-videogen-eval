"""End-to-end on the mock path: generate -> stub judge -> full run dir."""

import asyncio

from vgeval.report import leaderboard
from vgeval.runner import run_batch
from vgeval.schemas import RUBRIC_DIMS
from vgeval.scoring import judge_run
from vgeval.store import RunStore


def test_full_mock_pipeline(temp_suite):
    rid = asyncio.run(run_batch(["mock"], temp_suite))
    store = RunStore.open(rid)

    # Generation artifacts exist.
    videos = list(store.videos_dir.glob("*.mp4"))
    assert len(videos) == 2  # 2 prompts × 1 provider
    assert store.manifest_path.exists()

    # Stub judge scores every done job with all 9 dims.
    scored = judge_run(rid, use_stub=True)
    assert len(scored) == 2
    for s in scored:
        assert set(s.dims) == set(RUBRIC_DIMS)

    # Judging is idempotent (no double-scoring without --force).
    assert judge_run(rid, use_stub=True) == []

    # Leaderboard aggregates.
    board = leaderboard(rid)
    assert board and "overall" in board[0]
