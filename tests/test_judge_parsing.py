"""Judge parsing test with a stubbed Anthropic client (offline, no key)."""

from pathlib import Path

from vgeval.judge.rubric import load_rubric
from vgeval.schemas import RUBRIC_DIMS, GenRequest, VideoResult


class _FakeBlock:
    type = "tool_use"
    name = "record_scores"

    def __init__(self, payload):
        self.input = payload


class _FakeMessage:
    def __init__(self, payload):
        self.content = [_FakeBlock(payload)]


class _FakeMessages:
    def __init__(self, payload):
        self._payload = payload
        self.captured = None

    def create(self, **kwargs):
        self.captured = kwargs
        return _FakeMessage(self._payload)


class _FakeClient:
    def __init__(self, payload):
        self.messages = _FakeMessages(payload)


def test_claude_judge_parses_tool_output(monkeypatch, sample_image, tmp_path):
    payload = {d: 4 for d in RUBRIC_DIMS}
    payload["rationale"] = "looks good"
    payload["flags"] = ["minor flicker"]

    import vgeval.judge.claude_judge as cj

    rubric = load_rubric()
    judge = cj.ClaudeJudge.__new__(cj.ClaudeJudge)  # bypass __init__ (no key needed)
    judge.rubric = rubric
    judge.model = "claude-opus-4-8"
    judge.client = _FakeClient(payload)
    judge._tool = rubric.tool_schema()

    frame = tmp_path / "frame_00.png"
    frame.write_bytes(sample_image.read_bytes())

    req = GenRequest(job_id="mock__p1", prompt_id="p1", prompt="x", source_image=str(sample_image))
    result = VideoResult(provider="mock", job_id="mock__p1", video_path="v.mp4", seconds=1, fps=8)

    score = judge.score(req, result, [Path(frame)])
    assert set(score.dims) == set(RUBRIC_DIMS)
    assert all(v == 4 for v in score.dims.values())
    assert score.flags == ["minor flicker"]
    # Forced tool use was requested.
    assert judge.client.messages.captured["tool_choice"]["name"] == "record_scores"
