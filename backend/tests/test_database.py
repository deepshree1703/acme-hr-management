"""Tests for local and PostgreSQL connection selection and adaptation."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app import database
from app.config import ConfigurationError, get_settings


def test_settings_use_local_database_when_database_url_is_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify that settings use local database when database url is unset."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "local.db"))

    settings = get_settings()

    assert settings.database_path == tmp_path / "local.db"
    assert settings.database_url is None


@pytest.mark.parametrize("database_url", [None, "", "   "])
def test_settings_require_database_url_on_vercel(
    monkeypatch: pytest.MonkeyPatch, database_url: str | None
) -> None:
    """Verify that settings require database url on vercel."""
    monkeypatch.setenv("VERCEL", "1")
    if database_url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", database_url)

    with pytest.raises(
        ConfigurationError,
        match="DATABASE_URL must be set and non-blank when running on Vercel",
    ):
        get_settings()


def test_settings_load_postgresql_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that settings load postgresql url."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    assert get_settings().database_url == "postgresql://user:pass@localhost/db"


def test_connect_uses_psycopg_dictionary_rows_and_qmark_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that connect uses psycopg dictionary rows and qmark adapter."""
    events: list[object] = []
    cursor = SimpleNamespace(
        rowcount=2,
        executemany=lambda sql, rows: events.append((sql, list(rows))),
    )

    class Transaction:
        def __enter__(self):
            """Enter the test connection context."""
            events.append("begin")

        def __exit__(self, exc_type, exc_value, traceback):
            """Exit the test connection context."""
            events.append("rollback" if exc_type else "commit")

    class RawConnection:
        def execute(self, sql, parameters=()):
            """Record or execute a SQL statement for the test double."""
            events.append((sql, parameters))
            return cursor

        def cursor(self):
            """Return the cursor used by the test connection."""
            return cursor

        def transaction(self):
            """Return the transaction context used by the test connection."""
            return Transaction()

        def close(self):
            """Mark the test connection as closed."""
            events.append("close")

    raw_connection = RawConnection()
    dict_row_factory = object()
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_connect(*args, **kwargs):
        """Return the fake connection used to test database setup."""
        calls.append((args, kwargs))
        return raw_connection

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setattr(
        database,
        "psycopg",
        SimpleNamespace(connect=fake_connect, Error=Exception),
    )
    monkeypatch.setattr(database, "dict_row", dict_row_factory)

    connection = database.connect()
    assert connection.dialect == "postgresql"
    assert calls == [
        (
            ("postgresql://user:pass@localhost/db",),
            {"row_factory": dict_row_factory, "prepare_threshold": None},
        )
    ]

    execute_result = connection.execute(
        "SELECT '?' AS literal, value FROM items WHERE id = ?", (7,)
    )
    assert execute_result is cursor
    result = connection.executemany(
        "INSERT INTO items VALUES (?, ?)", [(1, "a"), (2, "b")]
    )
    assert result is cursor
    assert result.rowcount == 2
    with connection:
        events.append("work")

    assert events[:2] == [
        ("SELECT '?' AS literal, value FROM items WHERE id = %s", (7,)),
        ("INSERT INTO items VALUES (%s, %s)", [(1, "a"), (2, "b")]),
    ]
    assert events[-3:] == ["begin", "work", "commit"]


def test_connect_keeps_local_sqlite_path_when_database_url_is_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify that connect keeps local sqlite path when database url is unset."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "local.db"))

    connection = database.connect()
    try:
        assert connection.dialect == "sqlite"
        assert connection.execute("SELECT 1").fetchone()[0] == 1
    finally:
        connection.close()
