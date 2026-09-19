"""Defect-hunt pass (parsing + conservative apply) and the leaderboard gate."""

from pathlib import Path

from vgeval.judge.rubric import resolve_rubric
from vgeval.judge.scorers import ScoreContext  # noqa: F401  (kept for parity/imports)
from vgeval.report import clip_overall
from vgeval.schemas import Defect, GenRequest, JudgeScore, VideoResult


def _score(dims):
    return JudgeScore(job_id="veo__nike", provider="veo", prompt_id="nike", dims=dict(dims))


def test_apply_defects_only_lowers_and_records():
    from vgeval.judge.defects import apply_defects

    rubric = resolve_rubric("rubric_v2")
    s = _score({"object_deformation": 4, "aesthetics": 5})
    apply_defects(
        s,
        [Defect(description="right arm merges into knee", dim="object_deformation",
                severity="severe")],
        rubric,
    )
    assert s.dims["object_deformation"] == 1     # severe -> capped to worst
    assert s.dims["aesthetics"] == 5             # untouched
    assert "object_deformation" in s.needs_review
    assert any("merges into knee" in d for d in s.defects)


def test_apply_defects_never_raises_a_score():
    from vgeval.judge.defects import apply_defects

    rubric = resolve_rubric("rubric_v2")
    s = _score({"object_deformation": 2})
    # A 'minor' maps to 3, but the critic must not raise an already-lower score.
    apply_defects(s, [Defect(description="tiny wobble", dim="object_deformation",
                             severity="minor")], rubric)
    assert s.dims["object_deformation"] == 2


def test_gate_caps_overall_on_severe_defect():
    # 15 great dims + one catastrophic object_deformation must NOT average to ~3.7.
    dims = {"prompt_adherence": 4, "aesthetics": 5, "hero_focal_clarity": 4,
            "video_quality": 4, "object_deformation": 1}
    overall, gated = clip_overall(dims, gate_threshold=2)
    assert gated is True
    assert overall == 1.0  # capped at the worst defect, not the mean


def test_gate_not_triggered_when_clean():
    dims = {"prompt_adherence": 4, "object_deformation": 5, "aesthetics": 4}
    overall, gated = clip_overall(dims, gate_threshold=2)
    assert gated is False
    assert overall > 4


def test_claude_defect_hunter_parses_tool_output(sample_image, tmp_path):
    import vgeval.judge.defects as dh

    rubric = resolve_rubric("rubric_v2")
    hunter = dh.ClaudeDefectHunter.__new__(dh.ClaudeDefectHunter)
    hunter.rubric = rubric
    hunter.model = "claude-opus-4-8"
    hunter._tool = dh.defect_tool_schema(rubric)

    class _Block:
        type = "tool_use"
        name = "record_defects"
        input = {"defects": [{"description": "extra limb", "dim": "object_deformation",
                              "severity": "major"}]}

    class _Msg:
        content = [_Block()]

    class _Msgs:
        def create(self, **kw):
            return _Msg()

    class _Client:
        messages = _Msgs()

    hunter.client = _Client()
    frame = tmp_path / "frame_00.png"
    frame.write_bytes(sample_image.read_bytes())
    req = GenRequest(job_id="veo__nike", prompt_id="nike", prompt="x",
                     source_image=str(sample_image))
    res = VideoResult(provider="veo", job_id="veo__nike", video_path="v.mp4", seconds=1, fps=8)

    found = hunter.hunt(req, res, [Path(frame)])
    assert len(found) == 1 and found[0].dim == "object_deformation"
