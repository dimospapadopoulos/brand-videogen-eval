"""End-to-end on rubric_v2: hybrid routing produces a merged, audited score."""

import asyncio

from vgeval.judge.rubric import resolve_rubric
from vgeval.runner import run_batch
from vgeval.scoring import judge_run


def test_v2_hybrid_pipeline(temp_suite, monkeypatch):
    # Give the suite entries a brand palette so the deterministic color dim runs.
    import vgeval.prompts as prompts

    orig = prompts.load_suite

    def patched(name="example_suite"):
        s = orig(name)
        for p in s.prompts:
            p.brand_palette = ["#E4002B", "#00A651"]
        return s

    monkeypatch.setattr(prompts, "load_suite", patched)
    monkeypatch.setattr("vgeval.runner.load_suite", patched)

    rid = asyncio.run(run_batch(["mock"], temp_suite, rubric_version="rubric_v2"))
    scored = judge_run(rid, use_stub=True)
    assert scored

    rubric = resolve_rubric("rubric_v2")
    det_names = {d.name for d in rubric.deterministic_dims()}
    human_names = {d.name for d in rubric.human_dims()}

    for s in scored:
        # deterministic dims computed (not skipped) because palette was supplied
        assert det_names <= set(s.dims), f"missing deterministic dims: {det_names - set(s.dims)}"
        assert s.methods["brand_color_adherence"] == "deterministic"
        # human_flag dims are flagged for review regardless of stub judge
        assert human_names <= set(s.needs_review)
        # every scored dim records its method (audit trail)
        assert set(s.methods) >= set(s.dims)
