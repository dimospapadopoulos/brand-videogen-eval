"""Load and validate a versioned prompt suite.

A suite is a YAML file under `prompts/` pairing each prompt with a source image
and a category. You provide the real suite; `prompts/example_suite.yaml` ships as
a runnable placeholder.

Format:
    version: example_v1
    prompts:
      - id: p001
        prompt: "A product rotating slowly on a pedestal, studio lighting"
        source_image: assets/samples/images/p001.png
        category: product
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from vgeval.config import REPO_ROOT, get_settings


class PromptEntry(BaseModel):
    id: str
    prompt: str
    source_image: str
    category: str = "uncategorized"

    # Optional ground truth for the brand/creative rubric dimensions.
    expected_copy: str | None = None
    locale: str | None = None
    brand_palette: list[str] = Field(default_factory=list)
    logo_ref: str | None = None


class Suite(BaseModel):
    version: str
    prompts: list[PromptEntry] = Field(min_length=1)


def resolve_suite_path(name: str) -> Path:
    """Resolve a suite by name, file stem, or path to a YAML file in prompts/."""
    p = Path(name)
    if p.exists():
        return p
    prompts_dir = get_settings().prompts_dir
    candidates = (prompts_dir / name, prompts_dir / f"{name}.yaml", prompts_dir / f"{name}.yml")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Prompt suite {name!r} not found. Looked in {prompts_dir}. "
        "Drop your suite YAML there (see prompts/example_suite.yaml)."
    )


def load_suite(name: str = "example_suite") -> Suite:
    path = resolve_suite_path(name)
    data = yaml.safe_load(path.read_text())
    suite = Suite.model_validate(data)
    _validate_source_images(suite)
    return suite


def _validate_source_images(suite: Suite) -> None:
    missing = []
    for entry in suite.prompts:
        img = Path(entry.source_image)
        if not img.is_absolute():
            img = REPO_ROOT / img
        if not img.exists():
            missing.append(entry.source_image)
    if missing:
        raise FileNotFoundError(
            "Suite references source images that don't exist: " + ", ".join(missing)
        )
