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
from vgeval.judge.rubric import Method, Rubric, RubricDim
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

    def score(
        self,
        req: GenRequest,
        result: VideoResult,
        frames: list[Path],
        dims: list[RubricDim],
    ) -> JudgeScore:
        content: list[dict] = [
            {"type": "text", "text": f"Generation prompt:\n{req.prompt}"},
        ]
        content.extend(_ground_truth_blocks(req, dims))
        content += [
            {"type": "text", "text": "ORIGINAL source image:"},
            _image_block(req.source_image),
            {"type": "text", "text": f"Sampled video frames (in order, {len(frames)} frames):"},
        ]
        content.extend(_image_block(f) for f in frames)
        content.append(
            {"type": "text", "text": "Call record_scores with an integer per dimension."}
        )

        tool = self.rubric.tool_schema(dims)
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self.rubric.instruction(dims),
            tools=[tool],
            tool_choice={"type": "tool", "name": "record_scores"},
            messages=[{"role": "user", "content": content}],
        )

        payload = _extract_tool_input(msg)
        scored = {d.name: int(payload[d.name]) for d in dims if d.name in payload}
        needs_review = [d.name for d in dims if d.method is Method.human_flag]
        return JudgeScore(
            job_id=req.job_id,
            provider=result.provider,
            prompt_id=req.prompt_id,
            dims=scored,
            methods={d.name: d.method.value for d in dims},
            rationale=str(payload.get("rationale", "")),
            flags=list(payload.get("flags", []) or []),
            needs_review=needs_review,
            transcribed_text=payload.get("transcribed_text"),
        )


def _ground_truth_blocks(req: GenRequest, dims: list[RubricDim]) -> list[dict]:
    """Inject ground-truth context when a dim requires it (e.g. expected copy)."""
    needs = {r for d in dims for r in d.requires}
    blocks: list[dict] = []
    if "expected_copy" in needs and req.expected_copy:
        blocks.append(
            {"type": "text", "text": f"Expected on-product copy (verbatim): {req.expected_copy!r}"}
        )
    if "locale" in needs and req.locale:
        blocks.append({"type": "text", "text": f"Target locale/language: {req.locale}"})
    if "logo_ref" in needs and req.logo_ref:
        blocks.append({"type": "text", "text": "Reference brand logo:"})
        blocks.append(_image_block(req.logo_ref))
    return blocks


def _extract_tool_input(msg: object) -> dict:
    for block in getattr(msg, "content", []):
        is_tool = getattr(block, "type", None) == "tool_use"
        if is_tool and getattr(block, "name", "") == "record_scores":
            return dict(block.input)
    raise RuntimeError("Judge did not return a record_scores tool call")
