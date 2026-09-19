"""Dedicated defect-hunt pass.

A second, focused judge call whose ONLY job is to compare the source image to the
sampled output frames and enumerate hallucinations / anatomy errors / deformation
/ objects appearing-disappearing / physics violations. It acts as a conservative
critic: findings can only *lower* the affected defect dimensions, never raise
them, and each finding is surfaced in the audit trail (flags + defects list) and,
when severe, routed to `needs_review`.

This is what catches failures the single-pass all-dimensions judge glosses over
(e.g. a limb merging into a knee), and it pairs with the leaderboard defect gate
so a caught dealbreaker can't be averaged away.
"""

from __future__ import annotations

from pathlib import Path

from vgeval.config import get_settings
from vgeval.judge.rubric import Rubric
from vgeval.schemas import DEFECT_GATE_DIMS, Defect, GenRequest, JudgeScore, VideoResult

_SEVERITIES = ("minor", "major", "severe")

_SYSTEM = (
    "You are a strict QA inspector for AI-generated advertising video. You are given "
    "the ORIGINAL source image, then frames sampled in order from a generated clip. "
    "Your ONLY job is to find DEFECTS and HALLUCINATIONS by comparing the frames to "
    "the source: missing / merged / duplicated / extra limbs or objects, broken "
    "anatomy, warped or melted geometry, objects that appear or vanish across frames, "
    "physically impossible motion, and mangled logos or text. For each defect give a "
    "short concrete description, the impacted dimension, and a severity. Report only "
    "defects that are actually visible — do not invent them. If there are none, return "
    "an empty list."
)


def _severity_to_score(severity: str, scale) -> int:
    """severe -> worst, major -> worst+1, minor -> worst+2 (clamped to the scale)."""
    offset = {"severe": 0, "major": 1, "minor": 2}.get(severity, 2)
    return max(scale.min, min(scale.max, scale.min + offset))


def _allowed_dims(rubric: Rubric) -> list[str]:
    present = {d.name for d in rubric.dims}
    return [d for d in DEFECT_GATE_DIMS if d in present]


def defect_tool_schema(rubric: Rubric) -> dict:
    dims = _allowed_dims(rubric)
    return {
        "name": "record_defects",
        "description": "Record every visible defect/hallucination (empty list if none).",
        "input_schema": {
            "type": "object",
            "properties": {
                "defects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "dim": {"type": "string", "enum": dims},
                            "severity": {"type": "string", "enum": list(_SEVERITIES)},
                        },
                        "required": ["description", "dim", "severity"],
                    },
                }
            },
            "required": ["defects"],
        },
    }


class StubDefectHunter:
    """Keyless no-op hunter (finds nothing) for tests / CI / canary."""

    def __init__(self, rubric: Rubric) -> None:
        self.rubric = rubric

    def hunt(self, req: GenRequest, result: VideoResult, frames: list[Path]) -> list[Defect]:
        return []


class ClaudeDefectHunter:
    """Runs the focused defect pass via a second Opus call."""

    def __init__(self, rubric: Rubric, *, model: str | None = None, api_key: str | None = None):
        settings = get_settings()
        self.rubric = rubric
        self.model = model or settings.judge_model
        key = api_key or settings.anthropic_api_key
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set (needed for the defect pass).")
        import anthropic

        self.client = anthropic.Anthropic(api_key=key)
        self._tool = defect_tool_schema(rubric)

    def hunt(self, req: GenRequest, result: VideoResult, frames: list[Path]) -> list[Defect]:
        from vgeval.judge.claude_judge import _image_block

        content: list[dict] = [
            {"type": "text", "text": "ORIGINAL source image:"},
            _image_block(req.source_image),
            {"type": "text", "text": f"Generated frames in order ({len(frames)}):"},
        ]
        content.extend(_image_block(f) for f in frames)
        content.append({"type": "text", "text": "Call record_defects with every visible defect."})

        msg = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=_SYSTEM,
            tools=[self._tool],
            tool_choice={"type": "tool", "name": "record_defects"},
            messages=[{"role": "user", "content": content}],
        )
        payload = _extract_defects(msg)
        out: list[Defect] = []
        for d in payload:
            try:
                out.append(Defect.model_validate(d))
            except Exception:  # noqa: BLE001 - skip malformed entries defensively
                continue
        return out


def apply_defects(score: JudgeScore, defects: list[Defect], rubric: Rubric) -> None:
    """Conservatively fold defect findings into a JudgeScore (lower-only)."""
    for d in defects:
        score.defects.append(f"{d.severity}: {d.description} [{d.dim}]")
        score.flags.append(f"DEFECT[{d.severity}]: {d.description} ({d.dim})")
        capped = _severity_to_score(d.severity, rubric.scale)
        if d.dim in score.dims:
            score.dims[d.dim] = min(score.dims[d.dim], capped)
        if d.severity == "severe" and d.dim not in score.needs_review:
            score.needs_review.append(d.dim)


def _extract_defects(msg: object) -> list[dict]:
    for block in getattr(msg, "content", []):
        is_tool = getattr(block, "type", None) == "tool_use"
        if is_tool and getattr(block, "name", "") == "record_defects":
            return list(block.input.get("defects", []))
    return []
