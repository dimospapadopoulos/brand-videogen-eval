"""Load/validate a rubric and build the judge instruction + tool schema.

A rubric is dimension-driven. Each dimension declares a `method` that routes how
it is scored, which is what makes the harness auditable:

  * ``vlm_absolute``          — the VLM scores it from frames + source image
  * ``vlm_with_ground_truth`` — VLM, with expected copy/locale injected
  * ``vlm_pairwise``          — best judged as an A/B preference (see `compare`);
                                in absolute scoring the VLM gives a provisional
  * ``deterministic``         — computed by CV/text code, NOT the VLM
  * ``human_flag``            — VLM triages, but the dim is flagged for a human

For routing purposes these collapse to three buckets (see `Method.bucket`):
``vlm`` (the three vlm_* + human_flag triage), ``deterministic``, and ``human``
(the review flag). The five names are kept because they document intent.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from vgeval.schemas import RUBRIC_DIMS

RUBRIC_PATH = Path(__file__).with_name("rubric.yaml")
RUBRIC_V2_PATH = Path(__file__).with_name("rubric_v2.yaml")


class Method(StrEnum):
    vlm_absolute = "vlm_absolute"
    vlm_with_ground_truth = "vlm_with_ground_truth"
    vlm_pairwise = "vlm_pairwise"
    deterministic = "deterministic"
    human_flag = "human_flag"

    @property
    def bucket(self) -> str:
        if self is Method.deterministic:
            return "deterministic"
        return "vlm"  # human_flag is VLM-triaged then flagged; routing-wise it's vlm

    @property
    def review(self) -> bool:
        return self is Method.human_flag


class RubricDim(BaseModel):
    name: str
    description: str
    low: str = ""
    high: str = ""
    band: str = "general"
    method: Method = Method.vlm_absolute
    requires: list[str] = Field(default_factory=list)  # ground-truth fields needed


class RubricScale(BaseModel):
    min: int
    max: int
    higher_is_better: bool = True


class Rubric(BaseModel):
    version: str
    scale: RubricScale
    dims: list[RubricDim]

    def validate_dims(self) -> None:
        names = [d.name for d in self.dims]
        if len(names) != len(set(names)):
            raise ValueError("Rubric has duplicate dimension names")
        # Backward-compat: the original v1 rubric must keep its fixed 9 dims.
        if self.version == "rubric_v1" and tuple(names) != RUBRIC_DIMS:
            raise ValueError(
                "rubric_v1 dims must exactly match RUBRIC_DIMS.\n"
                f"  expected: {RUBRIC_DIMS}\n  got:      {tuple(names)}"
            )

    # -- routing helpers ----------------------------------------------------- #
    def vlm_dims(self) -> list[RubricDim]:
        return [d for d in self.dims if d.method.bucket == "vlm"]

    def deterministic_dims(self) -> list[RubricDim]:
        return [d for d in self.dims if d.method.bucket == "deterministic"]

    def human_dims(self) -> list[RubricDim]:
        return [d for d in self.dims if d.method is Method.human_flag]

    def dim_names(self) -> list[str]:
        return [d.name for d in self.dims]

    # -- VLM prompt / tool schema (built over a subset) ---------------------- #
    def instruction(self, dims: list[RubricDim] | None = None) -> str:
        dims = dims or self.vlm_dims()
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
        for d in dims:
            lines.append(
                f"- {d.name}: {d.description} ({self.scale.min}={d.low} .. "
                f"{self.scale.max}={d.high})"
            )
        return "\n".join(lines)

    def tool_schema(self, dims: list[RubricDim] | None = None) -> dict:
        dims = dims or self.vlm_dims()
        props = {
            d.name: {
                "type": "integer",
                "minimum": self.scale.min,
                "maximum": self.scale.max,
                "description": d.description,
            }
            for d in dims
        }
        props["rationale"] = {"type": "string", "description": "Brief justification."}
        props["flags"] = {
            "type": "array",
            "items": {"type": "string"},
            "description": "Notable defects observed, if any.",
        }
        props["transcribed_text"] = {
            "type": "string",
            "description": "All legible text visible on/near the product (for copy audit).",
        }
        return {
            "name": "record_scores",
            "description": "Record the rubric scores for this video.",
            "input_schema": {
                "type": "object",
                "properties": props,
                "required": [d.name for d in dims],
            },
        }


def load_rubric(path: str | Path = RUBRIC_PATH) -> Rubric:
    data = yaml.safe_load(Path(path).read_text())
    rubric = Rubric.model_validate(data)
    rubric.validate_dims()
    return rubric


def resolve_rubric(name: str = "rubric_v1") -> Rubric:
    """Resolve a rubric by short name, stem, or path."""
    p = Path(name)
    if p.exists():
        return load_rubric(p)
    by_name = RUBRIC_PATH.with_name(f"{name}.yaml")
    if name in ("rubric_v1", "v1"):
        return load_rubric(RUBRIC_PATH)
    if name in ("rubric_v2", "v2"):
        return load_rubric(RUBRIC_V2_PATH)
    if by_name.exists():
        return load_rubric(by_name)
    raise FileNotFoundError(f"Unknown rubric {name!r}")
