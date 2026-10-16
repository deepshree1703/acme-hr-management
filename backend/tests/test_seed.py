"""Tests for the deterministic employee seed utility."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app import database
from app.database import connect
from scripts import seed as seed_module
from scripts.seed import seed_employees


def test_seed_is_repeatable_with_a_small_employee_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify that seed is repeatable with a small employee count."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "seed-test.db"))

    first_added, first_total = seed_employees(count=12, batch_size=5)
    second_added, second_total = seed_employees(count=12, batch_size=5)

    assert (first_added, first_total) == (12, 12)
    assert (second_added, second_total) == (0, 12)

    connection = connect()
    try:
        rows = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT employee_id) FROM employees"
        ).fetchone()
        assert tuple(rows) == (12, 12)
        designations = connection.execute(
            "SELECT COUNT(*) AS total, COUNT(designation) AS assigned FROM employees"
        ).fetchone()
        assert designations["total"] == designations["assigned"] == 12
        id_bounds = connection.execute(
            "SELECT MIN(employee_id), MAX(employee_id) FROM employees"
        ).fetchone()
        assert tuple(id_bounds) == ("EMP-00001", "EMP-00012")
    finally:
        connection.close()


def test_seed_counts_batches_when_psycopg_executemany_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that seed counts batches when psycopg executemany returns none."""
    inserted: list[tuple[object, ...]] = []
    statements: list[str] = []

    class FakeCursor:
        rowcount = 0

        def executemany(self, sql, rows):
            """Record or execute a batch of SQL statements for the test double."""
            batch = list(rows)
            statements.append(sql)
            inserted.extend(batch)
            self.rowcount = len(batch)
            return None

    class FakeTransaction:
        def __enter__(self):
            """Enter the test connection context."""
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            """Exit the test connection context."""
            return False

    class FakePostgresConnection:
        def cursor(self):
            """Return the cursor used by the test connection."""
            return FakeCursor()

        def execute(self, sql, parameters=()):
            """Record or execute a SQL statement for the test double."""
            assert "SELECT COUNT(*) AS total_count" in sql
            return SimpleNamespace(
                fetchone=lambda: {"total_count": len(inserted)},
                fetchall=lambda: [],
            )

        def transaction(self):
            """Return the transaction context used by the test connection."""
            return FakeTransaction()

        def close(self):
            """Mark the test connection as closed."""
            pass

    raw_connection = FakePostgresConnection()
    monkeypatch.setattr(seed_module, "init_db", lambda: None)
    monkeypatch.setattr(
        seed_module,
        "connect",
        lambda: database._ConnectionAdapter(raw_connection, "postgresql"),
    )

    added, total = seed_employees(count=7, batch_size=3)

    assert (added, total) == (7, 7)
    assert [len(batch) for batch in (inserted[:3], inserted[3:6], inserted[6:])] == [
        3,
        3,
        1,
    ]
    assert len(statements) == 3
    assert all(sql.count("%s") == 8 for sql in statements)
