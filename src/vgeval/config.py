"""Typed configuration loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = three levels up from this file (src/vgeval/config.py).
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings. All values overridable via env vars (prefix VGEVAL_)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VGEVAL_",
        extra="ignore",
    )

    # Secret. Read as the conventional ANTHROPIC_API_KEY (no VGEVAL_ prefix) from
    # both the environment AND the .env file. The explicit validation_alias is
    # what makes pydantic-settings bypass env_prefix for this one field, so a
    # plain `ANTHROPIC_API_KEY=...` line in .env is picked up.
    anthropic_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "VGEVAL_ANTHROPIC_API_KEY"),
    )

    judge_model: str = "claude-opus-4-8"
    concurrency: int = 8
    judge_frames: int = 6

    # Defect gate: a defect-gate dim scoring at/below this caps the clip's overall.
    # None -> default of scale.min + 1 (e.g. <=2 on a 1..5 scale). Raise to 3 for a
    # stricter integrity bar; set to 0 to effectively disable gating.
    gate_threshold: int | None = None

    # Paths (relative to repo root unless absolute).
    runs_dir: Path = REPO_ROOT / "runs"
    assets_dir: Path = REPO_ROOT / "assets" / "samples"
    prompts_dir: Path = REPO_ROOT / "prompts"
    cache_dir: Path = REPO_ROOT / ".cache" / "videos"


def get_settings() -> Settings:
    return Settings()
