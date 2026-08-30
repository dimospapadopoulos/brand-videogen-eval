"""Typed configuration loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

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

    # Secrets. anthropic_api_key has no prefix so it matches the conventional
    # ANTHROPIC_API_KEY env var.
    anthropic_api_key: str = ""

    judge_model: str = "claude-opus-4-8"
    concurrency: int = 8
    judge_frames: int = 6

    # Paths (relative to repo root unless absolute).
    runs_dir: Path = REPO_ROOT / "runs"
    assets_dir: Path = REPO_ROOT / "assets" / "samples"
    prompts_dir: Path = REPO_ROOT / "prompts"
    cache_dir: Path = REPO_ROOT / ".cache" / "videos"

    def model_post_init(self, __context: object) -> None:
        # Allow ANTHROPIC_API_KEY (no VGEVAL_ prefix) to populate the key.
        import os

        if not self.anthropic_api_key:
            self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")


def get_settings() -> Settings:
    return Settings()
