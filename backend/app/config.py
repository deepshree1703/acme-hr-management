"""Application configuration sourced from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path
    cors_origins: tuple[str, ...]


def get_settings() -> Settings:
    """Return database and CORS settings from the environment."""
    backend_directory = Path(__file__).resolve().parents[1]
    configured_path = os.getenv("DATABASE_PATH", "data/acme_salary_management.db").strip()
    if not configured_path:
        raise ValueError("DATABASE_PATH must not be empty")

    database_path = Path(configured_path).expanduser()
    if not database_path.is_absolute() and configured_path != ":memory:":
        database_path = backend_directory / database_path

    configured_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    cors_origins = tuple(
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    ) or ("http://localhost:5173",)

    return Settings(database_path=database_path, cors_origins=cors_origins)
