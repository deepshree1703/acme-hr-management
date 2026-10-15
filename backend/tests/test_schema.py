"""Tests for the initial SQLite schema."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.database import connect
from app.db_schema import init_db


def test_connection_can_be_queried_and_closed_from_another_thread(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "employees.db"))

    connection = connect()
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(
            lambda: (connection.execute("SELECT 1").fetchone()[0], connection.close())
        ).result()

    assert result == (1, None)


def _insert_employee(connection: sqlite3.Connection, **overrides: object) -> None:
    employee = {
        "employee_id": "EMP-00001",
        "name": "Alex Example",
        "department": "Operations",
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
    } <= indexes


def test_init_db_uses_postgresql_constraints_and_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import db_schema

    statements: list[str] = []

    class FakeConnection:
        dialect = "postgresql"

        def execute(self, sql, parameters=()):
            statements.append(sql)

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(db_schema, "connect", FakeConnection)

    db_schema.init_db()

    schema = statements[0]
    assert "employee_id ~ '^EMP-[0-9]{5}$'" in schema
    assert "annual_gross_base_salary DOUBLE PRECISION NOT NULL" in schema
    assert len(statements) == 5


def test_employee_constraints_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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
            {"employee_id": "EMP-1"},
            {"employee_id": "EMP-00001"},
        )
        for invalid_employee in invalid_employees:
            with pytest.raises(sqlite3.IntegrityError):
                with connection:
                    _insert_employee(connection, **invalid_employee)
    finally:
        connection.close()
