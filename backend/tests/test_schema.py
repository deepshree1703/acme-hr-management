"""Tests for the initial SQLite schema."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.database import connect
from app.db_schema import init_db


def test_connection_can_be_queried_and_closed_from_another_thread(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify that connection can be queried and closed from another thread."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "employees.db"))

    connection = connect()
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(
            lambda: (connection.execute("SELECT 1").fetchone()[0], connection.close())
        ).result()

    assert result == (1, None)


def _insert_employee(connection: sqlite3.Connection, **overrides: object) -> None:
    """Insert one employee fixture into the test database."""
    employee = {
        "employee_id": "EMP-00001",
        "name": "Alex Example",
        "department": "Operations",
        "designation": "Operations Analyst",
        "country": "India",
        "employment_status": "Active",
        "annual_gross_base_salary": 50000,
        "currency": "INR",
    }
    employee.update(overrides)
    columns = ", ".join(employee)
    placeholders = ", ".join("?" for _ in employee)
    connection.execute(
        f"INSERT INTO employees ({columns}) VALUES ({placeholders})",
        tuple(employee.values()),
    )


def test_init_db_creates_table_and_indexes_idempotently(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify that init db creates table and indexes idempotently."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "employees.db"))

    init_db()
    init_db()

    connection = connect()
    try:
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(employees)")
        }
        indexes = {
            row["name"] for row in connection.execute("PRAGMA index_list(employees)")
        }
    finally:
        connection.close()

    assert columns == {
        "employee_id",
        "name",
        "department",
        "designation",
        "country",
        "employment_status",
        "annual_gross_base_salary",
        "currency",
    }
    assert {
        "idx_employees_country",
        "idx_employees_department",
        "idx_employees_employment_status",
        "idx_employees_currency",
        "idx_employees_currency_salary",
    } <= indexes


def test_init_db_migrates_existing_rows_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Backfill a legacy table deterministically and preserve values on rerun."""
    database_path = tmp_path / "legacy.db"
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    legacy = sqlite3.connect(database_path)
    legacy.execute("""CREATE TABLE employees (
        employee_id TEXT PRIMARY KEY, name TEXT NOT NULL, department TEXT NOT NULL,
        country TEXT NOT NULL, employment_status TEXT NOT NULL,
        annual_gross_base_salary REAL NOT NULL, currency TEXT NOT NULL)""")
    legacy.executemany(
        "INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("EMP-00001", "A", "Engineering", "India", "Active", 1, "INR"),
            ("EMP-00002", "B", "Finance", "India", "Active", 1, "INR"),
            ("EMP-00003", "C", "Unknown", "India", "Active", 1, "INR"),
        ],
    )
    legacy.commit()
    legacy.close()

    init_db()
    connection = connect()
    try:
        first_run = [tuple(row) for row in connection.execute(
            "SELECT employee_id, designation FROM employees ORDER BY employee_id"
        ).fetchall()]
    finally:
        connection.close()
    connection = connect()
    try:
        with connection:
            connection.execute("""CREATE TRIGGER reject_second_migration_update
                BEFORE UPDATE ON employees
                BEGIN SELECT RAISE(ABORT, 'unexpected migration update'); END""")
    finally:
        connection.close()
    init_db()
    connection = connect()
    try:
        second_run = [tuple(row) for row in connection.execute(
            "SELECT employee_id, designation FROM employees ORDER BY employee_id"
        ).fetchall()]
    finally:
        connection.close()
    assert first_run == second_run == [
        ("EMP-00001", "Senior Software Engineer"),
        ("EMP-00002", "Accountant"),
        ("EMP-00003", "Employee"),
    ]


def test_init_db_backfills_null_designations_in_an_existing_column(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Backfill null and blank values after an interrupted earlier migration."""
    database_path = tmp_path / "partial-migration.db"
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    legacy = sqlite3.connect(database_path)
    legacy.execute("""CREATE TABLE employees (
        employee_id TEXT PRIMARY KEY, name TEXT NOT NULL, department TEXT NOT NULL,
        designation TEXT, country TEXT NOT NULL, employment_status TEXT NOT NULL,
        annual_gross_base_salary REAL NOT NULL, currency TEXT NOT NULL)""")
    legacy.executemany(
        "INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("EMP-00001", "A", "Engineering", None, "India", "Active", 1, "INR"),
            ("EMP-00002", "B", "Finance", "", "India", "Active", 1, "INR"),
            ("EMP-00003", "C", "Unknown", "Legacy Role", "India", "Active", 1, "INR"),
        ],
    )
    legacy.commit()
    legacy.close()

    init_db()
    connection = connect()
    try:
        result = [tuple(row) for row in connection.execute(
            "SELECT employee_id, designation FROM employees ORDER BY employee_id"
        ).fetchall()]
    finally:
        connection.close()
    assert result == [
        ("EMP-00001", "Senior Software Engineer"),
        ("EMP-00002", "Accountant"),
        ("EMP-00003", "Legacy Role"),
    ]


def test_init_db_uses_postgresql_constraints_and_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that init db uses postgresql constraints and types."""
    from app import db_schema

    statements: list[str] = []

    class FakeConnection:
        dialect = "postgresql"

        def execute(self, sql, parameters=()):
            """Record or execute a SQL statement for the test double."""
            statements.append(sql)
            if "information_schema.columns" in sql:
                return SimpleNamespace(fetchall=lambda: [
                    {
                        "column_name": name,
                        "is_nullable": "YES" if name == "designation" else "NO",
                    }
                    for name in (
                        "employee_id", "name", "department", "designation", "country",
                        "employment_status", "annual_gross_base_salary", "currency"
                    )
                ])
            return SimpleNamespace(fetchall=lambda: [])

        def close(self):
            """Mark the test connection as closed."""
            pass

        def __enter__(self):
            """Enter the test connection context."""
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            """Exit the test connection context."""
            return False

    monkeypatch.setattr(db_schema, "connect", FakeConnection)

    db_schema.init_db()

    schema = statements[0]
    assert "employee_id ~ '^EMP-[0-9]{5,}$'" in schema
    assert "annual_gross_base_salary DOUBLE PRECISION NOT NULL" in schema
    assert "annual_gross_base_salary <= 9999999999.99" in schema
    assert any("ADD COLUMN IF NOT EXISTS designation TEXT" in statement for statement in statements)
    assert any("ALTER COLUMN designation SET NOT NULL" in statement for statement in statements)


def test_sqlite_column_addition_treats_duplicate_column_race_as_success() -> None:
    """Accept a concurrent initializer adding designation first."""
    from app.db_schema import _designation_column_rows

    class RacingConnection:
        dialect = "sqlite"
        pragma_count = 0

        def execute(self, sql, parameters=()):
            if sql == "PRAGMA table_info(employees)":
                self.pragma_count += 1
                if self.pragma_count == 1:
                    return SimpleNamespace(fetchall=lambda: [{"name": "employee_id"}])
                return SimpleNamespace(fetchall=lambda: [
                    {"name": "employee_id"}, {"name": "designation"}
                ])
            if sql == "ALTER TABLE employees ADD COLUMN designation TEXT":
                raise sqlite3.OperationalError("duplicate column name: designation")
            raise AssertionError(f"Unexpected SQL: {sql}")

    rows = _designation_column_rows(RacingConnection())
    assert any(row["name"] == "designation" for row in rows)


def test_postgresql_wrapper_never_receives_literal_percent_in_schema_sql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guard every schema SQL statement before PostgreSQL placeholder translation."""
    from app import database, db_schema

    translated: list[str] = []
    translate = database._qmark_to_psycopg

    def guarded_translate(sql: str) -> str:
        assert "%" not in sql
        translated.append(sql)
        return translate(sql)

    class Cursor:
        def fetchall(self):
            return []

    class Transaction:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    class RawPostgresConnection:
        def execute(self, sql, parameters=()):
            if "information_schema.columns" in sql:
                return SimpleNamespace(fetchall=lambda: [
                    {"column_name": "designation", "is_nullable": "NO"}
                ])
            return Cursor()

        def transaction(self):
            return Transaction()

        def close(self):
            pass

    monkeypatch.setattr(database, "_qmark_to_psycopg", guarded_translate)
    wrapped = database._ConnectionAdapter(RawPostgresConnection(), "postgresql")
    monkeypatch.setattr(db_schema, "connect", lambda: wrapped)

    db_schema.init_db()

    assert translated


def test_employee_constraints_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify that employee constraints reject invalid values."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "employees.db"))
    init_db()

    connection = connect()
    try:
        with connection:
            _insert_employee(connection)
        invalid_employees = (
            {"employee_id": "EMP-00002", "employment_status": "On leave"},
            {"employee_id": "EMP-00003", "currency": "XYZ"},
            {"employee_id": "EMP-00004", "annual_gross_base_salary": -1},
            {"employee_id": "EMP-00005", "annual_gross_base_salary": 10000000000},
            {"employee_id": "EMP-1"},
            {"employee_id": "EMP-00001"},
        )
        for invalid_employee in invalid_employees:
            with pytest.raises(sqlite3.IntegrityError):
                with connection:
                    _insert_employee(connection, **invalid_employee)
    finally:
        connection.close()
