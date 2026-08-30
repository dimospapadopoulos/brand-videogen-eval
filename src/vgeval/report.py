"""Aggregate a run's judge scores into leaderboard / per-dimension summaries.

Pure functions over the run store so both the CLI and the Streamlit dashboard
share one source of truth.
"""

from __future__ import annotations

from statistics import mean

from vgeval.schemas import RUBRIC_DIMS
from vgeval.store import RunStore


def _scores(run_id: str):
    return RunStore.open(run_id).read_results()


def per_dimension(run_id: str) -> list[dict]:
    """Mean of each rubric dim per provider."""
    scores = _scores(run_id)
    by_provider: dict[str, list] = {}
    for s in scores:
        by_provider.setdefault(s.provider, []).append(s)
    rows = []
    for provider, items in sorted(by_provider.items()):
        row = {"provider": provider, "n": len(items)}
        for dim in RUBRIC_DIMS:
            row[dim] = round(mean(i.dims.get(dim, 0) for i in items), 3)
        rows.append(row)
    return rows


def leaderboard(run_id: str) -> list[dict]:
    """Providers ranked by overall mean (mean across all dims)."""
    rows = per_dimension(run_id)
    for row in rows:
        row["overall"] = round(mean(row[d] for d in RUBRIC_DIMS), 3)
    return sorted(rows, key=lambda r: r["overall"], reverse=True)


def pairwise_winrates(run_id: str) -> dict[str, float]:
    """Win rate per provider from recorded pairwise verdicts (if any)."""
    verdicts = RunStore.open(run_id).read_pairwise()
    wins: dict[str, int] = {}
    games: dict[str, int] = {}
    for v in verdicts:
        for p in (v.provider_a, v.provider_b):
            games[p] = games.get(p, 0) + 1
        if v.winner in wins or v.winner not in ("tie",):
            wins[v.winner] = wins.get(v.winner, 0) + 1
    return {p: round(wins.get(p, 0) / g, 3) for p, g in games.items() if g}
