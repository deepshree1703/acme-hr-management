"""API tests for creating and fetching employees."""

import asyncio

import pytest
from httpx2 import ASGITransport, AsyncClient, Response

from app.constants import (
    DESIGNATIONS_BY_DEPARTMENT,
    EMPLOYMENT_STATUSES,
    SUPPORTED_CURRENCIES,
)
from app.db_schema import init_db
from app.database import connect
from app.main import app


@pytest.fixture
def api_transport(monkeypatch: pytest.MonkeyPatch, tmp_path) -> ASGITransport:
    """Provide the API transport used by employee route tests."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "employees.db"))
    init_db()
    return ASGITransport(app=app)


def _request(
    transport: ASGITransport,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
    params: dict[str, str | int] | None = None,
) -> Response:
    """Send a request through the employee API test transport."""
    async def send_request() -> Response:
        """Send a request through the configured test transport."""
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=payload, params=params)

    return asyncio.run(send_request())


def valid_employee_payload() -> dict[str, object]:
    """Return a valid employee creation payload."""
    return {
        "name": "Alex Example",
        "department": "Operations",
        "designation": "Operations Analyst",
        "country": "India",
        "employment_status": "Active",
        "annual_gross_base_salary": 50000,
        "currency": "INR",
    }


def valid_update_payload() -> dict[str, object]:
    """Return a valid employee update payload."""
    return valid_employee_payload()


def _seed_employees(
    employees: list[dict[str, object]],
) -> None:
    """Insert employee fixtures for route tests."""
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


def _list_filter_employees() -> list[dict[str, object]]:
    """Create employee fixtures for list and filter tests."""
    return [
        {
            **valid_employee_payload(),
            "employee_id": "EMP-00001",
            "name": "Alice Smith",
            "department": "People",
            "country": "Canada",
            "employment_status": "Active",
            "currency": "CAD",
        },
        {
            **valid_employee_payload(),
            "employee_id": "EMP-00002",
            "name": "Alicia Morgan",
            "department": "People",
            "country": "Canada",
            "employment_status": "Inactive",
            "currency": "CAD",
        },
        {
            **valid_employee_payload(),
            "employee_id": "EMP-00003",
            "name": "Bob Smith",
            "department": "Engineering",
            "country": "India",
            "employment_status": "Active",
            "currency": "INR",
        },
        {
            **valid_employee_payload(),
            "employee_id": "EMP-00004",
            "name": "Charlie Lee",
            "department": "Engineering",
            "country": "Canada",
            "employment_status": "Active",
            "currency": "CAD",
        },
    ]


def test_create_employee_returns_created_record(api_transport: ASGITransport) -> None:
    """Verify that create employee returns created record."""
    response = _request(api_transport, "POST", "/employees", valid_employee_payload())

    assert response.status_code == 201
    assert response.json() == {
        **valid_employee_payload(),
        "employee_id": "EMP-00001",
        "annual_gross_base_salary": 50000.0,
    }


def test_two_creates_get_different_ids(
    api_transport: ASGITransport,
) -> None:
    """Verify that two creates get different ids."""
    first = _request(api_transport, "POST", "/employees", valid_employee_payload())
    second = _request(api_transport, "POST", "/employees", valid_employee_payload())
    assert first.json()["employee_id"] == "EMP-00001"
    assert second.json()["employee_id"] == "EMP-00002"


def test_create_id_uses_highest_numeric_part(api_transport: ASGITransport) -> None:
    """Verify that create id uses highest numeric part."""
    _seed_employees([
        valid_employee_payload() | {"employee_id": "EMP-99999"},
        valid_employee_payload() | {"employee_id": "EMP-100000"},
    ])
    response = _request(api_transport, "POST", "/employees", valid_employee_payload())
    assert response.json()["employee_id"] == "EMP-100001"


def test_create_id_after_deleting_latest_uses_new_current_maximum(
    api_transport: ASGITransport,
) -> None:
    """Verify that create id after deleting latest uses new current maximum."""
    first = _request(api_transport, "POST", "/employees", valid_employee_payload())
    latest = _request(api_transport, "POST", "/employees", valid_employee_payload())
    _request(api_transport, "DELETE", f"/employees/{latest.json()['employee_id']}")
    created = _request(api_transport, "POST", "/employees", valid_employee_payload())
    assert first.json()["employee_id"] == "EMP-00001"
    assert created.json()["employee_id"] == "EMP-00002"


def test_next_id_matches_next_created_employee(api_transport: ASGITransport) -> None:
    """Verify that next id matches next created employee."""
    _seed_employees([valid_employee_payload() | {"employee_id": "EMP-99999"}])
    preview = _request(api_transport, "GET", "/employees/next-id")
    created = _request(api_transport, "POST", "/employees", valid_employee_payload())
    assert preview.status_code == 200
    assert preview.json() == {"employee_id": "EMP-100000"}
    assert created.json()["employee_id"] == preview.json()["employee_id"]


def test_create_rejects_client_sent_employee_id(api_transport: ASGITransport) -> None:
    """Verify that create rejects client sent employee id."""
    payload = valid_employee_payload() | {"employee_id": "EMP-00001"}
    assert _request(api_transport, "POST", "/employees", payload).status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("currency", "XYZ"),
        ("annual_gross_base_salary", -1),
        ("employee_id", "EMP-1234"),
    ],
)
def test_create_employee_rejects_invalid_payloads(
    api_transport: ASGITransport, field: str, value: object
) -> None:
    """Verify that create employee rejects invalid payloads."""
    payload = valid_employee_payload()
    payload[field] = value

    response = _request(api_transport, "POST", "/employees", payload)

    assert response.status_code == 422


def test_get_existing_employee_returns_record(api_transport: ASGITransport) -> None:
    """Verify that get existing employee returns record."""
    payload = valid_employee_payload()
    _request(api_transport, "POST", "/employees", payload)

    response = _request(api_transport, "GET", "/employees/EMP-00001")

    assert response.status_code == 200
    assert response.json()["employee_id"] == "EMP-00001"
    assert response.json()["name"] == "Alex Example"


def test_get_missing_employee_returns_not_found(api_transport: ASGITransport) -> None:
    """Verify that get missing employee returns not found."""
    response = _request(api_transport, "GET", "/employees/EMP-99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Employee not found"


def test_employee_filter_options_return_distinct_values_and_supported_options(
    api_transport: ASGITransport,
) -> None:
    """Verify that employee filter options return distinct values and supported options."""
    _seed_employees(
        [
            {
                **valid_employee_payload(),
                "employee_id": "EMP-00001",
                "country": "Canada",
                "department": "Engineering",
            },
            {
                **valid_employee_payload(),
                "employee_id": "EMP-00002",
                "country": "Canada",
                "department": "Finance",
            },
            {
                **valid_employee_payload(),
                "employee_id": "EMP-00003",
                "country": "India",
                "department": "Engineering",
            },
        ]
    )

    response = _request(api_transport, "GET", "/employees/filters")

    assert response.status_code == 200
    assert response.json() == {
        "countries": ["Canada", "India"],
        "departments": ["Engineering", "Finance"],
        "employment_statuses": list(EMPLOYMENT_STATUSES),
        "currencies": list(SUPPORTED_CURRENCIES),
        "designations_by_department": {
            department: list(designations)
            for department, designations in DESIGNATIONS_BY_DEPARTMENT.items()
        },
    }
    designation_options = response.json()["designations_by_department"]
    assert len(designation_options) == 8
    assert all(len(designations) == 5 for designations in designation_options.values())


def test_update_employee_returns_replacement_record(api_transport: ASGITransport) -> None:
    """Verify that update employee returns replacement record."""
    _request(api_transport, "POST", "/employees", valid_employee_payload())
    payload = valid_update_payload()
    payload.update(
        {
            "name": "Jordan Example",
            "department": "Finance",
            "designation": "Financial Analyst",
            "country": "Canada",
            "employment_status": "Inactive",
            "annual_gross_base_salary": 72000,
            "currency": "CAD",
        }
    )

    response = _request(api_transport, "PUT", "/employees/EMP-00001", payload)

    assert response.status_code == 200
    assert response.json() == {
        "employee_id": "EMP-00001",
        **payload,
        "annual_gross_base_salary": 72000.0,
    }


@pytest.mark.parametrize("method", ["POST", "PUT"])
@pytest.mark.parametrize(
    ("department", "designation", "field"),
    [
        ("Engineering", "XYZ", "designation"),
        ("Finance", "Software Engineer", "designation"),
        ("Unknown Department", "XYZ", "department"),
    ],
)
def test_create_and_update_reject_uncontrolled_department_designation(
    api_transport: ASGITransport,
    method: str,
    department: str,
    designation: str,
    field: str,
) -> None:
    if method == "PUT":
        _request(api_transport, "POST", "/employees", valid_employee_payload())
    payload = valid_employee_payload() | {
        "department": department,
        "designation": designation,
    }
    path = "/employees" if method == "POST" else "/employees/EMP-00001"
    response = _request(api_transport, method, path, payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == field
    assert f"{field.capitalize()} must be one of:" in response.json()["detail"][0]["msg"]


def test_legacy_employee_values_remain_readable_and_can_be_corrected(
    api_transport: ASGITransport,
) -> None:
    _seed_employees([
        valid_employee_payload() | {
            "employee_id": "EMP-00001",
            "department": "Legacy Department",
            "designation": "Employee",
        }
    ])

    fetched = _request(api_transport, "GET", "/employees/EMP-00001")
    listed = _request(api_transport, "GET", "/employees")
    assert fetched.status_code == listed.status_code == 200
    assert fetched.json()["designation"] == "Employee"
    assert listed.json()["items"][0]["department"] == "Legacy Department"

    updated = _request(
        api_transport,
        "PUT",
        "/employees/EMP-00001",
        valid_employee_payload() | {
            "department": "Engineering",
            "designation": "Software Engineer",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["department"] == "Engineering"
    assert updated.json()["designation"] == "Software Engineer"


def test_update_missing_employee_returns_not_found(
    api_transport: ASGITransport,
) -> None:
    """Verify that update missing employee returns not found."""
    response = _request(
        api_transport,
        "PUT",
        "/employees/EMP-99999",
        valid_update_payload(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Employee not found"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("currency", "XYZ"),
        ("annual_gross_base_salary", -1),
    ],
)
def test_update_employee_rejects_invalid_payloads(
    api_transport: ASGITransport, field: str, value: object
) -> None:
    """Verify that update employee rejects invalid payloads."""
    payload = valid_update_payload()
    payload[field] = value

    response = _request(api_transport, "PUT", "/employees/EMP-00001", payload)

    assert response.status_code == 422


def test_update_employee_rejects_employee_id_in_body(
    api_transport: ASGITransport,
) -> None:
    """Verify that update employee rejects employee id in body."""
    payload = valid_update_payload()
    payload["employee_id"] = "EMP-00002"

    response = _request(api_transport, "PUT", "/employees/EMP-00001", payload)

    assert response.status_code == 422


def test_delete_employee_returns_no_content_and_fetch_then_returns_not_found(
    api_transport: ASGITransport,
) -> None:
    """Verify that delete employee returns no content and fetch then returns not found."""
    _request(api_transport, "POST", "/employees", valid_employee_payload())

    response = _request(api_transport, "DELETE", "/employees/EMP-00001")

    assert response.status_code == 204
    assert response.content == b""
    assert _request(api_transport, "GET", "/employees/EMP-00001").status_code == 404


def test_delete_missing_employee_returns_not_found(
    api_transport: ASGITransport,
) -> None:
    """Verify that delete missing employee returns not found."""
    response = _request(api_transport, "DELETE", "/employees/EMP-99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Employee not found"


def test_list_employees_uses_fixed_size_pages_and_reports_totals(
    api_transport: ASGITransport,
) -> None:
    """Verify that list employees uses fixed size pages and reports totals."""
    employees = []
    for index in range(1, 46):
        employee = valid_employee_payload()
        employee["employee_id"] = f"EMP-{index:05d}"
        employee["name"] = f"Employee {index:02d}"
        employees.append(employee)
    _seed_employees(employees)

    expected_page_lengths = (20, 20, 5)
    for page, expected_length in enumerate(expected_page_lengths, start=1):
        response = _request(
            api_transport,
            "GET",
            "/employees",
            params={"page": page, "page_size": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == expected_length
        assert data["total"] == 45
        assert data["page"] == page
        assert data["page_size"] == 20
        assert data["total_pages"] == 3
        assert data["items"] == sorted(data["items"], key=lambda item: item["employee_id"])

    beyond_last_page = _request(
        api_transport,
        "GET",
        "/employees",
        params={"page": 4},
    ).json()
    assert beyond_last_page["items"] == []
    assert beyond_last_page["total"] == 45
    assert beyond_last_page["total_pages"] == 3


def test_list_employees_searches_name_case_insensitively(api_transport: ASGITransport) -> None:
    """Verify that list employees searches name case insensitively."""
    _seed_employees(_list_filter_employees())

    response = _request(
        api_transport,
        "GET",
        "/employees",
        params={"search": "aLi"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["total"] == 2
    assert [item["employee_id"] for item in data["items"]] == [
        "EMP-00001",
        "EMP-00002",
    ]


def test_list_employees_searches_by_employee_id(api_transport: ASGITransport) -> None:
    """Verify that list employees searches by employee id."""
    _seed_employees(_list_filter_employees())

    response = _request(
        api_transport,
        "GET",
        "/employees",
        params={"search": "EMP-00003"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["total"] == 1
    assert [item["employee_id"] for item in data["items"]] == ["EMP-00003"]


def test_list_employees_searches_employee_id_by_case_insensitive_prefix(
    api_transport: ASGITransport,
) -> None:
    """Verify that list employees searches employee id by case insensitive prefix."""
    employees = []
    for index in range(1, 21):
        employee = valid_employee_payload()
        employee["employee_id"] = f"EMP-{index:05d}"
        employee["name"] = f"Person {index}"
        employees.append(employee)
    _seed_employees(employees)

    response = _request(
        api_transport,
        "GET",
        "/employees",
        params={"search": "emp-0001"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["total"] == 10
    assert [item["employee_id"] for item in data["items"]] == [
        f"EMP-{index:05d}" for index in range(10, 20)
    ]

    unrelated_prefix = _request(
        api_transport,
        "GET",
        "/employees",
        params={"search": "XYZ-"},
    ).json()
    assert unrelated_prefix["items"] == []
    assert unrelated_prefix["total"] == 0


@pytest.mark.parametrize(
    ("filter_params", "expected_ids"),
    [
        ({"country": "Canada"}, ["EMP-00001", "EMP-00002", "EMP-00004"]),
        ({"department": "Engineering"}, ["EMP-00003", "EMP-00004"]),
        ({"employment_status": "Active"}, ["EMP-00001", "EMP-00003", "EMP-00004"]),
    ],
)
def test_list_employees_applies_each_exact_filter(
    api_transport: ASGITransport,
    filter_params: dict[str, str],
    expected_ids: list[str],
) -> None:
    """Verify that list employees applies each exact filter."""
    _seed_employees(_list_filter_employees())

    response = _request(
        api_transport,
        "GET",
        "/employees",
        params=filter_params,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["total"] == len(expected_ids)
    assert [item["employee_id"] for item in data["items"]] == expected_ids


def test_list_employees_combines_filters_with_and(api_transport: ASGITransport) -> None:
    """Verify that list employees combines filters with and."""
    _seed_employees(_list_filter_employees())

    response = _request(
        api_transport,
        "GET",
        "/employees",
        params={
            "search": "alice",
            "country": "Canada",
            "department": "People",
            "employment_status": "Active",
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["total"] == 1
    assert [item["employee_id"] for item in data["items"]] == ["EMP-00001"]


def test_list_employees_returns_empty_results_with_zero_totals(
    api_transport: ASGITransport,
) -> None:
    """Verify that list employees returns empty results with zero totals."""
    response = _request(
        api_transport,
        "GET",
        "/employees",
        params={"country": "Nowhere"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
    }


def _salary_filter_employees() -> list[dict[str, object]]:
    """Build a compact mixed-currency dataset for salary filter tests."""
    specs = [
        (1, "Alice Smith", "Sales", "Canada", "Active", "USD", 100),
        (2, "Bob Jones", "Sales", "Canada", "Inactive", "USD", 200),
        (3, "Carol Lee", "Engineering", "India", "Active", "USD", 300),
        (4, "Alicia Morgan", "Sales", "Canada", "Active", "EUR", 150),
        (5, "Alan Chen", "Engineering", "India", "Inactive", "EUR", 250),
    ]
    return [
        valid_employee_payload() | {
            "employee_id": f"EMP-{number:05d}",
            "name": name,
            "department": department,
            "country": country,
            "employment_status": status,
            "currency": currency,
            "annual_gross_base_salary": salary,
        }
        for number, name, department, country, status, currency, salary in specs
    ]


def _list_salary_filtered(
    transport: ASGITransport, **params: str | int
) -> dict[str, object]:
    response = _request(transport, "GET", "/employees", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_salary_filters_cover_currency_bounds_and_inclusive_edges(
    api_transport: ASGITransport,
) -> None:
    _seed_employees(_salary_filter_employees())

    assert [row["employee_id"] for row in _list_salary_filtered(
        api_transport, currency="USD"
    )["items"]] == ["EMP-00001", "EMP-00002", "EMP-00003"]
    assert [row["employee_id"] for row in _list_salary_filtered(
        api_transport, currency="USD", min_salary=200
    )["items"]] == ["EMP-00002", "EMP-00003"]
    assert [row["employee_id"] for row in _list_salary_filtered(
        api_transport, currency="USD", max_salary=200
    )["items"]] == ["EMP-00001", "EMP-00002"]
    assert [row["employee_id"] for row in _list_salary_filtered(
        api_transport, currency="USD", min_salary=200, max_salary=200
    )["items"]] == ["EMP-00002"]


def test_salary_ranges_are_scoped_to_currency(
    api_transport: ASGITransport,
) -> None:
    _seed_employees(_salary_filter_employees())
    usd = _list_salary_filtered(api_transport, currency="USD", min_salary=100, max_salary=200)
    eur = _list_salary_filtered(api_transport, currency="EUR", min_salary=100, max_salary=200)
    assert [row["employee_id"] for row in usd["items"]] == ["EMP-00001", "EMP-00002"]
    assert [row["employee_id"] for row in eur["items"]] == ["EMP-00004"]


def test_salary_range_combines_with_existing_filters(
    api_transport: ASGITransport,
) -> None:
    _seed_employees(_salary_filter_employees())
    result = _list_salary_filtered(
        api_transport,
        currency="USD",
        min_salary=100,
        max_salary=300,
        department="Sales",
        country="Canada",
        search="alice",
        employment_status="Active",
    )
    assert result["total"] == 1
    assert [row["employee_id"] for row in result["items"]] == ["EMP-00001"]


def test_salary_range_pagination_and_empty_result(
    api_transport: ASGITransport, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.routers import employees as employee_routes
    from app import repository as employee_repository

    _seed_employees(_salary_filter_employees())
    monkeypatch.setattr(employee_routes, "PAGE_SIZE", 2)
    monkeypatch.setattr(employee_repository, "PAGE_SIZE", 2)
    page = _list_salary_filtered(
        api_transport, currency="USD", min_salary=100, page=2
    )
    assert page["total"] == 3
    assert page["total_pages"] == 2
    assert [row["employee_id"] for row in page["items"]] == ["EMP-00003"]

    empty = _list_salary_filtered(api_transport, currency="EUR", min_salary=1000)
    assert empty["items"] == []
    assert empty["total"] == 0
    assert empty["total_pages"] == 0


@pytest.mark.parametrize(
    ("params", "expected_status"),
    [
        ({"min_salary": 100}, 400),
        ({"currency": "USD", "min_salary": 200, "max_salary": 100}, 400),
        ({"currency": "XYZ"}, 422),
        ({"currency": "USD", "min_salary": -1}, 422),
        ({"currency": "USD", "min_salary": "inf"}, 422),
        ({"currency": "USD", "max_salary": "nan"}, 422),
    ],
)
def test_salary_filters_reject_invalid_ranges(
    api_transport: ASGITransport,
    params: dict[str, str | int],
    expected_status: int,
) -> None:
    response = _request(api_transport, "GET", "/employees", params=params)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "query", [{"employment_status": "On leave"}, {"page": 0}]
)
def test_list_employees_rejects_invalid_query_parameters(
    api_transport: ASGITransport, query: dict[str, str | int]
) -> None:
    """Verify that list employees rejects invalid query parameters."""
    response = _request(api_transport, "GET", "/employees", params=query)

    assert response.status_code == 422
