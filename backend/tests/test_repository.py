"""Direct repository tests independent of the HTTP test thread pool."""

from pathlib import Path

import pytest

from app.database import connect
from app.db_schema import init_db
from app.repository import create_employee, get_salary_dashboard, list_employees
from app.schemas import EmployeeCreate


def test_repository_queries_work_with_database_neutral_count_and_rounding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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
