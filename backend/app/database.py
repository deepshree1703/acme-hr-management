"""SQLite and PostgreSQL connection helpers."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator, Sequence
from typing import Any, Protocol

from app.config import get_settings


class Cursor(Protocol):
    """Cursor operations shared by sqlite3 and psycopg."""

    rowcount: int

    def fetchone(self) -> Any:
        """Return the next row, or None when the result set is exhausted."""
        ...

    def fetchall(self) -> list[Any]:
        """Return all remaining rows from the result set."""
        ...


class DatabaseConnection(Protocol):
    """Connection operations shared by SQLite and PostgreSQL."""

    dialect: str

    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> Cursor:
        """Execute one parameterized SQL statement and return its cursor."""
        ...

    def executemany(
        self, sql: str, parameters: Iterable[Sequence[Any]]
    ) -> Cursor:
        """Execute a parameterized SQL statement for each parameter set."""
        ...

    def close(self) -> None:
        """Release the underlying database connection."""
        ...

    def __enter__(self) -> DatabaseConnection:
        """Begin a connection context and return this connection."""
        ...

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool | None:
        """Finish the connection context, committing or rolling back as needed."""
        ...


try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # Local SQLite use doesn't require PostgreSQL packages.
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]

DATABASE_ERRORS: tuple[type[Exception], ...] = (
    sqlite3.Error,
    *((psycopg.Error,) if psycopg is not None else ()),
)


def _qmark_to_psycopg(sql: str) -> str:
    """Translate qmark parameters without changing quoted question marks."""
    result: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote is not None:
            result.append(char)
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    result.append(sql[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in ("'", '"'):
            quote = char
            result.append(char)
        elif char == "?":
            result.append("%s")
        else:
            result.append(char)
        index += 1
    return "".join(result)


class _ConnectionAdapter:
    """Preserve shared SQL and transaction semantics across database drivers."""

    def __init__(self, connection: Any, dialect: str) -> None:
        """Wrap a driver connection with the shared database interface."""
        self._connection = connection
        self.dialect = dialect
        self._transactions: list[Any] = []

    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> Cursor:
        """Execute SQL, adapting qmark placeholders for PostgreSQL when needed."""
        if self.dialect == "postgresql":
            sql = _qmark_to_psycopg(sql)
        return self._connection.execute(sql, parameters)

    def executemany(
        self, sql: str, parameters: Iterable[Sequence[Any]]
    ) -> Cursor:
        """Execute SQL for multiple parameter sets using the selected driver."""
        if self.dialect == "postgresql":
            sql = _qmark_to_psycopg(sql)
            cursor = self._connection.cursor()
            cursor.executemany(sql, parameters)
            return cursor
        return self._connection.executemany(sql, parameters)

    def close(self) -> None:
        """Close the wrapped database connection."""
        self._connection.close()

    def __enter__(self) -> _ConnectionAdapter:
        """Start a transaction and return this adapter as a context manager."""
        if self.dialect == "postgresql":
            transaction = self._connection.transaction()
            transaction.__enter__()
            self._transactions.append(transaction)
        else:
            self._connection.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool | None:
        """Commit or roll back the active transaction when leaving the context."""
        if self.dialect == "postgresql":
            return self._transactions.pop().__exit__(exc_type, exc_value, traceback)
        return self._connection.__exit__(exc_type, exc_value, traceback)


def connect() -> DatabaseConnection:
    """Use PostgreSQL when DATABASE_URL is set, otherwise local SQLite."""
    settings = get_settings()
    if settings.database_url:
        if psycopg is None:
            raise RuntimeError("psycopg is required when DATABASE_URL is set")
        connection = psycopg.connect(
            settings.database_url,
            row_factory=dict_row,
            prepare_threshold=None,
        )
        return _ConnectionAdapter(connection, "postgresql")

    database_path = settings.database_path
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, check_same_thread=False)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
    except Exception:
        connection.close()
        raise
    return _ConnectionAdapter(connection, "sqlite")


def get_connection() -> Iterator[DatabaseConnection]:
    """Yield a connection for a request and always close it afterwards."""
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def check_database() -> None:
    """Raise a database driver error if the configured database cannot be queried."""
    connection = connect()
    try:
        connection.execute("SELECT 1").fetchone()
    finally:
        connection.close()
