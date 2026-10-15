"""Tests for the salary dashboard endpoint."""

import asyncio
from pathlib import Path

import pytest
from httpx2 import ASGITransport, AsyncClient, Response

from app.database import connect
from app.db_schema import init_db
from app.main import app


@pytest.fixture
def dashboard_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> ASGITransport:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "dashboard.db"))
    init_db()
    return ASGITransport(app=app)


def _get_dashboard(transport: ASGITransport) -> Response:
    async def send_request() -> Response:
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/dashboard")

    return asyncio.run(send_request())


def _insert_employees(employees: list[dict[str, object]]) -> None:
    connection = connect()
    try:
        for employee in employees:
            with connection:
                connection.execute(
                    """INSERT INTO employees (employee_id, name, department, country,
                       employment_status, annual_gross_base_salary, currency)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    tuple(employee[key] for key in (
                        "employee_id", "name", "department", "country",
                        "employment_status", "annual_gross_base_salary", "currency"
                    )),
                )
    finally:
        connection.close()


def _employee(
    employee_id: str,
    *,
    salary: int | float,
    currency: str,
    country: str,
    status: str = "Active",
) -> dict[str, object]:
    return {
        "employee_id": employee_id,
        "name": f"Employee {employee_id}",
        "department": "Finance",
        "country": country,
        "employment_status": status,
        "annual_gross_base_salary": salary,
        "currency": currency,
    }


def test_dashboard_groups_and_averages_salaries_by_currency(
    dashboard_transport: ASGITransport,
) -> None:
    _insert_employees(
        [
            _employee("EMP-00001", salary=100_000, currency="USD", country="United States"),
            _employee(
                "EMP-00002",
                salary=120_000,
                currency="USD",
                country="United States",
                status="Inactive",
            ),
            _employee("EMP-00003", salary=1_200_000, currency="INR", country="India"),
            _employee("EMP-00004", salary=60_000.126, currency="EUR", country="Germany"),
        ]
    )

    response = _get_dashboard(dashboard_transport)

    assert response.status_code == 200
    assert response.json() == {
        "currencies": [
            {
                "currency": "EUR",
                "headcount": 1,
                "average_annual_gross_base_salary": 60_000.13,
            },
            {
                "currency": "INR",
                "headcount": 1,
                "average_annual_gross_base_salary": 1_200_000.0,
            },
            {
                "currency": "USD",
                "headcount": 2,
                "average_annual_gross_base_salary": 110_000.0,
            },
        ],
        "total_headcount": 4,
    }


def test_dashboard_empty_database_returns_no_currency_groups(
    dashboard_transport: ASGITransport,
) -> None:
    response = _get_dashboard(dashboard_transport)

    assert response.status_code == 200
    assert response.json() == {"currencies": [], "total_headcount": 0}
