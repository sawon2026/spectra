"""Spectra configuration with safe defaults."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SpectraSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SPECTRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Field(default_factory=lambda: Path.home() / ".spectra")
    database_url: str | None = None
    require_scope_for_execution: bool = True
    policy_strict: bool = True
    max_command_timeout_seconds: int = 120
    allowed_binaries: list[str] = Field(
        default_factory=lambda: [
            "file",
            "sha256sum",
            "sha1sum",
            "md5sum",
            "strings",
            "xxd",
            "python",
            "python3",
        ]
    )
    log_level: str = "INFO"
    log_json: bool = False

    def get_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.data_dir / "spectra.db"
        return f"sqlite:///{db_path}"

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @field_validator("allowed_binaries", mode="before")
    @classmethod
    def split_binaries(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


@lru_cache
def get_settings() -> SpectraSettings:
    return SpectraSettings()
