"""Application configuration with secure defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SpectraSettings(BaseSettings):
    """Spectra runtime configuration.

    All sensitive defaults favour local, offline, non-network behaviour.
    """

    model_config = SettingsConfigDict(
        env_prefix="SPECTRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Storage
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".spectra")
    database_url: str | None = None  # defaults to sqlite under data_dir

    # Runtime
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    environment: Literal["development", "production", "test"] = "development"

    # Security / policy
    require_scope_for_execution: bool = True
    allow_network_by_default: bool = False
    max_command_timeout_seconds: int = Field(default=600, ge=1, le=86400)
    enable_sandbox: bool = False  # opt-in

    # AI / model (placeholder for later phases)
    model_provider: str = "none"
    model_api_base: str | None = None
    model_api_key: str | None = None  # never logged

    @field_validator("data_dir", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        return Path(v).expanduser().resolve()

    def get_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.data_dir / "spectra.db"
        return f"sqlite:///{db_path}"

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "cases").mkdir(exist_ok=True)
        (self.data_dir / "artifacts").mkdir(exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)
        return self.data_dir


def get_settings() -> SpectraSettings:
    return SpectraSettings()
