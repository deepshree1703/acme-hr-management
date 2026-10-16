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
    """Provide the database transport used by dashboard tests."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "dashboard.db"))
    init_db()
    return ASGITransport(app=app)


def _get_dashboard(
    transport: ASGITransport,
    path: str = "/dashboard",
    params: dict[str, str] | None = None,
) -> Response:
    """Request a dashboard endpoint from the test application."""
    async def send_request() -> Response:
        """Send a request through the configured test transport."""
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path, params=params)

    return asyncio.run(send_request())


def _insert_employees(employees: list[dict[str, object]]) -> None:
    """Insert employee records for dashboard test cases."""
    connection = connect()
    try:
        for employee in employees:
            with connection:
                connection.execute(
                    """INSERT INTO employees (employee_id, name, department, designation, country,
                       employment_status, annual_gross_base_salary, currency)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    tuple(employee[key] for key in (
                        "employee_id", "name", "department", "designation", "country",
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
    department: str = "Finance",
) -> dict[str, object]:
    """Build an employee record with optional field overrides."""
    return {
        "employee_id": employee_id,
        "name": f"Employee {employee_id}",
        "department": department,
        "designation": "Financial Analyst",
        "country": country,
        "employment_status": status,
        "annual_gross_base_salary": salary,
        "currency": currency,
    }


def test_dashboard_groups_and_averages_salaries_by_currency(
    dashboard_transport: ASGITransport,
) -> None:
    """Verify that dashboard groups and averages salaries by currency."""
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
                "minimum_annual_gross_base_salary": 60_000.126,
                "maximum_annual_gross_base_salary": 60_000.126,
            },
            {
                "currency": "INR",
                "headcount": 1,
                "average_annual_gross_base_salary": 1_200_000.0,
                "minimum_annual_gross_base_salary": 1_200_000.0,
                "maximum_annual_gross_base_salary": 1_200_000.0,
            },
            {
                "currency": "USD",
                "headcount": 2,
                "average_annual_gross_base_salary": 110_000.0,
                "minimum_annual_gross_base_salary": 100_000.0,
                "maximum_annual_gross_base_salary": 120_000.0,
            },
        ],
        "total_headcount": 4,
    }


def test_dashboard_empty_database_returns_no_currency_groups(
    dashboard_transport: ASGITransport,
) -> None:
    """Verify that dashboard empty database returns no currency groups."""
    response = _get_dashboard(dashboard_transport)

    assert response.status_code == 200
    assert response.json() == {"currencies": [], "total_headcount": 0}
    assert _get_dashboard(
        dashboard_transport, "/dashboard/by-department"
    ).json() == []
    assert _get_dashboard(dashboard_transport, "/dashboard/by-country").json() == []


def _insert_summary_dataset() -> None:
    _insert_employees([
        _employee("EMP-00001", salary=100, currency="USD", country="United States"),
        _employee(
            "EMP-00002", salary=200, currency="USD", country="United States",
            status="Inactive",
        ),
        _employee(
            "EMP-00003", salary=300, currency="USD", country="India",
            department="Engineering",
        ),
        _employee(
            "EMP-00004", salary=50, currency="EUR", country="Germany",
        ),
        _employee(
            "EMP-00005", salary=150, currency="EUR", country="India",
            status="Inactive", department="Engineering",
        ),
    ])


def test_dashboard_returns_currency_minimum_maximum_and_legacy_fields(
    dashboard_transport: ASGITransport,
) -> None:
    _insert_summary_dataset()
    response = _get_dashboard(dashboard_transport)
    assert response.status_code == 200
    data = response.json()
    assert data["total_headcount"] == 5
    assert data["currencies"] == [
        {
            "currency": "EUR",
            "headcount": 2,
            "average_annual_gross_base_salary": 100.0,
            "minimum_annual_gross_base_salary": 50.0,
            "maximum_annual_gross_base_salary": 150.0,
        },
        {
            "currency": "USD",
            "headcount": 3,
            "average_annual_gross_base_salary": 200.0,
            "minimum_annual_gross_base_salary": 100.0,
            "maximum_annual_gross_base_salary": 300.0,
        },
    ]


def test_dashboard_department_and_country_groups_keep_currencies_separate(
    dashboard_transport: ASGITransport,
) -> None:
    _insert_summary_dataset()
    departments = _get_dashboard(dashboard_transport, "/dashboard/by-department")
    countries = _get_dashboard(dashboard_transport, "/dashboard/by-country")
    assert departments.status_code == countries.status_code == 200
    assert departments.json() == [
        {
            "name": "Engineering",
            "headcount": 2,
            "currencies": [
                {
                    "currency": "EUR", "headcount": 1,
                    "average_annual_gross_base_salary": 150.0,
                    "minimum_annual_gross_base_salary": 150.0,
                    "maximum_annual_gross_base_salary": 150.0,
                },
                {
                    "currency": "USD", "headcount": 1,
                    "average_annual_gross_base_salary": 300.0,
                    "minimum_annual_gross_base_salary": 300.0,
                    "maximum_annual_gross_base_salary": 300.0,
                },
            ],
        },
        {
            "name": "Finance",
            "headcount": 3,
            "currencies": [
                {
                    "currency": "EUR", "headcount": 1,
                    "average_annual_gross_base_salary": 50.0,
                    "minimum_annual_gross_base_salary": 50.0,
                    "maximum_annual_gross_base_salary": 50.0,
                },
                {
                    "currency": "USD", "headcount": 2,
                    "average_annual_gross_base_salary": 150.0,
                    "minimum_annual_gross_base_salary": 100.0,
                    "maximum_annual_gross_base_salary": 200.0,
                },
            ],
        },
    ]
    assert [group["name"] for group in countries.json()] == [
        "Germany", "India", "United States"
    ]
    india = countries.json()[1]
    assert india["headcount"] == 2
    assert [(summary["currency"], summary["average_annual_gross_base_salary"])
            for summary in india["currencies"]] == [("EUR", 150.0), ("USD", 300.0)]


@pytest.mark.parametrize(
    ("filters", "total", "expected_currency_headcounts"),
    [
        ({"department": "Finance"}, 3, {"EUR": 1, "USD": 2}),
        ({"country": "India"}, 2, {"EUR": 1, "USD": 1}),
        ({"employment_status": "Active"}, 3, {"EUR": 1, "USD": 2}),
        (
            {"department": "Finance", "country": "United States", "employment_status": "Active"},
            1,
            {"USD": 1},
        ),
    ],
)
def test_dashboard_filters_apply_to_all_figures_and_total(
    dashboard_transport: ASGITransport,
    filters: dict[str, str],
    total: int,
    expected_currency_headcounts: dict[str, int],
) -> None:
    _insert_summary_dataset()
    response = _get_dashboard(dashboard_transport, params=filters)
    assert response.status_code == 200
    data = response.json()
    assert data["total_headcount"] == total
    assert {
        row["currency"]: row["headcount"] for row in data["currencies"]
    } == expected_currency_headcounts


def test_department_and_country_summaries_accept_all_filters(
    dashboard_transport: ASGITransport,
) -> None:
    _insert_summary_dataset()
    filters = {
        "department": "Engineering",
        "country": "India",
        "employment_status": "Inactive",
    }
    department_summary = _get_dashboard(
        dashboard_transport, "/dashboard/by-department", filters
    ).json()
    country_summary = _get_dashboard(
        dashboard_transport, "/dashboard/by-country", filters
    ).json()
    assert department_summary[0]["headcount"] == 1
    assert department_summary[0]["currencies"][0]["currency"] == "EUR"
    assert country_summary[0]["headcount"] == 1
    assert country_summary[0]["currencies"][0]["currency"] == "EUR"


def test_dashboard_routes_return_empty_results_when_no_rows_match(
    dashboard_transport: ASGITransport,
) -> None:
    _insert_summary_dataset()
    assert _get_dashboard(
        dashboard_transport, params={"country": "Nowhere"}
    ).json() == {"currencies": [], "total_headcount": 0}
    assert _get_dashboard(
        dashboard_transport, "/dashboard/by-department", {"country": "Nowhere"}
    ).json() == []
    assert _get_dashboard(
        dashboard_transport, "/dashboard/by-country", {"country": "Nowhere"}
    ).json() == []


def test_dashboard_rejects_invalid_employment_status(
    dashboard_transport: ASGITransport,
) -> None:
    for path in (
        "/dashboard",
        "/dashboard/by-department",
        "/dashboard/by-country",
    ):
        response = _get_dashboard(
            dashboard_transport, path, {"employment_status": "On leave"}
        )
        assert response.status_code == 422
