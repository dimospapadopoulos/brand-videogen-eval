"""Claude (Opus 4.8) vision judge.

Claude has vision over images, not raw video, so we send the ORIGINAL source
image followed by N sampled output frames, plus the prompt and rubric, and force
a structured tool call so scores come back typed (no text parsing).
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from vgeval.config import get_settings
from vgeval.judge.rubric import Rubric
from vgeval.schemas import GenRequest, JudgeScore, VideoResult


def _image_block(path: str | Path) -> dict:
    path = Path(path)
    media_type = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.standard_b64encode(path.read_bytes()).decode()
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


class ClaudeJudge:
    """VLM-as-judge backed by the Anthropic Messages API with forced tool use."""

    def __init__(self, rubric: Rubric, *, model: str | None = None, api_key: str | None = None):
        settings = get_settings()
        self.rubric = rubric
        self.model = model or settings.judge_model
        key = api_key or settings.anthropic_api_key
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Use the stub judge for keyless runs, "
                "or set the key in .env for a real judge pass."
            )
        import anthropic

        self.client = anthropic.Anthropic(api_key=key)
        self._tool = rubric.tool_schema()

    def score(self, req: GenRequest, result: VideoResult, frames: list[Path]) -> JudgeScore:
        content: list[dict] = [
            {"type": "text", "text": f"Generation prompt:\n{req.prompt}"},
            {"type": "text", "text": "ORIGINAL source image:"},
            _image_block(req.source_image),
            {"type": "text", "text": f"Sampled video frames (in order, {len(frames)} frames):"},
        ]
        content.extend(_image_block(f) for f in frames)
        content.append(
            {"type": "text", "text": "Call record_scores with an integer per dimension."}
        )

        msg = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self.rubric.instruction(),
            tools=[self._tool],
            tool_choice={"type": "tool", "name": "record_scores"},
            messages=[{"role": "user", "content": content}],
        )

        payload = _extract_tool_input(msg)
        dims = {d.name: int(payload[d.name]) for d in self.rubric.dims}
        return JudgeScore(
            job_id=req.job_id,
            provider=result.provider,
            prompt_id=req.prompt_id,
            dims=dims,
            rationale=str(payload.get("rationale", "")),
            flags=list(payload.get("flags", []) or []),
        )


def _extract_tool_input(msg: object) -> dict:
    for block in getattr(msg, "content", []):
        is_tool = getattr(block, "type", None) == "tool_use"
        if is_tool and getattr(block, "name", "") == "record_scores":
            return dict(block.input)
    raise RuntimeError("Judge did not return a record_scores tool call")
