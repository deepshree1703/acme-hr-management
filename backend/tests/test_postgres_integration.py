"""Opt-in integration test for a dedicated PostgreSQL test database."""

from __future__ import annotations

import os
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlsplit

import pytest

from app.config import get_settings
from app.database import connect
from app.db_schema import init_db
from app.repository import get_employee_by_id, get_salary_dashboard, list_employees
from scripts.seed import seed_employees

SEED_COUNT = 12


def _database_target(url: str) -> tuple[str, int | None, str]:
    parsed = urlsplit(url)
    port = parsed.port or (
        5432 if parsed.scheme in {"postgres", "postgresql"} else None
    )
    return (parsed.hostname or "").lower(), port, parsed.path.rstrip("/")


def test_postgres_database_layer_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run only against an explicitly configured, empty test database."""
    test_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not test_url:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated PostgreSQL test database")
    if os.getenv("CONFIRM_TEST_DATABASE_WRITES") != "YES":
        pytest.fail(
            "Set CONFIRM_TEST_DATABASE_WRITES=YES to authorize test database writes"
        )
    if os.getenv("VERCEL"):
        pytest.fail("PostgreSQL integration tests must not run in a Vercel deployment")

    parsed = urlsplit(test_url)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        pytest.fail("TEST_DATABASE_URL must be a PostgreSQL connection URL")

    app_url = get_settings().database_url
    if app_url and _database_target(test_url) == _database_target(app_url):
        pytest.fail("TEST_DATABASE_URL points to the configured application database")

    monkeypatch.setenv("DATABASE_URL", test_url)

    # Refuse to seed a database that already contains application data.
    connection = connect()
    try:
        relation = connection.execute(
            "SELECT to_regclass('employees') AS table_name"
        ).fetchone()["table_name"]
        if relation is not None:
            count = connection.execute(
                "SELECT COUNT(*) AS total_count FROM employees"
            ).fetchone()["total_count"]
            if count:
                pytest.fail(
                    "The PostgreSQL test database must have an empty employees table"
                )
    finally:
        connection.close()

    initialized = False
    try:
        init_db()
        initialized = True

        assert seed_employees(count=SEED_COUNT, batch_size=5) == (SEED_COUNT, SEED_COUNT)
        assert seed_employees(count=SEED_COUNT, batch_size=5) == (0, SEED_COUNT)

        connection = connect()
        try:
            employees, total = list_employees(connection, page=1)
            assert total == SEED_COUNT
            assert len(employees) == SEED_COUNT
            assert get_employee_by_id(connection, "EMP-00001") == employees[0]

            dashboard, headcount = get_salary_dashboard(connection)
            assert headcount == SEED_COUNT

            salaries_by_currency: dict[str, list[Decimal]] = defaultdict(list)
            for employee in employees:
                salaries_by_currency[employee.currency].append(
                    Decimal(str(employee.annual_gross_base_salary))
                )
            expected = {
                currency: (
                    len(salaries),
                    float(
                        (sum(salaries) / len(salaries)).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )
                    ),
                )
                for currency, salaries in salaries_by_currency.items()
            }
            actual = {
                summary.currency: (
                    summary.headcount,
                    summary.average_annual_gross_base_salary,
                )
                for summary in dashboard
            }
            assert actual == expected
        finally:
            connection.close()
    finally:
        if initialized:
            connection = connect()
            try:
                with connection:
                    connection.execute(
                        "DELETE FROM employees WHERE employee_id >= ? AND employee_id <= ?",
                        ("EMP-00001", f"EMP-{SEED_COUNT:05d}"),
                    )
            finally:
                connection.close()
