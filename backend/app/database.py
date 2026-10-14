"""SQLite connection helpers."""

import sqlite3
from collections.abc import Iterator

from app.config import get_settings


def connect() -> sqlite3.Connection:
    """Open a SQLite connection using the configured database path."""
    database_path = get_settings().database_path
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
    except Exception:
        connection.close()
        raise
    return connection


def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a connection for a request and always close it afterwards."""
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def check_database() -> None:
    """Raise an SQLite error if the configured database cannot be queried."""
    connection = connect()
    try:
        connection.execute("SELECT 1").fetchone()
    finally:
        connection.close()
