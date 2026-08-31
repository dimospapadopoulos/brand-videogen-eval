"""Aggregate a run's judge scores into leaderboard / per-dimension summaries.

Dimension-agnostic: the dimension set and order come from the run's rubric
snapshot when present, else from the union of scored dims. Pure functions over
the store so the CLI and dashboard share one source of truth.
"""

from __future__ import annotations

from statistics import mean

import yaml

from vgeval.store import RunStore


def run_dims(run_id: str) -> list[str]:
    """Ordered dimension names for a run (rubric snapshot first, else observed)."""
    store = RunStore.open(run_id)
    snap = store.read_rubric_snapshot()
    if snap:
        data = yaml.safe_load(snap)
        return [d["name"] for d in data.get("dims", [])]
    seen: list[str] = []
    for s in store.read_results():
        for k in s.dims:
            if k not in seen:
                seen.append(k)
    return seen


def dim_bands(run_id: str) -> dict[str, str]:
    """dim name -> band, from the rubric snapshot (empty if none)."""
    snap = RunStore.open(run_id).read_rubric_snapshot()
    if not snap:
        return {}
    data = yaml.safe_load(snap)
    return {d["name"]: d.get("band", "general") for d in data.get("dims", [])}


def per_dimension(run_id: str) -> list[dict]:
    """Mean of each scored dim per provider (dims absent for a provider omitted)."""
    scores = RunStore.open(run_id).read_results()
    dims = run_dims(run_id)
    by_provider: dict[str, list] = {}
    for s in scores:
        by_provider.setdefault(s.provider, []).append(s)
    rows = []
    for provider, items in sorted(by_provider.items()):
        row: dict = {"provider": provider, "n": len(items)}
        for dim in dims:
            vals = [i.dims[dim] for i in items if dim in i.dims]
            if vals:
                row[dim] = round(mean(vals), 3)
        rows.append(row)
    return rows


def leaderboard(run_id: str) -> list[dict]:
    """Providers ranked by overall mean (mean across that provider's scored dims)."""
    dims = run_dims(run_id)
    rows = per_dimension(run_id)
    for row in rows:
        present = [row[d] for d in dims if d in row]
        row["overall"] = round(mean(present), 3) if present else 0.0
    return sorted(rows, key=lambda r: r["overall"], reverse=True)


def pairwise_winrates(run_id: str) -> dict[str, float]:
    """Win rate per provider from recorded pairwise verdicts (if any)."""
    verdicts = RunStore.open(run_id).read_pairwise()
    wins: dict[str, int] = {}
    games: dict[str, int] = {}
    for v in verdicts:
        for p in (v.provider_a, v.provider_b):
            games[p] = games.get(p, 0) + 1
        if v.winner != "tie":
            wins[v.winner] = wins.get(v.winner, 0) + 1
    return {p: round(wins.get(p, 0) / g, 3) for p, g in games.items() if g}
