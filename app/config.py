"""Application settings, read from environment variables (and a local .env via python-dotenv).

Values are validated by Pydantic at startup, so a typo like MIN_CONFIDENCE=0,7 fails fast with a
clear message instead of surfacing later as a strange guard decision.

GEMINI_API_KEY is a SecretStr: printing or logging the settings shows '**********', never the key.
Only app/ai/gemini.py calls .get_secret_value(), at the moment it builds the client.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr, field_validator

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    gemini_api_key: SecretStr | None = None  # optional: the API process never calls Gemini
    database_url: str
    vision_model: str = "gemini-3.5-flash-lite"
    images_dir: Path = ROOT / "data" / "images"

    # Mismatch guard thresholds (provisional; calibrated in Phase 3)
    min_confidence: float = Field(0.70, ge=0, le=1)
    min_post_confidence: float = Field(0.50, ge=0, le=1)
    min_similarity: float = Field(0.65, ge=-1, le=1)
    guard_top_k: int = Field(5, ge=1, le=50)

    # Cost and pacing
    ai_budget_usd: float = Field(1.00, gt=0)
    gemini_rpm: float = Field(5, gt=0)  # max requests per minute the worker will send
    gemini_timeout_s: float = Field(60, gt=0, le=600)  # give up on a single Gemini request after this

    @field_validator("images_dir")
    @classmethod
    def _relative_to_repo_root(cls, path: Path) -> Path:
        # "data/images" in .env means <repo>/data/images, whatever folder the process starts in
        return path if path.is_absolute() else ROOT / path


def load_settings(env: dict[str, str] | None = None) -> Settings:
    """Build Settings from env vars. Field `foo_bar` is read from FOO_BAR; unset ones use defaults."""
    if env is None:
        load_dotenv(ROOT / ".env")  # does not override variables already set (e.g. by Docker)
        env = dict(os.environ)
    values = {
        name: env[name.upper()]
        for name in Settings.model_fields
        if env.get(name.upper()) not in (None, "")
    }
    return Settings.model_validate(values)


@lru_cache
def get_settings() -> Settings:
    return load_settings()
