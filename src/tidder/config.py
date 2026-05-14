"""Layered configuration: defaults < config file < env vars < CLI flags.

The CLI layer is responsible for applying flag overrides on top of a
``Settings`` instance loaded here. Env vars are picked up automatically via
``pydantic-settings``; the optional TOML config file is loaded by hand so we
can keep the precedence explicit.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = Path.home() / ".config" / "tidder"
CONFIG_FILE = CONFIG_DIR / "config.toml"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"

DEFAULT_UPLOADS_DIR = Path("uploads")
DEFAULT_OUTPUTS_DIR = Path("outputs")


class Settings(BaseSettings):
    """All tunable knobs. Lower-precedence sources fill in unset fields."""

    model_config = SettingsConfigDict(
        env_prefix="TIDDER_",
        env_file=None,
        extra="ignore",
    )

    # LLM
    llm_provider: str = "ollama"
    llm_model: str | None = None
    llm_host: str = "http://localhost:11434"
    api_key: str | None = None

    # Processing
    confidence_threshold: float = 0.75
    retry_threshold: int = 3
    concurrency: int = 4

    # Paths
    uploads_dir: Path = DEFAULT_UPLOADS_DIR
    outputs_dir: Path = DEFAULT_OUTPUTS_DIR


def _load_config_file(path: Path = CONFIG_FILE) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def load_settings(**flag_overrides: Any) -> Settings:
    """Resolve settings with the documented precedence.

    Flag overrides win, then env vars (handled by pydantic-settings), then the
    TOML config file, then in-code defaults.
    """
    file_values = _load_config_file()
    cleaned_flags = {k: v for k, v in flag_overrides.items() if v is not None}
    return Settings(**{**file_values, **cleaned_flags})
