"""Application configuration sourced from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path


def get_settings() -> Settings:
    """Return settings, defaulting to a local SQLite file under backend/data."""
    backend_directory = Path(__file__).resolve().parents[1]
    configured_path = os.getenv("DATABASE_PATH", "data/acme_salary_management.db").strip()
    if not configured_path:
        raise ValueError("DATABASE_PATH must not be empty")

    database_path = Path(configured_path).expanduser()
    if not database_path.is_absolute() and configured_path != ":memory:":
        database_path = backend_directory / database_path

    return Settings(database_path=database_path)
