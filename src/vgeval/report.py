"""Aggregate a run's judge scores into leaderboard / per-dimension summaries.

Dimension-agnostic: the dimension set and order come from the run's rubric
snapshot when present, else from the union of scored dims. Pure functions over
the store so the CLI and dashboard share one source of truth.
"""

from __future__ import annotations

from statistics import mean

import yaml

from vgeval.schemas import DEFECT_GATE_DIMS
from vgeval.store import RunStore


def _scale(run_id: str) -> tuple[int, int]:
    """(min, max) from the run's rubric snapshot; defaults to (1, 5)."""
    snap = RunStore.open(run_id).read_rubric_snapshot()
    if snap:
        s = (yaml.safe_load(snap) or {}).get("scale", {})
        return int(s.get("min", 1)), int(s.get("max", 5))
    return 1, 5


def clip_overall(dims: dict[str, int], gate_threshold: int) -> tuple[float, bool]:
    """Per-clip overall with the integrity gate.

    Normally the mean across scored dims — but if any defect-gate dim scores at or
    below `gate_threshold`, the overall is capped at that worst defect score, so a
    catastrophic hallucination can't be averaged away. Returns (overall, gated).
    """
    if not dims:
        return 0.0, False
    base = mean(dims.values())
    defect_scores = [dims[d] for d in DEFECT_GATE_DIMS if d in dims]
    worst = min(defect_scores) if defect_scores else None
    if worst is not None and worst <= gate_threshold:
        return round(min(base, float(worst)), 3), True
    return round(base, 3), False


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
    """Providers ranked by mean per-clip gated overall.

    Each clip's overall is gated (a severe integrity defect caps it), then averaged
    per provider — so one catastrophic clip pulls the model down instead of being
    diluted by good dimensions. `gated` flags providers with any capped clip.
    """
    smin, _ = _scale(run_id)
    gate_threshold = smin + 1  # e.g. 1..5 scale -> gate at <= 2
    results = RunStore.open(run_id).read_results()
    rows = per_dimension(run_id)

    per_provider: dict[str, list] = {}
    for s in results:
        per_provider.setdefault(s.provider, []).append(s)

    for row in rows:
        items = per_provider.get(row["provider"], [])
        overalls, gated_any = [], False
        for s in items:
            o, g = clip_overall(s.dims, gate_threshold)
            overalls.append(o)
            gated_any = gated_any or g
        row["overall"] = round(mean(overalls), 3) if overalls else 0.0
        row["gated"] = gated_any
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
