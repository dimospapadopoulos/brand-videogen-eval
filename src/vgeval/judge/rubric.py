"""Load/validate the rubric and build the judge instruction + tool schema."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from vgeval.schemas import RUBRIC_DIMS

RUBRIC_PATH = Path(__file__).with_name("rubric.yaml")


class RubricDim(BaseModel):
    name: str
    description: str
    low: str = ""
    high: str = ""


class RubricScale(BaseModel):
    min: int
    max: int
    higher_is_better: bool = True


class Rubric(BaseModel):
    version: str
    scale: RubricScale
    dims: list[RubricDim]

    def validate_dims(self) -> None:
        names = tuple(d.name for d in self.dims)
        if names != RUBRIC_DIMS:
            raise ValueError(
                "Rubric dims must exactly match RUBRIC_DIMS in order.\n"
                f"  expected: {RUBRIC_DIMS}\n  got:      {names}"
            )

    def instruction(self) -> str:
        lines = [
            "You are an expert evaluator of AI-generated image-to-video clips for "
            "advertising and promotional use.",
            "You are given the ORIGINAL source image, then several frames sampled in "
            "order from the generated video, plus the generation prompt.",
            f"Score each dimension on an integer scale from {self.scale.min} to "
            f"{self.scale.max}, where {self.scale.max} is best.",
            "Compare the video frames against the source image to judge fidelity and "
            "defects. Be strict and specific.",
            "",
            "Dimensions:",
        ]
        for d in self.dims:
            lines.append(f"- {d.name}: {d.description} ({self.scale.min}={d.low} .. "
                         f"{self.scale.max}={d.high})")
        return "\n".join(lines)

    def tool_schema(self) -> dict:
        """JSON schema for the structured-output tool the judge must call."""
        props = {
            d.name: {
                "type": "integer",
                "minimum": self.scale.min,
                "maximum": self.scale.max,
                "description": d.description,
            }
            for d in self.dims
        }
        props["rationale"] = {"type": "string", "description": "Brief justification."}
        props["flags"] = {
            "type": "array",
            "items": {"type": "string"},
            "description": "Notable defects observed, if any.",
        }
        return {
            "name": "record_scores",
            "description": "Record the rubric scores for this video.",
            "input_schema": {
                "type": "object",
                "properties": props,
                "required": list(RUBRIC_DIMS),
            },
        }


def load_rubric(path: str | Path = RUBRIC_PATH) -> Rubric:
    data = yaml.safe_load(Path(path).read_text())
    rubric = Rubric.model_validate(data)
    rubric.validate_dims()
    return rubric
