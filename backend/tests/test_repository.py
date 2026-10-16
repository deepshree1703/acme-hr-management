"""Direct repository tests independent of the HTTP test thread pool."""

from pathlib import Path

import pytest

from app.database import connect
from app.db_schema import init_db
from app.repository import (
    create_employee,
    get_salary_dashboard,
    get_salary_group_summaries,
    list_employees,
)
from app.schemas import EmployeeCreate


def test_repository_queries_work_with_database_neutral_count_and_rounding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify that repository queries work with database neutral count and rounding."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "repository.db"))
    init_db()
    connection = connect()
    try:
        create_employee(
            connection,
            EmployeeCreate(
                name="Alex Example",
                department="Operations",
                designation="Operations Analyst",
                country="India",
                employment_status="Active",
                annual_gross_base_salary=60000.13,
                currency="INR",
            ),
        )
        employees, total = list_employees(connection, page=1)
        summaries, headcount = get_salary_dashboard(connection)

        assert total == headcount == 1
        assert employees[0].employee_id == "EMP-00001"
        assert summaries[0].average_annual_gross_base_salary == 60000.13
    finally:
        connection.close()


def test_dashboard_repository_summaries_are_filtered_and_currency_scoped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check dashboard statistics and dimension summaries on SQLite directly."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "dashboard-repository.db"))
    init_db()
    connection = connect()
    try:
        connection.executemany(
            """INSERT INTO employees (
                employee_id, name, department, designation, country,
                employment_status, annual_gross_base_salary, currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                ("EMP-00001", "A", "Finance", "Analyst", "US", "Active", 100, "USD"),
                ("EMP-00002", "B", "Finance", "Analyst", "US", "Inactive", 200, "USD"),
                ("EMP-00003", "C", "Engineering", "Engineer", "India", "Active", 300, "USD"),
                ("EMP-00004", "D", "Finance", "Analyst", "Germany", "Active", 50, "EUR"),
                ("EMP-00005", "E", "Engineering", "Engineer", "India", "Inactive", 150, "EUR"),
            ],
        )

        summaries, total = get_salary_dashboard(connection)
        assert total == 5
        assert [
            (
                item.currency,
                item.headcount,
                item.average_annual_gross_base_salary,
                item.minimum_annual_gross_base_salary,
                item.maximum_annual_gross_base_salary,
            )
            for item in summaries
        ] == [("EUR", 2, 100.0, 50.0, 150.0), ("USD", 3, 200.0, 100.0, 300.0)]

        finance, finance_total = get_salary_dashboard(
            connection, department="Finance", country="US", employment_status="Active"
        )
        assert finance_total == 1
        assert [(item.currency, item.headcount) for item in finance] == [("USD", 1)]

        by_department = get_salary_group_summaries(
            connection, group_by="department"
        )
        assert [(item.name, item.headcount) for item in by_department] == [
            ("Engineering", 2), ("Finance", 3)
        ]
        finance_group = by_department[1]
        assert [(item.currency, item.headcount) for item in finance_group.currencies] == [
            ("EUR", 1), ("USD", 2)
        ]

        by_country = get_salary_group_summaries(connection, group_by="country")
        assert [(item.name, item.headcount) for item in by_country] == [
            ("Germany", 1), ("India", 2), ("US", 2)
        ]
    finally:
        connection.close()
